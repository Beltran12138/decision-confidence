"""The control case: one construct, many venues, genuinely different answers.

These tests exist to keep the construct rule falsifiable. If every input
produced ``not_comparable``, the rule would be unfalsifiable and therefore
worthless — so the load-bearing assertion here is that funding-only input
*does* yield a composite, and that disagreement *within* ``carry_cost`` is
reported as the factual disagreement it is.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from adapters import observe_vendor  # noqa: E402
from decision_confidence import build_report  # noqa: E402

SUBJ = "PEPE"


def _report(rates):
    obs = observe_vendor("funding", "funding", SUBJ, {"rates": rates})
    return build_report(SUBJ, obs)


class TestFundingIsOneConstructAcrossVenues(unittest.TestCase):
    def test_every_venue_becomes_its_own_observation(self) -> None:
        obs = observe_vendor("funding", "funding", SUBJ, {"rates": [
            {"venue": "binance", "rate": 0.0001},
            {"venue": "okx", "rate": 0.0002},
            {"venue": "hyperliquid", "rate": 0.00001},
        ]})
        self.assertEqual(len(obs), 3)
        self.assertEqual({o.construct for o in obs}, {"carry_cost"})
        self.assertEqual(
            [o.source_id for o in obs],
            ["funding:binance", "funding:okx", "funding:hyperliquid"],
        )

    def test_single_construct_still_produces_a_composite(self) -> None:
        """The falsification test for the whole construct rule.

        All five venues measure carry cost, so averaging them is legal and a
        composite must appear. A layer that refused here would be refusing to
        answer rather than refusing to mislead.
        """
        report = _report([
            {"venue": "binance", "rate": 0.0001},
            {"venue": "okx", "rate": 0.00012},
            {"venue": "gate", "rate": 0.00009},
        ])
        self.assertIsNotNone(report.composite)
        self.assertNotEqual(report.verdict, "not_comparable")
        self.assertEqual([g.construct for g in report.constructs], ["carry_cost"])
        self.assertEqual(
            [c for c in report.contradictions if c.kind == "construct_mismatch"], [],
        )

    def test_within_construct_spread_is_a_real_contradiction(self) -> None:
        """Same question, different answers — the disagreement that is factual."""
        report = _report([
            {"venue": "binance", "rate": 0.00001},   # ~1.1% annualized
            {"venue": "okx", "rate": 0.0005},        # ~54.8% annualized
        ])
        rng = [c for c in report.contradictions if c.kind == "range"]
        self.assertTrue(rng)
        self.assertEqual(rng[0].constructs, ["carry_cost"])
        self.assertIn("same question", rng[0].detail)
        self.assertEqual(report.confidence, "low")  # high-severity spread

    def test_settlement_interval_is_not_ignored(self) -> None:
        """Identical raw rates are not identical carry costs.

        Hyperliquid settles hourly and Binance 8-hourly, so the same 0.0008
        is 8x the annualized cost on Hyperliquid. Comparing the raw numbers
        would call these venues in agreement when they are 613 points apart.
        """
        obs = observe_vendor("funding", "funding", SUBJ, {"rates": [
            {"venue": "binance", "rate": 0.0008},
            {"venue": "hyperliquid", "rate": 0.0008},
        ]})
        scores = {o.source_id: o.normalized_0_100 for o in obs}
        self.assertNotEqual(scores["funding:binance"], scores["funding:hyperliquid"])
        self.assertIn("+87.60%", obs[0].note)
        self.assertIn("+700.80%", obs[1].note)

    def test_no_perp_market_is_unavailable_not_safe(self) -> None:
        obs = observe_vendor("funding", "funding", SUBJ, {"rates": []})
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].status, "unavailable")
        self.assertIsNone(obs[0].normalized_0_100)
        self.assertEqual(obs[0].construct, "carry_cost")

    def test_negative_funding_is_cost_not_discount(self) -> None:
        """A crowded short paying to stay short is extremity, not free money."""
        obs = observe_vendor("funding", "funding", SUBJ, {"rates": [
            {"venue": "binance", "rate": -0.0008},
        ]})
        self.assertEqual(obs[0].normalized_0_100, 80)
        self.assertIn("shorts pay", obs[0].note)


if __name__ == "__main__":
    unittest.main()
