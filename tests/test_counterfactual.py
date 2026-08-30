"""The third axis: does the agent read its inputs, or recite an outcome?

Stdlib ``unittest`` only.

    python -m unittest discover tests

Assertions are anchored on meaning, and every number asserted here can be
checked by hand against a hypergeometric table — which matters more than usual,
because the whole module is one exact test plus a dispatch on its result.
"""

from __future__ import annotations

import os
import sys
import unittest
from math import comb

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from counterfactual import (  # noqa: E402
    COSMETIC, MATERIAL, Perturbation, fisher_one_sided,
    minimum_perturbations, perturbation_audit, remedies,
)
from messages import LANGS, text  # noqa: E402


def mat(n, flips):
    return [Perturbation(MATERIAL, "m%d" % i, i < flips) for i in range(n)]


def cos(n, flips):
    return [Perturbation(COSMETIC, "c%d" % i, i < flips) for i in range(n)]


class FisherArithmetic(unittest.TestCase):
    """The exact test, checked against the hypergeometric definition."""

    def test_a_perfect_three_three_split_is_exactly_five_percent(self):
        """The number the whole floor rests on: 1 / C(6,3) = 1/20."""
        self.assertAlmostEqual(fisher_one_sided(3, 0, 0, 3), 1 / comb(6, 3), places=12)
        self.assertAlmostEqual(fisher_one_sided(3, 0, 0, 3), 0.05, places=12)

    def test_the_page_and_the_cli_quote_a_checkable_default(self):
        """``docs/index.html`` loads 1/4 material and 0/4 cosmetic on arrival and
        its footer states the answer, the same way the window half states
        58/8/48. A published number with nothing pinning it drifts on the next
        edit and is then wrong in two places at once — the footer and the CLI's
        ``--material 1/4 --cosmetic 0/4``, which is the same case."""
        r = perturbation_audit(mat(4, 1) + cos(4, 0))
        self.assertEqual(r.verdict, "memorised")
        self.assertAlmostEqual(r.p_value, 0.5, places=12)
        self.assertAlmostEqual(r.best_possible_p, 1 / comb(8, 4), places=12)
        self.assertEqual("%.4f" % r.best_possible_p, "0.0143")
        self.assertEqual(r.perturbations_required, 6)

    def test_a_degenerate_table_is_not_significant(self):
        """No variation in a margin means nothing can be concluded from it."""
        for table in [(0, 0, 0, 0), (3, 0, 3, 0), (0, 3, 0, 3), (2, 2, 0, 0)]:
            self.assertEqual(fisher_one_sided(*table), 1.0, table)

    def test_more_extreme_splits_give_smaller_p(self):
        p33 = fisher_one_sided(3, 0, 0, 3)
        p44 = fisher_one_sided(4, 0, 0, 4)
        p55 = fisher_one_sided(5, 0, 0, 5)
        self.assertGreater(p33, p44)
        self.assertGreater(p44, p55)

    def test_the_direction_is_one_sided(self):
        """Material above cosmetic is significant; the reverse must not be."""
        self.assertLessEqual(fisher_one_sided(5, 0, 0, 5), 0.05)
        self.assertGreater(fisher_one_sided(0, 5, 5, 0), 0.05)


class MinimumSize(unittest.TestCase):

    def test_six_is_the_floor_at_five_percent(self):
        self.assertEqual(minimum_perturbations(0.05),
                         {"material": 3, "cosmetic": 3, "total": 6})

    def test_a_stricter_alpha_costs_more_perturbations(self):
        self.assertGreater(minimum_perturbations(0.01)["total"],
                           minimum_perturbations(0.05)["total"])

    def test_an_impossible_alpha_is_refused(self):
        for bad in (0.0, 1.0, -0.1, 2.0):
            with self.assertRaises(ValueError):
                minimum_perturbations(bad)


class Verdicts(unittest.TestCase):

    def test_all_five_verdicts_are_reachable(self):
        """A checker that can only ever say one thing is not a checker."""
        got = {
            perturbation_audit(mat(6, 5) + cos(6, 0)).verdict,
            perturbation_audit(mat(6, 0) + cos(6, 0)).verdict,
            perturbation_audit(mat(6, 6) + cos(6, 6)).verdict,
            perturbation_audit(mat(8, 8)).verdict,
            perturbation_audit(mat(2, 2) + cos(2, 0)).verdict,
        }
        self.assertEqual(got, {"responsive", "memorised", "unstable",
                               "no_control", "no_power"})

    def test_a_totally_unresponsive_agent_is_memorised_not_unstable(self):
        """Regression, first direction.

        The first dispatch compared the two rates. At 0% and 0% the test
        ``cosmetic >= material`` fires, and an agent that never moves at all
        was called *unstable* — the opposite of what it is.
        """
        r = perturbation_audit(mat(6, 0) + cos(6, 0))
        self.assertEqual(r.verdict, "memorised")
        self.assertEqual(r.material_rate, 0.0)
        self.assertEqual(r.cosmetic_rate, 0.0)

    def test_an_agent_that_flips_on_everything_is_unstable_not_memorised(self):
        """Regression, other direction: 100% and 100% fell through to memorised."""
        self.assertEqual(perturbation_audit(mat(6, 6) + cos(6, 6)).verdict, "unstable")

    def test_one_cosmetic_flip_is_enough_to_be_unstable(self):
        """The bar is one, not a rate: a conclusion that moves on a renamed
        ticker is a real problem at any frequency."""
        self.assertEqual(perturbation_audit(mat(6, 2) + cos(6, 1)).verdict, "unstable")
        self.assertEqual(perturbation_audit(mat(6, 2) + cos(6, 0)).verdict, "memorised")

    def test_missing_either_kind_is_no_control_however_clean_the_rest(self):
        """Eight perfect material flips still say nothing without a control."""
        self.assertEqual(perturbation_audit(mat(8, 8)).verdict, "no_control")
        self.assertEqual(perturbation_audit(cos(8, 0)).verdict, "no_control")
        self.assertIsNone(perturbation_audit(mat(8, 8)).p_value)

    def test_no_power_is_about_the_audit_not_the_agent(self):
        """A perfect 2+2 split is still unreadable, and says so."""
        r = perturbation_audit(mat(2, 2) + cos(2, 0))
        self.assertEqual(r.verdict, "no_power")
        self.assertEqual(r.p_value, r.best_possible_p)   # already the best case
        self.assertGreater(r.best_possible_p, r.alpha)

    def test_the_boundary_case_passes_exactly(self):
        r = perturbation_audit(mat(3, 3) + cos(3, 0))
        self.assertEqual(r.verdict, "responsive")
        self.assertAlmostEqual(r.p_value, 0.05, places=12)

    def test_a_stricter_alpha_turns_that_boundary_into_no_power(self):
        self.assertEqual(
            perturbation_audit(mat(3, 3) + cos(3, 0), alpha=0.01).verdict, "no_power")


