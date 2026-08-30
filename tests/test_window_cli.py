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

**Assertions go through message keys, not through literal strings.** The
output is translated now, and a suite pinned to one language would silently
stop covering the other — which is the same failure as not testing ``tools/``
at all, one level up.

    python -m unittest discover tests
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
CLI = os.path.join(ROOT, "tools", "window.py")

from messages import LANGS, text  # noqa: E402


def run(*args, lang="en"):
    out = subprocess.run([sys.executable, CLI, "--lang", lang, *args],
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 0, out.stderr
    return out.stdout


CJK = r"　-〿一-鿿＀-￯"


def flat(s):
    """Undo wrapping before comparing.

    The library returns one sentence; the CLI wraps it and indents the
    continuations. Asserting the unwrapped string against wrapped output fails
    for a reason that has nothing to do with what is being tested.

    Collapsing whitespace is not enough on its own: a line break between two
    Chinese characters carries no space in the original, so turning it into one
    leaves ``少试， 不能`` where the source says ``少试，不能``. English keeps
    its spaces; CJK-to-CJK ones are removed.
    """
    s = re.sub(r"\s+", " ", s).strip()
    return re.sub(r"(?<=[" + CJK + r"]) (?=[" + CJK + r"])", "", s)


def remedies(text_out, lang="en"):
    """Just the "what to do about it" block."""
    head = text("cli.section_remedies", lang)
    tail = text("cli.section_sweep", lang)
    body = text_out.split(head, 1)
    return body[1].split(tail, 1)[0] if len(body) > 1 else ""


BASE = ("--cutoff", "2024-10", "--start", "2020-01", "--end", "2025-06")
CLEAN = ("--cutoff", "2015-01", "--start", "2020-01", "--end", "2025-06")
NOHOLD = ("--cutoff", "2026-01", "--start", "2020-01", "--end", "2025-06")


class RemedyDispatch(unittest.TestCase):
    """Each case runs in every language: a dispatch bug is language-independent,
    but a *translation* that drops a branch would only show up in its own."""

    def test_no_remedy_ever_prints_an_inverted_date_range(self):
        """Bug 1. The open-book span is empty when the cutoff precedes the start."""
        for lang in LANGS:
            for args in (CLEAN, CLEAN + ("--trials", "20")):
                r = remedies(run(*args, lang=lang), lang)
                self.assertNotIn("2015-01", r, lang)
                self.assertNotIn(flat(text("remedy.clean_only", lang,
                                      start="2020-01", open_end="2015-01")), flat(r), lang)

    def test_switching_models_is_not_offered_when_it_cannot_work(self):
        """Bug 2. No cutoff supplies months the whole backtest does not contain."""
        for lang in LANGS:
            r = remedies(run(*BASE, "--trials", "20", lang=lang), lang)  # needs 112 of 66
            self.assertIn(flat(text("remedy.earlier_model_insufficient", lang,
                               total_months=66, months_required=112)), flat(r), lang)

    def test_switching_models_is_offered_when_it_does_work(self):
        """The falsifier for the test above — the branch must be reachable."""
        for lang in LANGS:
            r = remedies(run(*BASE, lang=lang), lang)                     # needs 48 of 66
            self.assertIn(flat(text("remedy.earlier_model", lang, latest="2021-06")), flat(r), lang)
            self.assertNotIn(flat(text("remedy.earlier_model_insufficient", lang,
                                  total_months=66, months_required=48)), flat(r), lang)

    def test_reporting_the_clean_segment_needs_a_clean_segment(self):
        """Bug 3. Nothing is out of sample, so there is no clean segment to report."""
        for lang in LANGS:
            want = flat(text("remedy.clean_only", lang,
                             start="2020-01", open_end="2024-10"))
            self.assertNotIn(want, flat(remedies(run(*NOHOLD, lang=lang), lang)), lang)
            self.assertIn(want, flat(remedies(run(*BASE, lang=lang), lang)), lang)

    def test_an_empty_sample_is_never_said_to_demonstrate_a_sharpe(self):
        """Bug 4. ``SR inf`` reads as the opposite of what it means."""
        for lang in LANGS:
            for args in (NOHOLD, NOHOLD + ("--trials", "30")):
                out = run(*args, lang=lang)
                # The word boundary is load-bearing and was once lost to an
                # escaping accident: English contains "inference" and "in
                # full", so a plain substring check fails on correct output —
                # while a mangled boundary passes on any output at all.
                self.assertIsNone(re.search(r"\binf\b", out),
                                  "bare 'inf' in %s output" % lang)
                self.assertIsNone(re.search(r"\bnan\b", out),
                                  "bare 'nan' in %s output" % lang)

    def test_the_screening_remedy_appears_only_when_screening_costs_something(self):
        for lang in LANGS:
            want = flat(text("remedy.measure_overlap", lang, trials=20))
            self.assertNotIn(want, flat(remedies(run(*BASE, lang=lang), lang)), lang)
            self.assertNotIn(want, flat(remedies(run(*BASE, "--trials", "1",
                                                     lang=lang), lang)), lang)
            self.assertIn(want, flat(remedies(run(*BASE, "--trials", "20",
                                                  lang=lang), lang)), lang)

    def test_the_screening_remedy_points_at_something_that_can_do_the_job(self):
        """Regression: it used to name tools/neff.py, which takes this repo's
        JSONL corpus and cannot be fed an arbitrary set of return series. The
        page's paste-a-table half can. Naming the wrong instrument is the same
        failure as inviting a number."""
        for lang in LANGS:
            r = remedies(run(*BASE, "--trials", "20", lang=lang), lang)
            self.assertIn("docs/index.html", r, lang)
            self.assertNotIn("tools/neff.py", r, lang)

    def test_an_already_discounted_count_is_not_told_to_discount_again(self):
        for lang in LANGS:
            r = remedies(run(*BASE, "--trials", "20", "--effective-trials", "4",
                             lang=lang), lang)
            self.assertIn(flat(text("remedy.already_discounted", lang, n_eff=4)), flat(r), lang)
            self.assertNotIn(flat(text("remedy.measure_overlap", lang, trials=20)), flat(r), lang)


class Reporting(unittest.TestCase):

    def test_undeclared_screening_is_stated_rather_than_omitted(self):
        for lang in LANGS:
            out = run(*BASE, lang=lang)
            self.assertIn(flat(text("cli.section_selection", lang)), flat(out), lang)
            self.assertIn(flat(text("undeclared_selection", lang)), flat(out.replace("\n  ", " ")), lang)

    def test_declaring_trials_moves_the_requirement_on_screen(self):
        for lang in LANGS:
            plain, screened = run(*BASE, lang=lang), run(*BASE, "--trials", "20", lang=lang)
            self.assertIn("48", plain, lang)
            self.assertIn("112", screened, lang)
            self.assertIn("3.05", screened, lang)

    def test_english_is_the_default(self):
        """The reason this whole layer exists: the README is English and the
        first run used to answer in Chinese."""
        out = subprocess.run([sys.executable, CLI, *BASE],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stderr)
        han = [c for c in out.stdout if "一" <= c <= "鿿"]
        self.assertFalse(han, "Chinese in default output: %r" % han[:20])

    def test_chinese_is_reachable_and_carries_the_same_numbers(self):
        en, zh = run(*BASE, "--trials", "20", lang="en"), run(*BASE, "--trials", "20", lang="zh")
        self.assertTrue([c for c in zh if "一" <= c <= "鿿"])
        for number in ("66", "58", "87.9%", "112", "3.05", "2.3"):
            self.assertIn(number, en, number)
            self.assertIn(number, zh, number)

    def test_an_unknown_language_falls_back_rather_than_erroring(self):
        """argparse rejects it, which is the right answer for a CLI flag —
        the library's silent fallback is for programmatic callers."""
        out = subprocess.run([sys.executable, CLI, *BASE, "--lang", "tlh"],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")

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
