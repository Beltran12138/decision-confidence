"""Tests for where the trial count came from.

The arithmetic these guard is trivial — a product and a set size. What they
actually guard is the claim the module makes: that a derived count and a
declared one are distinguishable downstream. A test suite that only checked the
integers would pass on a version where provenance never reached the report,
which is the version this module exists to replace.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import trial_count as tc
from effective_window import effective_window, selection_penalty


class TestConstructors(unittest.TestCase):
    def test_grid_multiplies_and_shows_its_working(self):
        g = tc.from_grid(configs=6, windows=4, scenarios=2)
        self.assertEqual(g.count, 48)
        self.assertEqual(g.provenance, "grid")
        # Every dimension must be visible, or a reader cannot tell which were
        # counted — the derivation is the whole point of not taking an integer.
        for name in ("configs", "windows", "scenarios"):
            self.assertIn(name, g.derivation)
        self.assertIn("48", g.derivation)

    def test_grid_rejects_empty_and_nonsense(self):
        with self.assertRaises(ValueError):
            tc.from_grid()
        with self.assertRaises(ValueError):
            tc.from_grid(configs=0)
        with self.assertRaises(ValueError):
            tc.from_grid(configs=2.5)
        # bool is an int subclass; counting True as one dimension is a bug
        with self.assertRaises(ValueError):
            tc.from_grid(configs=True)

    def test_runs_counts_distinct_configurations_not_records(self):
        runs = [{"a": a, "b": b, "seed": s}
                for a in (1, 2, 3) for b in (10, 20) for s in (1, 2)]
        r = tc.from_runs(runs, fields=["a", "b"])
        self.assertEqual(len(runs), 12)
        self.assertEqual(r.count, 6)          # seeds are not separate trials here
        self.assertEqual(r.evidence["records"], 12)

    def test_runs_requires_the_caller_to_say_what_one_trial_is(self):
        runs = [{"a": 1}]
        with self.assertRaises(ValueError):
            tc.from_runs(runs)                                     # neither
        with self.assertRaises(ValueError):
            tc.from_runs(runs, fields=["a"], key=lambda r: r["a"])  # both

    def test_empty_log_is_an_error_not_a_count_of_zero(self):
        # The whole family-1 failure in one line: an absent record must not
        # arrive downstream as the number zero.
        with self.assertRaises(ValueError):
            tc.from_runs([], fields=["a"])

    def test_incomplete_records_inflate_rather_than_shrink(self):
        runs = [{"a": 1, "b": 1}, {"a": 1, "b": 1}, {"a": 1}]
        r = tc.from_runs(runs, fields=["a", "b"])
        # Two identical complete records collapse to one; the incomplete one is
        # kept as distinct. Dropping it would report 1 — fewer trials than were
        # actually run, which is the wrong direction to be wrong in.
        self.assertEqual(r.count, 2)
        self.assertEqual(r.evidence["incomplete_records"], 1)

    def test_coverage_replaces_the_generic_warning(self):
        runs = [{"a": 1}]
        generic = tc.from_runs(runs, fields=["a"])
        stated = tc.from_runs(runs, fields=["a"], coverage="MLflow exp 4 from 2026-07")
        self.assertNotEqual(generic.blind_to, stated.blind_to)
        self.assertIn("MLflow exp 4 from 2026-07", stated.blind_to)

    def test_every_provenance_names_a_blind_spot(self):
        # An empty blind_to would be a claim of completeness. None of the three
        # methods can make that claim, so none of them may print an empty list.
        for t in (tc.declared(3),
                  tc.from_grid(x=3),
                  tc.from_runs([{"a": 1}], fields=["a"])):
            self.assertTrue(t.blind_to, f"{t.provenance} claimed completeness")

    def test_declared_is_not_checkable_and_the_others_are(self):
        self.assertFalse(tc.declared(20).checkable)
        self.assertTrue(tc.from_grid(x=20).checkable)
        self.assertTrue(tc.from_runs([{"a": 1}], fields=["a"]).checkable)

    def test_bad_provenance_rejected(self):
        with self.assertRaises(ValueError):
            tc.TrialCount(count=1, provenance="vibes", derivation="")
        with self.assertRaises(ValueError):
            tc.TrialCount(count=0, provenance="grid", derivation="")


class TestReachesTheReport(unittest.TestCase):
    """The arithmetic must not change; the evidence must."""

    def test_same_count_same_months_either_way(self):
        bare = effective_window("2024-10", "2020-01", "2025-06", trials=20)
        grid = effective_window("2024-10", "2020-01", "2025-06",
                                trials=tc.from_grid(configs=5, windows=2, scenarios=2))
        self.assertEqual(bare.months_required, grid.months_required)
        self.assertEqual(bare.selection.t_adjusted, grid.selection.t_adjusted)
        self.assertEqual(bare.verdict, grid.verdict)

    def test_but_the_provenance_differs(self):
        bare = effective_window("2024-10", "2020-01", "2025-06", trials=20)
        grid = effective_window("2024-10", "2020-01", "2025-06",
                                trials=tc.from_grid(configs=5, windows=2, scenarios=2))
        self.assertEqual(bare.selection.provenance, "declared")
        self.assertEqual(grid.selection.provenance, "grid")
        self.assertNotEqual(bare.selection.note, grid.selection.note)
        self.assertNotEqual(bare.selection.blind_to, grid.selection.blind_to)

    def test_a_bare_integer_is_recorded_as_declared_not_as_blank(self):
        # The regression this guards: leaving provenance None for the commonest
        # case would let an unverifiable number print as an unmarked fact.
        p = selection_penalty(7)
        self.assertEqual(p.provenance, "declared")
        self.assertTrue(p.derivation)
        self.assertTrue(p.blind_to)

    def test_provenance_survives_to_dict(self):
        w = effective_window("2024-10", "2020-01", "2025-06",
                             trials=tc.from_runs([{"a": 1}, {"a": 2}], fields=["a"]))
        d = w.to_dict()["selection"]
        self.assertEqual(d["provenance"], "log")
        self.assertIn("distinct", d["derivation"])
        self.assertTrue(d["blind_to"])

    def test_trials_one_stays_an_exact_identity(self):
        # The existing invariant must not move: a single declared attempt
        # returns the caller's own bar unchanged.
        p = selection_penalty(1)
        self.assertEqual(p.t_adjusted, p.t_base)
        self.assertEqual(p.months_adjusted, p.months_base)
        self.assertEqual(p.provenance, "declared")

    def test_effective_trials_still_discounts_a_derived_count(self):
        w = effective_window("2024-10", "2020-01", "2025-06",
                             trials=tc.from_grid(configs=4, windows=5),
                             effective_trials=6.0)
        self.assertEqual(w.selection.trials, 20)
        self.assertEqual(w.selection.effective_trials, 6.0)
        self.assertEqual(w.selection.provenance, "grid")

    def test_notes_render_in_both_languages(self):
        for lang in ("en", "zh"):
            g = tc.from_grid(configs=3, windows=2, lang=lang)
            self.assertTrue(g.note(lang))
            self.assertIn("6", g.note(lang))
            for t in (tc.declared(3, lang=lang),
                      tc.from_runs([{"a": 1}], fields=["a"], lang=lang)):
                self.assertTrue(t.note(lang))


if __name__ == "__main__":
    unittest.main()
