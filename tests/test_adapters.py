"""Adapter tests, run entirely offline against payloads captured from the live APIs.

Fixtures in ``tests/fixtures/`` are real responses recorded on 2026-07-26 (see
that directory's README). Tests never touch the network: a test suite whose
outcome depends on three third-party services staying up is not a test suite.

    python -m unittest discover tests
"""

from __future__ import annotations

import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from adapters import DEFAULT_REGISTRY, observe_vendor, supported_vendors  # noqa: E402
from adapters import dexscreener, goplus, honeypot_is  # noqa: E402
from decision_confidence import (  # noqa: E402
    SourceObservation,
    build_report,
    detect_contradictions,
)

FIXTURES = os.path.join(ROOT, "tests", "fixtures")
PEPE = "0x6982508145454ce325ddbe47a25d4ec3d2311933"
USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"


def fx(name: str):
    with open(os.path.join(FIXTURES, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


class TestGoPlusAdapter(unittest.TestCase):
    def test_one_payload_yields_two_constructs(self) -> None:
        obs = goplus.parse(PEPE, fx("goplus_pepe"))
        self.assertEqual(len(obs), 2)
        self.assertEqual(
            [o.construct for o in obs],
            ["authority_control", "holder_concentration"],
        )

    def test_renounced_owner_is_discounted_not_ignored(self) -> None:
        authority, _ = goplus.parse(PEPE, fx("goplus_pepe"))
        self.assertEqual(authority.status, "ok")
        self.assertIn("owner_renounced", authority.note)
        self.assertLess(authority.normalized_0_100, 30)

    def test_live_owner_controls_score_high_but_never_maximal(self) -> None:
        # USDT can mint, pause, blacklist and change balances. That is high
        # authority risk — but it is not a honeypot, and the score must keep
        # those two apart. Additive penalties would have saturated at 100.
        authority, _ = goplus.parse(USDT, fx("goplus_usdt"))
        self.assertGreaterEqual(authority.normalized_0_100, 55)
        self.assertLessEqual(authority.normalized_0_100, goplus.AUTHORITY_SOFT_CEILING)
        self.assertLess(authority.normalized_0_100, 100)
        for flag in ("is_mintable", "transfer_pausable", "is_blacklisted"):
            self.assertIn(flag, authority.note)

    def test_honeypot_flag_is_a_hard_fail(self) -> None:
        payload = {"code": "1", "result": {PEPE: {"is_honeypot": "1", "is_open_source": "1"}}}
        authority, _ = goplus.parse(PEPE, payload)
        self.assertEqual(authority.normalized_0_100, 100)
        self.assertIn("hard fail", authority.note)

    def test_absent_flags_are_unknown_not_safe(self) -> None:
        payload = {"code": "1", "result": {PEPE: {"is_mintable": "1"}}}
        authority, _ = goplus.parse(PEPE, payload)
        self.assertIn("absent from payload", authority.note)
        self.assertIn("not safe", authority.note)

    def test_vendor_error_code_is_unavailable(self) -> None:
        obs = goplus.parse(PEPE, {"code": "4029", "message": "rate limit", "result": {}})
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].status, "unavailable")
        self.assertIsNone(obs[0].normalized_0_100)
        self.assertIn("4029", obs[0].note)

    def test_empty_result_is_unavailable_not_clean(self) -> None:
        obs = goplus.parse(PEPE, {"code": 1, "message": "OK", "result": {}})
        self.assertEqual(obs[0].status, "unavailable")

    def test_concentration_reads_top_holder(self) -> None:
        _, conc = goplus.parse(USDT, fx("goplus_usdt"))
        self.assertEqual(conc.status, "ok")
        self.assertIn("top-1 holder 19.30%", conc.note)


class TestHoneypotIsAdapter(unittest.TestCase):
    def test_successful_simulation_scores_tradability(self) -> None:
        obs, = honeypot_is.parse(PEPE, fx("honeypot_is_pepe"))
        self.assertEqual(obs.status, "ok")
        self.assertEqual(obs.construct, "tradability")
        self.assertLessEqual(obs.normalized_0_100, 10)

    def test_failed_simulation_is_unavailable_not_low_risk(self) -> None:
        # The failure mode this guards: reading "probe did not run" as "found
        # nothing, therefore safe".
        payload = {"simulationSuccess": False, "simulationError": "no liquidity",
                   "summary": {"risk": "low", "riskLevel": 0}}
        obs, = honeypot_is.parse(PEPE, payload)
        self.assertEqual(obs.status, "unavailable")
        self.assertIsNone(obs.normalized_0_100)
        self.assertIn("cannot conclude", obs.note)

    def test_honeypot_is_maximal(self) -> None:
        obs, = honeypot_is.parse(PEPE, {"honeypotResult": {"isHoneypot": True}})
        self.assertEqual(obs.normalized_0_100, 100)

    def test_severe_sell_tax_raises_a_low_score(self) -> None:
        payload = {"simulationSuccess": True, "summary": {"risk": "low", "riskLevel": 2},
                   "simulationResult": {"sellTax": 75}}
        obs, = honeypot_is.parse(PEPE, payload)
        self.assertGreaterEqual(obs.normalized_0_100, 90)
        self.assertIn("sellTax", obs.note)


