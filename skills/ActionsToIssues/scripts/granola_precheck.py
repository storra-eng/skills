#!/usr/bin/env python3
"""Zero-token pre-check: is there any new Granola meeting worth waking a model for?

Makes ONE Granola `list_meetings` call over MCP, compares the result with a small local state file
and prints a verdict. Run it from your scheduler before starting the agent; start the agent only
when this script says there is work (or when it cannot tell).

Stdout, on a well-formed answer:

    OK seen=<n> others=<m> new=<k> defer=<d> state=ok|absent
    new <meeting id> <minutes since it started | unknown>
    defer <meeting id> <minutes since it started>
    VERDICT idle | work

Exit status:

    0   idle  - nothing new; safe to skip the model
    10  work  - at least one new, old-enough meeting; run the agent
    1   fail  - anything else (one line, `FAIL <reason>`); run the agent
    2   usage error

Only exit 0 may skip the model. Every other path is a doubt, and a doubt must wake the agent: the
pre-check can only ever make a run cheaper, never blinder. Output never contains a response body,
a meeting title or a token - only fixed phrases, ids, counts and an HTTP code or exception class.

The script never refreshes a token. Whatever owns the OAuth session (your agent platform's MCP
client) owns the refresh chain; a second writer racing a rotating refresh token can destroy the
credential. An expired or rejected token is a FAIL, the agent is woken, and its own MCP client
refreshes on the 401.

Configuration (flag, then environment):

    --auth-file / MCP_AUTH_FILE      JSON file holding the OAuth tokens (see below)
    --auth-key  / MCP_AUTH_SERVER    key of the Granola entry in that file (default "granola")
    GRANOLA_ACCESS_TOKEN             a bearer token directly, instead of a file
    GRANOLA_MCP_URL                  MCP endpoint for GRANOLA_ACCESS_TOKEN only (https, or loopback for tests);
                                     a token read from a file goes only to that file's serverUrl
    --state     / MN2L_STATE         state file listing handled meetings (see below)
    --min-age   / PRECHECK_MIN_AGE_MIN   minutes since a meeting STARTED before it counts as new (default 30).
                                     The script has no end time, so this is a heuristic: set it above your
                                     longest regular meeting (for example 90) or a long meeting is read half-finished.
    --no-defer                       judge every meeting regardless of age (use on the day's last run)
    --rows                           print every meeting and leave classification to the caller (needs no state
                                     file): `OK seen=<n> others=<m>` then one `id <meeting id> <minutes since start>
                                     <note length seconds> <minutes since last update>` line each, `unknown` where a
                                     value could not be read. Exit 0 on a well-formed answer, 1 on anything else.
    --days      / PRECHECK_DAYS      how many UTC days to look back, today included (default 2)
    PRECHECK_HTTP_TIMEOUT            seconds (default 15)

The pre-check cannot refresh a token. If the access token has expired it FAILs, which wakes the agent, and the
agent's own MCP client refreshes it - so on an idle day expect roughly one paid wake per access-token lifetime.

No auth location is assumed: set one of --auth-file or GRANOLA_ACCESS_TOKEN. The auth file is
expected to look like `{"granola": {"serverUrl": "...", "tokens": {"accessToken": "...",
"expiresAt": <epoch seconds or milliseconds>}}}`, which is the shape several MCP clients write.

State file (required: no path configured is a FAIL; a path whose file does not exist yet is a first run, reported
as `state=absent`): `{"handled": [...]}` where each entry is either a meeting id or an object with an
`ids` list (one meeting can arrive as several notes, one per capturer, and every id must be
recorded so a sibling is not rediscovered as new). A missing file means nothing is handled yet.
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from granola_reply import (  # noqa: E402,F401  (re-exported: tests and callers import these from here)
    ATTR_RE, COUNT_RE, DATE_RE, ID_RE, MEETING_TAG_RE, MONTHS, WRAPPER_CLOSE_RE, WRAPPER_OPEN_RE, Fail,
    has_second_wrapper, note_length_sec, parse_instant, parse_iso, parse_meetings, quiet_minutes,
    top_level_meeting_tags, wrapper_body)

DEFAULT_URL = "https://mcp.granola.ai/mcp"
PROTOCOL_VERSION = "2025-06-18"
# An access token this close to expiry is treated as expired: the call would race it.
EXPIRY_SKEW_SEC = 60
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

def check_url(url):
    """The bearer token must only ever travel over https, or to a loopback test server."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "https" and parts.hostname:
        return url
    if parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS:
        return url
    raise Fail("url-not-https")


