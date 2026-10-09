"""Tests for granola_precheck.py. Synthetic data only: ids, titles and tokens here are invented."""
import datetime as dt
import http.server
import importlib.util
import json
import os
import pathlib
import tempfile
import threading
import unittest

SCRIPT = (pathlib.Path(__file__).resolve().parent.parent
          / "skills" / "meeting-notes-to-linear" / "scripts" / "granola_precheck.py")
spec = importlib.util.spec_from_file_location("granola_precheck", SCRIPT)
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

NOW = dt.datetime(2030, 1, 15, 14, 0, tzinfo=dt.timezone.utc)
ID1 = "00000000-0000-4000-8000-000000000001"
ID2 = "00000000-0000-4000-8000-000000000002"
ID3 = "00000000-0000-4000-8000-000000000003"
FAKE_TOKEN = "not-a-real-token"


def meeting(mid, date="Jan 15, 2030 9:00 AM GMT+0", mine="true", title="Synthetic sync"):
    return f'<meeting id="{mid}" title="{title}" date="{date}" captured_by_me="{mine}">notes</meeting>'


def reply(*meetings, count=None):
    n = len(meetings) if count is None else count
    return f'<meetings_data count="{n}">' + "".join(meetings) + "</meetings_data>"


def write_json(directory, name, data):
    path = os.path.join(directory, name)
    with open(path, "w") as f:
        json.dump(data, f)
    return path


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

    def test_garbage_is_none(self):
        self.assertIsNone(pc.parse_instant("yesterday-ish"))
        self.assertIsNone(pc.parse_instant(None))


class ParseMeetings(unittest.TestCase):
    def test_counts_and_ages(self):
        text = reply(meeting(ID1, "Jan 15, 2030 9:00 AM GMT+0"),
                     meeting(ID2, "Jan 15, 2030 1:45 PM GMT+0", mine="false"))
        seen, others, rows = pc.parse_meetings(text, NOW)
        self.assertEqual((seen, others), (2, 1))
        self.assertEqual(rows, [(ID1, 300), (ID2, 15)])

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
        self.assertEqual(rows, [(ID1, None)])

    def test_future_date_is_unknown_age(self):
        _, _, rows = pc.parse_meetings(reply(meeting(ID1, "Jan 16, 2030 9:00 AM GMT+0")), NOW)
        self.assertEqual(rows, [(ID1, None)])

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


class Classify(unittest.TestCase):
    ROWS = [(ID1, 300), (ID2, 10), (ID3, None)]

    def test_handled_dropped_young_deferred_unknown_is_old(self):
        new, deferred = pc.classify(self.ROWS, {ID1}, 30)
        self.assertEqual(new, [(ID3, None)])
        self.assertEqual(deferred, [(ID2, 10)])

    def test_no_defer_judges_young_meetings(self):
        new, deferred = pc.classify(self.ROWS, set(), 30, defer=False)
        self.assertEqual([m for m, _ in new], [ID1, ID2, ID3])
        self.assertEqual(deferred, [])

    def test_everything_handled_is_idle(self):
        self.assertEqual(pc.classify(self.ROWS, {ID1, ID2, ID3}, 30), ([], []))


