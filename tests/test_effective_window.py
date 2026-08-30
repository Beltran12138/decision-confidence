"""Regression tests for the time axis.

Stdlib ``unittest`` only — no test-runner dependency.

    python -m unittest discover tests

Assertions are anchored on meaning rather than on the arithmetic that produced
them, for the reason recorded in ``tests/test_decision_confidence.py``: a test
that recomputes the implementation agrees with it by construction. Where a
number is asserted, it is one that can be checked by counting on a calendar.
"""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from decision_confidence import (  # noqa: E402
    Contradiction,
    build_report,
    observe_from_raw,
    synthesize_confidence,
)
from effective_window import (  # noqa: E402
    effective_window,
    months_for_power,
)


def obs(source_id, score, construct=None):
    o = observe_from_raw(source_id, "SUBJ", {"score": score})
    o.construct = construct
    return o


class MonthCounting(unittest.TestCase):
    """The split itself. Every number here is countable by hand."""

    def test_a_range_is_inclusive_of_both_endpoints(self):
        # Jan through Jun of one year is six months, not five.
        w = effective_window("2019-01", "2020-01", "2020-06")
        self.assertEqual(w.total_months, 6)

    def test_the_cutoff_month_itself_counts_as_seen(self):
        """A model whose knowledge ends in October has read October.

        This is the whole of the one-month ambiguity documented in
        ``test_the_one_month_of_ambiguity_is_worth_naming``; fixing the
        convention here is what stops it being silent.
        """
        w = effective_window("2020-03", "2020-01", "2020-06")
        self.assertEqual(w.open_book_months, 3)   # Jan, Feb, Mar
        self.assertEqual(w.effective_months, 3)   # Apr, May, Jun

    def test_a_cutoff_before_the_backtest_leaves_it_entirely_clean(self):
        w = effective_window("2015-12", "2020-01", "2020-06")
        self.assertEqual(w.open_book_months, 0)
        self.assertEqual(w.effective_months, w.total_months)

    def test_a_cutoff_after_the_backtest_leaves_nothing(self):
        w = effective_window("2030-01", "2020-01", "2020-06")
        self.assertEqual(w.effective_months, 0)
        self.assertEqual(w.open_book_share, 1.0)

    def test_the_two_halves_always_sum_to_the_whole(self):
        """No month is dropped or double-counted, whatever the cutoff."""
        for cutoff in ("2018-06", "2020-01", "2022-07", "2025-06", "2028-01"):
            w = effective_window(cutoff, "2020-01", "2025-06")
            self.assertEqual(
                w.open_book_months + w.effective_months, w.total_months,
                f"months lost at cutoff {cutoff}",
            )


class PowerRequirement(unittest.TestCase):
    """How long the clean remainder has to be to reject anything."""

    def test_a_sharpe_of_one_needs_four_clean_years(self):
        self.assertEqual(months_for_power(target_sharpe=1.0, t_threshold=2.0), 48)

    def test_halving_the_sharpe_quadruples_the_requirement(self):
        """The quadratic is the surprising part, so it is asserted directly."""
        strong = months_for_power(target_sharpe=1.0)
        weak = months_for_power(target_sharpe=0.5)
        self.assertEqual(weak, 4 * strong)

    def test_a_stricter_t_bar_costs_more_sample(self):
        lenient = months_for_power(target_sharpe=1.0, t_threshold=2.0)
        strict = months_for_power(target_sharpe=1.0, t_threshold=3.0)
        self.assertGreater(strict, lenient)

    def test_a_nonpositive_sharpe_is_refused_rather_than_returning_a_number(self):
        with self.assertRaises(ValueError):
            months_for_power(target_sharpe=0.0)


