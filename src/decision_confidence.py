"""Agent decision-confidence meta-layer.

Consumes risk signals that a caller has already fetched from several external
sources, maps them onto one 0-100 risk basis, detects cross-source
contradictions, and emits a :class:`DecisionReport` carrying a confidence
label and an audit trail.

Design constraints (see ``docs/ARCHITECTURE.md``):

* **Caller-supplied only.** Nothing here performs network I/O. Fetching,
  API keys, rate limits and caching are the caller's job.
* **Never fabricate.** A source that is missing or malformed is recorded as
  such and lowers confidence; it is never guessed.
* **Does not touch the token instance.** ``normalize.py`` (``score_token`` /
  ``TokenInputs``) is a separate, frozen public API. This module reuses its
  *methodology* — 0-100 risk basis, clamping, verdict bands, confidence
  degraded by thin evidence or internal contradiction — not its code.

Stdlib only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

__all__ = [
    "SourceObservation",
    "Contradiction",
    "AuditEntry",
    "DecisionReport",
    "observe_safety_score",
    "observe_risk_score",
    "observe_kyt_tier",
    "observe_fraud_probability",
    "observe_from_raw",
    "composite_from_observations",
    "detect_contradictions",
    "synthesize_confidence",
    "build_report",
    "CONSTRUCTS",
]


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

# A fraud-class source scoring at or above this, while a peer still reads
# "safe", is treated as a hard flag rather than ordinary disagreement.
HARD_FLAG_FRAUD_RISK = 70

# What a source actually measures. Two vendors can disagree numerically while
# both being right, because they are scoring different constructs — a
# structural-authority scanner and a honeypot simulator answer different
# questions. Declaring the construct lets the layer separate *definitional*
# disagreement from *factual* disagreement instead of averaging both away.
#
# A source may leave this unset; behaviour is then exactly as before.
CONSTRUCTS = {
    "authority_control",    # what the deployer / owner can still do
    "tradability",          # can the position actually be exited (simulation)
    "liquidity_depth",      # is there enough depth to exit at size
    "holder_concentration",  # how concentrated is the holder base
    "compliance_exposure",  # sanctions / KYT style exposure
    "fraud_prediction",     # scam / fraud classifier output
}


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class SourceObservation:
    source_id: str
    subject: str
    raw: Dict[str, Any]
    normalized_0_100: Optional[int]
    status: str  # ok | missing | malformed | unavailable
    note: str = ""
    construct: Optional[str] = None  # see CONSTRUCTS; None = undeclared


@dataclass
class Contradiction:
    sources: List[str]
    kind: str  # range | polarity | hard_flag | construct_mismatch
    detail: str
    severity: str = "medium"
    constructs: Optional[List[str]] = None  # constructs involved, when declared


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


REPORT_NOTE = (
    "Caller-supplied only — the library performs no network I/O. "
    "Thresholds are rough heuristics, not calibrated. "
    "Not investment advice; not a safety or compliance guarantee. "
    "Meta-layer quality is bounded by upstream source quality."
)


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
# Normalizers: one vendor payload → SourceObservation on the 0-100 risk basis
#
# Direction convention: 0 = safe / low risk, 100 = maximum risk. A vendor that
# reports *safety* must be flipped, and the flip is recorded in ``note`` so the
# audit trail explains the transformation.
# ---------------------------------------------------------------------------

def observe_safety_score(
    source_id: str,
    subject: str,
    raw: Dict[str, Any],
    *,
    key: str = "score",
) -> SourceObservation:
    """0-100 *safety* score (high = safe). Flipped to risk."""
    score = raw.get(key)
    if score is None:
        return SourceObservation(source_id, subject, raw, None, "missing", "no score")
    if not isinstance(score, (int, float)) or score < 0 or score > 100:
        return SourceObservation(source_id, subject, raw, None, "malformed", "score out of range")
    risk = _clamp(100 - float(score))
    return SourceObservation(
        source_id, subject, raw, risk, "ok",
        "flipped safety_0_100 → risk_0_100",
    )


def observe_risk_score(
    source_id: str,
    subject: str,
    raw: Dict[str, Any],
    *,
    key: str = "score",
) -> SourceObservation:
    """0-100 *risk* score, already on the engine's basis."""
    score = raw.get(key)
    if score is None:
        return SourceObservation(source_id, subject, raw, None, "missing", "no score")
    if not isinstance(score, (int, float)) or score < 0 or score > 100:
        return SourceObservation(source_id, subject, raw, None, "malformed", "score out of range")
    return SourceObservation(
        source_id, subject, raw, _clamp(float(score)), "ok",
        "risk_0_100 taken as-is",
    )


