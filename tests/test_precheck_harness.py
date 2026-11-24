"""The pre-check run as a script: precheck.py (the harness) and granola_precheck.py (the Granola shim).

In-process tests cannot catch a Fail class that exists twice (a file executed as __main__ and also
imported), which would turn every fixed FAIL reason into `FAIL unexpected (Fail)`. Synthetic data only."""
import http.server
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest

from test_precheck import ID1, ID2, FAKE_TOKEN, FakeGranola, meeting, reply

SCRIPTS = pathlib.Path(__file__).resolve().parent.parent / "skills" / "actions-to-issues" / "scripts"


def run_script(name, argv, env):
    base = {k: v for k, v in os.environ.items()
            if not k.startswith(("GRANOLA_", "MCP_", "MN2L_", "PRECHECK_", "FIREFLIES_", "FATHOM_"))}
    p = subprocess.run([sys.executable, str(SCRIPTS / name)] + list(argv), env={**base, **env},
                       capture_output=True, text=True, timeout=30)
    return p.returncode, p.stdout, p.stderr


class Scripts(unittest.TestCase):
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
        FakeGranola.get_text = None
        FakeGranola.list_text = reply(meeting(ID1, "Jan 1, 2000 9:00 AM GMT+0"),
                                      meeting(ID2, "Jan 1, 2000 9:00 AM GMT+0", mine="false"))
        self.env = {"GRANOLA_ACCESS_TOKEN": FAKE_TOKEN, "GRANOLA_MCP_URL": self.url,
                    "MN2L_STATE": os.path.join(self.tmp.name, "absent.json")}

    def both(self, argv=(), env=None):
        env = {**self.env, **(env or {})}
        shim = run_script("granola_precheck.py", argv, env)
        harness = run_script("precheck.py", ["--source", "granola"] + list(argv), env)
        return shim, harness

    def test_shim_and_harness_print_the_same_verdict(self):
        shim, harness = self.both()
        self.assertEqual(shim, harness)
        rc, out, err = shim
        self.assertEqual(rc, 10)
        self.assertEqual(err, "")
        lines = out.splitlines()
        self.assertEqual(lines[0], "OK seen=2 others=1 new=2 defer=0 state=absent")
        self.assertEqual(lines[-1], "VERDICT work")

    def test_harness_defaults_to_granola(self):
        rc, out, _ = run_script("precheck.py", [], self.env)
        self.assertEqual(rc, 10)
        self.assertTrue(out.startswith("OK seen=2 others=1"))

    def test_a_failure_raised_inside_a_source_keeps_its_fixed_reason(self):
        FakeGranola.mode = "unauthorised"
        for rc, out, _ in self.both():
            self.assertEqual((rc, out), (1, "FAIL token-rejected (HTTP 401)\n"))

    def test_a_parse_failure_keeps_its_fixed_reason(self):
        FakeGranola.list_text = reply(meeting(ID1), count=5)
        for rc, out, _ in self.both():
            self.assertEqual(rc, 1)
            self.assertTrue(out.startswith("FAIL count-mismatch"), out)

    def test_missing_credentials_is_reported_before_the_state_file(self):
        for rc, out, _ in self.both(env={"GRANOLA_ACCESS_TOKEN": "", "MN2L_STATE": ""}):
            self.assertEqual((rc, out), (1, "FAIL token-missing (no auth configured)\n"))

    def test_unknown_source_is_a_usage_error(self):
        rc, out, _ = run_script("precheck.py", ["--source", "nope"], self.env)
        self.assertEqual((rc, out), (2, "FAIL usage (unknown --source)\n"))

    def test_source_from_environment(self):
        rc, out, _ = run_script("precheck.py", [], {**self.env, "MN2L_SOURCE": "fathom"})
        self.assertEqual((rc, out), (1, "FAIL token-missing (FATHOM_API_KEY not set)\n"))

    def test_shim_ignores_mn2l_source(self):
        rc, out, _ = run_script("granola_precheck.py", [], {**self.env, "MN2L_SOURCE": "fathom"})
        self.assertEqual(rc, 10)


if __name__ == "__main__":
    unittest.main()
