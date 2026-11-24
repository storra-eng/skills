#!/usr/bin/env python3
"""Zero-token pre-check for Granola: kept so existing schedulers keep working unchanged.

Equivalent to `precheck.py --source granola`; flags, environment, output and exit codes are the same
(see precheck.py for the harness and source_granola.py for Granola's credentials). An explicit
`--source` still wins. New setups should call precheck.py directly.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Re-exported: tests and callers import these from here.
from precheck_lib import (  # noqa: E402,F401
    LOOPBACK_HOSTS, PROTOCOL_VERSION, Client, Fail, _NoRedirect, _OPENER, check_url)
from granola_reply import (  # noqa: E402,F401
    ATTR_RE, COUNT_RE, DATE_RE, ID_RE, MEETING_TAG_RE, MONTHS, WRAPPER_CLOSE_RE, WRAPPER_OPEN_RE,
    has_second_wrapper, note_length_sec, parse_instant, parse_iso, parse_meetings, quiet_minutes,
    timing_from_reply, top_level_meeting_tags, wrapper_body)
from source_granola import (  # noqa: E402,F401
    DEFAULT_URL, EXPIRY_SKEW_SEC, fetch_timing, list_meetings_text, load_token)
import precheck as _harness  # noqa: E402
from precheck import classify, load_handled, run  # noqa: E402,F401


def build_parser(env=None):
    return _harness.build_parser(env, default_source="granola")


def main(argv=None):
    return _harness.main(argv, default_source="granola")


if __name__ == "__main__":
    sys.exit(main())
