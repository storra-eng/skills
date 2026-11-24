"""Checks the tracker-adapter contract hosts rely on: every tracker the config offers has an adapter file that lists
its read and write tools separately, and SKILL.md's frontmatter permissions agree with it."""
import json
import pathlib
import re
import unittest

SKILL = pathlib.Path(__file__).resolve().parent.parent / "skills" / "actions-to-issues"
REFS = SKILL / "references"
REQUIRED = ["## Server", "## Read tools", "## Write tools", "## Config block", "## Card categorisation lines",
            "## Calls", "## Read the response"]


def offered_trackers():
    config = (SKILL / "assets" / "config.example.yaml").read_text()
    m = re.search(r"^tracker:\s*(\w+)\s*#\s*([\w |]+?);", config, re.M)
    assert m, "config.example.yaml must have a 'tracker: <name>  # a | b | c; ...' line"
    names = [n.strip() for n in m.group(2).split("|")]
    assert m.group(1) in names
    return names


def section(text, heading):
    m = re.search(r"(?m)^" + re.escape(heading) + r"\b.*$", text)
    assert m, f"no '{heading}' heading"
    start = m.end()
    nxt = text.find("\n## ", start)
    return text[start:] if nxt == -1 else text[start:nxt]


def first_paragraph_tools(text, heading):
    body = section(text, heading).strip()
    return set(re.findall(r"`([A-Za-z_]+)`", body.split("\n\n")[0]))


def frontmatter_permissions():
    text = (SKILL / "SKILL.md").read_text()
    line = next(ln for ln in text.splitlines() if ln.startswith("metadata: "))
    perms = json.loads(line[len("metadata: "):])["permissions"]

    def parse(entries):
        out = {}
        for e in entries:
            name, tools = e.split(":", 1)
            out[name.strip()] = {re.sub(r"\s*\(.*\)", "", t).strip() for t in tools.split(",")}
        return out

    return parse(perms["read"]), parse(perms["write"])


class TrackerAdapterContract(unittest.TestCase):
    def test_default_is_linear(self):
        config = (SKILL / "assets" / "config.example.yaml").read_text()
        self.assertRegex(config, r"(?m)^tracker: linear\b")
        self.assertRegex((SKILL / "SKILL.md").read_text(), r"tracker-<tracker>\.md \(default linear\)")

    def test_every_offered_tracker_has_an_adapter(self):
        for name in offered_trackers():
            with self.subTest(tracker=name):
                path = REFS / f"tracker-{name}.md"
                self.assertTrue(path.is_file(), f"missing {path.name}")
                text = path.read_text()
                for heading in REQUIRED:
                    self.assertRegex(text, r"(?m)^" + re.escape(heading) + r"\b", f"{path.name} lacks '{heading}'")

    def test_read_and_write_tools_are_disjoint_and_named(self):
        for name in offered_trackers():
            with self.subTest(tracker=name):
                text = (REFS / f"tracker-{name}.md").read_text()
                read = first_paragraph_tools(text, "## Read tools")
                write = first_paragraph_tools(text, "## Write tools")
                self.assertTrue(read, "no read tools listed")
                self.assertEqual(len(write), 2, "the skill needs exactly a create tool and a comment tool")
                self.assertFalse(read & write, f"tools listed as both read and write: {read & write}")

    def test_frontmatter_permissions_match_adapters(self):
        fm_read, fm_write = frontmatter_permissions()
        for name in offered_trackers():
            with self.subTest(tracker=name):
                text = (REFS / f"tracker-{name}.md").read_text()
                self.assertEqual(fm_read.get(name), first_paragraph_tools(text, "## Read tools"))
                self.assertEqual(fm_write.get(name), first_paragraph_tools(text, "## Write tools"))

    def test_claims_are_sourced_and_dated(self):
        for name in offered_trackers():
            with self.subTest(tracker=name):
                server = section((REFS / f"tracker-{name}.md").read_text(), "## Server")
                self.assertRegex(server, r"https://")
                self.assertRegex(server, r"\d{1,2} \w{3} 20\d\d")


if __name__ == "__main__":
    unittest.main()
