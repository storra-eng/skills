import unittest


class SandboxTest(unittest.TestCase):
    def test_sandbox_line(self):
        # STO-1061 live check: this fails on purpose; the Release Engineer should fix it.
        self.assertEqual(1 + 1, 3)
