"""Parsing of a Granola `list_meetings` reply, shared by granola_precheck.py (kept beside it so the skill
folder stays self-contained). Pure functions: no network, no files, no token handling.

Everything here fails closed: a reply that is not positively understood raises Fail, which the
caller must treat as a doubt (wake the agent), never as an idle day."""
import datetime as dt
import re

MEETING_TAG_RE = re.compile(r'<meeting\b((?:[^>"]|"[^"]*")*)>', re.S)
ATTR_RE = re.compile(r'([\w:.-]+)\s*=\s*"([^"]*)"')
COUNT_RE = re.compile(r'<meetings_data\b[^>]*?\bcount="(\d+)"')
# `<meeting>` tags are read from INSIDE the `<meetings_data>` wrapper and nowhere else. The server
# can put other blocks BESIDE that wrapper whose entries look like meetings (for example a block of
# duplicate recordings); counting those makes a correct reply read as parser drift and wakes the
# agent on every tick. Scoping to the wrapper's body, rather than stripping known sibling blocks by
# name, means the next sibling the server adds cannot break this the same way.
WRAPPER_OPEN_RE = re.compile(r'<meetings_data\b((?:[^>"]|"[^"]*")*)>', re.S)
WRAPPER_CLOSE_RE = re.compile(r'</meetings_data\s*>')
# Anything that is not shaped like an opaque id is a parse we do not trust.
ID_RE = re.compile(r"[A-Za-z0-9_-]{6,}\Z")
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
DATE_RE = re.compile(
    r"(\w{3})\w*\s+(\d{1,2}),\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*([AP])M"
    r"(?:\s*GMT([+-])(\d{1,2})(?::?(\d{2}))?)?", re.I)


class Fail(Exception):
    pass


def parse_instant(human):
    """"Aug 13, 2026 12:00 PM GMT+2" -> aware datetime, or None.

    A date with no `GMT<offset>` is None rather than UTC: here a wrong instant decides whether a
    meeting is held back as too young, and a local time read as UTC would be hours too young.
    None is read by the caller as OLD - fail open."""
    m = DATE_RE.search(human or "")
    if not m:
        return None
    mon, day, year, hour, minute, half, sign, off_h, off_m = m.groups()
    if not sign:
        return None
    mon = MONTHS.get(mon.title())
    if not mon:
        return None
    if not 1 <= int(hour) <= 12 or int(minute) > 59:
        return None
    hour = int(hour) % 12 + (12 if half.upper() == "P" else 0)
    offset = dt.timedelta(hours=int(off_h or 0), minutes=int(off_m or 0))
    try:
        return dt.datetime(int(year), mon, int(day), hour, int(minute),
                           tzinfo=dt.timezone(-offset if sign == "-" else offset))
    except ValueError:
        return None


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


def note_length_sec(a):
    """Seconds between a note's `created_at` and `updated_at` attributes, or None. The list reply
    carries no meeting length; a capture creates the note when it starts and keeps touching it while
    it runs, so for a note nobody edits later the difference is how long it recorded for. A late
    edit moves it too, which can only cause a harmless extra read. Unparseable is None (unknown)."""
    c, u = parse_iso(a.get("created_at")), parse_iso(a.get("updated_at"))
    if c is None or u is None:
        return None
    secs = int((u - c).total_seconds())
    return secs if secs >= 0 else None


