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
    "ConstructGroup",
    "Contradiction",
    "AuditEntry",
    "DecisionReport",
    "observe_safety_score",
    "observe_risk_score",
    "observe_kyt_tier",
    "observe_fraud_probability",
    "observe_from_raw",
    "composite_from_observations",
    "group_by_construct",
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
# questions. Averaging them is not a noisy estimate of one truth; it is a
# category error, and no amount of extra sources fixes it.
#
# The construct is therefore *structural*, not an annotation: sources are
# grouped by it, averaged only within a group, and a subject whose usable
# sources span more than one construct has **no single composite** — see
# :func:`group_by_construct` and :func:`build_report`.
#
# A source may leave this unset. All-undeclared input behaves exactly as it did
# before constructs existed: one group, one composite.
CONSTRUCTS = {
    "authority_control",    # what the deployer / owner can still do
    "tradability",          # can the position actually be exited (simulation)
    "liquidity_depth",      # is there enough depth to exit at size
    "holder_concentration",  # how unevenly is supply distributed
    "holder_base",          # how many holders there are at all
    "compliance_exposure",  # sanctions / KYT style exposure
    "fraud_prediction",     # scam / fraud classifier output
    "carry_cost",           # what holding the position costs (perp funding)
    "execution_cost",       # what crossing the spread costs right now
    "trading_activity",     # how much is actually changing hands
    "price_volatility",     # how wide the recent range is
    "price_momentum",       # which way it has moved and how hard
}

# Group label for sources that never declared a construct.
UNDECLARED = "undeclared"


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
class ConstructGroup:
    """All sources that measure the same thing, and the one average that is legal.

    ``score`` is a weighted mean *within* the construct, so it compares
    like with like. ``spread`` is disagreement between sources that were asked
    the same question — the only kind that is genuinely factual.
    """
    construct: str
    source_ids: List[str]
    score: Optional[int]
    verdict: str
    spread: int
    n_ok: int
    n_unusable: int
    note: str = ""


@dataclass
class Contradiction:
    sources: List[str]
    kind: str  # range | polarity | hard_flag | construct_mismatch
    detail: str
    severity: str = "medium"  # high | medium | low | info
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
    constructs: List[ConstructGroup] = field(default_factory=list)
    blended_composite_unsafe: Optional[int] = None
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
    """Weighted mean over usable sources. Equal weight unless told otherwise.

    **Construct-blind.** Averaging sources that measure different constructs is
    a category error; this function will happily do it anyway. It is retained
    because it is the legal average *within* one construct — which is how
    :func:`group_by_construct` uses it — and because a caller that genuinely
    wants the old blended number can still reach it via
    ``DecisionReport.blended_composite_unsafe``.
    """
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


def group_by_construct(
    observations: Sequence[SourceObservation],
    weights: Optional[Dict[str, float]] = None,
) -> List[ConstructGroup]:
    """Partition observations by what they actually measure.

    One group per construct, each carrying the only average that compares like
    with like, plus the within-group spread — disagreement between sources that
    were asked the *same* question, which is the factual kind.

    Sources with no declared construct fall into a single ``undeclared`` group,
    so all-undeclared input yields exactly one group and the historic
    single-composite behaviour is preserved.

    Groups are ordered by descending score (unscoreable groups last) so the
    sharpest finding reads first.
    """
    buckets: Dict[str, List[SourceObservation]] = {}
    for o in observations:
        buckets.setdefault(o.construct or UNDECLARED, []).append(o)

    groups: List[ConstructGroup] = []
    for construct, obs in buckets.items():
        ok = [o for o in obs if o.status == "ok" and o.normalized_0_100 is not None]
        score = composite_from_observations(ok, weights)
        vals = [o.normalized_0_100 for o in ok]
        spread = (max(vals) - min(vals)) if len(vals) >= 2 else 0
        unusable = [o for o in obs if o not in ok]
        note = ""
        if unusable:
            # `unavailable` is not `safe` — a group that lost every source is
            # reported as unscoreable rather than silently dropped.
            note = "; ".join(f"{o.source_id}: {o.status}" for o in unusable)
        groups.append(ConstructGroup(
            construct=construct,
            source_ids=[o.source_id for o in obs],
            score=score,
            verdict=_band(score) if score is not None else "unknown",
            spread=spread,
            n_ok=len(ok),
            n_unusable=len(unusable),
            note=note,
        ))

    groups.sort(key=lambda g: (g.score is None, -(g.score or 0), g.construct))
    return groups


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


