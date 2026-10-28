"""Tests for the Granola reply parser (granola_reply.py, re-exported by granola_precheck.py). Synthetic data only."""
import datetime as dt
import importlib.util
import pathlib
import unittest

SCRIPT = (pathlib.Path(__file__).resolve().parent.parent
          / "skills" / "ActionsToIssues" / "scripts" / "granola_precheck.py")
spec = importlib.util.spec_from_file_location("granola_precheck", SCRIPT)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

NOW = dt.datetime(2030, 1, 15, 14, 0, tzinfo=dt.timezone.utc)
ID1 = "00000000-0000-4000-8000-000000000001"
ID2 = "00000000-0000-4000-8000-000000000002"
ID3 = "00000000-0000-4000-8000-000000000003"


def meeting(mid, date="Jan 15, 2030 9:00 AM GMT+0", mine="true", title="Synthetic sync"):
    return f'<meeting id="{mid}" title="{title}" date="{date}" captured_by_me="{mine}">notes</meeting>'


def reply(*meetings, count=None):
    n = len(meetings) if count is None else count
    return f'<meetings_data count="{n}">' + "".join(meetings) + "</meetings_data>"


class ParseInstant(unittest.TestCase):
    def test_offset_applied(self):
        got = pc.parse_instant("Jan 15, 2030 9:00 AM GMT+2")
        self.assertEqual(got, dt.datetime(2030, 1, 15, 7, 0, tzinfo=dt.timezone.utc))

    def test_pm_and_negative_offset(self):
        got = pc.parse_instant("Jan 15, 2030 12:30 PM GMT-5")
        self.assertEqual(got, dt.datetime(2030, 1, 15, 17, 30, tzinfo=dt.timezone.utc))

    def test_midnight_is_zero_hour(self):
        got = pc.parse_instant("Jan 15, 2030 12:05 AM GMT+0")
        self.assertEqual(got.hour, 0)

    def test_no_offset_is_none_not_utc(self):
        self.assertIsNone(pc.parse_instant("Jan 15, 2030 9:00 AM"))

    def test_impossible_clock_values_are_none(self):
        self.assertIsNone(pc.parse_instant("Jan 15, 2030 13:00 PM GMT+0"))
        self.assertIsNone(pc.parse_instant("Jan 15, 2030 0:30 AM GMT+0"))
        self.assertIsNone(pc.parse_instant("Jan 15, 2030 9:75 AM GMT+0"))

    def test_garbage_is_none(self):
        self.assertIsNone(pc.parse_instant("yesterday-ish"))
        self.assertIsNone(pc.parse_instant(None))


class ParseMeetings(unittest.TestCase):
    def test_counts_and_ages(self):
        text = reply(meeting(ID1, "Jan 15, 2030 9:00 AM GMT+0"),
                     meeting(ID2, "Jan 15, 2030 1:45 PM GMT+0", mine="false"))
        seen, others, rows = pc.parse_meetings(text, NOW)
        self.assertEqual((seen, others), (2, 1))
        self.assertEqual(rows, [(ID1, 300, None, None), (ID2, 15, None, None)])

    def test_empty_day_is_a_positive_answer(self):
        self.assertEqual(pc.parse_meetings('<meetings_data count="0" />', NOW), (0, 0, []))

    def test_count_mismatch_fails(self):
        with self.assertRaisesRegex(pc.Fail, "count-mismatch"):
            pc.parse_meetings(reply(meeting(ID1), count=2), NOW)

    def test_missing_count_fails(self):
        with self.assertRaisesRegex(pc.Fail, "no-count"):
            pc.parse_meetings("<meetings_data>" + meeting(ID1) + "</meetings_data>", NOW)

    def test_renamed_tag_does_not_read_as_idle(self):
        text = '<meetings_data count="1"><note id="%s" date="x"/></meetings_data>' % ID1
        with self.assertRaisesRegex(pc.Fail, "count-mismatch"):
            pc.parse_meetings(text, NOW)

    def test_no_wrapper_fails(self):
        with self.assertRaisesRegex(pc.Fail, "no-meetings-wrapper"):
            pc.parse_meetings("Rate limit exceeded", NOW)

    def test_bad_id_fails(self):
        with self.assertRaisesRegex(pc.Fail, "unparseable-meeting-id"):
            pc.parse_meetings(reply(meeting("x y")), NOW)

    def test_date_without_offset_is_unknown_age(self):
        _, _, rows = pc.parse_meetings(reply(meeting(ID1, "Jan 15, 2030 1:59 PM")), NOW)
        self.assertEqual(rows, [(ID1, None, None, None)])

    def test_future_date_is_unknown_age(self):
        _, _, rows = pc.parse_meetings(reply(meeting(ID1, "Jan 16, 2030 9:00 AM GMT+0")), NOW)
        self.assertEqual(rows, [(ID1, None, None, None)])

    def test_duplicate_attribute_fails_rather_than_overriding_the_id(self):
        text = ('<meetings_data count="1"><meeting id="%s" title="a" id="%s" date="x"></meeting></meetings_data>'
                % (ID1, ID2))
        with self.assertRaisesRegex(pc.Fail, "duplicate-attribute"):
            pc.parse_meetings(text, NOW)

    def test_id_with_trailing_newline_is_refused(self):
        text = '<meetings_data count="1"><meeting id="%s\n" date="x"/></meetings_data>' % ID1
        with self.assertRaisesRegex(pc.Fail, "unparseable-meeting-id"):
            pc.parse_meetings(text, NOW)

    def test_attribute_containing_angle_bracket_still_parses(self):
        text = reply(meeting(ID1, title="a > b"))
        self.assertEqual(pc.parse_meetings(text, NOW)[0], 1)