class Verdicts(unittest.TestCase):

    def test_no_clean_months_reads_as_no_holdout(self):
        w = effective_window("2026-01", "2020-01", "2025-06")
        self.assertEqual(w.verdict, "no_holdout")

    def test_some_clean_months_but_too_few_reads_as_underpowered(self):
        w = effective_window("2024-10", "2020-01", "2025-06", target_sharpe=1.0)
        self.assertEqual(w.verdict, "underpowered")

    def test_enough_clean_months_reads_as_sufficient(self):
        w = effective_window("2019-12", "2020-01", "2025-06", target_sharpe=1.0)
        self.assertEqual(w.verdict, "sufficient")

    def test_sufficient_is_reachable_so_the_module_is_falsifiable(self):
        """A checker that can only ever say "not enough" is not a checker.

        Same guard as ``test_single_construct_still_produces_a_composite`` in
        the sibling suite: refusal dressed as judgement is unfalsifiable, so at
        least one input must be able to pass.
        """
        verdicts = {
            effective_window(c, "2020-01", "2025-06").verdict
            for c in ("2019-12", "2024-10", "2026-01")
        }
        self.assertEqual(verdicts, {"sufficient", "underpowered", "no_holdout"})

    def test_the_limits_travel_with_every_result(self):
        """Both caveats are printed with the number, not left in a docstring."""
        for cutoff in ("2019-12", "2024-10", "2026-01"):
            note = effective_window(cutoff, "2020-01", "2025-06").note
            self.assertIn("i.i.d", note)          # autocorrelation caveat
            self.assertIn("多重检验", note)        # strategy-screening caveat


class TheWorkedExample(unittest.TestCase):
    """The configuration used in the 2026-08-29 talk, recomputed here.

    It is a test rather than a comment because the talk quoted a share, and a
    quoted share whose convention is unstated is precisely what this repo
    exists to catch.
    """

    def setUp(self):
        self.w = effective_window(
            "2024-10", "2020-01", "2025-06", target_sharpe=1.0, t_threshold=2.0,
        )

    def test_the_backtest_is_five_and_a_half_years(self):
        self.assertEqual(self.w.total_months, 66)

    def test_most_of_it_is_open_book(self):
        # 2020-01 .. 2024-10 inclusive = 4 full years + 10 months.
        self.assertEqual(self.w.open_book_months, 58)
        self.assertGreater(self.w.open_book_share, 0.85)

    def test_the_one_month_of_ambiguity_is_worth_naming(self):
        """Whether the cutoff month is "seen" moves the headline share by a point.

        Counting the cutoff month gives 58/66 = 87.9%; excluding it gives
        57/66 = 86.4%. Both are defensible readings of "knowledge cutoff:
        October 2024", and nobody quoting either one says which they used.
        The convention is fixed in code — inclusive — so the number cannot
        drift between tellings.
        """
        inclusive = effective_window("2024-10", "2020-01", "2025-06")
        exclusive = effective_window("2024-09", "2020-01", "2025-06")
        self.assertEqual(inclusive.open_book_months, 58)
        self.assertEqual(exclusive.open_book_months, 57)
        self.assertAlmostEqual(exclusive.open_book_share, 0.864, places=3)

    def test_the_clean_remainder_is_a_sixth_of_what_an_inference_needs(self):
        """The finding the share alone does not deliver.

        "86% was open book" invites the reply "fine, I will trust the other
        14%". The other 14% is eight months against a 48-month requirement.
        """
        self.assertEqual(self.w.effective_months, 8)
        self.assertEqual(self.w.months_required, 48)
        self.assertLess(self.w.power_ratio, 0.2)
        self.assertEqual(self.w.verdict, "underpowered")


class BadInput(unittest.TestCase):
    """Caller mistakes are refused, not absorbed into a plausible number."""

    def test_an_inverted_range_is_refused(self):
        with self.assertRaises(ValueError):
            effective_window("2024-10", "2025-06", "2020-01")

    def test_an_unparseable_date_is_refused(self):
        for bad in ("2024", "2024/10", "twenty-24-10", "2024-13", ""):
            with self.assertRaises(ValueError):
                effective_window(bad, "2020-01", "2025-06")

    def test_a_non_string_date_is_refused(self):
        with self.assertRaises(ValueError):
            effective_window(202410, "2020-01", "2025-06")


