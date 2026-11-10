"""Tests for the deterministic half of the skill. Run: python -m unittest -v

They need pandoc 3.1+ on PATH and run on macOS, Windows and Linux.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "plugins", "gdoc-to-overleaf", "skills", "gdoc-to-overleaf")
SCRIPT = os.path.join(SKILL, "scripts", "g2o.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import common  # noqa: E402
import latex_words  # noqa: E402


def run(*args):
    proc = subprocess.run([sys.executable, SCRIPT] + list(args), capture_output=True,
                          text=True, encoding="utf-8")
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
    except ValueError:
        data = None
    return proc.returncode, data, proc.stderr


class Prepared(unittest.TestCase):
    """One prepare run shared by the tests below."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="g2o-test-")
        cls.work = os.path.join(cls.tmp, "work")
        code, cls.summary, err = run("prepare", os.path.join(FIXTURES, "test-paper.docx"),
                                     "--out", cls.work)
        assert code == 0, err
        cls.project = os.path.join(cls.work, "project")
        cls.source = os.path.join(cls.work, "source.json")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def fresh_project(self, body=None):
        """A copy of the prepared project, optionally with a replacement body."""
        dst = tempfile.mkdtemp(prefix="g2o-proj-", dir=self.tmp)
        shutil.rmtree(dst)
        shutil.copytree(self.project, dst)
        if body is not None:
            with open(os.path.join(dst, "gdoc", "body.tex"), "w", encoding="utf-8") as fh:
                fh.write(body)
        return dst

    def inferred(self):
        with open(os.path.join(FIXTURES, "inferred-body.tex"), encoding="utf-8") as fh:
            return fh.read()

    def check(self, project, *extra):
        return run("check", project, "--source", self.source, *extra)


