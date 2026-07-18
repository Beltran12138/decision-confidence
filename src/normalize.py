"""
normalize - multi-source token-risk normalization framework.

Map heterogeneous risk inputs (concentration, liquidity, contract, holder
base, funding extremity) onto one comparable 0-100 basis, flag extremes, and
return a single composite verdict with an honest confidence label.

Originally built for a sandboxed runtime with no outbound network, where live
data acquisition is the caller's job and the agent's value is a *repeatable,
comparable basis* - not data freshness. The framework itself is general
purpose: only the inputs change between domains.

Pure standard library. No network, no on-chain reads, no execution.

License: MIT
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "score_token",
    "snapshot_lookup",
    "score_concentration",
    "score_liquidity",
    "score_contract",
    "score_holders",
    "annualize_funding",
    "score_funding",
    "Verdict",
    "DimensionResult",
    "TokenInputs",
    "SNAPSHOT_TABLE",
    "SNAPSHOT_DATE",
    "WEIGHTS",
    "VERDICT_BANDS",
    "VENUE_INTERVAL_HOURS",
]

__version__ = "0.1.0"


# ---------------------------------------------------------------------------
# Configuration - thresholds are ROUGH HEURISTICS, not calibrated against any
# dataset. Tweak to taste; document any change you make.
# ---------------------------------------------------------------------------

SNAPSHOT_DATE = "2026-07-13"

SNAPSHOT_TABLE: Dict[str, Dict[str, str]] = {
    "BTC":  {"tier": "blue-chip",          "baseline": "low",          "why": "established, deeply distributed, deepest liquidity"},
    "ETH":  {"tier": "blue-chip",          "baseline": "low",          "why": "established base asset; smart-contract platform risk separate"},
    "SOL":  {"tier": "large-cap L1",       "baseline": "low-moderate", "why": "distributed but newer; bridge / L1-outage tail risk"},
    "DOGE": {"tier": "meme (established)", "baseline": "moderate",     "why": "high volatility, concentrated early holdings, multi-year track record"},
    "SHIB": {"tier": "meme (established)", "baseline": "moderate",     "why": "same profile as DOGE"},
    "PEPE": {"tier": "meme (recent)",      "baseline": "high",         "why": "extreme volatility, typical concentration, rug-adjacent category"},
    "WIF":  {"tier": "meme (recent)",      "baseline": "high",         "why": "same profile as PEPE"},
}

UNKNOWN_ENTRY: Dict[str, str] = {
    "tier": "unknown",
    "baseline": "extreme",
    "why": "default-deny; no snapshot entry - demand full data before any action",
}

# Composite weights - rough, sum to 1.0. Re-normalized at runtime over
# whichever dimensions actually have data, so partial inputs still work.
WEIGHTS: Dict[str, float] = {
    "concentration": 0.30,
    "liquidity":     0.20,
    "contract":      0.25,
    "holders":       0.15,
    "funding":       0.10,
}

# Verdict bands applied to the 0-100 composite.
VERDICT_BANDS: List[Tuple[int, str]] = [
    (30, "low"),
    (55, "moderate"),
    (80, "high"),
    (101, "extreme"),
]

# Confidence thresholds: count of dimensions that actually have a score.
CONFIDENCE_HIGH = 4
CONFIDENCE_MEDIUM = 2

# Funding-rate annualization defaults (settlement interval in hours).
VENUE_INTERVAL_HOURS: Dict[str, int] = {
    "binance": 8, "okx": 8, "gate": 8,
    "hyperliquid": 1, "dydx": 1,
}
DEFAULT_INTERVAL_HOURS = 8


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DimensionResult:
    """One dimension's normalized score plus the raw input that produced it."""
    score: Optional[int]
    raw: Dict[str, Any]
    flag: Optional[str] = None


