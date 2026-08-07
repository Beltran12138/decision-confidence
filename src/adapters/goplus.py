"""GoPlus Token Security adapter.

Endpoint (free, no key required for basic rate-limited access)::

    GET https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses=0x...

Response envelope verified live on 2026-07-26 against Ethereum PEPE and USDT::

    {"code": 1, "message": "OK", "result": {"<lowercased address>": { ... }}}

Two traps this adapter exists to absorb:

1. **Every flag is a string** — ``"0"`` / ``"1"``, not a bool.
2. **A missing field means "not applicable / not detected", not ``False``.**
   Treating absence as "safe" is the single easiest way to under-report risk
   with this vendor, so absent flags are counted and reported in the note
   rather than silently scored as zero.

Two observations come out of one payload: contract *authority control* and
*holder concentration*. They are different constructs and are kept apart
deliberately — see ``adapters/__init__.py``.

Thresholds below are rough heuristics, uncalibrated against any labelled set.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from decision_confidence import SourceObservation

SOURCE_ID = "goplus"

# Additive authority penalties. Rough, uncalibrated.
FLAG_PENALTIES: Dict[str, int] = {
    "owner_change_balance": 35,
    "can_take_back_ownership": 30,
    "hidden_owner": 30,
    "selfdestruct": 30,
    "is_mintable": 25,
    "transfer_pausable": 20,
    "slippage_modifiable": 20,
    "personal_slippage_modifiable": 20,
    "is_blacklisted": 15,
    "trading_cooldown": 15,
    "is_proxy": 15,
    "anti_whale_modifiable": 10,
    "external_call": 10,
}

# Simulation verdicts. These end the discussion — but about *tradability*, not
# about authority. GoPlus reaches them by simulating a buy and a sell, which is
# the same question honeypot.is answers, so they belong in the same construct
# and must be comparable with it. They were emitted under `authority_control`
# until 2026-08-07; that mislabelled a tradability measurement as a structural
# one, and it mattered twice:
#
#   * calibration — these are the fields a vendor backfills once a token is
#     known dead, so leaving them in `authority_control` contaminated the one
#     construct whose value does not change post-mortem;
#   * detection — two vendors answering the same question were filed under
#     different constructs and could therefore never be compared, which is
#     precisely the failure this library exists to catch.
HARD_FAIL: Dict[str, Tuple[int, str]] = {
    "is_honeypot": (100, "honeypot detected"),
    "cannot_sell_all": (95, "cannot sell entire balance"),
    "cannot_buy": (90, "cannot buy"),
}

# A clean simulation is evidence of tradability, not proof of it — a token can
# pass today and be pausable tomorrow, which is what `authority_control` is
# for. The partial value carries the uncertainty of a payload that answered
# only some of the three checks.
TRADABILITY_CLEAN = 5
TRADABILITY_PARTIAL = 15

NOT_OPEN_SOURCE_PENALTY = 30
RENOUNCED_OWNER_DISCOUNT = 20

# Penalties are combined with noisy-OR, not addition. Addition saturates: six
# ordinary flags sum past 100 and a merely centralised token scores identically
# to a confirmed honeypot. Noisy-OR keeps each additional flag meaningful while
# never reaching certainty, and 100 stays reserved for HARD_FAIL.
AUTHORITY_SOFT_CEILING = 90
BURN_ADDRESSES = {
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
    "",
}

# Holder concentration → risk. Mirrors the token instance's thinking.
CONCENTRATION_BANDS = [(5, 10), (10, 25), (20, 45), (35, 65), (50, 80), (101, 95)]


def _flag(token: Dict[str, Any], key: str) -> Optional[bool]:
    """``"1"`` → True, ``"0"`` → False, absent/unparseable → None (unknown)."""
    v = token.get(key)
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip()
    if s == "1":
        return True
    if s == "0":
        return False
    return None


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _unwrap(subject: str, raw: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
    """Pull the per-token object out of the envelope. Returns ``(token, reason)``."""
    if not isinstance(raw, dict):
        return None, "raw is not an object"
    if "result" not in raw:
        # Caller already unwrapped; accept the bare token object.
        return (raw, "") if raw else (None, "empty payload")
    code = raw.get("code")
    if code is not None and str(code) != "1":
        return None, f"vendor returned code={code!r} message={raw.get('message')!r}"
    result = raw.get("result") or {}
    if not isinstance(result, dict) or not result:
        return None, "vendor returned no record for this address"
    key = subject.lower()
    if key in result:
        return result[key], ""
    # Vendor keys by lowercased address; fall back to the single entry present.
    if len(result) == 1:
        return next(iter(result.values())), ""
    return None, "address not present in multi-address result"


def _tradability(subject: str, raw: Dict[str, Any], token: Dict[str, Any]) -> SourceObservation:
    """GoPlus's buy/sell simulation, filed under the construct it measures.

    Lands in the same group as honeypot.is, so when the two disagree the engine
    reports a `range` contradiction between two vendors that were asked the
    same question — a factual disagreement, not a definitional one.
    """
    source_id = SOURCE_ID + ":tradability"
    states = {key: _flag(token, key) for key in HARD_FAIL}
    for key, (score, why) in HARD_FAIL.items():
        if states[key] is True:
            return SourceObservation(
                source_id, subject, raw, score, "ok",
                f"simulation hard fail: {why} ({key}=1)",
                construct="tradability",
            )

    known = [k for k, v in states.items() if v is not None]
    if not known:
        return SourceObservation(
            source_id, subject, raw, None, "unavailable",
            "payload carries none of " + ", ".join(HARD_FAIL),
            construct="tradability",
        )
    if len(known) == len(HARD_FAIL):
        return SourceObservation(
            source_id, subject, raw, TRADABILITY_CLEAN, "ok",
            "buy/sell simulation clean on all three checks",
            construct="tradability",
        )
    missing = [k for k in HARD_FAIL if states[k] is None]
    return SourceObservation(
        source_id, subject, raw, TRADABILITY_PARTIAL, "ok",
        f"clean on {', '.join(known)}; {', '.join(missing)} absent — "
        "scored as unknown, not safe",
        construct="tradability",
    )


def _authority(subject: str, raw: Dict[str, Any], token: Dict[str, Any]) -> SourceObservation:
    """Structural rights only. Simulation verdicts go to :func:`_tradability`."""
    contributions: List[int] = []
    fired: List[str] = []
    unknown: List[str] = []
    for key, penalty in FLAG_PENALTIES.items():
        state = _flag(token, key)
        if state is None:
            unknown.append(key)
        elif state:
            contributions.append(penalty)
            fired.append(key)

    open_source = _flag(token, "is_open_source")
    if open_source is False:
        contributions.append(NOT_OPEN_SOURCE_PENALTY)
        fired.append("closed_source")
    elif open_source is None:
        unknown.append("is_open_source")

    for tax_key in ("buy_tax", "sell_tax", "transfer_tax"):
        tax = _num(token.get(tax_key))
        if tax is None:
            continue
        if tax >= 0.50:
            contributions.append(40)
            fired.append(f"{tax_key}>=50%")
        elif tax >= 0.10:
            contributions.append(20)
            fired.append(f"{tax_key}>=10%")

    survival = 1.0
    for penalty in contributions:
        survival *= 1.0 - (penalty / 100.0)
    risk = int(round((1.0 - survival) * AUTHORITY_SOFT_CEILING))

    owner = str(token.get("owner_address", "")).lower()
    if owner in BURN_ADDRESSES and risk > 0:
        # Several flagged capabilities are inert once ownership is renounced.
        # Discount rather than zero out: renouncement does not disarm a proxy
        # upgrade path or a hidden second admin.
        risk = max(0, risk - RENOUNCED_OWNER_DISCOUNT)
        fired.append("owner_renounced(-%d)" % RENOUNCED_OWNER_DISCOUNT)

    risk = max(0, min(AUTHORITY_SOFT_CEILING, risk))
    note = "authority flags fired: " + (", ".join(fired) if fired else "none")
    if unknown:
        note += f"; {len(unknown)} flag(s) absent from payload, scored as unknown not safe"
    return SourceObservation(
        SOURCE_ID, subject, raw, risk, "ok", note, construct="authority_control",
    )


def _concentration(subject: str, raw: Dict[str, Any], token: Dict[str, Any]) -> SourceObservation:
    holders = token.get("holders")
    source_id = SOURCE_ID + ":concentration"
    if not isinstance(holders, list) or not holders:
        return SourceObservation(
            source_id, subject, raw, None, "unavailable",
            "vendor returned no holder breakdown", construct="holder_concentration",
        )
    percents = [_num(h.get("percent")) for h in holders if isinstance(h, dict)]
    percents = [p for p in percents if p is not None]
    if not percents:
        return SourceObservation(
            source_id, subject, raw, None, "malformed",
            "holder entries carry no parseable percent",
            construct="holder_concentration",
        )
    # Vendor reports fractions (0.19 = 19%). Values > 1 are already percentages.
    scale = 1.0 if max(percents) > 1.0 else 100.0
    scaled = [p * scale for p in percents]

    # A share of supply outside 0-100% is not a very concentrated token, it is a
    # broken measurement. Observed on real payloads: GoPlus returned top-1
    # percents of 5e3, 1e9 and 4.6e30 — the arithmetic of balance/totalSupply
    # when the supply has been burned to zero or near it.
    #
    # Scoring it anyway would land every one of them in the top risk band and
    # look like a triumph: in a 400-subject rug-pull sample all 29 such payloads
    # carried the scam label. That correlation is real and worthless — it
    # measures a supply destroyed *by* the rug, and the concentration that
    # actually preceded it is unknown. Unknown is what we report.
    if not (0.0 <= max(scaled) <= 100.0) or min(scaled) < 0.0:
        return SourceObservation(
            source_id, subject, raw, None, "malformed",
            f"vendor reported a holder share of {max(scaled):.3g}% of supply — "
            "outside 0-100%, so the balance/supply ratio is not meaningful "
            "(typically a burned or near-zero total supply)",
            construct="holder_concentration",
        )

    top1 = scaled[0]
    locked = sum(
        1 for h in holders
        if isinstance(h, dict) and str(h.get("is_locked", "0")) == "1"
    )
    risk = next(risk for ceiling, risk in CONCENTRATION_BANDS if top1 < ceiling)
    note = f"top-1 holder {top1:.2f}% of supply → risk {risk}"
    if locked:
        note += f"; {locked}/{len(holders)} top holders flagged locked (not discounted)"
    return SourceObservation(
        source_id, subject, raw, risk, "ok", note, construct="holder_concentration",
    )


def parse(subject: str, raw: Dict[str, Any]) -> List[SourceObservation]:
    """GoPlus payload → three observations, one per construct it actually measures.

    ``authority_control`` (structural rights), ``holder_concentration``
    (distribution) and ``tradability`` (buy/sell simulation). One vendor, three
    questions — collapsing them into one number before the meta-layer sees it
    would destroy exactly the information the meta-layer exists to reason about.
    """
    token, reason = _unwrap(subject, raw)
    if token is None:
        return [SourceObservation(
            SOURCE_ID, subject, raw if isinstance(raw, dict) else {}, None,
            "unavailable", reason, construct="authority_control",
        )]
    return [
        _authority(subject, raw, token),
        _concentration(subject, raw, token),
        _tradability(subject, raw, token),
    ]