class ReportIntegration(unittest.TestCase):
    """How the second axis meets the first — and where it stops."""

    def good_sources(self):
        return [obs("a", 20, "tradability"), obs("b", 24, "tradability"),
                obs("c", 22, "tradability")]

    def test_omitting_the_window_changes_nothing(self):
        """Absent is unknown, not clean. Every pre-existing caller is untouched."""
        without = build_report("SUBJ", self.good_sources())
        self.assertIsNone(without.window)
        self.assertEqual(without.confidence, "high")

    def test_a_clean_window_does_not_by_itself_raise_confidence(self):
        w = effective_window("2015-01", "2020-01", "2025-06")
        rep = build_report("SUBJ", self.good_sources(), window=w)
        self.assertEqual(rep.window.verdict, "sufficient")
        self.assertEqual(rep.confidence, "high")   # same as without a window

    def test_a_failed_window_floors_confidence_despite_perfect_agreement(self):
        """No number of agreeing sources repairs a period the model has read."""
        many = [obs(f"s{i}", 20 + i, "tradability") for i in range(10)]
        clean = build_report("SUBJ", many)
        self.assertEqual(clean.confidence, "high")

        w = effective_window("2026-01", "2020-01", "2025-06")
        contaminated = build_report("SUBJ", many, window=w)
        self.assertEqual(contaminated.confidence, "low")

    def test_underpowered_floors_confidence_too(self):
        w = effective_window("2024-10", "2020-01", "2025-06")
        rep = build_report("SUBJ", self.good_sources(), window=w)
        self.assertEqual(rep.confidence, "low")

    def test_the_window_does_not_move_the_verdict(self):
        """Verdict is about the subject's risk; how a backtest was cut is not."""
        w = effective_window("2026-01", "2020-01", "2025-06")
        without = build_report("SUBJ", self.good_sources())
        with_win = build_report("SUBJ", self.good_sources(), window=w)
        self.assertEqual(with_win.verdict, without.verdict)
        self.assertEqual(with_win.composite, without.composite)

    def test_the_window_is_not_filed_as_a_contradiction(self):
        """It disagrees with no source, so it does not belong in that list."""
        w = effective_window("2026-01", "2020-01", "2025-06")
        rep = build_report("SUBJ", self.good_sources(), window=w)
        kinds = {c.kind for c in rep.contradictions}
        self.assertNotIn("window", kinds)
        self.assertNotIn("knowledge_window", kinds)

    def test_the_split_is_recorded_in_the_audit_trail(self):
        w = effective_window("2024-10", "2020-01", "2025-06")
        rep = build_report("SUBJ", self.good_sources(), window=w)
        steps = [e for e in rep.audit if e.step == "window"]
        self.assertEqual(len(steps), 1)
        self.assertIn("underpowered", steps[0].detail)

    def test_the_report_still_serialises(self):
        w = effective_window("2024-10", "2020-01", "2025-06")
        d = build_report("SUBJ", self.good_sources(), window=w).to_dict()
        self.assertEqual(d["window"]["verdict"], "underpowered")

    def test_confidence_can_be_capped_without_any_contradiction(self):
        """The cap is independent of the source axis, and reachable on its own."""
        w = effective_window("2026-01", "2020-01", "2025-06")
        self.assertEqual(synthesize_confidence(5, [], None, w), "low")
        self.assertEqual(synthesize_confidence(5, [], None, None), "high")

    def test_a_sufficient_window_leaves_the_source_axis_in_charge(self):
        """A clean backtest does not launder a contradiction between sources."""
        w = effective_window("2015-01", "2020-01", "2025-06")
        clash = [Contradiction(sources=["a", "b"], kind="polarity",
                               detail="", severity="high")]
        self.assertEqual(synthesize_confidence(5, clash, None, w), "low")


if __name__ == "__main__":
    unittest.main()