def quiet_minutes(a, now):
    """Minutes since the note was last updated, or None. A note still being written has moved a
    moment ago; a caller can wait for it to go quiet rather than re-reading it every tick."""
    u = parse_iso(a.get("updated_at"))
    if u is None:
        return None
    m = int((now - u).total_seconds() // 60)
    return m if m >= 0 else 0


def wrapper_body(text):
    """The text inside the `<meetings_data>` wrapper, or None when it has no close. A self-closing
    `<meetings_data count="0" />` is an empty body."""
    m = WRAPPER_OPEN_RE.search(text or "")
    if m is None:
        return None
    if m.group(1).rstrip().endswith("/"):
        return ""
    close = WRAPPER_CLOSE_RE.search(text, m.end())
    if close is None:
        return None
    return text[m.end():close.start()]


def has_second_wrapper(text):
    """True when a further `<meetings_data>` open tag follows the first one anywhere - after its close
    (a paged or multi-day listing) or inside its body (a nested wrapper, whose own count= could otherwise
    agree with the outer one). Only the first body is read, so either is a doubt, not something to merge."""
    m = WRAPPER_OPEN_RE.search(text or "")
    if m is None:
        return False
    return WRAPPER_OPEN_RE.search(text, m.end()) is not None


def top_level_meeting_tags(text):
    """Yield the opening `<meeting ...>` tags that are not nested inside another meeting.

    Note text sits inside these tags and is written by other people. Skipping from each opening tag to
    its closing tag stops markup-looking text in a note from inflating the parsed count. It is not a
    full defence: text that closes the tag itself can still break out, which is why a count mismatch
    is a FAIL (a wake), never a pass. The worst a participant can do is cost one agent run."""
    pos = 0
    while True:
        m = MEETING_TAG_RE.search(text, pos)
        if not m:
            return
        yield m
        pos = m.end()
        if not m.group(0).endswith("/>"):
            close = text.find("</meeting>", pos)
            if close != -1:
                pos = close + len("</meeting>")


def parse_meetings(text, now):
    """Parse a `list_meetings` text reply -> (seen, others, rows).

    rows is a list of (meeting id, minutes since start | None, note length in seconds | None,
    minutes since last update | None). `others` counts notes captured by someone other than the
    signed-in account. Raises Fail unless the reply is positively understood."""
    # The wrapper's OPEN TAG is the test for "is this a listing at all", not the substring: a renamed
    # tag (`<meetings_data_v2>`) contains it and would otherwise be reported as an unterminated
    # wrapper, sending the reader after a cut-off reply instead of the format drift it is.
    if WRAPPER_OPEN_RE.search(text) is None:
        if re.search(r"<meetings_data\b", text):
            raise Fail("truncated-meetings-wrapper")
        raise Fail("no-meetings-wrapper")
    body = wrapper_body(text)
    if body is None:
        raise Fail("unterminated-meetings-wrapper")
    if has_second_wrapper(text):
        raise Fail("multiple-meetings-wrappers")
    tags = []
    for m in top_level_meeting_tags(body):
        pairs = ATTR_RE.findall(m.group(1))
        # A repeated attribute name (for example from an unescaped quote in a title) would let a later
        # value silently override `id`, `date` or `captured_by_me`. Refuse rather than pick one.
        if len({k for k, _ in pairs}) != len(pairs):
            raise Fail("duplicate-attribute")
        tags.append(dict(pairs))
    # count= is REQUIRED, not merely checked when present. It is the second witness that the tag
    # regex still matches the reply: without it, a renamed tag or a dropped attribute parses as zero
    # meetings and reports an idle day from a reply this script did not understand. A genuinely empty
    # day still answers `<meetings_data count="0" />`.
    cm = COUNT_RE.search(text)
    if not cm:
        raise Fail("no-count (the wrapper carries no count= to check the parse against)")
    if int(cm.group(1)) != len(tags):
        raise Fail(f"count-mismatch (wrapper {cm.group(1)}, parsed {len(tags)})")
    rows, others = [], 0
    for a in tags:
        mid = a.get("id", "")
        if not ID_RE.match(mid):
            raise Fail("unparseable-meeting-id")
        if a.get("captured_by_me") == "false":
            others += 1
        inst = parse_instant(a.get("date"))
        age_min = None if inst is None else int((now - inst).total_seconds() // 60)
        # A start in the FUTURE is a misread date, not a very young meeting: unknown, which the
        # caller treats as old. Only a date that parsed to a plausible past instant may hold one back.
        rows.append((mid, None if age_min is None or age_min < 0 else age_min,
                     note_length_sec(a), quiet_minutes(a, now)))
    return len(tags), others, rows