def detect_contradictions(
    observations: Sequence[SourceObservation],
    fraud_source_ids: Optional[Iterable[str]] = None,
) -> List[Contradiction]:
    """Cross-source disagreement, as a first-class output rather than a side effect.

    ``range`` and ``polarity`` are evaluated **within a construct only**. Two
    sources answering different questions cannot contradict each other, so
    comparing them produces a finding that is not merely weak but meaningless;
    the split across constructs is reported by :func:`group_by_construct`
    instead, and flagged here once as an informational
    ``construct_mismatch``.

    ``hard_flag`` deliberately crosses constructs: a fraud classifier firing
    while any peer still reads safe is not excused by measuring something else.

    Fewer than two usable sources *in a group* yields nothing for that group —
    thin evidence is handled by confidence, not by inventing a contradiction.
    """
    ok = [o for o in observations if o.status == "ok" and o.normalized_0_100 is not None]
    found: List[Contradiction] = []
    if len(ok) < 2:
        return found

    scores = {o.source_id: o.normalized_0_100 for o in ok}
    constructs = {o.source_id: o.construct for o in ok}

    by_construct: Dict[str, List[SourceObservation]] = {}
    for o in ok:
        by_construct.setdefault(o.construct or UNDECLARED, []).append(o)

    for construct, group in by_construct.items():
        if len(group) < 2:
            continue
        gscores = {o.source_id: o.normalized_0_100 for o in group}
        label = None if construct == UNDECLARED else [construct]
        gvals = list(gscores.values())
        gspread = max(gvals) - min(gvals)
        if gspread >= RANGE_SPREAD:
            lo_id = min(gscores, key=gscores.get)
            hi_id = max(gscores, key=gscores.get)
            found.append(Contradiction(
                sources=[lo_id, hi_id],
                kind="range",
                detail=(
                    f"spread {gspread} ≥ {RANGE_SPREAD} within {construct}: "
                    f"{lo_id}={gscores[lo_id]} vs {hi_id}={gscores[hi_id]} — "
                    "same question, different answers"
                ),
                severity="medium" if gspread < 60 else "high",
                constructs=label,
            ))

        ids = list(gscores.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                sa, sb = gscores[a], gscores[b]
                if (sa <= POLARITY_LOW and sb >= POLARITY_HIGH) or (
                    sb <= POLARITY_LOW and sa >= POLARITY_HIGH
                ):
                    lo, hi = (a, b) if sa <= POLARITY_LOW else (b, a)
                    found.append(Contradiction(
                        sources=[a, b],
                        kind="polarity",
                        detail=(
                            f"polarity clash within {construct}: "
                            f"{lo}={gscores[lo]} (≤{POLARITY_LOW}) vs "
                            f"{hi}={gscores[hi]} (≥{POLARITY_HIGH})"
                        ),
                        severity="high",
                        constructs=label,
                    ))

    # Structural, not a disagreement: several constructs are in play, so there
    # is no single number to be confident *about*. Informational severity —
    # this must not be scored as evidence quality, because sources measuring
    # different things is the normal case, not a defect.
    declared = sorted({c for c in constructs.values() if c})
    if len(declared) >= 2:
        found.append(Contradiction(
            sources=sorted(scores.keys()),
            kind="construct_mismatch",
            detail=(
                str(len(declared)) + " distinct constructs in play ("
                + ", ".join(declared)
                + "); these measure different things, so no single composite "
                "is defined — read the per-construct scores instead"
            ),
            severity="info",
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
    groups: Optional[Sequence[ConstructGroup]] = None,
) -> str:
    """Evidence-quality label — NOT a probability that the verdict is correct.

    ``info``-severity entries are excluded: ``construct_mismatch`` says the
    sources answered different questions, which is a fact about the subject,
    not a weakness in the evidence. Four reliable sources covering four
    constructs are strong evidence *and* have no single composite; conflating
    those two things is the mistake this layer exists to avoid.

    A construct with **no usable source at all** does cap confidence, because
    that is not thinner evidence on a question — it is a question that was
    never answered. ``unavailable`` is not ``safe``, and a report that reads
    ``high`` while an entire construct is blind would launder the gap.
    """
    scored = [c for c in contradictions if c.severity != "info"]
    high_sev = any(c.severity == "high" for c in scored)
    if high_sev or n_ok < 2:
        return "low"
    if scored:
        return "medium"
    blind = [g for g in (groups or []) if g.n_ok == 0]
    if blind:
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

    groups = group_by_construct(observations, weights)
    for g in groups:
        audit.append(AuditEntry(
            step="group",
            source_id=",".join(g.source_ids),
            detail=(
                f"construct={g.construct} score={g.score} spread={g.spread} "
                f"n_ok={g.n_ok} n_unusable={g.n_unusable}"
            ),
        ))

    # The blended number is computed either way, but it is only *returned* as
    # the composite when every usable source shares one construct. Otherwise
    # the composite is undefined and the caller must read the groups — a number
    # that averages a honeypot simulation with an authority scan is not a noisy
    # estimate of anything, and silently emitting one is the failure mode this
    # layer exists to prevent.
    blended = composite_from_observations(observations, weights)
    scoreable = {g.construct for g in groups if g.n_ok > 0}
    comparable = len(scoreable) <= 1
    composite = blended if comparable else None
    audit.append(AuditEntry(
        step="composite",
        detail=(
            f"composite={composite} comparable={comparable} "
            f"constructs={sorted(scoreable)} blended_composite_unsafe={blended}"
        ),
    ))

    contradictions = detect_contradictions(observations, fraud_source_ids)
    for c in contradictions:
        audit.append(AuditEntry(
            step="contradict",
            detail=f"{c.kind}/{c.severity}: {c.detail}",
            source_id=",".join(c.sources),
        ))

    n_ok = sum(1 for o in observations if o.status == "ok" and o.normalized_0_100 is not None)
    confidence = synthesize_confidence(n_ok, contradictions, groups)
    blind = [g.construct for g in groups if g.n_ok == 0]
    audit.append(AuditEntry(
        step="confidence",
        detail=(
            f"n_ok={n_ok} confidence={confidence} "
            f"n_contradictions={len(contradictions)} blind_constructs={blind}"
        ),
    ))

    if composite is not None:
        verdict = _band(composite)
    elif not comparable:
        verdict = "not_comparable"
    else:
        verdict = "unknown"

    return DecisionReport(
        subject=subject,
        observations=observations,
        composite=composite,
        verdict=verdict,
        confidence=confidence,
        contradictions=contradictions,
        constructs=groups,
        blended_composite_unsafe=blended,
        audit=audit,
        note=REPORT_NOTE,
    )
