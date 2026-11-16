"""--rows mode: note timing backfilled from get_meetings (STO-999). Synthetic data only."""
import http.server
import threading
import unittest

from test_precheck import ID1, FAKE_TOKEN, NOW, FakeGranola, meeting, pc, reply


class RowsTiming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeGranola)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/mcp"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        FakeGranola.mode = "json"
        FakeGranola.seen_auth = []
        self.env = {"GRANOLA_ACCESS_TOKEN": FAKE_TOKEN, "GRANOLA_MCP_URL": self.url}

    def _rows(self, listing, get_text=None, get_error=False):
        FakeGranola.list_text = listing
        FakeGranola.get_text, FakeGranola.get_error, FakeGranola.calls = get_text, get_error, []
        self.addCleanup(lambda: setattr(FakeGranola, "get_text", None))
        self.addCleanup(lambda: setattr(FakeGranola, "get_error", False))
        args = pc.build_parser(self.env).parse_args(["--rows", "--days", "1"])
        return pc.run(args, env=self.env, now=NOW)

    def test_rows_mode_backfills_note_timing_from_get_meetings(self):
        # The live list reply stopped carrying created_at/updated_at (STO-999).
        got = (f'<meetings_data count="1"><meeting id="{ID1}" title="t" date="Jan 15, 2030 9:00 AM GMT" '
               'created_at="2030-01-15T09:00:40.000+00:00" updated_at="2030-01-15T09:50:40.000+00:00">'
               'n</meeting></meetings_data>')
        out, rc = self._rows(reply(meeting(ID1, "Jan 15, 2030 9:00 AM GMT")), got)
        self.assertEqual(out.splitlines(), ["OK seen=1 others=0", f"id {ID1} 300 3000 249"])
        self.assertEqual(FakeGranola.get_args["meeting_ids"], [ID1])

    def test_rows_mode_survives_a_failed_get_meetings(self):
        out, rc = self._rows(reply(meeting(ID1)), get_error=True)
        self.assertEqual((rc, out.splitlines()[1]), (0, f"id {ID1} 300 unknown unknown"))
        self.assertIn("get_meetings", FakeGranola.calls)

    def test_more_than_ten_ids_are_fetched_in_chunks_of_ten(self):
        ids = [f"00000000-0000-4000-8000-{n:012d}" for n in range(1, 13)]
        self._rows(reply(*[meeting(i) for i in ids]), get_error=True)
        self.assertEqual(FakeGranola.calls.count("get_meetings"), 2)

    def test_rows_mode_skips_get_meetings_when_the_list_already_has_timing(self):
        full = (f'<meetings_data count="1"><meeting id="{ID1}" title="t" date="Jan 15, 2030 9:00 AM GMT+0" '
                'created_at="2030-01-15T09:00:00.000+00:00" updated_at="2030-01-15T09:30:00.000+00:00">'
                'n</meeting></meetings_data>')
        self._rows(full)
        self.assertNotIn("get_meetings", FakeGranola.calls)


if __name__ == "__main__":
    unittest.main()