def load_token(auth_file=None, auth_key="granola", env=None, now=None):
    """Return (access token, endpoint url). Raises Fail with a fixed phrase on any problem."""
    env = os.environ if env is None else env
    now = time.time() if now is None else now
    direct = env.get("GRANOLA_ACCESS_TOKEN")
    if direct:
        # No expiry is known for a bare token; only a 401 can settle it.
        return direct, check_url(env.get("GRANOLA_MCP_URL") or DEFAULT_URL)
    if not auth_file:
        raise Fail("token-missing (no auth configured)")
    try:
        with open(auth_file) as f:
            auth = json.load(f)
    except FileNotFoundError:
        raise Fail("token-missing (auth file not found)")
    except (OSError, ValueError) as e:
        raise Fail(f"token-unreadable ({type(e).__name__})")
    entry = auth.get(auth_key) if isinstance(auth, dict) else None
    tokens = entry.get("tokens") if isinstance(entry, dict) else None
    access = tokens.get("accessToken") if isinstance(tokens, dict) else None
    if not isinstance(access, str) or not access:
        raise Fail("token-missing (no access token in auth file)")
    exp = tokens.get("expiresAt")
    # ABSENT is not expired: a server that issues non-expiring tokens has none, and treating that
    # as expired would wake the model on every tick. Only a 401 settles it then.
    if exp is not None:
        if isinstance(exp, bool) or not isinstance(exp, (int, float)):
            raise Fail("token-expiry-unreadable")
        exp_s = exp / 1000 if exp > 1e12 else exp
        if exp_s - now < EXPIRY_SKEW_SEC:
            raise Fail("token-expired")
    # GRANOLA_MCP_URL deliberately does not apply here: a token read from a file is only ever sent to the
    # server that file says issued it, never to an endpoint a stray environment variable names.
    url = entry.get("serverUrl") or DEFAULT_URL
    if not isinstance(url, str):
        raise Fail("url-not-https")
    return access, check_url(url)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Any 3xx is a FAIL. urllib's default handler follows a redirect on POST and re-sends every
    header except the content ones - Authorization included - to whatever host Location names.
    The token must only ever reach the URL it was issued for."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Fail(f"http-{code} (redirect refused)")


_OPENER = urllib.request.build_opener(_NoRedirect)


class Client:
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
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     method="POST", headers=headers)
        try:
            with _OPENER.open(req, timeout=self.timeout) as r:
                sid = r.headers.get("Mcp-Session-Id")
                if sid:
                    self.session = sid
                ctype = r.headers.get("Content-Type", "")
                raw = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            e.close()
            if e.code == 401:
                raise Fail("token-rejected (HTTP 401)")
            raise Fail(f"http-{e.code}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Fail(f"transport ({type(e).__name__})")
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


def load_handled(path):
    """Set of every meeting id the state file records as handled.

    No configured path is a FAIL: with nothing to compare against, every meeting in the window would
    read as new on every tick and the zero-token saving would silently disappear. A configured path
    whose file does not exist yet is the legitimate first run, and means nothing is handled."""
    if not path:
        raise Fail("state-missing (no state file configured)")
    try:
        with open(path) as f:
            state = json.load(f)
    except FileNotFoundError:
        return set()
    except (OSError, ValueError) as e:
        raise Fail(f"state-unreadable ({type(e).__name__})")
    entries = state.get("handled") if isinstance(state, dict) else None
    if not isinstance(entries, list):
        raise Fail("state-malformed (no handled list)")
    ids = set()
    for e in entries:
        if isinstance(e, str):
            ids.add(e)
        elif isinstance(e, dict) and isinstance(e.get("ids"), list):
            if not all(isinstance(i, str) for i in e["ids"]):
                raise Fail("state-malformed (non-string id)")
            ids.update(e["ids"])
        else:
            raise Fail("state-malformed (unrecognised entry)")
    return ids


def classify(rows, handled, min_age, defer=True):
    """Split rows into (new, deferred). Unknown age counts as old; handled ids are dropped."""
    new, deferred = [], []
    for row in rows:
        mid, age = row[0], row[1]
        if mid in handled:
            continue
        if defer and age is not None and age < min_age:
            deferred.append((mid, age))
        else:
            new.append((mid, age))
    return new, deferred


def list_meetings_text(client, today, days):
    init = client.post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {},
                                   "clientInfo": {"name": "ActionsToIssues-precheck",
                                                  "version": "1.0"}}}, 1)
    if "error" in init or "result" not in init:
        raise Fail("initialize-refused")
    negotiated = init["result"].get("protocolVersion") if isinstance(init["result"], dict) else None
    client.protocol = negotiated if isinstance(negotiated, str) and negotiated else PROTOCOL_VERSION
    try:
        client.post({"jsonrpc": "2.0", "method": "notifications/initialized"}, None)
    except Fail as e:
        # A 401 here is a real verdict; anything else is the server declining a notification.
        if str(e).startswith("token-"):
            raise
    resp = client.post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                        "params": {"name": "list_meetings", "arguments": {
                            # `time_range` is required with a custom range: omitted, the server
                            # may return a wider default window with no sign it substituted.
                            # The window is whole UTC days, read in a zone we cannot see, so it
                            # spans yesterday as well by default: a meeting that straddles
                            # midnight, or starts late in a western time zone, would otherwise
                            # fall outside "today" and read as an idle day.
                            "time_range": "custom",
                            "custom_start": f"{(today - dt.timedelta(days=days - 1)).isoformat()}T00:00:00",
                            # End at tomorrow's midnight, not "now": a naive timestamp is read in a
                            # zone we cannot see, and an end hours in the past would hide the
                            # newest meetings and read as idle. Notes cannot exist in the future.
                            "custom_end": f"{(today + dt.timedelta(days=1)).isoformat()}T00:00:00",
                        }}}, 2)
    if "error" in resp:
        raise Fail("jsonrpc-error")
    res = resp.get("result")
    if not isinstance(res, dict):
        raise Fail("no-result")
    if res.get("isError"):
        # Rate-limit replies arrive this way. The text is not echoed: the same slot carries
        # meeting content on a good answer.
        raise Fail("tool-error (isError)")
    content = res.get("content") or []
    texts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
    return "\n".join(t for t in texts if isinstance(t, str))


