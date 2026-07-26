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

# Flags that end the discussion on their own.
HARD_FAIL: Dict[str, Tuple[int, str]] = {
    "is_honeypot": (100, "honeypot detected"),
    "cannot_sell_all": (95, "cannot sell entire balance"),
    "cannot_buy": (90, "cannot buy"),
}

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


def _authority(subject: str, raw: Dict[str, Any], token: Dict[str, Any]) -> SourceObservation:
    for key, (score, why) in HARD_FAIL.items():
        if _flag(token, key) is True:
            return SourceObservation(
                SOURCE_ID, subject, raw, score, "ok",
                f"hard fail: {why} ({key}=1)",
                construct="authority_control",
            )

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
    top1 = percents[0] * scale
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
    """GoPlus payload → [authority_control observation, holder_concentration observation]."""
    token, reason = _unwrap(subject, raw)
    if token is None:
        return [SourceObservation(
            SOURCE_ID, subject, raw if isinstance(raw, dict) else {}, None,
            "unavailable", reason, construct="authority_control",
        )]
    return [_authority(subject, raw, token), _concentration(subject, raw, token)]
