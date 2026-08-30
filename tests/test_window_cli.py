"""The CLI's remedy dispatch — a regression suite for four shipped-then-caught bugs.

``tools/`` had no tests, which is the same as declaring its branches cannot
fail. Adding ``--trials`` produced four wrong lines in one sitting, every one of
them a *combination* of causes rather than a bad formula:

1. an inverted date range (``2020-01 .. 2015-01``) when the cutoff preceded the
   backtest start, so the open-book span was empty;
2. "switch to an earlier model" offered when no cutoff whatsoever could supply
   the months a screening-corrected bar demanded;
3. "report only the clean segment" offered when the clean segment was empty;
4. ``SR inf`` — the Sharpe a zero-month sample could demonstrate.

None would have been caught by testing the library: the arithmetic was right
each time and the dispatch was wrong. Run the tool, read what it says.

    python -m unittest discover tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(ROOT, "tools", "window.py")


def run(*args):
    out = subprocess.run([sys.executable, CLI, *args],
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return out.stdout


def remedies(text):
    """Just the 那要怎么办 block."""
    body = text.split("那要怎么办", 1)
    return body[1].split("同一段区间", 1)[0] if len(body) > 1 else ""


BASE = ("--cutoff", "2024-10", "--start", "2020-01", "--end", "2025-06")
CLEAN = ("--cutoff", "2015-01", "--start", "2020-01", "--end", "2025-06")
NOHOLD = ("--cutoff", "2026-01", "--start", "2020-01", "--end", "2025-06")


class RemedyDispatch(unittest.TestCase):

    def test_no_remedy_ever_prints_an_inverted_date_range(self):
        """Bug 1. The open-book span is empty when the cutoff precedes the start."""
        for args in (CLEAN, CLEAN + ("--trials", "20")):
            r = remedies(run(*args))
            self.assertNotIn("2015-01", r,
                             "open-book span named despite there being none")
            self.assertNotIn("标为开卷", r)

    def test_switching_models_is_not_offered_when_it_cannot_work(self):
        """Bug 2. No cutoff supplies months the whole backtest does not contain."""
        r = remedies(run(*BASE, "--trials", "20"))     # needs 112, total is 66
        self.assertIn("换更早的模型不够", r)
        self.assertIn("66", r)
        self.assertIn("112", r)

    def test_switching_models_is_offered_when_it_does_work(self):
        """The falsifier for the test above — the branch must be reachable."""
        r = remedies(run(*BASE))                        # needs 48, total is 66
        self.assertIn("及更早即够", r)
        self.assertNotIn("换更早的模型不够", r)

    def test_reporting_the_clean_segment_needs_a_clean_segment(self):
        """Bug 3. Nothing is out of sample, so there is no clean segment to report."""
        self.assertNotIn("只报干净段", remedies(run(*NOHOLD)))
        self.assertIn("只报干净段", remedies(run(*BASE)))

    def test_an_empty_sample_is_never_said_to_demonstrate_a_sharpe(self):
        """Bug 4. ``SR inf`` reads as the opposite of what it means."""
        for args in (NOHOLD, NOHOLD + ("--trials", "30")):
            out = run(*args)
            self.assertNotIn("inf", out)
            self.assertNotIn("nan", out)

    def test_the_screening_remedy_appears_only_when_screening_costs_something(self):
        self.assertNotIn("Kish", remedies(run(*BASE)))
        self.assertNotIn("Kish", remedies(run(*BASE, "--trials", "1")))
        self.assertIn("Kish", remedies(run(*BASE, "--trials", "20")))

    def test_the_screening_remedy_points_at_something_that_can_do_the_job(self):
        """Regression: it used to name tools/neff.py, which takes this repo's
        JSONL corpus and cannot be fed an arbitrary set of return series. The
        page's paste-a-table half can. Naming the wrong instrument is the same
        failure as inviting a number."""
        r = remedies(run(*BASE, "--trials", "20"))
        self.assertIn("docs/index.html", r)
        self.assertNotIn("tools/neff.py", r)

    def test_an_already_discounted_count_is_not_told_to_discount_again(self):
        r = remedies(run(*BASE, "--trials", "20", "--effective-trials", "4"))
        self.assertIn("再降只能靠真的少试", r)
        self.assertNotIn("Kish", r)


class Reporting(unittest.TestCase):

    def test_undeclared_screening_is_stated_rather_than_omitted(self):
        out = run(*BASE)
        self.assertIn("变体筛选校正", out)
        self.assertIn("未申报", out)

    def test_declaring_trials_moves_the_requirement_on_screen(self):
        plain, screened = run(*BASE), run(*BASE, "--trials", "20")
        self.assertIn("48 个月", plain)
        self.assertIn("112 个月", screened)
        self.assertIn("2.00  →  3.05", screened)

    def test_bad_dates_exit_nonzero_rather_than_printing_a_number(self):
        out = subprocess.run([sys.executable, CLI, "--cutoff", "2024-13",
                              "--start", "2020-01", "--end", "2025-06"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 1)
        self.assertEqual(out.stdout.strip(), "")

    def test_impossible_trial_counts_exit_nonzero(self):
        out = subprocess.run([sys.executable, CLI, *BASE,
                              "--trials", "5", "--effective-trials", "9"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main()
