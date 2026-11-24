#!/usr/bin/env python3
"""Zero-token pre-check: is there any new meeting note worth waking a model for?

Asks the configured note source (one `source_<name>.py` module beside this file) for the meetings in a
short window, compares them with a small local state file and prints a verdict. Run it from your
scheduler before starting the agent; start the agent only when this script says there is work (or
when it cannot tell).

Stdout, on a well-formed answer:

    OK seen=<n> others=<m|unknown> new=<k> defer=<d> state=ok|absent
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
a meeting title or a credential - only fixed phrases, ids, counts and an HTTP code or exception class.

Configuration (flag, then environment); each source's own credentials are in its module's docstring:

    --source    / MN2L_SOURCE        note source: granola (default), fireflies, fathom. Must match the
                                     `source:` key in the skill's config (this script reads no YAML).
    --auth-file / MCP_AUTH_FILE      JSON file of OAuth tokens, for sources reached over MCP
    --auth-key  / MCP_AUTH_SERVER    key of the source's entry in that file (default: the source name)
    --state     / MN2L_STATE         state file listing handled meetings (see below)
    --min-age   / PRECHECK_MIN_AGE_MIN   minutes since a meeting STARTED before it counts as new (default 30).
                                     There is no end time, so this is a heuristic: set it above your longest
                                     regular meeting (for example 90) or a long meeting is read half-finished.
    --no-defer                       judge every meeting regardless of age (use on the day's last run)
    --rows                           print every meeting and leave classification to the caller (needs no state
                                     file): `OK seen=<n> others=<m>` then one `id <meeting id> <minutes since start>
                                     <note length seconds> <minutes since last update>` line each, `unknown` where a
                                     value could not be read. Exit 0 on a well-formed answer, 1 on anything else.
    --days      / PRECHECK_DAYS      how many UTC days to look back, today included (default 2)
    PRECHECK_HTTP_TIMEOUT            seconds (default 15)

`others` counts notes captured by someone other than the signed-in account, for a source that reports
it; a source that does not prints `others=unknown` rather than a number nobody read.

State file (required: no path configured is a FAIL; a path whose file does not exist yet is a first run, reported
as `state=absent`): `{"handled": [...]}` where each entry is either a meeting id or an object with an
`ids` list (one meeting can arrive as several notes, one per capturer, and every id must be
recorded so a sibling is not rediscovered as new). A missing file means nothing is handled yet.
"""
import argparse
import datetime as dt
import importlib
import json
import os
import re
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from precheck_lib import Fail  # noqa: E402

SOURCES = ("granola", "fireflies", "fathom")
DEFAULT_SOURCE = "granola"
# Whatever a source returns is printed on a line of its own and later compared with the state file, so
# it must be a single plain token. Each source checks its own, stricter, id shape first.
SAFE_ID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,128}\Z")


def load_source(name):
    if name not in SOURCES:
        raise Fail("unknown-source")
    return importlib.import_module(f"source_{name}")


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


def run(args, env=None, now=None):
    env = os.environ if env is None else env
    now = now or dt.datetime.now(dt.timezone.utc)
    source = load_source(args.source)
    creds = source.credentials(args, env, now)
    # --rows hands the classification to the caller (a host that keeps its own record of what is
    # handled), so it needs no state file and never reads one. Checked before any network call.
    handled = None if args.rows else load_handled(args.state)
    state_note = "ok" if args.state and os.path.exists(args.state) else "absent"
    seen, others, rows = source.fetch(creds, args, env, now, args.rows)
    if not all(isinstance(r[0], str) and SAFE_ID_RE.match(r[0]) for r in rows):
        raise Fail("unparseable-meeting-id")
    if seen != len(rows):
        raise Fail("count-mismatch")
    others = "unknown" if others is None else others

    def f(v):
        return "unknown" if v is None else str(v)
    if args.rows:
        lines = [f"OK seen={seen} others={others}"]
        lines += [f"id {mid} {f(age)} {f(length)} {f(quiet)}" for mid, age, length, quiet in rows]
        return ("\n".join(lines), 0)
    new, deferred = classify(rows, handled, args.min_age, defer=not args.no_defer)
    lines = [f"OK seen={seen} others={others} new={len(new)} defer={len(deferred)} state={state_note}"]
    lines += [f"new {mid} {f(age)}" for mid, age in new]
    lines += [f"defer {mid} {age}" for mid, age in deferred]
    lines.append("VERDICT work" if new else "VERDICT idle")
    return ("\n".join(lines), 10 if new else 0)


def build_parser(env=None, default_source=None):
    env = os.environ if env is None else env
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--source", default=default_source or env.get("MN2L_SOURCE") or DEFAULT_SOURCE)
    p.add_argument("--auth-file", default=env.get("MCP_AUTH_FILE"))
    p.add_argument("--auth-key", default=env.get("MCP_AUTH_SERVER"))
    p.add_argument("--state", default=env.get("MN2L_STATE"))
    p.add_argument("--min-age", type=int, default=int(env.get("PRECHECK_MIN_AGE_MIN", "30")))
    p.add_argument("--days", type=int, default=int(env.get("PRECHECK_DAYS", "2")))
    p.add_argument("--no-defer", action="store_true")
    p.add_argument("--rows", action="store_true",
                   help="print every meeting (id, minutes since start, note length s, minutes since "
                        "update) and leave classification to the caller; needs no state file")
    return p


def main(argv=None, default_source=None):
    try:
        args = build_parser(default_source=default_source).parse_args(argv)
    except ValueError:
        print("FAIL usage (bad numeric environment value)")
        return 2
    if args.days < 1 or args.min_age < 0:
        print("FAIL usage (--days >= 1 and --min-age >= 0)")
        return 2
    if args.source not in SOURCES:
        print("FAIL usage (unknown --source)")
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
