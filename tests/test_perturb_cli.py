"""tools/perturb.py — the surface, not the arithmetic.

The maths is covered in ``test_counterfactual.py``. What is only reachable by
running the tool is its argument parsing and its dispatch, and that is exactly
where ``tools/window.py`` produced four wrong lines in one sitting. Run the
tool, read what it says.

    python -m unittest discover tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
CLI = os.path.join(ROOT, "tools", "perturb.py")

from messages import LANGS, text  # noqa: E402
from textcompare import flat  # noqa: E402


def run(*args, expect=0):
    out = subprocess.run([sys.executable, CLI, *args],
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == expect, "exit %d: %s" % (out.returncode, out.stderr)
    return out


class Arguments(unittest.TestCase):

    def test_an_impossible_ratio_is_refused(self):
        """5 flips out of 3 runs is not a typo to be clamped away."""
        out = run("--material", "5/3", "--cosmetic", "0/3", expect=2)
        self.assertIn("impossible", out.stderr)

    def test_a_malformed_ratio_is_refused(self):
        for bad in ("5", "5-3", "abc", "5/", "/3"):
            out = run("--material", bad, "--cosmetic", "0/3", expect=2)
            self.assertIn("expected flipped/total", out.stderr, bad)

    def test_omitting_a_kind_entirely_is_no_control_not_a_crash(self):
        out = run("--material", "6/6")
        self.assertIn("no_control", out.stdout)


class Dispatch(unittest.TestCase):
    """One case per verdict: a tool that can only say one thing is not a tool."""

    CASES = {
        "responsive": ("5/6", "0/6"),
        "memorised": ("0/6", "0/6"),
        "unstable": ("6/6", "6/6"),
        "no_power": ("2/2", "0/2"),
    }

    def test_each_verdict_is_reachable_and_named(self):
        for verdict, (m, c) in self.CASES.items():
            out = run("--material", m, "--cosmetic", c).stdout
            self.assertIn(verdict, out, verdict)

    def test_the_verdict_prose_matches_the_shared_table(self):
        for verdict, (m, c) in self.CASES.items():
            for lang in LANGS:
                out = run("--material", m, "--cosmetic", c, "--lang", lang).stdout
                self.assertIn(flat(text("cf.verdict." + verdict, lang)), flat(out),
                              "%s/%s" % (verdict, lang))

    def test_no_power_shows_that_it_is_already_the_best_case(self):
        """The number that explains the verdict, not just the verdict."""
        out = run("--material", "2/2", "--cosmetic", "0/2").stdout
        self.assertIn("best possible", out)
        self.assertIn("already the best", out)

    def test_a_passing_run_does_not_show_that_note(self):
        self.assertNotIn("already the best",
                         run("--material", "5/6", "--cosmetic", "0/6").stdout)

    def test_the_floor_is_always_on_screen(self):
        """Six is the number a caller needs before running anything at all."""
        for m, c in [("5/6", "0/6"), ("2/2", "0/2"), ("6/6", "")]:
            args = ["--material", m] + (["--cosmetic", c] if c else [])
            self.assertIn("6 (3 + 3)", run(*args).stdout, m)

    def test_the_limits_travel_with_every_verdict(self):
        for verdict, (m, c) in self.CASES.items():
            out = run("--material", m, "--cosmetic", c).stdout
            self.assertIn(flat(text("cf.limits", "en")), flat(out), verdict)


class Language(unittest.TestCase):

    def test_english_is_the_default(self):
        out = run("--material", "5/6", "--cosmetic", "0/6").stdout
        self.assertFalse([c for c in out if "一" <= c <= "鿿"])

    def test_chinese_is_reachable_and_keeps_the_numbers(self):
        zh = run("--material", "5/6", "--cosmetic", "0/6", "--lang", "zh").stdout
        self.assertTrue([c for c in zh if "一" <= c <= "鿿"])
        for number in ("5/6", "0.0076", "6 (3 + 3)"):
            self.assertIn(number, zh, number)


class Layout(unittest.TestCase):
    """Same projector constraint as tools/window.py."""

    def test_no_line_overflows_a_terminal(self):
        import unicodedata

        def cols(s):
            return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

        for lang in LANGS:
            for m, c in [("5/6", "0/6"), ("0/6", "0/6"), ("2/2", "0/2")]:
                out = run("--material", m, "--cosmetic", c, "--lang", lang).stdout
                for line in out.splitlines():
                    if set(line.strip()) == {"─"}:
                        continue
                    self.assertLessEqual(cols(line), 84, repr(line))


if __name__ == "__main__":
    unittest.main()