class TestDexScreenerAdapter(unittest.TestCase):
    def test_deep_pool_is_low_risk(self) -> None:
        obs, = dexscreener.parse(PEPE, fx("dexscreener_pepe"), chain="ethereum")
        self.assertEqual(obs.status, "ok")
        self.assertLessEqual(obs.normalized_0_100, 15)
        self.assertIn("ethereum", obs.note)

    def test_wrong_chain_is_unavailable_rather_than_a_fork_chain_number(self) -> None:
        # Real capture: querying the Ethereum USDT address returns PulseChain
        # pools only. Scoring those would report six figures of liquidity for
        # the largest stablecoin in existence.
        obs, = dexscreener.parse(USDT, fx("dexscreener_usdt"), chain="ethereum")
        self.assertEqual(obs.status, "unavailable")
        self.assertIn("pulsechain", obs.note)

    def test_multichain_payload_without_a_hint_refuses_to_guess(self) -> None:
        payload = {"pairs": [
            {"chainId": "ethereum", "dexId": "uniswap", "liquidity": {"usd": 1_000}},
            {"chainId": "bsc", "dexId": "pancake", "liquidity": {"usd": 9_000_000}},
        ]}
        obs, = dexscreener.parse("0xabc", payload)
        self.assertEqual(obs.status, "unavailable")
        self.assertIn("refusing to guess", obs.note)

    def test_no_pairs_is_unavailable(self) -> None:
        obs, = dexscreener.parse("0xabc", {"pairs": []})
        self.assertEqual(obs.status, "unavailable")

    def test_for_chain_binds_the_adapter(self) -> None:
        bound = dexscreener.for_chain("ethereum")
        obs, = bound(PEPE, fx("dexscreener_pepe"))
        self.assertEqual(obs.status, "ok")


class TestRegistry(unittest.TestCase):
    def test_known_vendor_dispatches_to_its_adapter(self) -> None:
        obs = observe_vendor("goplus", "goplus", PEPE, fx("goplus_pepe"))
        self.assertEqual(len(obs), 2)

    def test_unknown_vendor_falls_back_to_shape_sniffing_and_says_so(self) -> None:
        obs, = observe_vendor("some_vendor", "sv", "SUBJ", {"score": 40})
        self.assertEqual(obs.normalized_0_100, 40)
        self.assertIn("shape sniffing", obs.note)

    def test_registry_lists_its_vendors(self) -> None:
        vendors = supported_vendors()
        for expected in ("goplus", "honeypot_is", "dexscreener"):
            self.assertIn(expected, vendors)
            self.assertTrue(vendors[expected])
        self.assertTrue(DEFAULT_REGISTRY.has("goplus"))


class TestConstructAwareContradictions(unittest.TestCase):
    """Disagreement between different constructs is not the same as being wrong."""

    @staticmethod
    def _obs(source_id, score, construct=None):
        return SourceObservation(source_id, "SUBJ", {}, score, "ok", "", construct=construct)

    def test_same_construct_clash_stays_high_severity(self) -> None:
        found = detect_contradictions([
            self._obs("a", 5, "fraud_prediction"),
            self._obs("b", 90, "fraud_prediction"),
        ])
        polarity = [c for c in found if c.kind == "polarity"]
        self.assertTrue(polarity)
        self.assertEqual(polarity[0].severity, "high")
        self.assertEqual([c for c in found if c.kind == "construct_mismatch"], [])

    def test_different_constructs_downgrade_and_explain(self) -> None:
        found = detect_contradictions([
            self._obs("a", 5, "tradability"),
            self._obs("b", 90, "authority_control"),
        ])
        polarity = [c for c in found if c.kind == "polarity"]
        self.assertTrue(polarity)
        self.assertEqual(polarity[0].severity, "medium")
        self.assertIn("definitional", polarity[0].detail)
        self.assertTrue([c for c in found if c.kind == "construct_mismatch"])

    def test_undeclared_constructs_behave_exactly_as_before(self) -> None:
        found = detect_contradictions([self._obs("a", 5), self._obs("b", 90)])
        polarity = [c for c in found if c.kind == "polarity"]
        self.assertEqual(polarity[0].severity, "high")
        self.assertEqual([c for c in found if c.kind == "construct_mismatch"], [])


class TestEndToEndOnRealPayloads(unittest.TestCase):
    def _report(self, key: str, subject: str):
        observations = []
        for vendor in ("goplus", "honeypot_is", "dexscreener"):
            payload = fx(f"{vendor}_{key}")
            if vendor == "dexscreener":
                payload["_chain"] = "ethereum"
            observations.extend(observe_vendor(vendor, vendor, subject, payload))
        return build_report(subject, observations)

    def test_agreeing_real_token(self) -> None:
        report = self._report("pepe", PEPE)
        self.assertEqual(report.verdict, "low")
        self.assertEqual(report.contradictions, [])
        self.assertEqual(report.confidence, "high")

    def test_disagreeing_real_token_is_flagged_not_averaged_away(self) -> None:
        report = self._report("usdt", USDT)
        kinds = {c.kind for c in report.contradictions}
        self.assertIn("range", kinds)
        self.assertIn("construct_mismatch", kinds)
        # One source could not be scored at all, and that is visible.
        unavailable = [o for o in report.observations if o.status == "unavailable"]
        self.assertEqual(len(unavailable), 1)
        self.assertEqual(report.confidence, "medium")


if __name__ == "__main__":
    unittest.main()