class State(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_missing_file_means_nothing_handled(self):
        self.assertEqual(pc.load_handled(os.path.join(self.tmp.name, "nope.json")), set())

    def test_no_path_configured_fails_rather_than_waking_forever(self):
        with self.assertRaisesRegex(pc.Fail, "state-missing"):
            pc.load_handled(None)

    def test_strings_and_sibling_objects(self):
        p = write_json(self.tmp.name, "s.json",
                       {"handled": [ID1, {"ids": [ID2, ID3], "outcome": "skipped: personal"}]})
        self.assertEqual(pc.load_handled(p), {ID1, ID2, ID3})

    def test_malformed_fails_rather_than_idling(self):
        p = write_json(self.tmp.name, "s.json", {"handled": [42]})
        with self.assertRaisesRegex(pc.Fail, "state-malformed"):
            pc.load_handled(p)
        p = write_json(self.tmp.name, "t.json", {"nothing": []})
        with self.assertRaisesRegex(pc.Fail, "state-malformed"):
            pc.load_handled(p)

    def test_non_string_id_inside_an_entry_fails(self):
        p = write_json(self.tmp.name, "s.json", {"handled": [{"ids": [ID1, 7]}]})
        with self.assertRaisesRegex(pc.Fail, "state-malformed"):
            pc.load_handled(p)

    def test_unreadable_json_fails(self):
        p = os.path.join(self.tmp.name, "bad.json")
        pathlib.Path(p).write_text("{not json")
        with self.assertRaisesRegex(pc.Fail, "state-unreadable"):
            pc.load_handled(p)


class Token(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def auth(self, **tokens):
        return write_json(self.tmp.name, "auth.json",
                          {"granola": {"serverUrl": "https://mcp.example.test/mcp",
                                       "tokens": {"accessToken": FAKE_TOKEN, **tokens}}})

    def test_reads_file_and_url(self):
        tok, url = pc.load_token(self.auth(), env={}, now=1000)
        self.assertEqual((tok, url), (FAKE_TOKEN, "https://mcp.example.test/mcp"))

    def test_nothing_configured_fails_and_assumes_no_default_path(self):
        with self.assertRaisesRegex(pc.Fail, "no auth configured"):
            pc.load_token(None, env={})

    def test_env_token_wins_and_uses_default_url(self):
        tok, url = pc.load_token(None, env={"GRANOLA_ACCESS_TOKEN": FAKE_TOKEN})
        self.assertEqual((tok, url), (FAKE_TOKEN, pc.DEFAULT_URL))

    def test_expired_in_seconds_and_milliseconds(self):
        with self.assertRaisesRegex(pc.Fail, "token-expired"):
            pc.load_token(self.auth(expiresAt=1000 + 30), env={}, now=1000)
        with self.assertRaisesRegex(pc.Fail, "token-expired"):
            pc.load_token(self.auth(expiresAt=(1000 + 30) * 1000 + 10**12), env={},
                          now=(1000 + 30 + 10**9 + 10**9))
        pc.load_token(self.auth(expiresAt=(10**9 + 500) * 1000), env={}, now=10**9)

    def test_absent_expiry_is_not_expired(self):
        pc.load_token(self.auth(), env={}, now=10**10)

    def test_unreadable_expiry_fails(self):
        with self.assertRaisesRegex(pc.Fail, "token-expiry-unreadable"):
            pc.load_token(self.auth(expiresAt="soon"), env={})

    def test_custom_auth_key(self):
        p = write_json(self.tmp.name, "a.json", {"other": {"tokens": {"accessToken": FAKE_TOKEN}}})
        tok, _ = pc.load_token(p, auth_key="other", env={})
        self.assertEqual(tok, FAKE_TOKEN)
        with self.assertRaisesRegex(pc.Fail, "token-missing"):
            pc.load_token(p, auth_key="granola", env={})

    def test_missing_and_unreadable_file(self):
        with self.assertRaisesRegex(pc.Fail, "token-missing"):
            pc.load_token(os.path.join(self.tmp.name, "nope.json"), env={})
        bad = os.path.join(self.tmp.name, "bad.json")
        pathlib.Path(bad).write_text("{")
        with self.assertRaisesRegex(pc.Fail, "token-unreadable"):
            pc.load_token(bad, env={})

    def test_plain_http_to_a_remote_host_is_refused(self):
        p = write_json(self.tmp.name, "a.json", {"granola": {
            "serverUrl": "http://mcp.example.test/mcp", "tokens": {"accessToken": FAKE_TOKEN}}})
        with self.assertRaisesRegex(pc.Fail, "url-not-https"):
            pc.load_token(p, env={})
        with self.assertRaisesRegex(pc.Fail, "url-not-https"):
            pc.load_token(None, env={"GRANOLA_ACCESS_TOKEN": FAKE_TOKEN,
                                     "GRANOLA_MCP_URL": "ftp://mcp.example.test/"})

    def test_loopback_http_is_allowed_for_tests(self):
        self.assertEqual(pc.check_url("http://127.0.0.1:9/mcp"), "http://127.0.0.1:9/mcp")


class FakeGranola(http.server.BaseHTTPRequestHandler):
    """A minimal MCP endpoint. Class attributes configure each test; nothing leaves loopback."""
    list_text = reply()
    mode = "json"          # json | sse | redirect | unauthorised | tool-error
    seen_auth = []
    last_args = {}
    seen_protocol = []

    def log_message(self, *a):
        pass

    def _send(self, status, body, ctype="application/json", extra=None):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        type(self).seen_auth.append(self.headers.get("Authorization"))
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.mode == "redirect":
            return self._send(302, "", extra={"Location": "http://127.0.0.1:1/elsewhere"})
        if self.mode == "unauthorised":
            return self._send(401, "no")
        method = body.get("method")
        if method == "initialize":
            return self._send(200, json.dumps({"jsonrpc": "2.0", "id": body["id"],
                                               "result": {"protocolVersion": "2025-03-26"}}),
                              extra={"Mcp-Session-Id": "synthetic-session"})
        if method == "notifications/initialized":
            return self._send(202, "")
        assert self.headers.get("Mcp-Session-Id") == "synthetic-session"
        type(self).last_args = body["params"]
        type(self).seen_protocol.append(self.headers.get("MCP-Protocol-Version"))
        result = {"isError": True, "content": [{"type": "text", "text": "Rate limit exceeded"}]} \
            if self.mode == "tool-error" else \
            {"content": [{"type": "text", "text": self.list_text}]}
        msg = json.dumps({"jsonrpc": "2.0", "id": body["id"], "result": result})
        if self.mode == "sse":
            return self._send(200, f"event: message\ndata: {json.dumps({'jsonrpc': '2.0', 'method': 'ping'})}\n\n"
                                   f"data: {msg}\n\n", ctype="text/event-stream")
        return self._send(200, msg)


class EndToEnd(unittest.TestCase):
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
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        FakeGranola.mode = "json"
        FakeGranola.seen_auth = []
        self.env = {"GRANOLA_ACCESS_TOKEN": FAKE_TOKEN, "GRANOLA_MCP_URL": self.url}

    def run_check(self, state=None, argv=()):
        # Default to a state file that does not exist yet: the legitimate first run.
        state = state or os.path.join(self.tmp.name, "absent-state.json")
        args = pc.build_parser(self.env).parse_args(list(argv) + ["--state", state])
        return pc.run(args, env=self.env, now=NOW)

    def state(self, handled):
        return write_json(self.tmp.name, "state.json", {"handled": handled})

    def test_new_meeting_means_work(self):
        FakeGranola.list_text = reply(meeting(ID1))
        out, rc = self.run_check()
        self.assertEqual(rc, 10)
        self.assertEqual(out.splitlines(),
                         ["OK seen=1 others=0 new=1 defer=0 state=absent", f"new {ID1} 300", "VERDICT work"])
        self.assertEqual(set(FakeGranola.seen_auth), {f"Bearer {FAKE_TOKEN}"})

    def test_everything_handled_is_idle(self):
        FakeGranola.list_text = reply(meeting(ID1), meeting(ID2, mine="false"))
        out, rc = self.run_check(self.state([{"ids": [ID1, ID2]}]))
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines(), ["OK seen=2 others=1 new=0 defer=0 state=ok", "VERDICT idle"])

    def test_request_asks_for_a_custom_range_spanning_yesterday_to_tomorrow(self):
        FakeGranola.list_text = reply()
        self.run_check()
        self.assertEqual(FakeGranola.last_args["name"], "list_meetings")
        self.assertEqual(FakeGranola.last_args["arguments"], {
            "time_range": "custom",
            "custom_start": "2030-01-14T00:00:00",
            "custom_end": "2030-01-16T00:00:00"})

    def test_negotiated_protocol_version_is_sent_after_initialize(self):
        FakeGranola.list_text = reply()
        FakeGranola.seen_protocol = []
        self.run_check()
        self.assertEqual(FakeGranola.seen_protocol, ["2025-03-26"])

    def test_days_flag_narrows_and_widens_the_window(self):
        FakeGranola.list_text = reply()
        self.run_check(argv=["--days", "1"])
        self.assertEqual(FakeGranola.last_args["arguments"]["custom_start"], "2030-01-15T00:00:00")
        self.run_check(argv=["--days", "3"])
        self.assertEqual(FakeGranola.last_args["arguments"]["custom_start"], "2030-01-13T00:00:00")

    def test_young_meeting_is_deferred_not_new(self):
        FakeGranola.list_text = reply(meeting(ID1, "Jan 15, 2030 1:50 PM GMT+0"))
        out, rc = self.run_check()
        self.assertEqual(rc, 0)
        self.assertIn(f"defer {ID1} 10", out)

    def test_no_defer_flag_judges_it(self):
        FakeGranola.list_text = reply(meeting(ID1, "Jan 15, 2030 1:50 PM GMT+0"))
        _, rc = self.run_check(argv=["--no-defer"])
        self.assertEqual(rc, 10)

    def test_empty_day_is_idle(self):
        FakeGranola.list_text = reply()
        out, rc = self.run_check()
        self.assertEqual((rc, out.splitlines()[0]), (0, "OK seen=0 others=0 new=0 defer=0 state=absent"))

    def test_sse_reply_is_understood(self):
        FakeGranola.mode = "sse"
        FakeGranola.list_text = reply(meeting(ID1))
        self.assertEqual(self.run_check()[1], 10)

    def test_redirect_is_refused_and_token_not_followed(self):
        FakeGranola.mode = "redirect"
        with self.assertRaisesRegex(pc.Fail, "redirect refused"):
            self.run_check()

    def test_401_is_a_fail(self):
        FakeGranola.mode = "unauthorised"
        with self.assertRaisesRegex(pc.Fail, "token-rejected"):
            self.run_check()

    def test_tool_error_is_a_fail_and_text_not_echoed(self):
        FakeGranola.mode = "tool-error"
        with self.assertRaises(pc.Fail) as cm:
            self.run_check()
        self.assertNotIn("Rate limit", str(cm.exception))

    def test_connection_refused_is_a_fail(self):
        self.env["GRANOLA_MCP_URL"] = "http://127.0.0.1:1/mcp"
        with self.assertRaisesRegex(pc.Fail, "transport"):
            self.run_check()


class MainEntryPoint(unittest.TestCase):
    def test_no_auth_configured_exits_1_and_prints_one_fail_line(self):
        saved = {k: os.environ.pop(k, None) for k in ("GRANOLA_ACCESS_TOKEN", "MCP_AUTH_FILE")}
        try:
            import contextlib
            import io
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = pc.main([])
        finally:
            os.environ.update({k: v for k, v in saved.items() if v is not None})
        self.assertEqual(rc, 1)
        self.assertEqual(buf.getvalue().strip(), "FAIL token-missing (no auth configured)")

    def test_missing_state_configuration_exits_1(self):
        import contextlib
        import io
        buf = io.StringIO()
        saved = os.environ.pop("MN2L_STATE", None)
        os.environ["GRANOLA_ACCESS_TOKEN"] = FAKE_TOKEN
        try:
            with contextlib.redirect_stdout(buf):
                rc = pc.main([])
        finally:
            os.environ.pop("GRANOLA_ACCESS_TOKEN", None)
            if saved is not None:
                os.environ["MN2L_STATE"] = saved
        self.assertEqual((rc, buf.getvalue().strip()), (1, "FAIL state-missing (no state file configured)"))

    def test_bad_flags_exit_2(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pc.main(["--days", "0"]), 2)


if __name__ == "__main__":
    unittest.main()
