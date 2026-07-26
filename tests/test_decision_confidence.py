"""Regression tests for the decision-confidence meta-layer.

Stdlib ``unittest`` only — no test-runner dependency.

    python -m unittest discover tests
"""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "examples"))

from decision_confidence import (  # noqa: E402
    build_report,
    observe_from_raw,
    observe_safety_score,
)
from decision_confidence_demo import case_agreeing, case_conflicting  # noqa: E402


class TestAgreeingSources(unittest.TestCase):
    """Three sources cluster tightly → usable composite, no disagreement."""

    def setUp(self) -> None:
        self.report = case_agreeing()

    def test_composite_and_verdict(self) -> None:
        # alpha flips 55 → 45, beta MEDIUM → 55, gamma 0.48 → 48; mean 49.33
        self.assertEqual(self.report.composite, 49)
        self.assertEqual(self.report.verdict, "moderate")

    def test_no_contradictions_and_high_confidence(self) -> None:
        self.assertEqual(self.report.contradictions, [])
        self.assertEqual(self.report.confidence, "high")

    def test_every_source_usable(self) -> None:
        self.assertEqual(len(self.report.observations), 3)
        self.assertTrue(all(o.status == "ok" for o in self.report.observations))


class TestConflictingSources(unittest.TestCase):
    """A fraud classifier fires while peers read safe → confidence collapses."""

    def setUp(self) -> None:
        self.report = case_conflicting()

    def test_confidence_is_low_despite_moderate_composite(self) -> None:
        # Composite alone (40) would read "moderate" — the point of the layer
        # is that the disagreement, not the average, drives confidence.
        self.assertEqual(self.report.composite, 40)
        self.assertEqual(self.report.verdict, "moderate")
        self.assertEqual(self.report.confidence, "low")

    def test_contradiction_kinds(self) -> None:
        kinds = {c.kind for c in self.report.contradictions}
        self.assertIn("range", kinds)
        self.assertIn("polarity", kinds)
        self.assertIn("hard_flag", kinds)

    def test_hard_flag_names_the_fraud_source(self) -> None:
        hard = [c for c in self.report.contradictions if c.kind == "hard_flag"]
        self.assertTrue(hard)
        for c in hard:
            self.assertIn("mock_gamma_fraud", c.sources)
            self.assertEqual(c.severity, "high")


class TestThinEvidence(unittest.TestCase):
    """One usable source cannot support a confident answer."""

    def test_single_ok_source_is_low_confidence(self) -> None:
        observations = [
            observe_safety_score("solo", "SUBJ", {"score": 70, "scale": "safety_0_100"}),
        ]
        report = build_report("SUBJ", observations)
        self.assertEqual(report.composite, 30)
        self.assertEqual(report.confidence, "low")
        self.assertEqual(report.contradictions, [])

    def test_missing_data_is_never_guessed(self) -> None:
        observations = [
            observe_from_raw("a", "SUBJ", {"score": None, "scale": "safety_0_100"}),
            observe_from_raw("b", "SUBJ", {"tier": None}),
        ]
        report = build_report("SUBJ", observations)
        self.assertIsNone(report.composite)
        self.assertEqual(report.verdict, "unknown")
        self.assertEqual(report.confidence, "low")
        self.assertTrue(all(o.normalized_0_100 is None for o in report.observations))


class TestShapeDispatch(unittest.TestCase):
    """observe_from_raw picks the normalizer from the payload's shape."""

    def test_safety_scale_is_flipped(self) -> None:
        obs = observe_from_raw("s", "SUBJ", {"score": 90, "scale": "safety_0_100"})
        self.assertEqual(obs.normalized_0_100, 10)

    def test_bare_score_is_taken_as_risk(self) -> None:
        obs = observe_from_raw("s", "SUBJ", {"score": 90})
        self.assertEqual(obs.normalized_0_100, 90)

    def test_unrecognised_shape_is_malformed(self) -> None:
        obs = observe_from_raw("s", "SUBJ", {"something_else": 1})
        self.assertEqual(obs.status, "malformed")
        self.assertIsNone(obs.normalized_0_100)


if __name__ == "__main__":
    unittest.main()
