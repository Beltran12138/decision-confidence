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


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse(subject: str, raw: Dict[str, Any]) -> List[SourceObservation]:
    """honeypot.is payload → one ``tradability`` observation."""
    def obs(score: Optional[int], status: str, note: str) -> List[SourceObservation]:
        return [SourceObservation(
            SOURCE_ID, subject, raw if isinstance(raw, dict) else {},
            score, status, note, construct="tradability",
        )]

    if not isinstance(raw, dict):
        return obs(None, "malformed", "raw is not an object")
    if raw.get("error") or raw.get("message") and "result" not in raw and "summary" not in raw:
        return obs(None, "unavailable", f"vendor error: {raw.get('error') or raw.get('message')}")

    hp = raw.get("honeypotResult") or {}
    if hp.get("isHoneypot") is True:
        return obs(100, "ok", "simulation says honeypot: sell blocked")

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
