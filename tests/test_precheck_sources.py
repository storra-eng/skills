"""Fireflies and Fathom pre-check sources against a loopback fake. Synthetic data only: every id, key and
time here is invented, and the reply shapes are the documented ones (see each source module)."""
import datetime as dt
import http.server
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import threading
import unittest
import urllib.parse

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "skills" / "actions-to-issues" / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("precheck", SCRIPTS / "precheck.py")
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)

NOW = dt.datetime(2030, 1, 15, 14, 0, tzinfo=dt.timezone.utc)
KEY = "not-a-real-key"
FF1, FF2 = "SyntheticFF0001", "SyntheticFF0002"
MS_9AM = int(dt.datetime(2030, 1, 15, 9, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
MS_1345 = int(dt.datetime(2030, 1, 15, 13, 45, tzinfo=dt.timezone.utc).timestamp() * 1000)


class Fake(http.server.BaseHTTPRequestHandler):
    """Serves `pages` in order (one JSON body per request), or a status. Records what it was sent."""
    pages = []
    status = 200
    requests = []

    def log_message(self, *a):
        pass

    def _reply(self):
        n = len(type(self).requests)
        if self.status == 302:
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/elsewhere")
            self.end_headers()
            return
        body = json.dumps(self.pages[min(n - 1, len(self.pages) - 1)] if self.pages else {}).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        type(self).requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(raw)})
        self._reply()

    def do_GET(self):
        type(self).requests.append({"path": self.path, "headers": dict(self.headers), "body": None})
        self._reply()


class Base(unittest.TestCase):
    source = None

    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        Fake.pages, Fake.status, Fake.requests = [], 200, []

    def check(self, argv=(), handled=None, env=None):
        state = os.path.join(self.tmp.name, "state.json")
        if handled is not None:
            with open(state, "w") as f:
                json.dump({"handled": handled}, f)
        args = pc.build_parser({}).parse_args(["--source", self.source, "--state", state] + list(argv))
        return pc.run(args, env={**self.env, **(env or {})}, now=NOW)

    def fails(self, reason, **kw):
        with self.assertRaises(pc.Fail) as cm:
            self.check(**kw)
        self.assertTrue(str(cm.exception).startswith(reason), str(cm.exception))


class Fireflies(Base):
    source = "fireflies"

    def setUp(self):
        super().setUp()
        self.env = {"FIREFLIES_API_KEY": KEY, "FIREFLIES_GRAPHQL_URL": self.base + "/graphql"}

    def page(self, *items):
        return {"data": {"transcripts": list(items)}}

    def test_new_and_deferred(self):
        Fake.pages = [self.page({"id": FF1, "date": MS_9AM}, {"id": FF2, "date": MS_1345})]
        out, rc = self.check()
        self.assertEqual(rc, 10)
        self.assertEqual(out.splitlines(), ["OK seen=2 others=unknown new=1 defer=1 state=absent",
                                            f"new {FF1} 300", f"defer {FF2} 15", "VERDICT work"])
        req = Fake.requests[0]
        self.assertEqual(req["headers"]["Authorization"], f"Bearer {KEY}")
        self.assertEqual(req["body"]["variables"], {"fromDate": "2030-01-14T00:00:00.000Z",
                                                    "toDate": "2030-01-16T00:00:00.000Z",
                                                    "limit": 50, "skip": 0})

    def test_handled_is_idle(self):
        Fake.pages = [self.page({"id": FF1, "date": MS_9AM})]
        out, rc = self.check(handled=[FF1])
        self.assertEqual(rc, 0)
        self.assertTrue(out.endswith("VERDICT idle"))

    def test_empty_day_is_idle(self):
        Fake.pages = [self.page()]
        self.assertEqual(self.check()[1], 0)

    def test_a_full_page_is_followed_with_skip(self):
        first = [{"id": f"SyntheticFFp{i:03d}", "date": MS_9AM} for i in range(50)]
        Fake.pages = [self.page(*first), self.page({"id": FF1, "date": MS_9AM})]
        out, rc = self.check()
        self.assertTrue(out.startswith("OK seen=51 "))
        self.assertEqual([r["body"]["variables"]["skip"] for r in Fake.requests], [0, 50])

    def test_never_ending_pages_are_a_fail_not_idle(self):
        Fake.pages = [self.page(*[{"id": f"SyntheticFFq{i:04d}", "date": MS_9AM} for i in range(n, n + 50)])
                      for n in range(0, 550, 50)]
        self.fails("too-many-pages")

    def test_duplicate_across_pages_is_a_fail(self):
        first = [{"id": f"SyntheticFFp{i:03d}", "date": MS_9AM} for i in range(50)]
        Fake.pages = [self.page(*first), self.page(first[-1])]
        self.fails("page-shift")

    def test_graphql_errors_are_a_fail_and_not_echoed(self):
        Fake.pages = [{"errors": [{"message": "synthetic secret detail"}], "data": None}]
        self.fails("graphql-error")

    def test_unexpected_shapes_are_a_fail(self):
        for body in ({"data": {}}, {"data": {"transcripts": {}}}, [], {"data": {"transcripts": [{"date": 1}]}},
                     {"data": {"transcripts": [{"id": "x y z!", "date": 1}]}}):
            Fake.pages, Fake.requests = [body], []
            with self.subTest(body=body):
                with self.assertRaises(pc.Fail):
                    self.check()

    def test_unreadable_date_is_unknown_age_and_counts_as_new(self):
        Fake.pages = [self.page({"id": FF1, "date": "yesterday"}, {"id": FF2, "date": True})]
        out, rc = self.check()
        self.assertEqual(rc, 10)
        self.assertIn(f"new {FF1} unknown", out)
        self.assertIn(f"new {FF2} unknown", out)

    def test_401_redirect_and_plain_http(self):
        Fake.status = 401
        self.fails("token-rejected (HTTP 401)")
        Fake.status = 302
        self.fails("http-302 (redirect refused)")
        self.fails("url-not-https", env={"FIREFLIES_GRAPHQL_URL": "http://example.com/graphql"})

    def test_missing_key(self):
        self.fails("token-missing", env={"FIREFLIES_API_KEY": ""})