def observe_kyt_tier(
    source_id: str,
    subject: str,
    raw: Dict[str, Any],
    *,
    key: str = "tier",
) -> SourceObservation:
    """Ordinal compliance tier mapped onto 0-100 by :data:`KYT_TIER_TO_RISK`."""
    tier = raw.get(key)
    if tier is None:
        return SourceObservation(source_id, subject, raw, None, "missing", "no tier")
    if not isinstance(tier, str):
        return SourceObservation(source_id, subject, raw, None, "malformed", "tier not str")
    upper = tier.upper()
    if upper not in KYT_TIER_TO_RISK:
        return SourceObservation(source_id, subject, raw, None, "malformed", f"unknown tier {tier}")
    return SourceObservation(
        source_id, subject, raw, KYT_TIER_TO_RISK[upper], "ok",
        f"tier {upper} → risk {KYT_TIER_TO_RISK[upper]}",
    )


def observe_fraud_probability(
    source_id: str,
    subject: str,
    raw: Dict[str, Any],
    *,
    key: str = "fraud_probability",
) -> SourceObservation:
    """Probability in [0, 1] scaled to the 0-100 risk basis."""
    p = raw.get(key)
    if p is None:
        return SourceObservation(source_id, subject, raw, None, "missing", "no fraud_probability")
    if not isinstance(p, (int, float)) or p < 0 or p > 1:
        return SourceObservation(source_id, subject, raw, None, "malformed", "p not in [0,1]")
    risk = _clamp(float(p) * 100.0)
    return SourceObservation(
        source_id, subject, raw, risk, "ok",
        f"fraud_probability {p} → risk {risk}",
    )


def observe_from_raw(source_id: str, subject: str, raw: Dict[str, Any]) -> SourceObservation:
    """Pick a normalizer from the payload's shape.

    Dispatch order — ``fraud_probability`` → ``tier`` → ``score`` (a ``scale``
    of ``safety_0_100`` selects the flip). Real deployments should register
    explicit per-vendor adapters instead of relying on shape sniffing; this
    exists so a generic tool surface can accept heterogeneous payloads without
    a vendor registry.
    """
    if not isinstance(raw, dict):
        return SourceObservation(source_id, subject, {}, None, "malformed", "raw not an object")
    if "fraud_probability" in raw:
        return observe_fraud_probability(source_id, subject, raw)
    if "tier" in raw:
        return observe_kyt_tier(source_id, subject, raw)
    if "score" in raw:
        scale = raw.get("scale")
        if scale == "safety_0_100":
            return observe_safety_score(source_id, subject, raw)
        return observe_risk_score(source_id, subject, raw)
    return SourceObservation(
        source_id, subject, raw, None, "malformed",
        "unrecognised payload shape (expected fraud_probability | tier | score)",
    )


# ---------------------------------------------------------------------------
# Engine: composite, contradictions, confidence
# ---------------------------------------------------------------------------

def composite_from_observations(
    observations: Sequence[SourceObservation],
    weights: Optional[Dict[str, float]] = None,
) -> Optional[int]:
    """Weighted mean over usable sources. Equal weight unless told otherwise."""
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


def _infer_fraud_sources(observations: Iterable[SourceObservation]) -> Set[str]:
    """Which sources are fraud/scam classifiers.

    Inferred from the payload (a ``fraud_probability`` key) or, failing that,
    from the source id. Callers that know their vendors should pass
    ``fraud_source_ids`` explicitly rather than rely on this.
    """
    inferred: Set[str] = set()
    for o in observations:
        if isinstance(o.raw, dict) and "fraud_probability" in o.raw:
            inferred.add(o.source_id)
        elif "fraud" in o.source_id.lower():
            inferred.add(o.source_id)
    return inferred


def _construct_qualifier(
    constructs: Dict[str, Optional[str]],
    a: str,
    b: str,
    base_severity: str,
):
    """Downgrade a pairwise clash when the two sources measure different things.

    Returns ``(severity, detail_suffix, constructs_involved)``. When either
    construct is undeclared the pair is treated exactly as before — this keeps
    construct tagging strictly opt-in.
    """
    ca, cb = constructs.get(a), constructs.get(b)
    if not ca or not cb or ca == cb:
        pair = [ca or cb] if (ca or cb) else None
        return base_severity, "", pair
    severity = "medium" if base_severity == "high" else base_severity
    suffix = (
        f" — but {a} measures {ca} and {b} measures {cb}; "
        "the disagreement may be definitional, not factual"
    )
    return severity, suffix, [ca, cb]


