"""OKX spot ticker adapter — five desk metrics off one payload.

Endpoint (free, no key, no account)::

    GET https://www.okx.com/api/v5/market/tickers?instType=SPOT

**Why this adapter exists.** Every trading desk shows these five numbers in
five separate columns: spread, book depth, turnover, range, and the 24h move.
Five columns reads as five checks. They come off *one* ticker payload, and
three of them are arithmetic on the same three prices. Whether that makes them
five votes or two is exactly the question ``tools/redundancy.py`` was written
to answer — so pointing it at a venue's own tape is the cheapest available
test of whether the tool generalises past the corpus it was built on.

**The trap this adapter exists for.** ``volCcy24h`` is denominated in the
*quote* currency, so it is only a USD figure on a USD-quoted pair. Reading it
as USD on a BTC-quoted pair overstates turnover by the price of BTC. This
adapter therefore refuses any instrument that is not quoted in USDT/USDC/USD
rather than converting — a wrong turnover number would land in the one
construct the redundancy check is most sensitive to.

Constructs: ``liquidity_depth`` (shared with dexscreener), plus
``execution_cost``, ``trading_activity``, ``price_volatility`` and
``price_momentum``. Thresholds below are rough and uncalibrated, in the same
class as every other band in this repo: they order instruments sensibly, they
are not claimed to be right.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from decision_confidence import SourceObservation

SOURCE_ID = "okx"

# Quote currencies whose notional is close enough to USD to read directly.
USD_QUOTES = {"USDT", "USDC", "USD", "DAI"}

# Each band list is (ceiling, risk). First ceiling the value falls under wins.
# Risk is 0-100, higher = worse, matching every other adapter in this repo.

# Quoted spread in basis points of mid.
SPREAD_BPS_BANDS = [(1, 5), (5, 20), (20, 45), (50, 70), (200, 88)]
SPREAD_BPS_WORST = 97

# Smaller side of the top of book, in USD. Bands are inverted (bigger = safer)
# so they are written as floors and scanned in descending order.
DEPTH_USD_FLOORS = [(500_000, 5), (100_000, 20), (20_000, 45), (5_000, 70), (1_000, 88)]
DEPTH_USD_WORST = 97

# 24h turnover in quote currency, USD-quoted pairs only.
TURNOVER_USD_FLOORS = [
    (100_000_000, 5), (10_000_000, 20), (1_000_000, 45),
    (100_000, 70), (10_000, 88),
]
TURNOVER_USD_WORST = 97

# (high - low) / last, as a fraction.
RANGE_BANDS = [(0.02, 10), (0.05, 30), (0.10, 55), (0.20, 75), (0.40, 90)]
RANGE_WORST = 97

# (last - open) / open. Downside is scored as risk; upside is not scored as
# safety beyond a floor, because a vertical move up is not evidence of health.
MOMENTUM_FLOORS = [(0.05, 15), (0.0, 30), (-0.05, 45), (-0.10, 65), (-0.20, 82)]
MOMENTUM_WORST = 95


def _num(raw: Dict[str, Any], key: str) -> Optional[float]:
    """OKX ships every numeric field as a string, and empty string for absent."""
    v = raw.get(key)
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _band(value: float, bands: List[tuple], worst: int) -> int:
    for ceiling, risk in bands:
        if value < ceiling:
            return risk
    return worst


def _floor(value: float, floors: List[tuple], worst: int) -> int:
    for floor, risk in floors:
        if value >= floor:
            return risk
    return worst


def parse(subject: str, raw: Dict[str, Any]) -> List[SourceObservation]:
    """One OKX ticker → five observations, one per construct.

    Every construct is emitted on every call, including when it could not be
    computed: a construct that silently vanishes on the hard instruments would
    bias the redundancy check toward the easy ones.
    """
    out: List[SourceObservation] = []

    def emit(construct: str, score: Optional[int], status: str, note: str) -> None:
        out.append(SourceObservation(
            f"{SOURCE_ID}:{construct}", subject,
            raw if isinstance(raw, dict) else {},
            score, status, note, construct=construct,
        ))

    def all_unavailable(reason: str) -> List[SourceObservation]:
        for c in ("liquidity_depth", "execution_cost", "trading_activity",
                  "price_volatility", "price_momentum"):
            emit(c, None, "unavailable", reason)
        return out

    if not isinstance(raw, dict):
        return all_unavailable("raw is not an object")

    inst = str(raw.get("instId") or "")
    if "-" not in inst:
        return all_unavailable("payload has no usable 'instId'")
    quote = inst.rsplit("-", 1)[1].upper()
    if quote not in USD_QUOTES:
        return all_unavailable(
            f"quote currency {quote} is not USD-like; volCcy24h would not be USD"
        )

    last = _num(raw, "last")
    bid, ask = _num(raw, "bidPx"), _num(raw, "askPx")
    bid_sz, ask_sz = _num(raw, "bidSz"), _num(raw, "askSz")
    high, low = _num(raw, "high24h"), _num(raw, "low24h")
    open24 = _num(raw, "open24h")
    turnover = _num(raw, "volCcy24h")

    # --- execution_cost: quoted spread ------------------------------------
    if bid and ask and bid > 0 and ask > 0 and ask >= bid:
        mid = (bid + ask) / 2
        bps = (ask - bid) / mid * 10_000
        emit("execution_cost", _band(bps, SPREAD_BPS_BANDS, SPREAD_BPS_WORST), "ok",
             f"quoted spread {bps:.1f} bps")
    else:
        emit("execution_cost", None, "unavailable", "no two-sided quote in payload")

    # --- liquidity_depth: smaller side of the top of book ------------------
    if last and bid_sz is not None and ask_sz is not None and last > 0:
        usd = min(bid_sz, ask_sz) * last
        if usd > 0:
            emit("liquidity_depth", _floor(usd, DEPTH_USD_FLOORS, DEPTH_USD_WORST), "ok",
                 f"thinner side of top of book ${usd:,.0f}")
        else:
            emit("liquidity_depth", None, "unavailable", "one side of the book is empty")
    else:
        emit("liquidity_depth", None, "unavailable", "payload has no book sizes")

    # --- trading_activity: 24h turnover ------------------------------------
    if turnover is not None and turnover > 0:
        emit("trading_activity",
             _floor(turnover, TURNOVER_USD_FLOORS, TURNOVER_USD_WORST), "ok",
             f"24h turnover ${turnover:,.0f}")
    else:
        emit("trading_activity", None, "unavailable", "vendor reports no 24h turnover")

    # --- price_volatility: 24h range ---------------------------------------
    if last and high is not None and low is not None and last > 0 and high >= low:
        rng = (high - low) / last
        emit("price_volatility", _band(rng, RANGE_BANDS, RANGE_WORST), "ok",
             f"24h range {rng * 100:.1f}% of last")
    else:
        emit("price_volatility", None, "unavailable", "payload has no 24h high/low")

    # --- price_momentum: 24h move ------------------------------------------
    if last and open24 and open24 > 0:
        mv = (last - open24) / open24
        emit("price_momentum", _floor(mv, MOMENTUM_FLOORS, MOMENTUM_WORST), "ok",
             f"24h move {mv * 100:+.1f}%")
    else:
        emit("price_momentum", None, "unavailable", "payload has no 24h open")

    return out
