"""Fireflies.ai note source for the pre-check harness (precheck.py): the documented GraphQL `transcripts`
query, read with an API key. No model, no MCP session.

Docs read 2026-11-24: https://docs.fireflies.ai/graphql-api/query/transcripts (arguments `fromDate`,
`toDate` as ISO 8601 DateTime, `limit` max 50, `skip`) and https://docs.fireflies.ai/getting-started/quickstart
(endpoint and `Authorization: Bearer <key>`). The docs do not give the unit of the returned `date`
field; it is read as epoch milliseconds when it is that large and seconds otherwise, and anything
else is unknown (which the harness treats as old - fail open).

Credentials:

    FIREFLIES_API_KEY        the API key (Fireflies: Integrations > Fireflies API). It is long-lived and
                             reaches every meeting its owner can see: keep it out of the agent's environment
    FIREFLIES_GRAPHQL_URL    endpoint override (https, or loopback for tests); default the documented one

`others` is unknown: the list has no notion of who captured a note relative to the key's owner.
"""
import datetime as dt
import os
import re
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from precheck_lib import Fail, check_url, get_json, minutes_since, parse_iso, window  # noqa: E402

NAME = "fireflies"
DEFAULT_URL = "https://api.fireflies.ai/graphql"
PAGE = 50          # the documented maximum for `limit`
MAX_PAGES = 10     # 500 meetings in two days is not a quiet day; a doubt, so wake the agent
# The id format is not documented; accept a plain opaque token and nothing else.
ID_RE = re.compile(r"[A-Za-z0-9_-]{6,128}\Z")
QUERY = ("query Precheck($fromDate: DateTime, $toDate: DateTime, $limit: Int, $skip: Int) "
         "{ transcripts(fromDate: $fromDate, toDate: $toDate, limit: $limit, skip: $skip) { id date } }")


def credentials(args, env, now):
    key = env.get("FIREFLIES_API_KEY")
    if not key:
        raise Fail("token-missing (FIREFLIES_API_KEY not set)")
    return key, check_url(env.get("FIREFLIES_GRAPHQL_URL") or DEFAULT_URL)


def _instant(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        try:
            return dt.datetime.fromtimestamp(v / 1000 if v > 1e11 else v, dt.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    return parse_iso(v) if isinstance(v, str) else None


def fetch(creds, args, env, now, rows_mode):
    key, url = creds
    start, end = window(now, args.days)
    iso = "%Y-%m-%dT%H:%M:%S.000Z"
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "Authorization": f"Bearer {key}", "User-Agent": "actions-to-issues-precheck/1.0"}
    timeout = float(env.get("PRECHECK_HTTP_TIMEOUT", "15"))
    rows, ids = [], set()
    for page in range(MAX_PAGES):
        body = {"query": QUERY, "variables": {"fromDate": start.strftime(iso), "toDate": end.strftime(iso),
                                              "limit": PAGE, "skip": page * PAGE}}
        doc = get_json(url, headers, timeout=timeout, method="POST", body=body)
        if not isinstance(doc, dict):
            raise Fail("reply-unexpected")
        if doc.get("errors"):
            # The message is not echoed: it may quote the request or an account detail.
            raise Fail("graphql-error")
        data = doc.get("data")
        items = data.get("transcripts") if isinstance(data, dict) else None
        if not isinstance(items, list) or len(items) > PAGE:
            raise Fail("reply-unexpected (no transcripts list)")
        for it in items:
            mid = it.get("id") if isinstance(it, dict) else None
            if not isinstance(mid, str) or not ID_RE.match(mid):
                raise Fail("unparseable-meeting-id")
            if mid in ids:
                # Offset paging over a list that changed between calls: a later page may also have
                # skipped one. Not something to paper over.
                raise Fail("page-shift (duplicate id across pages)")
            ids.add(mid)
            rows.append((mid, minutes_since(_instant(it.get("date")), now), None, None))
        if len(items) < PAGE:
            return len(rows), None, rows
    raise Fail("too-many-pages")