class ReportContents(unittest.TestCase):

    def test_the_limits_travel_with_every_verdict(self):
        for ps in [mat(6, 5) + cos(6, 0), mat(6, 0) + cos(6, 0), mat(8, 8)]:
            for lang in LANGS:
                self.assertIn(text("cf.limits", lang),
                              perturbation_audit(ps, lang=lang).note, lang)

    def test_language_changes_the_words_and_not_the_numbers(self):
        en = perturbation_audit(mat(6, 5) + cos(6, 0), lang="en")
        zh = perturbation_audit(mat(6, 5) + cos(6, 0), lang="zh")
        self.assertNotEqual(en.note, zh.note)
        self.assertNotEqual(en.summary(), zh.summary())
        self.assertEqual(en.verdict, zh.verdict)
        self.assertEqual(en.p_value, zh.p_value)

    def test_it_serialises(self):
        d = perturbation_audit(mat(6, 5) + cos(6, 0)).to_dict()
        self.assertEqual(d["verdict"], "responsive")
        self.assertEqual(len(d["perturbations"]), 12)

    def test_an_unknown_kind_is_refused_rather_than_bucketed(self):
        with self.assertRaises(ValueError):
            perturbation_audit([Perturbation("structural", "?", True)])

    def test_an_impossible_alpha_is_refused(self):
        with self.assertRaises(ValueError):
            perturbation_audit(mat(3, 3) + cos(3, 0), alpha=0)


class Remedies(unittest.TestCase):

    def test_the_missing_kind_is_the_one_asked_for(self):
        only_material = remedies(perturbation_audit(mat(8, 8)))
        self.assertIn(text("cf.remedy.add_cosmetic", "en"), only_material)
        self.assertNotIn(text("cf.remedy.add_material", "en"), only_material)

        only_cosmetic = remedies(perturbation_audit(cos(8, 0)))
        self.assertIn(text("cf.remedy.add_material", "en"), only_cosmetic)
        self.assertNotIn(text("cf.remedy.add_cosmetic", "en"), only_cosmetic)

    def test_a_full_set_is_not_told_to_add_more_kinds(self):
        r = remedies(perturbation_audit(mat(6, 5) + cos(6, 0)))
        self.assertNotIn(text("cf.remedy.add_cosmetic", "en"), r)
        self.assertNotIn(text("cf.remedy.add_material", "en"), r)

    def test_passing_still_says_what_it_does_not_prove(self):
        self.assertIn(text("cf.remedy.not_a_pass", "en"),
                      remedies(perturbation_audit(mat(6, 5) + cos(6, 0))))

    def test_the_caller_is_always_reminded_the_labels_are_theirs(self):
        """The escape hatch is named on every path, not only on failures."""
        for ps in [mat(6, 5) + cos(6, 0), mat(6, 0) + cos(6, 0), mat(8, 8),
                   mat(2, 2) + cos(2, 0)]:
            self.assertIn(text("cf.remedy.labels_are_yours", "en"),
                          remedies(perturbation_audit(ps)))

    def test_unflipped_material_is_pointed_at_when_it_is_the_problem(self):
        self.assertIn(text("cf.remedy.inspect_unflipped", "en", unflipped=5),
                      remedies(perturbation_audit(mat(6, 1) + cos(6, 0))))

    def test_flipped_cosmetic_is_pointed_at_even_when_the_verdict_passes(self):
        """A significant result does not excuse a conclusion that moved on a
        renamed ticker."""
        r = perturbation_audit(mat(10, 10) + cos(10, 1))
        self.assertEqual(r.verdict, "responsive")
        self.assertIn(text("cf.remedy.inspect_flipped_cosmetic", "en", flipped=1),
                      remedies(r))

    def test_remedies_follow_the_report_language(self):
        r = perturbation_audit(mat(6, 0) + cos(6, 0), lang="zh")
        self.assertIn(text("cf.remedy.labels_are_yours", "zh"), remedies(r))


if __name__ == "__main__":
    unittest.main()
