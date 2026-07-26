"""MCP server exposing the decision-confidence meta-layer as one tool.

Reference implementation, stdio transport. It is a **pure transform** of the
payloads the caller supplies: no network calls, no API keys, no chain reads.
Fetching from the underlying risk vendors — and everything that comes with it
(credentials, rate limits, caching, PII policy) — stays with the host.

Run directly::

    python src/mcp_server.py

or, once installed with the optional extra (``pip install -e ".[mcp]"``)::

    risk-normalize-mcp

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

from decision_confidence import (  # noqa: E402
    build_report,
    observe_from_raw,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "The MCP server needs the 'mcp' package: pip install -e \".[mcp]\""
    ) from exc


mcp = FastMCP("risk-normalize")


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
        sources: One entry per source, ``{"source_id": str, "raw": object}``.
            ``raw`` is the vendor payload as received. Recognised shapes:
            ``{"fraud_probability": 0.0-1.0}``, ``{"tier": "LOW|MEDIUM|HIGH"}``,
            ``{"score": 0-100, "scale": "safety_0_100"}`` (flipped to risk),
            or ``{"score": 0-100}`` (already risk). Unrecognised or malformed
            payloads are marked as such and lower confidence — they are never
            guessed at.
        weights: Optional per-source weight keyed by ``source_id``. Sources
            default to equal weight; a weight of 0 drops a source from the
            composite.

    Returns:
        A decision report: every observation with its normalized 0-100 risk
        value (0 = safe, 100 = maximum risk), the weighted ``composite``, a
        ``verdict`` band (low/moderate/high/extreme, or ``unknown`` when no
        source was usable), a ``confidence`` label (high/medium/low) reflecting
        evidence quality rather than probability of correctness, any
        cross-source ``contradictions``, and an ``audit`` trail that makes the
        result reconstructible without re-fetching.
    """
    observations = []
    for entry in sources:
        if not isinstance(entry, dict):
            continue
        source_id = str(entry.get("source_id") or f"source_{len(observations) + 1}")
        raw = entry.get("raw")
        observations.append(observe_from_raw(source_id, subject, raw if isinstance(raw, dict) else {}))

    report = build_report(subject, observations, weights)
    return report.to_dict()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
