"""Tests for the caller-supplied score table adapter.

This adapter is the one place the package takes a caller's own dimensions
rather than a vendor's payload, so the things worth pinning down are the ones
that would quietly corrupt a downstream redundancy number: scale handling,
what happens to a column that has no value, and whether the caller's construct
names survive intact.

    python -m unittest discover tests
"""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from adapters import DEFAULT_REGISTRY, observe_vendor, supported_vendors  # noqa: E402
from adapters import scores  # noqa: E402


def by_construct(obs):
    return {o.construct: o for o in obs}


class TestScoresAdapter(unittest.TestCase):

    def test_registered_and_reachable_by_vendor_name(self) -> None:
        self.assertIn("scores", supported_vendors())
        self.assertTrue(DEFAULT_REGISTRY.has("scores"))
        obs = observe_vendor("scores", "scores", "NVDA",
                             {"scores": {"a": 50}})
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].construct, "a")

    def test_declared_scale_is_mapped_onto_0_100(self) -> None:
        obs = by_construct(scores.parse("NVDA", {
            "scores": {"lo": 1, "mid": 3, "hi": 5}, "scale": [1, 5]}))
        self.assertEqual(obs["lo"].normalized_0_100, 0)
        self.assertEqual(obs["mid"].normalized_0_100, 50)
        self.assertEqual(obs["hi"].normalized_0_100, 100)

    def test_default_scale_is_0_100_not_guessed_from_the_data(self) -> None:
        # Guessing the scale from the observed range would make the same score
        # mean different things in two different batches.
        obs = by_construct(scores.parse("X", {"scores": {"a": 40, "b": 60}}))
        self.assertEqual(obs["a"].normalized_0_100, 40)
        self.assertEqual(obs["b"].normalized_0_100, 60)

    def test_polarity_flip_inverts_the_axis(self) -> None:
        obs = by_construct(scores.parse("X", {
            "scores": {"a": 5}, "scale": [1, 5], "polarity": "high_is_good"}))
        self.assertEqual(obs["a"].normalized_0_100, 0)
        self.assertIn("polarity flipped", obs["a"].note)

    def test_out_of_scale_value_is_clamped_and_says_so(self) -> None:
        obs = by_construct(scores.parse("X", {
            "scores": {"a": 9}, "scale": [1, 5]}))
        self.assertEqual(obs["a"].normalized_0_100, 100)
        self.assertIn("outside the declared scale", obs["a"].note)

    def test_missing_column_is_emitted_not_dropped(self) -> None:
        # A dimension that vanishes on the subjects it could not score would
        # bias the redundancy check toward the easy subjects.
        obs = by_construct(scores.parse("X", {"scores": {"a": 3, "b": None},
                                              "scale": [1, 5]}))
        self.assertEqual(set(obs), {"a", "b"})
        self.assertEqual(obs["b"].status, "missing")
        self.assertIsNone(obs["b"].normalized_0_100)

    def test_non_numeric_score_is_malformed_not_zero(self) -> None:
        obs = by_construct(scores.parse("X", {"scores": {"a": "n/a"}}))
        self.assertEqual(obs["a"].status, "malformed")
        self.assertIsNone(obs["a"].normalized_0_100)

    def test_caller_construct_names_are_kept_verbatim(self) -> None:
        # Not in this repo's CONSTRUCTS vocabulary, and that is the point:
        # the engine groups on the name the caller declared.
        obs = by_construct(scores.parse("NVDA", {
            "scores": {"physicalConstraint": 5, "moatCapture": 4},
            "scale": [1, 5]}))
        self.assertEqual(set(obs), {"physicalConstraint", "moatCapture"})
        self.assertTrue(all(o.source_id.startswith("scores:") for o in obs.values()))

    def test_degenerate_scale_yields_no_score_rather_than_dividing_by_zero(self) -> None:
        obs = by_construct(scores.parse("X", {"scores": {"a": 3}, "scale": [2, 2]}))
        self.assertIsNone(obs["a"].normalized_0_100)

    def test_garbage_payload_yields_nothing_rather_than_raising(self) -> None:
        self.assertEqual(scores.parse("X", {}), [])
        self.assertEqual(scores.parse("X", {"scores": "not a table"}), [])
        self.assertEqual(scores.parse("X", []), [])


if __name__ == "__main__":
    unittest.main()
