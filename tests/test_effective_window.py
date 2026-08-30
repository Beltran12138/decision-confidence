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
from statistics import NormalDist

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
    selection_penalty,
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
        """The caveats are printed with the number, not left in a docstring."""
        for cutoff in ("2019-12", "2024-10", "2026-01"):
            note = effective_window(cutoff, "2020-01", "2025-06").note
            self.assertIn("i.i.d", note)           # autocorrelation caveat
            self.assertIn("Bonferroni", note)      # independence-of-trials caveat


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


class SelectionEffect(unittest.TestCase):
    """The second way a clean remainder gets spent: screening variants."""

    RANGE = ("2024-10", "2020-01", "2025-06")

    def test_one_trial_is_an_exact_identity(self):
        """Declaring a single attempt must not move a single month.

        Regression for a real bug: α is derived from ``t_base`` and inverted
        back, which returns 2.0 to within ~1e-9 — and ``ceil`` turns that dust
        into a whole extra month (48 → 49). The identity is short-circuited,
        and this test is why.
        """
        plain = effective_window(*self.RANGE)
        one = effective_window(*self.RANGE, trials=1)
        self.assertEqual(one.months_required, plain.months_required)
        self.assertEqual(one.months_required, 48)
        self.assertEqual(one.selection.t_adjusted, one.selection.t_base)

    def test_more_trials_never_lowers_the_bar(self):
        prev_t, prev_m = 0.0, 0
        for n in (1, 2, 5, 10, 20, 50, 100):
            w = effective_window(*self.RANGE, trials=n)
            self.assertGreaterEqual(w.selection.t_adjusted, prev_t)
            self.assertGreaterEqual(w.months_required, prev_m)
            prev_t, prev_m = w.selection.t_adjusted, w.months_required

    def test_the_bonferroni_arithmetic_is_checkable_by_hand(self):
        """t = 2.0 implies α = 0.02275; over ten trials that is 0.002275.

        Asserted against the normal quantile of the divided α rather than
        against the implementation's own output, so the test does not agree
        with the code by construction.
        """
        w = effective_window(*self.RANGE, trials=10)
        expected = NormalDist().inv_cdf(1 - (1 - NormalDist().cdf(2.0)) / 10)
        self.assertAlmostEqual(w.selection.t_adjusted, expected, places=9)
        self.assertAlmostEqual(w.selection.t_adjusted, 2.8373, places=3)
        self.assertEqual(w.months_required, 97)

    def test_ten_variants_roughly_doubles_the_sample_needed(self):
        """The headline the count alone does not deliver."""
        one = effective_window(*self.RANGE, trials=1).months_required
        ten = effective_window(*self.RANGE, trials=10).months_required
        self.assertEqual(one, 48)
        self.assertEqual(ten, 97)
        self.assertGreater(ten / one, 2.0)

    def test_correlated_variants_are_discounted_like_sources_are(self):
        """Fifty settings of one strategy are not fifty independent tests."""
        naive = effective_window(*self.RANGE, trials=50)
        measured = effective_window(*self.RANGE, trials=50, effective_trials=5)
        self.assertLess(measured.selection.t_adjusted, naive.selection.t_adjusted)
        self.assertLess(measured.months_required, naive.months_required)
        # ...and the discounted count lands exactly where five trials would.
        five = effective_window(*self.RANGE, trials=5)
        self.assertEqual(measured.months_required, five.months_required)

    def test_a_long_clean_window_can_still_fail_on_screening(self):
        """The whole point: length alone does not settle it.

        Sixty-six months entirely after the cutoff passes on length and fails
        once twenty variants are declared.
        """
        clean = effective_window("2015-01", "2020-01", "2025-06")
        self.assertEqual(clean.verdict, "sufficient")
        screened = effective_window("2015-01", "2020-01", "2025-06", trials=20)
        self.assertEqual(screened.effective_months, clean.effective_months)
        self.assertEqual(screened.verdict, "underpowered")

    def test_screening_is_still_survivable_so_the_penalty_is_falsifiable(self):
        """A penalty nothing can clear is a refusal, not a measurement."""
        w = effective_window("2015-01", "2010-01", "2025-06", trials=20)
        self.assertGreater(w.effective_months, w.months_required)
        self.assertEqual(w.verdict, "sufficient")

    def test_undeclared_screening_is_named_rather_than_assumed_away(self):
        undeclared = effective_window(*self.RANGE)
        self.assertIsNone(undeclared.selection)
        self.assertIn("未申报", undeclared.note)
        declared = effective_window(*self.RANGE, trials=10)
        self.assertNotIn("未申报", declared.note)
        self.assertIn("10", declared.note)

    def test_declaring_one_trial_is_recorded_as_a_claim_not_a_default(self):
        note = effective_window(*self.RANGE, trials=1).note
        self.assertIn("主张", note)

    def test_the_summary_line_names_the_corrected_bar(self):
        s = effective_window(*self.RANGE, trials=10).summary()
        self.assertIn("2.84", s)
        self.assertIn("10 个变体", s)

    def test_impossible_trial_counts_are_refused(self):
        with self.assertRaises(ValueError):          # cannot try zero times
            effective_window(*self.RANGE, trials=0)
        with self.assertRaises(ValueError):          # more independent than numerous
            effective_window(*self.RANGE, trials=5, effective_trials=9)
        with self.assertRaises(ValueError):          # fewer than one independent test
            effective_window(*self.RANGE, trials=5, effective_trials=0.5)
        with self.assertRaises(ValueError):          # a discount on nothing
            effective_window(*self.RANGE, effective_trials=3)

    def test_the_penalty_is_reachable_on_its_own(self):
        p = selection_penalty(20, t_base=2.0, target_sharpe=1.0)
        self.assertEqual(p.months_base, 48)
        self.assertEqual(p.months_adjusted, 112)
        self.assertEqual(p.effective_trials, 20)

    def test_the_report_carries_the_penalty_through(self):
        w = effective_window("2015-01", "2020-01", "2025-06", trials=20)
        d = build_report("SUBJ", [obs("a", 20, "tradability"),
                                  obs("b", 24, "tradability")], window=w).to_dict()
        self.assertEqual(d["window"]["selection"]["trials"], 20)
        self.assertEqual(d["window"]["verdict"], "underpowered")


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
