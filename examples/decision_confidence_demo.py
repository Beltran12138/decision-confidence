"""Local mock: multi risk-API → normalize → contradict → confidence → report.

Three fictional vendors stand in for the on-chain-score, KYT-tier and
fraud-probability classes. The meta-layer itself lives in
``src/decision_confidence.py``; this file only supplies mock payloads, the
per-vendor adapters, and printing. Stdlib only, no network.

Run from the repo root:

    python examples/decision_confidence_demo.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict

# Make ``src/`` importable when running the demo directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from decision_confidence import (  # noqa: E402
    DecisionReport,
    SourceObservation,
    build_report,
    observe_fraud_probability,
    observe_kyt_tier,
    observe_safety_score,
)


# ---------------------------------------------------------------------------
# Mock vendors — fictional; stand-ins for on-chain score / KYT / fraud classes
# ---------------------------------------------------------------------------

def mock_alpha_risk(subject: str, *, safety_score: Any) -> Dict[str, Any]:
    """MockAlphaRisk: 0-100 *safety* score (high = safe). Must flip to risk."""
    if safety_score is None:
        return {"provider": "MockAlphaRisk", "scale": "safety_0_100", "score": None}
    return {
        "provider": "MockAlphaRisk",
        "scale": "safety_0_100",
        "score": safety_score,
        "subject": subject,
    }


def mock_beta_kyt(subject: str, *, tier: Any) -> Dict[str, Any]:
    """MockBetaKYT: ordinal tier string."""
    if tier is None:
        return {"provider": "MockBetaKYT", "tier": None}
    return {"provider": "MockBetaKYT", "tier": tier.upper(), "subject": subject}


def mock_gamma_fraud(subject: str, *, fraud_probability: Any) -> Dict[str, Any]:
    """MockGammaFraud: fraud probability in [0, 1]."""
    if fraud_probability is None:
        return {"provider": "MockGammaFraud", "fraud_probability": None}
    return {
        "provider": "MockGammaFraud",
        "fraud_probability": fraud_probability,
        "subject": subject,
    }


# ---------------------------------------------------------------------------
# Adapters: raw vendor payload → SourceObservation
#
# Each adapter is a thin binding of one vendor id to the normalizer that
# matches that vendor's scale. Vendor-specific field names would be unpacked
# here too, keeping that churn out of the engine.
# ---------------------------------------------------------------------------

def adapt_alpha_risk(subject: str, raw: Dict[str, Any]) -> SourceObservation:
    return observe_safety_score("mock_alpha_risk", subject, raw)


def adapt_beta_kyt(subject: str, raw: Dict[str, Any]) -> SourceObservation:
    return observe_kyt_tier("mock_beta_kyt", subject, raw)


def adapt_gamma_fraud(subject: str, raw: Dict[str, Any]) -> SourceObservation:
    return observe_fraud_probability("mock_gamma_fraud", subject, raw)


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

def case_agreeing(subject: str = "DEMO-AGREE") -> DecisionReport:
    """Three sources roughly agree: moderate risk, high confidence."""
    raws = [
        adapt_alpha_risk(subject, mock_alpha_risk(subject, safety_score=55)),
        adapt_beta_kyt(subject, mock_beta_kyt(subject, tier="MEDIUM")),
        adapt_gamma_fraud(subject, mock_gamma_fraud(subject, fraud_probability=0.48)),
    ]
    # After flip: alpha risk ≈ 45; beta 55; gamma 48 → tight cluster
    return build_report(subject, raws)


def case_conflicting(subject: str = "DEMO-CONFLICT") -> DecisionReport:
    """One source looks safe; another looks like fraud → low confidence."""
    raws = [
        adapt_alpha_risk(subject, mock_alpha_risk(subject, safety_score=92)),  # risk ≈ 8
        adapt_beta_kyt(subject, mock_beta_kyt(subject, tier="LOW")),            # risk 20
        adapt_gamma_fraud(subject, mock_gamma_fraud(subject, fraud_probability=0.91)),  # 91
    ]
    return build_report(subject, raws)


def _print_report(title: str, report: DecisionReport) -> None:
    print("=" * 72)
    print(title)
    print("=" * 72)
    print(f"subject:     {report.subject}")
    print(f"composite:   {report.composite}")
    print(f"verdict:     {report.verdict}")
    print(f"confidence:  {report.confidence}")
    print()
    print("-- observations (raw → normalized risk 0-100) --")
    for o in report.observations:
        print(
            f"  [{o.source_id}] status={o.status} "
            f"normalized={o.normalized_0_100} | raw={json.dumps(o.raw, sort_keys=True)}"
        )
        if o.note:
            print(f"    note: {o.note}")
    print()
    print("-- contradictions --")
    if not report.contradictions:
        print("  (none)")
    else:
        for c in report.contradictions:
            print(f"  [{c.severity}/{c.kind}] {c.detail}")
            print(f"    sources: {', '.join(c.sources)}")
    print()
    print("-- audit (summary) --")
    for e in report.audit:
        src = f" ({e.source_id})" if e.source_id else ""
        print(f"  {e.step}{src}: {e.detail}")
    print()
    print("-- note --")
    print(f"  {report.note}")
    print()
    print("-- JSON --")
    print(json.dumps(report.to_dict(), indent=2))
    print()


def main() -> None:
    _print_report("Case 1: agreeing sources (expect medium/high confidence)", case_agreeing())
    _print_report("Case 2: conflicting sources (expect low confidence + contradictions)", case_conflicting())


if __name__ == "__main__":
    main()