def run(args, env=None, now=None):
    env = os.environ if env is None else env
    now = now or dt.datetime.now(dt.timezone.utc)
    access, url = load_token(args.auth_file, args.auth_key, env, now.timestamp())
    # --rows hands the classification to the caller (a host that keeps its own record of what is
    # handled), so it needs no state file and never reads one.
    handled = None if args.rows else load_handled(args.state)
    state_note = "ok" if args.state and os.path.exists(args.state) else "absent"
    client = Client(access, url, float(env.get("PRECHECK_HTTP_TIMEOUT", "15")))
    text = list_meetings_text(client, now.date(), args.days)
    seen, others, rows = parse_meetings(text, now)
    if args.rows:
        def f(v):
            return "unknown" if v is None else str(v)
        lines = [f"OK seen={seen} others={others}"]
        lines += [f"id {mid} {f(age)} {f(length)} {f(quiet)}" for mid, age, length, quiet in rows]
        return ("\n".join(lines), 0)
    new, deferred = classify(rows, handled, args.min_age, defer=not args.no_defer)
    lines = [f"OK seen={seen} others={others} new={len(new)} defer={len(deferred)} state={state_note}"]
    lines += [f"new {mid} {'unknown' if age is None else age}" for mid, age in new]
    lines += [f"defer {mid} {age}" for mid, age in deferred]
    lines.append("VERDICT work" if new else "VERDICT idle")
    return ("\n".join(lines), 10 if new else 0)


def build_parser(env=None):
    env = os.environ if env is None else env
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--auth-file", default=env.get("MCP_AUTH_FILE"))
    p.add_argument("--auth-key", default=env.get("MCP_AUTH_SERVER", "granola"))
    p.add_argument("--state", default=env.get("MN2L_STATE"))
    p.add_argument("--min-age", type=int, default=int(env.get("PRECHECK_MIN_AGE_MIN", "30")))
    p.add_argument("--days", type=int, default=int(env.get("PRECHECK_DAYS", "2")))
    p.add_argument("--no-defer", action="store_true")
    p.add_argument("--rows", action="store_true",
                   help="print every meeting (id, minutes since start, note length s, minutes since "
                        "update) and leave classification to the caller; needs no state file")
    return p


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except ValueError:
        print("FAIL usage (bad numeric environment value)")
        return 2
    if args.days < 1 or args.min_age < 0:
        print("FAIL usage (--days >= 1 and --min-age >= 0)")
        return 2
    try:
        out, rc = run(args)
        print(out)
        return rc
    except Fail as e:
        print(f"FAIL {e}")
        return 1
    except Exception as e:  # anything unforeseen is a doubt, and a doubt wakes the model
        print(f"FAIL unexpected ({type(e).__name__})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
