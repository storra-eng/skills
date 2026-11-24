"""Shared plumbing for the pre-check harness (precheck.py) and its note-source modules (source_*.py).

Kept in its own module so that `Fail` exists exactly once: precheck.py is both run as a script and
imported by the Granola shim, and a class defined in a file that is executed as __main__ AND imported
exists twice, so a source's Fail would slip past the harness's `except Fail` and read as "unexpected".

Nothing here prints, and nothing here ever puts a response body or a token into an exception message:
callers echo `str(Fail)` to stdout, so every reason is a fixed phrase."""
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request

PROTOCOL_VERSION = "2025-06-18"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


class Fail(Exception):
    pass


def check_url(url):
    """A bearer token or API key must only ever travel over https, or to a loopback test server."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "https" and parts.hostname:
        return url
    if parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS:
        return url
    raise Fail("url-not-https")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Any 3xx is a FAIL. urllib's default handler follows a redirect and re-sends every header except
    the content ones - Authorization and API-key headers included - to whatever host Location names.
    A credential must only ever reach the URL it was issued for."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Fail(f"http-{code} (redirect refused)")


_OPENER = urllib.request.build_opener(_NoRedirect)


def http_request(url, headers, body=None, method="POST", timeout=15.0):
    """One HTTP exchange -> (response headers, decoded text). Every non-2xx is a Fail with a fixed phrase
    (401 as `token-rejected`); the body of an error reply is never read into the message."""
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.headers, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        e.close()
        if e.code == 401:
            raise Fail("token-rejected (HTTP 401)")
        raise Fail(f"http-{e.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Fail(f"transport ({type(e).__name__})")


def get_json(url, headers, timeout=15.0, method="GET", body=None):
    """An HTTP call whose reply must be a JSON document."""
    _h, raw = http_request(url, headers, body=body, method=method, timeout=timeout)
    try:
        return json.loads(raw)
    except ValueError:
        raise Fail("reply-not-json")


class Client:
    """A minimal MCP streamable-HTTP client: JSON-RPC over POST, JSON or SSE replies."""
    def __init__(self, access, url, timeout=15.0):
        self.access, self.url, self.timeout, self.session = access, url, timeout, None
        self.protocol = None   # negotiated MCP protocol version, sent on every request after initialize

    def post(self, body, want_id):
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   "Authorization": f"Bearer {self.access}"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        if self.protocol:
            headers["MCP-Protocol-Version"] = self.protocol
        rh, raw = http_request(self.url, headers, body=body, timeout=self.timeout)
        sid = rh.get("Mcp-Session-Id")
        if sid:
            self.session = sid
        ctype = rh.get("Content-Type", "")
        if want_id is None:
            return None
        msgs = []
        if "text/event-stream" in ctype:
            for ln in raw.splitlines():
                if ln.startswith("data:"):
                    try:
                        msgs.append(json.loads(ln[5:].strip()))
                    except ValueError:
                        continue
        else:
            try:
                msgs.append(json.loads(raw))
            except ValueError:
                raise Fail("reply-not-json")
        # The reply to OUR request, by id - an SSE stream may carry notifications first.
        for m in msgs:
            if isinstance(m, dict) and m.get("id") == want_id:
                return m
        raise Fail("reply-missing (no JSON-RPC message answering the request)")

    def initialize(self, client_name="ActionsToIssues-precheck"):
        init = self.post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                          "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                                     "clientInfo": {"name": client_name, "version": "1.0"}}}, 1)
        if "error" in init or "result" not in init:
            raise Fail("initialize-refused")
        negotiated = init["result"].get("protocolVersion") if isinstance(init["result"], dict) else None
        self.protocol = negotiated if isinstance(negotiated, str) and negotiated else PROTOCOL_VERSION
        try:
            self.post({"jsonrpc": "2.0", "method": "notifications/initialized"}, None)
        except Fail as e:
            # A 401 here is a real verdict; anything else is the server declining a notification.
            if str(e).startswith("token-"):
                raise

    def call_tool_text(self, name, arguments, req_id=2):
        """tools/call -> the concatenated text parts. A tool-level error is a Fail whose text is NOT
        echoed: on a good answer the same slot carries meeting content."""
        resp = self.post({"jsonrpc": "2.0", "id": req_id, "method": "tools/call",
                          "params": {"name": name, "arguments": arguments}}, req_id)
        if "error" in resp:
            raise Fail("jsonrpc-error")
        res = resp.get("result")
        if not isinstance(res, dict):
            raise Fail("no-result")
        if res.get("isError"):
            raise Fail("tool-error (isError)")
        content = res.get("content") or []
        texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return "\n".join(t for t in texts if isinstance(t, str))


def parse_iso(v):
    """ISO-8601 with an offset -> aware datetime, or None. The fraction is normalised to six digits
    first: fromisoformat before Python 3.11 accepts only 3 or 6, and a host python that rejected the
    server's precision would make every derived value unknown, silently."""
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:?\d{2})$", v or "")
    if not m:
        return None
    base, frac, tz = m.groups()
    tz = "+00:00" if tz == "Z" else (tz if ":" in tz else tz[:3] + ":" + tz[3:])
    try:
        return dt.datetime.fromisoformat(base + "." + ((frac or "0") + "000000")[:6] + tz)
    except ValueError:
        return None


def minutes_since(inst, now):
    """Whole minutes from `inst` to `now`, or None. A start in the FUTURE is a misread date, not a very
    young meeting: None, which every caller treats as old (fail open)."""
    if inst is None:
        return None
    m = int((now - inst).total_seconds() // 60)
    return None if m < 0 else m


def window(now, days):
    """(start, end) of the look-back window: `days` whole UTC days ending with today, end exclusive at
    tomorrow's midnight (notes cannot exist in the future, and an end of "now" read in another zone
    could hide the newest meetings)."""
    today = now.astimezone(dt.timezone.utc).date() if now.tzinfo else now.date()
    start = dt.datetime.combine(today - dt.timedelta(days=days - 1), dt.time(), dt.timezone.utc)
    return start, start + dt.timedelta(days=days)
