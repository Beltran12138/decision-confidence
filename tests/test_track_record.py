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
from track_record import effective_records, track_record  # noqa: E402


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


class Overlap(unittest.TestCase):
    """effective_records: identical series collapse, unmeasured pairs buy nothing."""

    def days(self, n):
        return ["2026-09-%02d" % (i + 1) for i in range(n)]

    def test_identical_series_count_once(self):
        d = self.days(25)
        xs = {k: float((i * 7) % 11) for i, k in enumerate(d)}
        o = effective_records({"a": xs, "b": dict(xs)})
        self.assertAlmostEqual(o.n_eff, 1.0)          # 2^2 / (2 + 2*1)
        self.assertLess(o.n_eff_floor, 1.2)

    def test_unmeasured_pair_buys_no_discount(self):
        # Here a lower n_eff shrinks the screening charge, so an unmeasured
        # pair is charged as independent: n_eff stays at n.
        a = {k: float(i) for i, k in enumerate(self.days(25))}
        b = {"2026-10-01": 1.0}
        o = effective_records({"a": a, "b": b})
        self.assertEqual(len(o.unmeasured), 1)
        self.assertAlmostEqual(o.n_eff, 2.0)
        self.assertAlmostEqual(o.n_eff_floor, 2.0)

    def test_floor_correction_raises_n_eff_on_noise(self):
        import random
        rng = random.Random(7)
        d = self.days(30)
        series = {f"w{j}": {k: rng.gauss(0, 1) for k in d} for j in range(10)}
        o = effective_records(series)
        # Independent noise: raw |rho| still charges ~0.15 per pair.
        self.assertLess(o.n_eff, o.n_eff_floor)
        self.assertGreater(o.n_eff_floor, 7.0)

    def test_mirror_images_are_two_chances(self):
        # Long and short the same thing: one of them tops the board either way.
        d = self.days(25)
        xs = {k: float((i * 7) % 11) for i, k in enumerate(d)}
        o = effective_records({"long": xs, "short": {k: -v for k, v in xs.items()}})
        self.assertAlmostEqual(o.n_eff, 2.0)
        self.assertAlmostEqual(o.mean_abs_rho, 1.0)

    def test_universe_extrapolation_agrees_at_n(self):
        d = self.days(25)
        base = {k: float(i % 5) for i, k in enumerate(d)}
        o = effective_records({"a": base, "b": {k: v + (i % 3) for i, (k, v)
                                                in enumerate(base.items())}},
                              universe=2)
        self.assertAlmostEqual(o.universe_n_eff, o.n_eff_floor)

    def test_universe_smaller_than_sample_rejected(self):
        d = {k: float(i) for i, k in enumerate(self.days(25))}
        with self.assertRaises(ValueError):
            effective_records({"a": d, "b": d, "c": d}, universe=2)


class HyperliquidAdapter(unittest.TestCase):

    def test_deposit_is_not_a_return(self):
        from adapters.hyperliquid import daily_returns
        day = 86_400_000
        t0 = 1_790_000_000_000 - 1_790_000_000_000 % day + 3_600_000
        payload = [["perpMonth", {
            # Account value doubles on day 2 from a deposit; PnL moves by 10.
            "accountValueHistory": [[t0, "1000"], [t0 + day, "2010"], [t0 + 2 * day, "2030"]],
            "pnlHistory": [[t0, "0"], [t0 + day, "10"], [t0 + 2 * day, "30"]],
        }]]
        r = list(daily_returns(payload).values())
        self.assertAlmostEqual(r[0], 10 / 1000)       # not (2010-1000)/1000
        self.assertAlmostEqual(r[1], 20 / 2010)

    def test_missing_window_is_empty_not_an_error(self):
        from adapters.hyperliquid import daily_returns
        self.assertEqual(daily_returns([["day", {}]]), {})