@dataclass
class Verdict:
    """The top-level result returned by ``score_token``."""
    token: str
    source: str                                      # "template" | "caller-supplied"
    snapshot_date: Optional[str]
    dimensions: Dict[str, Any]
    composite: Optional[int]
    verdict: str                                     # low | moderate | high | extreme | unknown
    confidence: str                                  # high | medium | low
    red_flags: List[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(x: float, lo: int = 0, hi: int = 100) -> int:
    return max(lo, min(hi, int(round(x))))


def _band(composite: int) -> str:
    for ceiling, label in VERDICT_BANDS:
        if composite < ceiling:
            return label
    return "extreme"


def _confidence(n_dims: int, contradiction: bool) -> str:
    if contradiction or n_dims < CONFIDENCE_MEDIUM:
        return "low"
    if n_dims >= CONFIDENCE_HIGH:
        return "high"
    return "medium"


# ---------------------------------------------------------------------------
# Per-dimension normalizers. Each returns DimensionResult with score=None when
# the caller supplied no input for that dimension.
# ---------------------------------------------------------------------------

def score_concentration(top10_pct: Optional[float] = None,
                        top1_pct: Optional[float] = None) -> DimensionResult:
    """Concentration risk - the single biggest rug vector.

    Driven mainly by top-10 holder share; top-1 > 50% is a red flag regardless.
    """
    if top10_pct is None and top1_pct is None:
        return DimensionResult(None, {})
    raw: Dict[str, Any] = {}
    if top10_pct is not None:
        raw["top10Pct"] = top10_pct
    if top1_pct is not None:
        raw["top1Pct"] = top1_pct

    score: Optional[int] = None
    if top10_pct is not None:
        if top10_pct < 30:
            score = 20
        elif top10_pct < 60:
            score = 50
        elif top10_pct < 80:
            score = 75
        else:
            score = 95

    flag = None
    if (top1_pct is not None) and top1_pct > 50:
        flag = "top-1 holder > 50% - unilateral-dump risk"
        if score is None:
            # Surface a defensible number even if only top-1 was supplied.
            score = 80
    return DimensionResult(_clamp(score) if score is not None else None, raw, flag)


def score_liquidity(pool_usd: Optional[float] = None) -> DimensionResult:
    """Main-pool size in USD."""
    if pool_usd is None:
        return DimensionResult(None, {})
    raw = {"poolUsd": pool_usd}
    if pool_usd > 10_000_000:
        score = 15
    elif pool_usd > 1_000_000:
        score = 40
    elif pool_usd > 100_000:
        score = 70
    else:
        score = 95
    flag = "thin pool" if pool_usd < 100_000 else None
    return DimensionResult(_clamp(score), raw, flag)


def score_contract(mint_authority: Optional[str] = None,
                   freeze_authority: Optional[str] = None,
                   source_verified: Optional[bool] = None,
                   honeypot: Optional[bool] = None) -> DimensionResult:
    """Contract authority + honeypot signals."""
    if all(v is None for v in (mint_authority, freeze_authority, source_verified, honeypot)):
        return DimensionResult(None, {})
    raw: Dict[str, Any] = {}
    if mint_authority is not None:
        raw["mintAuthority"] = mint_authority
    if freeze_authority is not None:
        raw["freezeAuthority"] = freeze_authority
    if source_verified is not None:
        raw["sourceVerified"] = source_verified
    if honeypot is not None:
        raw["honeypot"] = honeypot

    if honeypot:
        return DimensionResult(95, raw, "honeypot signal - sells reported failing")

    mint_bad = mint_authority in ("retained", "yes", True)
    freeze_bad = freeze_authority in ("retained", "yes", True)
    if mint_bad or freeze_bad:
        return DimensionResult(75, raw, "mint/freeze authority retained by deployer")

    renounced = mint_authority in ("renounced", "no", False) and \
        freeze_authority in ("renounced", "no", False)
    if renounced and source_verified:
        return DimensionResult(20, raw, None)
    if source_verified:
        return DimensionResult(45, raw, None)
    return DimensionResult(60, raw, "authority/verification status only partial")


def score_holders(count: Optional[int] = None) -> DimensionResult:
    """Total holder count."""
    if count is None:
        return DimensionResult(None, {})
    raw = {"count": count}
    if count > 100_000:
        score = 20
    elif count > 10_000:
        score = 45
    elif count > 1_000:
        score = 70
    else:
        score = 90
    return DimensionResult(_clamp(score), raw, None)


def annualize_funding(rate: float, interval_hours: Optional[int] = None,
                      venue: Optional[str] = None) -> float:
    """Annualize a periodic funding rate to a percentage.

    ``rate`` is the raw per-interval rate (e.g. ``0.001`` = 0.1%). Returns an
    annualized percentage (e.g. ``0.001`` per 8h -> 109.5).
    """
    if interval_hours is None and venue is not None:
        interval_hours = VENUE_INTERVAL_HOURS.get(venue.lower(), DEFAULT_INTERVAL_HOURS)
    if interval_hours is None or interval_hours <= 0:
        interval_hours = DEFAULT_INTERVAL_HOURS
    return rate * (24.0 / interval_hours) * 365.0 * 100.0


def score_funding(rates: Optional[List[Dict[str, Any]]] = None) -> DimensionResult:
    """Funding-extremity submodule.

    ``rates`` is a list of ``{venue, rate, intervalHours?}`` dicts. The signal
    is the annualized gap between the most-negative long-funding venue and the
    most-positive short-funding venue - a squeeze / positioning indicator,
    NOT free money.
    """
    if not rates:
        return DimensionResult(None, {})
    annualized: List[Dict[str, Any]] = []
    for r in rates:
        ann = annualize_funding(r["rate"], r.get("intervalHours"), r.get("venue"))
        annualized.append({"venue": r.get("venue", "?"), "annualizedPct": round(ann, 3)})
    ann_vals = [a["annualizedPct"] for a in annualized]
    gap = (max(ann_vals) - min(ann_vals)) if ann_vals else 0.0
    if gap < 10:
        score = 20
    elif gap < 25:
        score = 50
    else:
        score = 80
    long_venue = min(annualized, key=lambda a: a["annualizedPct"])
    short_venue = max(annualized, key=lambda a: a["annualizedPct"])
    raw = {
        "long": long_venue["venue"],
        "short": short_venue["venue"],
        "annualizedPct": round(gap, 3),
        "perVenue": annualized,
    }
    return DimensionResult(_clamp(score), raw, None)


# ---------------------------------------------------------------------------
# Path A - snapshot lookup (fast, no data needed, but qualitative & dated)
# ---------------------------------------------------------------------------

def snapshot_lookup(token: str) -> Dict[str, str]:
    """Return the qualitative baseline entry for a known token, or the
    default-deny 'unknown' entry."""
    return SNAPSHOT_TABLE.get(token.upper(), UNKNOWN_ENTRY)


def _baseline_to_composite(baseline: str) -> int:
    table = {"low": 20, "low-moderate": 40, "moderate": 50, "high": 75, "extreme": 90}
    return table.get(baseline, 90)


def _template_verdict(token: str) -> Verdict:
    entry = snapshot_lookup(token)
    composite = _baseline_to_composite(entry["baseline"])
    return Verdict(
        token=token.upper(),
        source="template",
        snapshot_date=SNAPSHOT_DATE,
        dimensions={"tier": entry["tier"], "baseline": entry["baseline"], "why": entry["why"]},
        composite=composite,
        verdict=_band(composite),
        confidence="low",  # template = qualitative baseline only
        red_flags=[],
        note=(
            "Template baseline from a dated snapshot, NOT live truth. "
            "Verify on-chain before acting. Not investment advice."
        ),
    )


# ---------------------------------------------------------------------------
# Path B - caller-supplied composite
# ---------------------------------------------------------------------------

@dataclass
class TokenInputs:
    """Caller-supplied risk inputs. Every field optional; missing dimensions
    are marked unknown and lower confidence - they are never guessed."""
    top10_pct: Optional[float] = None
    top1_pct: Optional[float] = None
    pool_usd: Optional[float] = None
    mint_authority: Optional[str] = None
    freeze_authority: Optional[str] = None
    source_verified: Optional[bool] = None
    honeypot: Optional[bool] = None
    holder_count: Optional[int] = None
    funding_rates: Optional[List[Dict[str, Any]]] = None


def score_token(token: str, inputs: Optional[TokenInputs] = None) -> Verdict:
    """Main entry point.

    Path A: ``inputs`` is None or completely empty -> snapshot lookup.
    Path B: any input supplied -> caller-supplied normalization.

    Never fabricates: if the token is unknown and no data is supplied, Path A
    returns a default-deny 'extreme until proven otherwise' baseline that
    explicitly asks for data rather than inventing a number.
    """
    has_data = inputs is not None and any(
        v is not None
        for v in (
            inputs.top10_pct, inputs.top1_pct, inputs.pool_usd,
            inputs.mint_authority, inputs.freeze_authority,
            inputs.source_verified, inputs.honeypot,
            inputs.holder_count, inputs.funding_rates,
        )
    )
    if not has_data:
        return _template_verdict(token)

    dims: Dict[str, DimensionResult] = {
        "concentration": score_concentration(inputs.top10_pct, inputs.top1_pct),
        "liquidity":     score_liquidity(inputs.pool_usd),
        "contract":      score_contract(inputs.mint_authority, inputs.freeze_authority,
                                        inputs.source_verified, inputs.honeypot),
        "holders":       score_holders(inputs.holder_count),
        "funding":       score_funding(inputs.funding_rates),
    }

    # Composite - re-normalize weights over present dimensions only.
    present = {k: v for k, v in dims.items() if v.score is not None}
    total_w = sum(WEIGHTS[k] for k in present)
    if total_w <= 0:
        composite: Optional[int] = None
    else:
        composite = _clamp(sum(present[k].score * WEIGHTS[k] for k in present) / total_w)

    red_flags = [v.flag for v in dims.values() if v.flag]
    n_dims = len(present)
    # Contradiction heuristic: a low composite alongside a hard red flag.
    contradiction = bool(red_flags) and composite is not None and composite < 35
    confidence = _confidence(n_dims, contradiction)

    dims_out = {k: {"score": v.score, "raw": v.raw, "flag": v.flag}
                for k, v in dims.items()}

    verdict_label = _band(composite) if composite is not None else "unknown"
    return Verdict(
        token=token.upper(),
        source="caller-supplied",
        snapshot_date=None,
        dimensions=dims_out,
        composite=composite,
        verdict=verdict_label,
        confidence=confidence,
        red_flags=red_flags,
        note=(
            "Caller-supplied only - the normalizer does no fetching. "
            "Thresholds are rough heuristics, not calibrated. "
            "Verify on-chain before acting. Not investment advice."
        ),
    )
