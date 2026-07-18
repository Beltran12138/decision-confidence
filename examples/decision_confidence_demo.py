"""Local mock: multi risk-API → normalize → contradict → confidence → report.

Phase 1 decision-confidence surface. All meta-layer logic lives in this
example (stdlib only, no network). Methodology aligns with src/normalize.py
(0-100 risk basis, missing ≠ guess, bands, honest confidence) but does not
call or modify score_token / TokenInputs.

Run from the repo root:

    python examples/decision_confidence_demo.py
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Heuristics — rough, uncalibrated (same honesty bar as normalize.py)
# ---------------------------------------------------------------------------

VERDICT_BANDS = [
    (30, "low"),
    (55, "moderate"),
    (80, "high"),
    (101, "extreme"),
]

KYT_TIER_TO_RISK = {
    "LOW": 20,
    "MEDIUM": 55,
    "MED": 55,
    "HIGH": 85,
}

# Contradiction heuristics
POLARITY_LOW = 30
POLARITY_HIGH = 70
RANGE_SPREAD = 40


# ---------------------------------------------------------------------------
# Data shapes (sketch implemented for the demo only)
# ---------------------------------------------------------------------------

@dataclass
class SourceObservation:
    source_id: str
    subject: str
    raw: Dict[str, Any]
    normalized_0_100: Optional[int]
    status: str  # ok | missing | malformed | unavailable
    note: str = ""


@dataclass
class Contradiction:
    sources: List[str]
    kind: str
    detail: str
    severity: str = "medium"


@dataclass
class AuditEntry:
    step: str
    detail: str
    source_id: Optional[str] = None


@dataclass
class DecisionReport:
    subject: str
    observations: List[SourceObservation]
    composite: Optional[int]
    verdict: str
    confidence: str
    contradictions: List[Contradiction]
    audit: List[AuditEntry] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Shared helpers (method-aligned with normalize.py; not imported from it)
# ---------------------------------------------------------------------------

def _clamp(x: float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(x))))


def _band(composite: int) -> str:
    for ceiling, label in VERDICT_BANDS:
        if composite < ceiling:
            return label
    return "extreme"


# ---------------------------------------------------------------------------
# Mock vendors — fictional; stand-ins for on-chain score / KYT / fraud classes
# ---------------------------------------------------------------------------

def mock_alpha_risk(subject: str, *, safety_score: Optional[int]) -> Dict[str, Any]:
    """MockAlphaRisk: 0-100 *safety* score (high = safe). Must flip to risk."""
    if safety_score is None:
        return {"provider": "MockAlphaRisk", "scale": "safety_0_100", "score": None}
    return {
        "provider": "MockAlphaRisk",
        "scale": "safety_0_100",
        "score": safety_score,
        "subject": subject,
    }


def mock_beta_kyt(subject: str, *, tier: Optional[str]) -> Dict[str, Any]:
    """MockBetaKYT: ordinal tier string."""
    if tier is None:
        return {"provider": "MockBetaKYT", "tier": None}
    return {"provider": "MockBetaKYT", "tier": tier.upper(), "subject": subject}


def mock_gamma_fraud(subject: str, *, fraud_probability: Optional[float]) -> Dict[str, Any]:
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
# ---------------------------------------------------------------------------

def adapt_alpha_risk(subject: str, raw: Dict[str, Any]) -> SourceObservation:
    source_id = "mock_alpha_risk"
    score = raw.get("score")
    if score is None:
        return SourceObservation(source_id, subject, raw, None, "missing", "no score")
    if not isinstance(score, (int, float)) or score < 0 or score > 100:
        return SourceObservation(source_id, subject, raw, None, "malformed", "score out of range")
    risk = _clamp(100 - float(score))
    return SourceObservation(
        source_id, subject, raw, risk, "ok",
        "flipped safety_0_100 → risk_0_100",
    )


def adapt_beta_kyt(subject: str, raw: Dict[str, Any]) -> SourceObservation:
    source_id = "mock_beta_kyt"
    tier = raw.get("tier")
    if tier is None:
        return SourceObservation(source_id, subject, raw, None, "missing", "no tier")
    if not isinstance(tier, str):
        return SourceObservation(source_id, subject, raw, None, "malformed", "tier not str")
    key = tier.upper()
    if key not in KYT_TIER_TO_RISK:
        return SourceObservation(source_id, subject, raw, None, "malformed", f"unknown tier {tier}")
    return SourceObservation(
        source_id, subject, raw, KYT_TIER_TO_RISK[key], "ok",
        f"tier {key} → risk {KYT_TIER_TO_RISK[key]}",
    )


def adapt_gamma_fraud(subject: str, raw: Dict[str, Any]) -> SourceObservation:
    source_id = "mock_gamma_fraud"
    p = raw.get("fraud_probability")
    if p is None:
        return SourceObservation(source_id, subject, raw, None, "missing", "no fraud_probability")
    if not isinstance(p, (int, float)) or p < 0 or p > 1:
        return SourceObservation(source_id, subject, raw, None, "malformed", "p not in [0,1]")
    risk = _clamp(float(p) * 100.0)
    return SourceObservation(
        source_id, subject, raw, risk, "ok",
        f"fraud_probability {p} → risk {risk}",
    )


# ---------------------------------------------------------------------------
# Engine: composite, contradictions, confidence
# ---------------------------------------------------------------------------

def composite_from_observations(
    observations: Sequence[SourceObservation],
    weights: Optional[Dict[str, float]] = None,
) -> Optional[int]:
    present = [o for o in observations if o.status == "ok" and o.normalized_0_100 is not None]
    if not present:
        return None
    wmap = weights or {}
    total_w = 0.0
    acc = 0.0
    for o in present:
        w = float(wmap.get(o.source_id, 1.0))
        if w <= 0:
            continue
        total_w += w
        acc += o.normalized_0_100 * w
    if total_w <= 0:
        return None
    return _clamp(acc / total_w)


def detect_contradictions(observations: Sequence[SourceObservation]) -> List[Contradiction]:
    ok = [o for o in observations if o.status == "ok" and o.normalized_0_100 is not None]
    found: List[Contradiction] = []
    if len(ok) < 2:
        return found

    scores = {o.source_id: o.normalized_0_100 for o in ok}
    vals = list(scores.values())
    spread = max(vals) - min(vals)
    if spread >= RANGE_SPREAD:
        lo_id = min(scores, key=scores.get)
        hi_id = max(scores, key=scores.get)
        found.append(Contradiction(
            sources=[lo_id, hi_id],
            kind="range",
            detail=(
                f"spread {spread} ≥ {RANGE_SPREAD}: "
                f"{lo_id}={scores[lo_id]} vs {hi_id}={scores[hi_id]}"
            ),
            severity="medium" if spread < 60 else "high",
        ))

    ids = list(scores.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            sa, sb = scores[a], scores[b]
            if (sa <= POLARITY_LOW and sb >= POLARITY_HIGH) or (
                sb <= POLARITY_LOW and sa >= POLARITY_HIGH
            ):
                found.append(Contradiction(
                    sources=[a, b],
                    kind="polarity",
                    detail=(
                        f"polarity clash: {a}={sa} (≤{POLARITY_LOW}) vs "
                        f"{b}={sb} (≥{POLARITY_HIGH})"
                        if sa <= POLARITY_LOW
                        else (
                            f"polarity clash: {b}={sb} (≤{POLARITY_LOW}) vs "
                            f"{a}={sa} (≥{POLARITY_HIGH})"
                        )
                    ),
                    severity="high",
                ))

    # Hard flag: very high fraud-class risk vs another source still "safe"
    fraud = next((o for o in ok if o.source_id == "mock_gamma_fraud"), None)
    if fraud is not None and fraud.normalized_0_100 is not None and fraud.normalized_0_100 >= 70:
        for o in ok:
            if o.source_id == fraud.source_id:
                continue
            if o.normalized_0_100 is not None and o.normalized_0_100 <= POLARITY_LOW:
                found.append(Contradiction(
                    sources=[fraud.source_id, o.source_id],
                    kind="hard_flag",
                    detail=(
                        f"fraud-class risk {fraud.normalized_0_100} vs "
                        f"{o.source_id} safe-band {o.normalized_0_100}"
                    ),
                    severity="high",
                ))

    return found


def synthesize_confidence(
    n_ok: int,
    contradictions: Sequence[Contradiction],
) -> str:
    high_sev = any(c.severity == "high" for c in contradictions)
    if high_sev or n_ok < 2:
        return "low"
    if contradictions:
        return "medium"
    if n_ok >= 3:
        return "high"
    return "medium"


def build_report(
    subject: str,
    observations: List[SourceObservation],
    weights: Optional[Dict[str, float]] = None,
) -> DecisionReport:
    audit: List[AuditEntry] = []
    for o in observations:
        audit.append(AuditEntry(
            step="adapt",
            source_id=o.source_id,
            detail=f"status={o.status} note={o.note!r}",
        ))
        if o.status == "ok":
            audit.append(AuditEntry(
                step="normalize",
                source_id=o.source_id,
                detail=f"normalized_0_100={o.normalized_0_100}",
            ))

    composite = composite_from_observations(observations, weights)
    audit.append(AuditEntry(
        step="composite",
        detail=f"composite={composite}",
    ))

    contradictions = detect_contradictions(observations)
    for c in contradictions:
        audit.append(AuditEntry(
            step="contradict",
            detail=f"{c.kind}/{c.severity}: {c.detail}",
            source_id=",".join(c.sources),
        ))

    n_ok = sum(1 for o in observations if o.status == "ok" and o.normalized_0_100 is not None)
    confidence = synthesize_confidence(n_ok, contradictions)
    audit.append(AuditEntry(
        step="confidence",
        detail=f"n_ok={n_ok} confidence={confidence} n_contradictions={len(contradictions)}",
    ))

    if composite is None:
        verdict = "unknown"
    else:
        verdict = _band(composite)

    return DecisionReport(
        subject=subject,
        observations=observations,
        composite=composite,
        verdict=verdict,
        confidence=confidence,
        contradictions=contradictions,
        audit=audit,
        note=(
            "Caller-supplied mock only — no network. "
            "Thresholds are rough heuristics, not calibrated. "
            "Not investment advice; not a safety or compliance guarantee. "
            "Meta-layer quality is bounded by upstream source quality."
        ),
    )


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
