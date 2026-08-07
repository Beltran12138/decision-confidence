"""MCP server exposing the decision-confidence meta-layer as one tool.

Reference implementation, stdio transport. It is a **pure transform** of the
payloads the caller supplies: no network calls, no API keys, no chain reads.
Fetching from the underlying risk vendors — and everything that comes with it
(credentials, rate limits, caching, PII policy) — stays with the host.

Run directly::

    python src/mcp_server.py

or, once installed with the optional extra (``pip install -e ".[mcp]"``)::

    decision-confidence-mcp

Requires the ``mcp`` package; the core library in ``decision_confidence.py``
and ``normalize.py`` remains dependency-free.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Optional

# Support running the file directly from a checkout, not just as an installed
# module.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters import observe_vendor, supported_vendors  # noqa: E402
from decision_confidence import build_report  # noqa: E402

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "The MCP server needs the 'mcp' package: pip install -e \".[mcp]\""
    ) from exc


mcp = FastMCP("decision-confidence")


@mcp.tool()
def decision_confidence(
    subject: str,
    sources: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Combine several risk-source readings into one decision report.

    Use when more than one external risk source has been consulted about the
    same subject and the agent needs a single, auditable read on how much to
    trust the combination — especially when the sources may disagree.

    Args:
        subject: What is being assessed (token address, symbol, account —
            caller-defined; treated as an opaque label).
        sources: One entry per source,
            ``{"source_id": str, "raw": object, "vendor": str?}``. ``raw`` is
            the vendor payload exactly as received. When ``vendor`` names a
            registered adapter (call ``list_supported_vendors``) the payload is
            parsed with that vendor's real field names, and one payload may
            produce several observations covering different risk constructs.
            Without ``vendor``, generic shapes are recognised by their keys:
            ``{"fraud_probability": 0.0-1.0}``, ``{"tier": "LOW|MEDIUM|HIGH"}``,
            ``{"score": 0-100, "scale": "safety_0_100"}`` (flipped to risk),
            or ``{"score": 0-100}`` (already risk). Unrecognised or malformed
            payloads are marked as such and lower confidence — they are never
            guessed at.
        weights: Optional per-source weight keyed by ``source_id``. Weights
            apply *within* a construct; sources default to equal weight and a
            weight of 0 drops a source.

    Returns:
        A decision report. **Read ``constructs`` first** — it is one entry per
        thing actually measured, each with the only average that compares like
        with like, plus the within-construct ``spread`` and how many of its
        sources were usable.

        ``composite`` is a single 0-100 risk value (0 = safe, 100 = maximum
        risk) **only when every usable source measures the same construct**.
        When they do not, ``composite`` is ``null`` and ``verdict`` is
        ``not_comparable``: averaging a honeypot simulation with a contract-
        authority scan is a category error, not a noisy estimate, and no
        weighting fixes it. The old blended number is still reachable as
        ``blended_composite_unsafe`` — the name is the warning.

        Also returned: ``confidence`` (high/medium/low — evidence quality, not
        probability of correctness; capped at medium when a construct has no
        usable source at all, because ``unavailable`` is not ``safe``),
        ``contradictions``, and an ``audit`` trail that makes the result
        reconstructible without re-fetching.

        ``contradictions`` of kind ``range`` and ``polarity`` are raised only
        between sources sharing a construct — sources answering different
        questions cannot contradict each other. The split itself appears once
        as an ``info``-severity ``construct_mismatch``, which does **not**
        lower confidence.
    """
    observations = []
    for entry in sources:
        if not isinstance(entry, dict):
            continue
        source_id = str(entry.get("source_id") or f"source_{len(observations) + 1}")
        vendor = entry.get("vendor")
        raw = entry.get("raw")
        observations.extend(observe_vendor(
            str(vendor) if vendor else None,
            source_id,
            subject,
            raw if isinstance(raw, dict) else {},
        ))

    report = build_report(subject, observations, weights)
    return report.to_dict()


@mcp.tool()
def list_supported_vendors() -> Dict[str, str]:
    """Vendors with a dedicated adapter, mapped to what each one contributes.

    Call this before ``decision_confidence`` to decide whether to tag a source
    with ``vendor``. Anything not listed still works — it falls back to generic
    shape recognition and the observation says so in its note.
    """
    return supported_vendors()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