class TestPrepare(Prepared):
    def test_outputs(self):
        for rel in ("project/main.tex", "project/gdoc/body.tex", "project/gdoc/support.tex",
                    "project/gdoc/figures/image1.png", "report.md", "source.json", "meta.json"):
            self.assertTrue(os.path.isfile(os.path.join(self.work, rel)), rel)
        self.assertEqual(self.summary["title"],
                         "Recursive Self-Improvement as a Fixed Point: A Test Paper")
        counts = self.summary["counts"]
        self.assertEqual((counts["footnotes"], counts["images"], counts["tables"]), (1, 1, 1))
        self.assertEqual(counts["comments"], 1)
        self.assertEqual(counts["suggestions"], 1)

    def test_suggestion_left_out(self):
        with open(os.path.join(self.project, "gdoc", "body.tex"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("The update loop is short:", body)
        self.assertNotIn("brief", body)
        self.assertNotIn("textquotesingle", body)
        self.assertIn("{gdoc/figures/image1.png}", body)

    def test_apostrophes_keep_word_boundaries(self):
        with open(os.path.join(self.project, "gdoc", "body.tex"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("Banach's theorem", body)
        self.assertIn("Good's paper", body)

    def test_report_surfaces_dropped_formatting(self):
        with open(os.path.join(self.work, "report.md"), encoding="utf-8") as fh:
            report = fh.read()
        for expected in ("[Title]", "[Subtitle]", "all monospace", "equation only",
                         "starts with a theorem-like label", "looks like a caption",
                         "contains typed LaTeX", "==TODO", "Cite Schmidhuber (1987) here.",
                         "suggest-insert", "heading carries its own number"):
            self.assertIn(expected, report)

    def test_refuses_non_empty_out(self):
        code, _, err = run("prepare", os.path.join(FIXTURES, "test-paper.docx"), "--out", self.work)
        self.assertEqual(code, 2)
        self.assertIn("not empty", err)


class TestCheck(Prepared):
    def test_raw_draft_flags_only_typed_latex(self):
        code, data, _ = self.check(self.project)
        self.assertEqual(code, 1)
        self.assertEqual(len(data["unexplained_changes"]), 1, data["unexplained_changes"])
        self.assertIn("epsilon", data["unexplained_changes"][0]["removed"])

    def test_inferred_structure_passes(self):
        code, data, _ = self.check(self.fresh_project(self.inferred()))
        self.assertEqual(code, 0, json.dumps(data, indent=1))
        whys = " ".join(x["why"] for x in data["explained_changes"])
        for expected in ("\\cite", "\\ref", "moved", "label or number"):
            self.assertIn(expected, whys)

    def assert_caught(self, old, new, count=1):
        body = self.inferred()
        self.assertEqual(body.count(old), count, old)
        code, data, _ = self.check(self.fresh_project(body.replace(old, new)))
        self.assertEqual(code, 1, "change was not caught: %r -> %r" % (old, new))
        return data

    def test_catches_changed_word(self):
        data = self.assert_caught("The update loop is short:", "The update loop is brief:")
        self.assertEqual(data["unexplained_changes"][0]["removed"], "short")

    def test_catches_dropped_sentence(self):
        self.assert_caught("which goes to zero.", "")

    def test_catches_changed_table_number(self):
        self.assert_caught("Baseline & 120", "Baseline & 12")

    def test_catches_dropped_footnote(self):
        data = self.assert_caught(
            "\\footnote{Good's paper is often cited as the origin of the intelligence explosion argument.}", "")
        self.assertTrue(data["count_mismatches"])

    def test_catches_changed_maths(self):
        self.assert_caught("\\lambda^{n}d(a_{0},a^{*})", "\\lambda^{2n}d(a_{0},a^{*})")

    def test_catches_number_dropped_after_item(self):
        self.assert_caught("\\item A convergence theorem", "\\item 12 A convergence theorem")

    def test_catches_dropped_list_item(self):
        self.assert_caught("\\item Meta-learning", "")

    def test_catches_missing_label(self):
        data = self.assert_caught("\\label{fig:steps}", "")
        self.assertTrue(any("fig:steps" in p for p in data["structure_problems"]))

    def test_allowance_explains_a_declared_change(self):
        project = self.fresh_project(self.inferred().replace(
            "The update loop is short:", "The update loop is brief:"))
        allow = os.path.join(self.tmp, "allow.json")
        with open(allow, "w", encoding="utf-8") as fh:
            json.dump([{"removed": "short", "added": "brief", "why": "author asked"},
                       {"removed": "never", "added": "used", "why": "stale"}], fh)
        code, data, _ = self.check(project, "--allow", allow)
        self.assertEqual(code, 0, data)
        self.assertTrue(any("stale" in w or "never" in w for w in data["warnings"]))


class TestPackage(Prepared):
    def test_manifest_and_zip(self):
        project = self.fresh_project(self.inferred())
        zpath = os.path.join(self.tmp, "out.zip")
        notes = os.path.join(self.tmp, "notes.json")
        with open(notes, "w", encoding="utf-8") as fh:
            json.dump({"doc": "https://docs.google.com/document/d/x/edit", "style": None,
                       "decisions": ["bold 'Theorem N.' -> theorem environment"]}, fh)
        code, data, err = run("package", project, "--zip", zpath, "--notes", notes)
        self.assertEqual(code, 0, err)
        with open(os.path.join(project, "gdoc", "gdoc-to-overleaf.json"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertIn("gdoc/body.tex", manifest["managed"])
        self.assertIn("gdoc/figures/image1.png", manifest["managed"])
        self.assertNotIn("main.tex", manifest["managed"])
        self.assertNotIn("gdoc/gdoc-to-overleaf.json", manifest["managed"])
        self.assertEqual(manifest["decisions"], ["bold 'Theorem N.' -> theorem environment"])
        names = zipfile.ZipFile(zpath).namelist()
        for expected in ("main.tex", "gdoc/body.tex", "gdoc/figures/image1.png",
                         "gdoc/gdoc-to-overleaf.json"):
            self.assertIn(expected, names)
        self.assertTrue(all("\\" not in n and not n.split("/")[-1].startswith(".") for n in names))


class TestUnits(unittest.TestCase):
    def test_hash_ignores_line_endings_and_trailing_space(self):
        d = tempfile.mkdtemp()
        try:
            a, b = os.path.join(d, "a.tex"), os.path.join(d, "b.tex")
            with open(a, "wb") as fh:
                fh.write(b"x \r\ny\r\n\r\n")
            with open(b, "wb") as fh:
                fh.write(b"x\ny")
            self.assertEqual(common.file_hash(a), common.file_hash(b))
        finally:
            shutil.rmtree(d)

    def tokens(self, body, preamble=""):
        d = tempfile.mkdtemp()
        try:
            with open(os.path.join(d, "main.tex"), "w", encoding="utf-8") as fh:
                fh.write(preamble + "\\begin{document}\n" + body + "\n\\end{document}\n")
            items, _ = latex_words.project_tokens(d)
            return [v if k == "w" else "<%s:%s>" % (k, v) for k, v in items]
        finally:
            shutil.rmtree(d)

    def test_text_commands_keep_words(self):
        self.assertEqual(self.tokens(r"An \emph{improvement} \textbf{operator}\\[2pt] here"),
                         ["an", "improvement", "operator", "here"])

    def test_skipped_arguments(self):
        self.assertEqual(self.tokens(r"See \href{https://x.org}{the site}\label{a} now."),
                         ["see", "the", "site", "now"])

    def test_accents_and_escapes(self):
        self.assertEqual(self.tokens(r"Op\'erations cost 5\% and 10\^{}x A\&B"),
                         ["opérations", "cost", "5%", "and", "10^x", "a&b"])

    def test_comments_ignored(self):
        self.assertEqual(self.tokens("keep % drop this\nalso"), ["keep", "also"])

    def test_title_from_preamble(self):
        self.assertEqual(self.tokens("Body", "\\title{My Title}\\author{A \\and B}\n"),
                         ["my", "title", "a", "b", "body"])

    def test_maths(self):
        self.assertEqual(self.tokens(r"x \(a_{1} \le b\) y \[c\] $d$"),
                         ["x", "<m:a_1\\leqb>", "y", "<m:c>", "<m:d>"])

    def test_typed_maths_regex_leaves_money_alone(self):
        sys.path.insert(0, os.path.dirname(SCRIPT))
        import g2o
        self.assertEqual(g2o.TYPED_MATH.split("costs $5 and $10 today"), ["costs $5 and $10 today"])
        self.assertEqual(g2o.TYPED_MATH.split("set $x^2$ now")[1], "x^2")


if __name__ == "__main__":
    unittest.main()
