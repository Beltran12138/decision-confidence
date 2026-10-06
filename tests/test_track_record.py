"""Track records: two readings split at the pick date.

Expected numbers are hand-computed literals, not calls back into
``months_for_power`` — a test that recomputes the answer with the code under
test agrees with it by construction.

    python -m unittest discover tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
CLI = os.path.join(ROOT, "tools", "record.py")

from messages import LANGS, text  # noqa: E402
from textcompare import flat  # noqa: E402
from track_record import track_record  # noqa: E402


class Arithmetic(unittest.TestCase):

    def test_leaderboard_example(self):
        # SR 3 at t 2: (2/3)^2 * 12 = 5.33 -> 6 months.
        # 4800 trials: alpha 0.02275 / 4800 -> t ~ 4.43; (4.43/3)^2 * 12 = 26.2 -> 27.
        r = track_record("2026-03", "2026-08", target_sharpe=3, trials=4800)
        self.assertEqual(r.total_months, 6.0)
        self.assertEqual(r.as_shown.selection.months_base, 6)
        self.assertEqual(r.as_shown.months_required, 27)
        self.assertAlmostEqual(r.as_shown.t_bar, 4.43, places=2)
        self.assertEqual(r.as_shown.verdict, "underpowered")
        self.assertIsNone(r.since_picked)

    def test_undeclared_trials_is_plain_bar_and_said_so(self):
        r = track_record("2026-03", "2026-08", target_sharpe=3)
        self.assertEqual(r.as_shown.months_required, 6)
        self.assertEqual(r.as_shown.verdict, "sufficient")
        self.assertIn(text("record.undeclared_universe", "en"), r.note)

    def test_since_picked_carries_no_screening_charge(self):
        r = track_record("2026-01", "2026-12", picked="2026-06",
                         target_sharpe=2, trials=4800)
        self.assertEqual(r.as_shown.months, 6.0)      # Jan..Jun, pick month seen
        self.assertEqual(r.since_picked.months, 6.0)  # Jul..Dec
        self.assertEqual(r.as_shown.months_required, 59)
        self.assertEqual(r.since_picked.months_required, 12)
        self.assertIsNone(r.since_picked.selection)
        self.assertEqual(r.since_picked.t_bar, 2.0)

    def test_pick_on_last_day_leaves_nothing_out_of_sample(self):
        r = track_record("2026-03", "2026-08", picked="2026-08")
        self.assertEqual(r.since_picked.months, 0.0)
        self.assertEqual(r.since_picked.verdict, "no_holdout")

    def test_day_precision_when_every_date_has_a_day(self):
        # 2026-03-01..2026-04-14 inclusive = 45 days = 1.48 months.
        r = track_record("2026-03-01", "2026-04-14")
        self.assertEqual(r.precision, "day")
        self.assertEqual(r.total_months, 1.5)

    def test_mixed_precision_falls_back_to_months(self):
        r = track_record("2026-03-01", "2026-04-14", picked="2026-03")
        self.assertEqual(r.precision, "month")
        self.assertEqual(r.total_months, 2.0)

    def test_no_combined_verdict(self):
        r = track_record("2020-01", "2026-12", picked="2026-06", target_sharpe=1)
        self.assertEqual(r.as_shown.verdict, "sufficient")
        self.assertEqual(r.since_picked.verdict, "underpowered")
        self.assertFalse(hasattr(r, "verdict"))


class Rejections(unittest.TestCase):

    def test_bad_inputs(self):
        for kw in (dict(start="2026-08", end="2026-03"),
                   dict(start="2026-03", end="2026-08", picked="2026-09"),
                   dict(start="2026-03", end="2026-08", picked="2026-02"),
                   dict(start="2026-02-30", end="2026-08-01"),
                   dict(start="2026-13", end="2026-14"),
                   dict(start="2026-03", end="2026-08", effective_trials=3)):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                track_record(**kw)


class Cli(unittest.TestCase):

    def run_cli(self, *args):
        p = subprocess.run([sys.executable, CLI, *args], capture_output=True,
                           text=True, encoding="utf-8")
        return p.returncode, p.stdout, p.stderr

    def test_both_languages_print_limits_and_no_pick(self):
        for lang in LANGS:
            with self.subTest(lang=lang):
                rc, out, _ = self.run_cli("--start", "2026-03", "--end", "2026-08",
                                          "--sharpe", "3", "--trials", "4800",
                                          "--lang", lang)
                self.assertEqual(rc, 0)
                self.assertIn(flat(text("record.limits", lang)), flat(out))
                self.assertIn(flat(text("record.no_pick", lang)), flat(out))
                self.assertIn("27", out)

    def test_pick_prints_both_readings_and_refuses_to_combine(self):
        rc, out, _ = self.run_cli("--start", "2026-01", "--end", "2026-12",
                                  "--picked", "2026-06", "--sharpe", "2")
        self.assertEqual(rc, 0)
        self.assertIn(text("record.cli.since_picked", "en"), out)
        self.assertIn(flat(text("record.cli.no_combined", "en")), flat(out))

    def test_bad_input_exits_1(self):
        rc, _, err = self.run_cli("--start", "2026-08", "--end", "2026-03")
        self.assertEqual(rc, 1)
        self.assertTrue(err.strip())


if __name__ == "__main__":
    unittest.main()
