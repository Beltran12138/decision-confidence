"""honeypot.is v2 adapter — buy/sell simulation.

Endpoint (free, no key)::

    GET https://api.honeypot.is/v2/IsHoneypot?address=0x...

Shape verified live on 2026-07-26 (Ethereum PEPE, USDT). Fields used::

    simulationSuccess            bool
    honeypotResult.isHoneypot    bool
    summary.risk                 "low" | "medium" | "high" | ...
    summary.riskLevel            int, 0-100
    summary.flags                list
    simulationResult.buyTax/sellTax/transferTax   percent, 0-100

The construct here is **tradability**: can the position actually be exited.
That is a narrower question than "is this token safe", and keeping the two
apart is the point of the construct tag — a token can be perfectly tradable
and still be controlled by an owner who can freeze it tomorrow.

The important case this adapter handles correctly: ``simulationSuccess`` is
false. A simulation that could not run is ``unavailable``, **not** low risk.
Reading a failed probe as "nothing found, so safe" is the classic way a
multi-source pipeline talks itself into false confidence.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from decision_confidence import SourceObservation

SOURCE_ID = "honeypot_is"

RISK_WORD_TO_SCORE = {
    "very_low": 5,
    "low": 10,
    "medium": 50,
    "high": 85,
    "very_high": 95,
}

# A sell tax this high is an exit tax in all but name.
SELL_TAX_SEVERE = 50.0
SELL_TAX_HEAVY = 10.0

# contractCode penalties, combined noisy-OR like the GoPlus authority score so
# the two land on a comparable shape. Rough, uncalibrated, and built on three
# signals rather than thirteen — the ceiling is lower on purpose, because this
# source cannot see enough to justify a high score.
NOT_OPEN_SOURCE = 45
ROOT_CLOSED = 30
PROXY = 20
PROXY_CALLS = 15
STRUCTURE_CEILING = 70

# Single-pair depth, USD. Mirrors the DexScreener bands so the two are on one
# scale; a thin routed pair is thin regardless of who measured it.
LIQUIDITY_BANDS = [(1_000, 90), (10_000, 70), (100_000, 45), (1_000_000, 25),
                   (float("inf"), 10)]


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _structure(subject: str, raw: Dict[str, Any]) -> Optional[SourceObservation]:
    """``contractCode`` → a second opinion on ``authority_control``.

    **A falsifier, not a confirmer.** GoPlus reads thirteen authority flags;
    honeypot.is reports three structural facts and cannot see mint, pause,
    freeze or blacklist at all. So a *finding* here is informative and a clean
    result is not: "the three things I can check are fine" does not mean "this
    deployer holds no power over you", and scoring it 0 would say exactly that.

    The concrete failure that forced this. Ethereum USDT: GoPlus reads 69 —
    mintable, pausable, blacklisting, balance-changing. This source sees an
    open-source non-proxy contract and, scored symmetrically, reads 0. The
    engine would then raise a 69-point `range` contradiction between two
    sources that do not actually disagree — one of them simply was not asked
    the question. That is a coverage gap wearing the costume of a factual
    disagreement, and it is precisely the confusion this library exists to
    prevent, so it must not manufacture one.

    Clean therefore returns ``unavailable`` with the reason stated. The
    asymmetry is the honest shape of a partial probe.
    """
    code = raw.get("contractCode")
    if not isinstance(code, dict) or not code:
        return None

    fired: List[str] = []
    contributions: List[int] = []
    if code.get("openSource") is False:
        contributions.append(NOT_OPEN_SOURCE)
        fired.append("closed_source")
    if code.get("rootOpenSource") is False and code.get("openSource") is not False:
        contributions.append(ROOT_CLOSED)
        fired.append("root_closed_source")
    if code.get("isProxy") is True:
        contributions.append(PROXY)
        fired.append("is_proxy")
    if code.get("hasProxyCalls") is True:
        contributions.append(PROXY_CALLS)
        fired.append("has_proxy_calls")

    if not fired:
        return SourceObservation(
            SOURCE_ID + ":structure", subject, raw, None, "unavailable",
            "open-source, non-proxy — but this source cannot see mint, pause, "
            "freeze or blacklist rights, so a clean structural check is not "
            "evidence of low authority risk",
            construct="authority_control",
        )

    survival = 1.0
    for penalty in contributions:
        survival *= 1.0 - (penalty / 100.0)
    risk = int(round((1.0 - survival) * STRUCTURE_CEILING))
    return SourceObservation(
        SOURCE_ID + ":structure", subject, raw, risk, "ok",
        "structural flags: " + ", ".join(fired)
        + " — 3 signals only; a finding here is real, a clean result would not "
          "have been",
        construct="authority_control",
    )


def _liquidity(subject: str, raw: Dict[str, Any]) -> Optional[SourceObservation]:
    """``pair.liquidity`` → a second opinion on ``liquidity_depth``.

    Single-pair depth in USD, for the pair the simulation actually routed
    through. Narrower than DexScreener's view across every pool, and reported
    as such.
    """
    pair = raw.get("pair")
    if not isinstance(pair, dict):
        return None
    usd = _num(pair.get("liquidity"))
    if usd is None:
        return None
    risk = next(risk for ceiling, risk in LIQUIDITY_BANDS if usd < ceiling)
    name = ((pair.get("pair") or {}).get("name") if isinstance(pair.get("pair"), dict) else None)
    return SourceObservation(
        SOURCE_ID + ":liquidity", subject, raw, risk, "ok",
        f"routed pair {name or '?'} holds ${usd:,.0f} — one pair, not the whole book",
        construct="liquidity_depth",
    )


def parse(subject: str, raw: Dict[str, Any]) -> List[SourceObservation]:
    """honeypot.is payload → tradability, plus structure and liquidity when present.

    One vendor, three constructs. Emitting only the tradability verdict — which
    this adapter did until 2026-08-07 — threw away the two fields that give
    `authority_control` and `liquidity_depth` a second opinion, and a construct
    with one source is a construct the contradiction rules never touch.
    """
    def obs(score: Optional[int], status: str, note: str) -> List[SourceObservation]:
        primary = SourceObservation(
            SOURCE_ID, subject, raw if isinstance(raw, dict) else {},
            score, status, note, construct="tradability",
        )
        if not isinstance(raw, dict):
            return [primary]
        extra = [o for o in (_structure(subject, raw), _liquidity(subject, raw)) if o]
        return [primary] + extra

    if not isinstance(raw, dict):
        return obs(None, "malformed", "raw is not an object")
    if raw.get("error") or raw.get("message") and "result" not in raw and "summary" not in raw:
        return obs(None, "unavailable", f"vendor error: {raw.get('error') or raw.get('message')}")

    hp = raw.get("honeypotResult") or {}
    if hp.get("isHoneypot") is True:
        # The score stays 100 — reporting what the vendor said is this layer's
        # job, and second-guessing it here would hide the disagreement instead
        # of surfacing it. What the note must carry is *why*, because the
        # vendor's own reasoning is sometimes much weaker than its verdict.
        #
        # Binance-Peg Tezos (BSC, 0x16939ef7…): honeypotResult says HONEYPOT
        # DETECTED at riskLevel 100, on the strength of one `low_fail_rate`
        # flag of severity "medium" (index 12), simulated through the
        # PancakeSwap V3 XTZ-ETH pair. GoPlus reads the same token as entirely
        # clean. A thin routed pool is a property of the route, not of the
        # token — and an auditor who sees only "100" cannot tell that.
        reason = hp.get("honeypotReason") or "no reason given"
        summary = raw.get("summary") or {}
        flags = raw.get("flags") or summary.get("flags") or []
        detail = []
        for f in flags[:3]:
            if isinstance(f, dict):
                detail.append(f"{f.get('flag')}({f.get('severity')})")
            else:
                detail.append(str(f))
        pair_name = ((raw.get("pair") or {}).get("pair") or {}).get("name")
        note = f"vendor verdict: {reason}"
        if detail:
            note += "; basis: " + ", ".join(detail)
        if pair_name:
            note += f"; simulated through {pair_name}"
        return obs(100, "ok", note)

    if raw.get("simulationSuccess") is not True:
        reason = raw.get("simulationError") or "simulation did not succeed"
        # Not scoring this as safe is the whole point.
        return obs(None, "unavailable", f"{reason} — cannot conclude tradable")

    summary = raw.get("summary") or {}
    level = summary.get("riskLevel")
    word = str(summary.get("risk", "")).strip().lower()
    if isinstance(level, (int, float)) and 0 <= float(level) <= 100:
        score = int(round(float(level)))
        basis = f"summary.riskLevel={level}"
    elif word in RISK_WORD_TO_SCORE:
        score = RISK_WORD_TO_SCORE[word]
        basis = f"summary.risk={word!r} (no numeric riskLevel)"
    else:
        return obs(None, "malformed", "no usable summary.riskLevel or summary.risk")

    sim = raw.get("simulationResult") or {}
    sell_tax = _num(sim.get("sellTax"))
    bumps: List[str] = []
    if sell_tax is not None:
        if sell_tax >= SELL_TAX_SEVERE and score < 90:
            score = 90
            bumps.append(f"sellTax {sell_tax}% ≥ {SELL_TAX_SEVERE}%")
        elif sell_tax >= SELL_TAX_HEAVY and score < 45:
            score = 45
            bumps.append(f"sellTax {sell_tax}% ≥ {SELL_TAX_HEAVY}%")

    flags = raw.get("flags") or summary.get("flags") or []
    note = basis
    if bumps:
        note += "; raised by " + ", ".join(bumps)
    if flags:
        note += f"; {len(flags)} vendor flag(s): " + ", ".join(str(f) for f in flags[:4])
    return obs(score, "ok", note)
