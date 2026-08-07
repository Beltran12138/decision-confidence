"""Perp funding rates → one ``carry_cost`` observation **per venue**.

Every other adapter here contributes a construct measured by a single vendor.
This one is the control case: five venues, one construct, five numbers. Binance
and Hyperliquid quoting different funding for the same asset are answering
*exactly the same question* and giving different answers — so unlike the
authority-scanner-vs-honeypot gap, that disagreement is factual, and the engine
should report the spread rather than explain it away.

Having both cases in one library is what makes the construct rule falsifiable.
A layer that only ever says "these are not comparable" has not built a judgment,
it has built an excuse.

Note what this adapter deliberately does *not* do: ``normalize.score_funding``
in the token instance collapses all venues into one extremity score before any
meta-layer sees them. That is the same mistake the construct split exists to
prevent, committed inside this package — kept there because that module is a
frozen public API, not repeated here.

Payload shapes accepted (caller-fetched, as always — no network here)::

    {"venue": "binance", "rate": 0.0008, "intervalHours": 8}
    {"rates": [{"venue": "binance", "rate": 0.0008}, {"venue": "hyperliquid", ...}]}

``rate`` is the raw per-interval rate (``0.0008`` = 0.08% per settlement).
Interval defaults come from :data:`normalize.VENUE_INTERVAL_HOURS` — CEX venues
settle 8-hourly, Hyperliquid and dYdX hourly — so an unannotated rate is not
silently compared across incompatible periods.

Thresholds below are **rough, uncalibrated heuristics**, the same honesty bar
as the rest of the package.
"""

from __future__ import annotations

from typing import Any, Dict, List

from decision_confidence import SourceObservation
from normalize import annualize_funding

CONSTRUCT = "carry_cost"

# Annualized |funding| → risk. Extremity in either direction is the signal: a
# deeply negative rate is not a discount, it is a crowded short paying to stay
# short. This is a positioning/squeeze indicator, NOT a yield estimate.
BANDS = [
    (10.0, 20),
    (25.0, 40),
    (50.0, 60),
    (100.0, 80),
]
EXTREME_RISK = 95


def _score(annualized_pct: float) -> int:
    mag = abs(annualized_pct)
    for ceiling, risk in BANDS:
        if mag < ceiling:
            return risk
    return EXTREME_RISK


def _one(subject: str, raw: Dict[str, Any], entry: Dict[str, Any]) -> SourceObservation:
    venue = entry.get("venue")
    rate = entry.get("rate")
    source_id = f"funding:{venue}" if venue else "funding:?"

    if rate is None:
        return SourceObservation(
            source_id, subject, raw, None, "missing",
            "no rate in entry", construct=CONSTRUCT,
        )
    if not isinstance(rate, (int, float)) or isinstance(rate, bool):
        return SourceObservation(
            source_id, subject, raw, None, "malformed",
            f"rate is {type(rate).__name__}, expected number", construct=CONSTRUCT,
        )

    ann = annualize_funding(float(rate), entry.get("intervalHours"), venue)
    side = "longs pay" if ann > 0 else ("shorts pay" if ann < 0 else "flat")
    return SourceObservation(
        source_id, subject, raw, _score(ann), "ok",
        f"{rate} per interval → {ann:+.2f}% annualized ({side})",
        construct=CONSTRUCT,
    )


def parse(subject: str, raw: Dict[str, Any]) -> List[SourceObservation]:
    """One observation per venue. A venue that failed to fetch stays visible.

    An empty venue list is reported as ``unavailable`` rather than omitted:
    a subject with no perp market is a construct nobody could measure, which
    must reach the engine so it caps confidence instead of vanishing.
    """
    if not isinstance(raw, dict):
        return [SourceObservation(
            "funding", subject, {}, None, "malformed",
            "raw not an object", construct=CONSTRUCT,
        )]

    if "error" in raw:
        return [SourceObservation(
            "funding", subject, raw, None, "unavailable",
            str(raw["error"]), construct=CONSTRUCT,
        )]

    entries = raw.get("rates")
    if entries is None and "rate" in raw:
        entries = [raw]
    if not isinstance(entries, list) or not entries:
        return [SourceObservation(
            "funding", subject, raw, None, "unavailable",
            "no perp venue reported a rate for this subject", construct=CONSTRUCT,
        )]

    return [_one(subject, raw, e) for e in entries if isinstance(e, dict)] or [
        SourceObservation(
            "funding", subject, raw, None, "malformed",
            "rates list held no usable entries", construct=CONSTRUCT,
        )
    ]
