"""Per-vendor adapters: one real vendor payload → one or more observations.

Phase 3 replaces shape sniffing (``decision_confidence.observe_from_raw``) with
an explicit registry. Shape sniffing guesses a normalizer from the keys present;
that is fine for a generic tool surface and wrong for production, because two
vendors can ship the same key with opposite polarity, and one vendor can carry
several *different* risk constructs in a single response.

Two properties every adapter here holds to:

* **No network.** An adapter is a pure function of ``(subject, raw)``. Fetching,
  API keys, retries, rate limits and caching belong to the caller. See
  ``examples/live_multi_source.py`` for the only networked code in this repo.
* **One payload may yield several observations.** Real vendors are not
  single-scalar. GoPlus carries both contract-authority findings and holder
  concentration; compliance vendors typically separate ownership risk from
  counterparty risk. Collapsing that to one number before the meta-layer sees
  it destroys exactly the information the meta-layer exists to reason about.

Every adapter declares a ``construct`` per observation (see
``decision_confidence.CONSTRUCTS``) so the engine can tell definitional
disagreement from factual disagreement.

All thresholds in these adapters are **rough, uncalibrated heuristics** — the
same honesty bar as the rest of the package. ``tools/calibrate.py`` is the
instrument for fixing that once labelled data is in hand.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from decision_confidence import SourceObservation, observe_from_raw

from adapters import dexscreener, funding, goplus, honeypot_is, okx

__all__ = [
    "AdapterRegistry",
    "DEFAULT_REGISTRY",
    "observe_vendor",
    "supported_vendors",
]

ParseFn = Callable[[str, Dict[str, Any]], List[SourceObservation]]


class AdapterRegistry:
    """Maps a vendor id to its parser. Deliberately tiny — a dict with a policy."""

    def __init__(self) -> None:
        self._parsers: Dict[str, ParseFn] = {}
        self._describe: Dict[str, str] = {}

    def register(self, vendor: str, parse: ParseFn, description: str = "") -> None:
        self._parsers[vendor] = parse
        self._describe[vendor] = description

    def has(self, vendor: str) -> bool:
        return vendor in self._parsers

    def vendors(self) -> Dict[str, str]:
        return dict(self._describe)

    def observe(
        self,
        vendor: Optional[str],
        source_id: str,
        subject: str,
        raw: Dict[str, Any],
    ) -> List[SourceObservation]:
        """Parse with the registered adapter, or fall back to shape sniffing.

        An unknown vendor is not an error — it degrades to
        ``observe_from_raw`` and says so in the note, so a caller integrating a
        vendor we have never seen still gets a usable observation rather than a
        crash.
        """
        if vendor and vendor in self._parsers:
            obs = self._parsers[vendor](subject, raw)
            for o in obs:
                if not o.source_id:
                    o.source_id = source_id
            return obs
        fallback = observe_from_raw(source_id, subject, raw)
        suffix = (
            f"no adapter registered for vendor {vendor!r}; used shape sniffing"
            if vendor
            else "no vendor declared; used shape sniffing"
        )
        fallback.note = f"{fallback.note} ({suffix})" if fallback.note else suffix
        return [fallback]


DEFAULT_REGISTRY = AdapterRegistry()
DEFAULT_REGISTRY.register(
    "goplus", goplus.parse,
    "GoPlus Token Security — authority flags, holder concentration, buy/sell simulation",
)
DEFAULT_REGISTRY.register(
    "honeypot_is", honeypot_is.parse,
    "honeypot.is v2 — buy/sell simulation, tradability",
)
DEFAULT_REGISTRY.register(
    "dexscreener", dexscreener.parse,
    "DexScreener — pool liquidity depth",
)
DEFAULT_REGISTRY.register(
    "funding", funding.parse,
    "Perp funding rates — carry cost, one observation per venue",
)
DEFAULT_REGISTRY.register(
    "okx", okx.parse,
    "OKX spot ticker — spread, book depth, turnover, range and 24h move "
    "off a single payload",
)


def observe_vendor(
    vendor: Optional[str],
    source_id: str,
    subject: str,
    raw: Dict[str, Any],
) -> List[SourceObservation]:
    """Convenience wrapper over :data:`DEFAULT_REGISTRY`."""
    return DEFAULT_REGISTRY.observe(vendor, source_id, subject, raw)


def supported_vendors() -> Dict[str, str]:
    return DEFAULT_REGISTRY.vendors()
