"""Fathom note source for the pre-check harness (precheck.py): the documented REST `GET /meetings`
call, read with an API key. No model, no MCP session.

Docs read 2026-11-24: https://developers.fathom.ai/api-reference/meetings/list-meetings and
https://developers.fathom.ai/api-reference/openapi.yaml (base `https://api.fathom.ai/external/v1`,
`X-Api-Key` header, `created_after` / `created_before`, `cursor`; reply `items`, `next_cursor`, `limit`;
each meeting's `recording_id` is an integer, with `recording_start_time`, `recording_end_time` and
`scheduled_start_time` as date-times). The docs do not define `created_at` or say whether a meeting
is listed before post-call processing finishes; the window filters on it as documented. `next_cursor`
is a required (nullable) field of the reply, so a reply without it is not understood.

Credentials:

    FATHOM_API_KEY     the user's API key. It is long-lived and sees every meeting its owner recorded or
                       was shared: keep it out of the agent's environment
    FATHOM_API_URL     base URL override (https, or loopback for tests); default the documented one

`others` is unknown: the reply names the recorder, but not who the key belongs to.
"""
import os
import sys
import urllib.parse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from precheck_lib import Fail, check_url, get_json, minutes_since, parse_iso, window  # noqa: E402

NAME = "fathom"
DEFAULT_URL = "https://api.fathom.ai/external/v1"
MAX_PAGES = 20   # the page size is not documented; beyond this is a doubt, so wake the agent


def credentials(args, env, now):
    key = env.get("FATHOM_API_KEY")
    if not key:
        raise Fail("token-missing (FATHOM_API_KEY not set)")
    return key, check_url((env.get("FATHOM_API_URL") or DEFAULT_URL).rstrip("/"))


def _row(it, now):
    rid = it.get("recording_id") if isinstance(it, dict) else None
    if isinstance(rid, bool) or not isinstance(rid, int) or rid <= 0:
        raise Fail("unparseable-meeting-id")
    rs, re_ = parse_iso(it.get("recording_start_time")), parse_iso(it.get("recording_end_time"))
    start = rs or parse_iso(it.get("scheduled_start_time"))
    length = int((re_ - rs).total_seconds()) if rs and re_ and re_ >= rs else None
    return str(rid), minutes_since(start, now), length, None


def fetch(creds, args, env, now, rows_mode):
    key, base = creds
    start, end = window(now, args.days)
    params = {"created_after": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "created_before": end.strftime("%Y-%m-%dT%H:%M:%SZ")}
    headers = {"Accept": "application/json", "X-Api-Key": key,
               "User-Agent": "actions-to-issues-precheck/1.0"}
    timeout = float(env.get("PRECHECK_HTTP_TIMEOUT", "15"))
    rows, ids = [], set()
    for _ in range(MAX_PAGES):
        doc = get_json(f"{base}/meetings?{urllib.parse.urlencode(params)}", headers, timeout=timeout)
        items = doc.get("items") if isinstance(doc, dict) else None
        cursor = doc.get("next_cursor") if isinstance(doc, dict) else None
        if not isinstance(items, list) or "next_cursor" not in doc or not (cursor is None or isinstance(cursor, str)):
            raise Fail("reply-unexpected (no items / next_cursor)")
        for it in items:
            row = _row(it, now)
            if row[0] in ids:
                raise Fail("page-shift (duplicate id across pages)")
            ids.add(row[0])
            rows.append(row)
        if not cursor:
            return len(rows), None, rows
        params["cursor"] = cursor
    raise Fail("too-many-pages")
