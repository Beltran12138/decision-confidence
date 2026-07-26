"""DexScreener adapter — exit-liquidity depth.

Endpoint (free, no key)::

    GET https://api.dexscreener.com/latest/dex/tokens/{address}

**The trap this adapter exists for.** That endpoint is keyed by *address*, not
by (chain, address). Verified live on 2026-07-26: querying the Ethereum USDT
address returned 30 pairs whose three deepest pools were on PulseChain — a fork
chain where the same address exists with a fraction of the liquidity. An
adapter that takes ``pairs[0]``, or even ``max(liquidity)``, silently scores the
wrong chain.

So: this adapter will not guess. Either the caller says which chain it asked
about, or — when the payload spans several chains — the observation comes back
``unavailable`` naming the chains it saw. Refusing to answer is cheaper than a
confidently wrong liquidity number.

Construct: ``liquidity_depth``. Thresholds are rough and uncalibrated.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from decision_confidence import SourceObservation

SOURCE_ID = "dexscreener"

# Deepest pool in USD → risk. Rough, uncalibrated.
LIQUIDITY_BANDS = [
    (10_000, 95),
    (50_000, 80),
    (250_000, 60),
    (1_000_000, 35),
    (5_000_000, 15),
]
DEEP_POOL_RISK = 5


def _usd(pair: Dict[str, Any]) -> float:
    liq = pair.get("liquidity")
    if not isinstance(liq, dict):
        return 0.0
    try:
        return float(liq.get("usd") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _band(usd: float) -> int:
    for ceiling, risk in LIQUIDITY_BANDS:
        if usd < ceiling:
            return risk
    return DEEP_POOL_RISK


def parse(subject: str, raw: Dict[str, Any], chain: Optional[str] = None) -> List[SourceObservation]:
    """DexScreener payload → one ``liquidity_depth`` observation.

    ``chain`` may also be supplied inside the payload as ``_chain`` — a
    convention for callers who pass raw responses around as plain dicts.
    """
    def obs(score: Optional[int], status: str, note: str) -> List[SourceObservation]:
        return [SourceObservation(
            SOURCE_ID, subject, raw if isinstance(raw, dict) else {},
            score, status, note, construct="liquidity_depth",
        )]

    if not isinstance(raw, dict):
        return obs(None, "malformed", "raw is not an object")

    pairs = raw.get("pairs")
    if pairs is None:
        return obs(None, "malformed", "payload has no 'pairs' key")
    if not isinstance(pairs, list) or not pairs:
        return obs(None, "unavailable", "vendor lists no trading pairs for this address")

    want = (chain or raw.get("_chain") or "").strip().lower()
    chains = sorted({str(p.get("chainId", "")).lower() for p in pairs if isinstance(p, dict)})
    if want:
        pairs = [p for p in pairs if str(p.get("chainId", "")).lower() == want]
        if not pairs:
            return obs(
                None, "unavailable",
                f"no pairs on chain {want!r}; vendor returned " + ", ".join(chains),
            )
    elif len(chains) > 1:
        return obs(
            None, "unavailable",
            "payload spans " + str(len(chains)) + " chains (" + ", ".join(chains)
            + ") and no chain was specified — refusing to guess which one was meant",
        )

    deepest = max(pairs, key=_usd)
    usd = _usd(deepest)
    if usd <= 0:
        return obs(None, "unavailable", "vendor reports no liquidity figure for any pair")

    risk = _band(usd)
    note = (
        f"deepest pool ${usd:,.0f} on {deepest.get('dexId', '?')}"
        f" ({deepest.get('chainId', '?')}) → risk {risk}"
    )
    if len(pairs) > 1:
        note += f"; {len(pairs)} pool(s) considered"
    return obs(risk, "ok", note)


def for_chain(chain: str) -> Callable[[str, Dict[str, Any]], List[SourceObservation]]:
    """Bind the adapter to one chain, for registering as e.g. ``dexscreener:ethereum``."""
    def _parse(subject: str, raw: Dict[str, Any]) -> List[SourceObservation]:
        return parse(subject, raw, chain=chain)
    return _parse
