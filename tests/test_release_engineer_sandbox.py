import unittest


class SandboxTest(unittest.TestCase):
    def test_sandbox_line(self):
        self.assertEqual(1 + 1, 2)