class MarkupInNotes(unittest.TestCase):
    def test_meeting_lookalike_inside_a_note_is_not_counted(self):
        injected = ('<meeting id="' + ID1 + '" date="Jan 15, 2030 9:00 AM GMT+0" captured_by_me="true">'
                    'text <meeting id="aaaaaa1" date="x"> more</meeting>')
        seen, _, rows = pc.parse_meetings('<meetings_data count="1">' + injected + '</meetings_data>', NOW)
        self.assertEqual((seen, [r[0] for r in rows]), (1, [ID1]))

    def test_self_closing_tags_are_each_counted(self):
        text = ('<meetings_data count="2"><meeting id="%s" date="x"/><meeting id="%s" date="x"/></meetings_data>'
                % (ID1, ID2))
        self.assertEqual(pc.parse_meetings(text, NOW)[0], 2)

    def test_a_note_that_closes_the_tag_itself_still_fails_open(self):
        text = ('<meetings_data count="1"><meeting id="%s" date="x">a</meeting>'
                '<meeting id="aaaaaa1" date="x"></meeting></meetings_data>' % ID1)
        with self.assertRaisesRegex(pc.Fail, "count-mismatch"):
            pc.parse_meetings(text, NOW)


def timed_meeting(mid, created, updated):
    return (f'<meeting id="{mid}" title="Synthetic sync" date="Jan 15, 2030 9:00 AM GMT+0" '
            f'captured_by_me="true" created_at="{created}" updated_at="{updated}">notes</meeting>')


class WrapperScoping(unittest.TestCase):
    def test_meetings_beside_the_wrapper_are_not_counted(self):
        # A block of duplicate recordings sits BESIDE the wrapper; its entries are not meetings.
        text = (reply(meeting(ID1)) +
                f'<duplicate_recordings><meeting id="{ID2}" other_ids="{ID3}"></meeting></duplicate_recordings>')
        seen, _, rows = pc.parse_meetings(text, NOW)
        self.assertEqual((seen, [r[0] for r in rows]), (1, [ID1]))

    def test_second_wrapper_is_a_doubt(self):
        with self.assertRaisesRegex(pc.Fail, "multiple-meetings-wrappers"):
            pc.parse_meetings(reply(meeting(ID1)) + reply(meeting(ID2)), NOW)

    def test_nested_wrapper_is_a_doubt(self):
        text = ('<meetings_data count="1">' + reply(meeting(ID1)) + '</meetings_data>')
        with self.assertRaisesRegex(pc.Fail, "multiple-meetings-wrappers"):
            pc.parse_meetings(text, NOW)

    def test_unterminated_wrapper_fails(self):
        with self.assertRaisesRegex(pc.Fail, "unterminated-meetings-wrapper"):
            pc.parse_meetings('<meetings_data count="1">' + meeting(ID1), NOW)

    def test_truncated_wrapper_open_tag_fails(self):
        with self.assertRaisesRegex(pc.Fail, "truncated-meetings-wrapper"):
            pc.parse_meetings('<meetings_data count="1" ', NOW)

    def test_renamed_wrapper_reads_as_missing_list(self):
        with self.assertRaisesRegex(pc.Fail, "no-meetings-wrapper"):
            pc.parse_meetings('<meetings_data_v2 count="0" />', NOW)

    def test_self_closing_empty_day_is_positive(self):
        self.assertEqual(pc.parse_meetings('<meetings_data count="0" />', NOW), (0, 0, []))


class NoteTiming(unittest.TestCase):
    def test_length_and_quiet_minutes(self):
        text = reply(timed_meeting(ID1, "2030-01-15T09:00:00.123456Z", "2030-01-15T09:30:00Z"))
        _, _, rows = pc.parse_meetings(text, NOW)
        self.assertEqual(rows, [(ID1, 300, 1799, 270)])

    def test_unparseable_or_reversed_times_are_unknown(self):
        text = reply(timed_meeting(ID1, "garbage", "2030-01-15T09:30:00Z"),
                     timed_meeting(ID2, "2030-01-15T10:00:00Z", "2030-01-15T09:00:00Z"))
        _, _, rows = pc.parse_meetings(text, NOW)
        self.assertEqual([(r[2]) for r in rows], [None, None])

    def test_millisecond_fraction_parses(self):
        self.assertEqual(pc.parse_iso("2030-01-15T09:00:00.5+01:00").hour, 9)


if __name__ == "__main__":
    unittest.main()