def detect_contradictions(
    observations: Sequence[SourceObservation],
    fraud_source_ids: Optional[Iterable[str]] = None,
) -> List[Contradiction]:
    """Cross-source disagreement, as a first-class output rather than a side effect.

    Three families: ``range`` (spread across usable sources), ``polarity``
    (one source safe while another is high risk), and ``hard_flag`` (a
    fraud-class source firing while a peer still reads safe). Fewer than two
    usable sources yields nothing — thin evidence is handled by confidence,
    not by inventing a contradiction.
    """
    ok = [o for o in observations if o.status == "ok" and o.normalized_0_100 is not None]
    found: List[Contradiction] = []
    if len(ok) < 2:
        return found

    scores = {o.source_id: o.normalized_0_100 for o in ok}
    constructs = {o.source_id: o.construct for o in ok}
    vals = list(scores.values())
    spread = max(vals) - min(vals)
    if spread >= RANGE_SPREAD:
        lo_id = min(scores, key=scores.get)
        hi_id = max(scores, key=scores.get)
        sev, qual, pair_constructs = _construct_qualifier(constructs, lo_id, hi_id,
                                                          "medium" if spread < 60 else "high")
        found.append(Contradiction(
            sources=[lo_id, hi_id],
            kind="range",
            detail=(
                f"spread {spread} ≥ {RANGE_SPREAD}: "
                f"{lo_id}={scores[lo_id]} vs {hi_id}={scores[hi_id]}{qual}"
            ),
            severity=sev,
            constructs=pair_constructs,
        ))

    ids = list(scores.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            sa, sb = scores[a], scores[b]
            if (sa <= POLARITY_LOW and sb >= POLARITY_HIGH) or (
                sb <= POLARITY_LOW and sa >= POLARITY_HIGH
            ):
                sev, qual, pair_constructs = _construct_qualifier(constructs, a, b, "high")
                found.append(Contradiction(
                    sources=[a, b],
                    kind="polarity",
                    detail=(
                        (
                            f"polarity clash: {a}={sa} (≤{POLARITY_LOW}) vs "
                            f"{b}={sb} (≥{POLARITY_HIGH})"
                            if sa <= POLARITY_LOW
                            else (
                                f"polarity clash: {b}={sb} (≤{POLARITY_LOW}) vs "
                                f"{a}={sa} (≥{POLARITY_HIGH})"
                            )
                        ) + qual
                    ),
                    severity=sev,
                    constructs=pair_constructs,
                ))

    # Composite-level warning: a wide spread across sources that measure
    # different things means the *composite*, not any source, is the doubtful
    # artefact. Only fires when constructs were actually declared.
    declared = sorted({c for c in constructs.values() if c})
    if len(declared) >= 2 and spread >= RANGE_SPREAD:
        found.append(Contradiction(
            sources=sorted(scores.keys()),
            kind="construct_mismatch",
            detail=(
                "composite mixes " + str(len(declared)) + " distinct constructs ("
                + ", ".join(declared)
                + f"); spread {spread} may be definitional rather than factual, "
                "so the weighted mean is not a like-for-like average"
            ),
            severity="medium",
            constructs=declared,
        ))

    # Hard flag: very high fraud-class risk vs another source still "safe"
    fraud_ids = set(fraud_source_ids) if fraud_source_ids is not None else _infer_fraud_sources(ok)
    for fraud in ok:
        if fraud.source_id not in fraud_ids:
            continue
        if fraud.normalized_0_100 is None or fraud.normalized_0_100 < HARD_FLAG_FRAUD_RISK:
            continue
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
    """Evidence-quality label — NOT a probability that the verdict is correct."""
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
    fraud_source_ids: Optional[Iterable[str]] = None,
) -> DecisionReport:
    """Run the full pipeline and record every step in the audit trail."""
    audit: List[AuditEntry] = []
    for o in observations:
        audit.append(AuditEntry(
            step="adapt",
            source_id=o.source_id,
            detail=(
                f"status={o.status} note={o.note!r}"
                + (f" construct={o.construct}" if o.construct else "")
            ),
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

    contradictions = detect_contradictions(observations, fraud_source_ids)
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
        note=REPORT_NOTE,
    )