class Fathom(Base):
    source = "fathom"

    def setUp(self):
        super().setUp()
        self.env = {"FATHOM_API_KEY": KEY, "FATHOM_API_URL": self.base + "/external/v1"}

    @staticmethod
    def meeting(rid, start="2030-01-15T09:00:00Z", end="2030-01-15T09:30:00Z"):
        return {"recording_id": rid, "title": "Synthetic sync", "recording_start_time": start,
                "recording_end_time": end, "scheduled_start_time": start}

    def test_rows_and_query(self):
        Fake.pages = [{"limit": 10, "next_cursor": None,
                       "items": [self.meeting(101), self.meeting(102, "2030-01-15T13:50:00Z", None)]}]
        out, rc = self.check(["--rows"])
        self.assertEqual(rc, 0)
        self.assertEqual(out.splitlines(), ["OK seen=2 others=unknown", "id 101 300 1800 unknown",
                                            "id 102 10 unknown unknown"])
        req = Fake.requests[0]
        self.assertEqual(req["headers"]["X-Api-Key"], KEY)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(req["path"]).query)
        self.assertEqual(q, {"created_after": ["2030-01-14T00:00:00Z"], "created_before": ["2030-01-16T00:00:00Z"]})

    def test_handled_ids_are_strings_of_recording_id(self):
        Fake.pages = [{"limit": 10, "next_cursor": None, "items": [self.meeting(101)]}]
        self.assertEqual(self.check(handled=["101"])[1], 0)
        self.assertEqual(self.check(handled=[])[1], 10)

    def test_cursor_is_followed(self):
        Fake.pages = [{"limit": 1, "next_cursor": "c-2", "items": [self.meeting(101)]},
                      {"limit": 1, "next_cursor": None, "items": [self.meeting(102)]}]
        out, _ = self.check()
        self.assertTrue(out.startswith("OK seen=2 "))
        self.assertIn("cursor=c-2", Fake.requests[1]["path"])

    def test_endless_cursor_is_a_fail_not_idle(self):
        Fake.pages = [{"limit": 1, "next_cursor": f"c-{i}", "items": [self.meeting(200 + i)]} for i in range(21)]
        self.fails("too-many-pages")

    def test_duplicate_is_a_fail(self):
        Fake.pages = [{"limit": 1, "next_cursor": "c-2", "items": [self.meeting(101)]},
                      {"limit": 1, "next_cursor": None, "items": [self.meeting(101)]}]
        self.fails("page-shift")

    def test_unexpected_shapes_are_a_fail(self):
        for body in ({}, {"items": []}, {"items": {}, "next_cursor": None}, {"items": [{}], "next_cursor": None},
                     {"items": [{"recording_id": "101"}], "next_cursor": None},
                     {"items": [{"recording_id": True}], "next_cursor": None},
                     {"items": [], "next_cursor": 5}):
            Fake.pages, Fake.requests = [body], []
            with self.subTest(body=body):
                with self.assertRaises(pc.Fail):
                    self.check()

    def test_empty_day_is_idle(self):
        Fake.pages = [{"limit": 10, "next_cursor": None, "items": []}]
        self.assertEqual(self.check()[1], 0)

    def test_401_429_redirect_and_plain_http(self):
        Fake.status = 401
        self.fails("token-rejected (HTTP 401)")
        Fake.status = 429
        self.fails("http-429")
        Fake.status = 302
        self.fails("http-302 (redirect refused)")
        self.fails("url-not-https", env={"FATHOM_API_URL": "http://example.com/v1"})


if __name__ == "__main__":
    unittest.main()
