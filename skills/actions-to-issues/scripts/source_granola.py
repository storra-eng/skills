"""Granola note source for the pre-check harness (precheck.py): one `list_meetings` call over Granola's
MCP server, plus `get_meetings` for note timing in `--rows` mode. The reply parser is granola_reply.py.

Credentials (no location is assumed: set one):

    --auth-file / MCP_AUTH_FILE      JSON file holding the OAuth tokens, shaped
                                     `{"granola": {"serverUrl": "...", "tokens": {"accessToken": "...",
                                     "expiresAt": <epoch seconds or milliseconds>}}}` (several MCP clients
                                     write this shape)
    --auth-key  / MCP_AUTH_SERVER    key of the Granola entry in that file (default "granola")
    GRANOLA_ACCESS_TOKEN             a bearer token directly, instead of a file
    GRANOLA_MCP_URL                  MCP endpoint for GRANOLA_ACCESS_TOKEN only (https, or loopback for tests);
                                     a token read from a file goes only to that file's serverUrl

The script never refreshes a token. Whatever owns the OAuth session (your agent platform's MCP client)
owns the refresh chain; a second writer racing a rotating refresh token can destroy the credential. An
expired or rejected token is a FAIL, the agent is woken, and its own MCP client refreshes on the 401.
"""
import datetime as dt
import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from precheck_lib import Client, Fail, check_url  # noqa: E402
from granola_reply import parse_meetings, timing_from_reply  # noqa: E402

NAME = "granola"
DEFAULT_URL = "https://mcp.granola.ai/mcp"
# An access token this close to expiry is treated as expired: the call would race it.
EXPIRY_SKEW_SEC = 60
# `others` counts notes captured by someone other than the signed-in account (`captured_by_me="false"`).
HAS_OTHERS = True


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


def list_meetings_text(client, today, days):
    client.initialize()
    return client.call_tool_text("list_meetings", {
        # `time_range` is required with a custom range: omitted, the server may return a wider default
        # window with no sign it substituted. The window is whole UTC days, read in a zone we cannot see,
        # so it spans yesterday as well by default: a meeting that straddles midnight, or starts late in
        # a western time zone, would otherwise fall outside "today" and read as an idle day.
        "time_range": "custom",
        "custom_start": f"{(today - dt.timedelta(days=days - 1)).isoformat()}T00:00:00",
        # End at tomorrow's midnight, not "now": a naive timestamp is read in a zone we cannot see, and
        # an end hours in the past would hide the newest meetings and read as idle.
        "custom_end": f"{(today + dt.timedelta(days=1)).isoformat()}T00:00:00",
    })


def fetch_timing(client, ids):
    """`created_at`/`updated_at` for `ids` from `get_meetings`, ten ids a call (the tool's limit), or
    {} for any chunk that fails.

    The list reply no longer carries them (seen 2026-11-16; before 2026-10-28 it did), and without
    them a caller can neither hold back a note still being written nor notice one that grew.
    Best effort by design: unknown is what every caller already treats as the fail-open answer."""
    ids = list(dict.fromkeys(ids))
    out = {}
    for i in range(0, len(ids), 10):
        chunk = ids[i:i + 10]
        try:
            text = client.call_tool_text("get_meetings", {"meeting_ids": chunk, "attachments": "none",
                                                          "max_participants": 0}, req_id=3)
            out.update(timing_from_reply(text, set(chunk)))
        except Fail:
            continue
    return out


def credentials(args, env, now):
    """Read before the state file and before any network call, so a missing credential is reported first."""
    return load_token(args.auth_file, args.auth_key or NAME, env, now.timestamp())


def fetch(creds, args, env, now, rows_mode):
    """-> (seen, others, rows), rows = [(meeting id, minutes since start | None, note length s | None,
    minutes since last update | None)]. Raises Fail unless the reply is positively understood."""
    access, url = creds
    client = Client(access, url, float(env.get("PRECHECK_HTTP_TIMEOUT", "15")))
    text = list_meetings_text(client, now.date(), args.days)
    seen, others, rows = parse_meetings(text, now)
    if rows_mode:
        # Only --rows needs note timing; the classifying mode has no use for it.
        need = [mid for mid, _age, length, quiet in rows if length is None or quiet is None]
        timing = fetch_timing(client, need) if need else {}
        if timing:
            seen, others, rows = parse_meetings(text, now, timing)
    return seen, others, rows
