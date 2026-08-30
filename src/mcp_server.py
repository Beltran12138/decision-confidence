"""MCP server exposing the decision-confidence meta-layer.

Reference implementation, stdio transport. It is a **pure transform** of what
the caller supplies: no network calls, no API keys, no chain reads. Fetching
from the underlying risk vendors — and everything that comes with it
(credentials, rate limits, caching, PII policy) — stays with the host.

Two axes, and they are separate tools on purpose. ``decision_confidence``
discounts evidence **across sources** and takes a subject plus vendor payloads.
``knowledge_window`` discounts it **across time** and takes three dates and a
trial count. A subject and a backtest are not the same object, so folding the
second into the first would be exactly the category error this library exists
to catch. An agent reads them separately; neither answer needs the other.

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
from effective_window import effective_window, remedies  # noqa: E402

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
def knowledge_window(
    cutoff: str,
    start: str,
    end: str,
    target_sharpe: float = 1.0,
    t_threshold: float = 2.0,
    trials: Optional[int] = None,
    effective_trials: Optional[float] = None,
    lang: str = "en",
) -> Dict[str, Any]:
    """Check whether a backtest could have told anyone anything, before trusting it.

    Call this **before quoting or acting on any backtest number** — a Sharpe, a
    return, a hit rate — that came out of a historical simulation run by, or
    evaluated with, a language model. It is pure arithmetic on dates and a
    count: it needs no price series and no returns, so it can be run before the
    performance figures even exist, and it disqualifies a result on grounds that
    no amount of good performance repairs.

    Two things get charged against a backtest:

    1. **What the model already read.** A model with a knowledge cutoff has seen
       what happened before that date. Months of the backtest lying before the
       cutoff do not test whether a strategy works; they test whether the model
       remembers. A 2020-01..2025-06 backtest against an October 2024 cutoff is
       58 of 66 months open book.
    2. **What the search cost.** If several variants were screened and the best
       kept, the survivor's t-statistic is the maximum of many draws. The bar
       rises and the sample needed rises quadratically: ten variants take the
       requirement from 48 clean months to 97.

    Args:
        cutoff: The model's knowledge cutoff, ``YYYY-MM``. Use the cutoff of the
            model that produced or evaluated the strategy, not today's date.
        start: Backtest start, ``YYYY-MM``, inclusive.
        end: Backtest end, ``YYYY-MM``, inclusive.
        target_sharpe: The annualised Sharpe **being claimed**, not the one the
            backtest printed. It decides how long the clean remainder must be:
            2.0 needs 12 months, 1.0 needs 48, 0.5 needs 192. Halving it
            quadruples the requirement.
        t_threshold: The t bar the clean sample must clear. 2.0 by default.
        trials: How many strategy variants were screened before this one was
            kept. **If you do not know, ask the user — do not omit it.**
            Omitting it is not a neutral default: it asserts the strategy was
            specified before anyone looked, which is the strongest claim
            available here, and the result will say so. Self-reported counts
            also run low, because nobody counts the variant they glanced at and
            abandoned, so treat a small number sceptically rather than as
            precise.
        effective_trials: How many of those trials were *independent*. Fifty
            parameter settings of one strategy are not fifty independent tests.
            Pass this only when it has been **measured** — ``tools/neff.py``
            computes it from the variants' return series. Do not estimate it,
            and do not let a user assert it without a measurement: a freely
            chosen discount is an escape hatch, not a correction. Omitted, the
            full count is charged, which over-penalises on purpose.
        lang: Language for the prose fields (``note``, ``remedies``,
            ``summary``). ``en`` by default; ``zh`` for Chinese. The numbers
            and ``verdict`` are identical either way. An unrecognised tag falls
            back to English rather than failing — answering in the wrong
            language beats not answering.

    Returns:
        ``verdict`` is the headline and has three values:

        * ``no_holdout`` — nothing is out of sample. Any performance figure from
          this range is recall, not evidence. Do not quote it.
        * ``underpowered`` — some of it is out of sample, but too little to
          support an inference. **Report this as "this backtest cannot tell
          you", not as "the strategy does not work"** — it rejects nothing in
          either direction.
        * ``sufficient`` — length has stopped being the binding constraint.
          This is *not* evidence the strategy works; it means the result has
          become eligible to be examined.

        Also returned: ``open_book_months`` / ``effective_months`` /
        ``months_required`` and ``power_ratio`` (clean months as a fraction of
        what an inference needs); ``selection`` with the corrected t bar and
        what screening cost in months, or ``null`` when ``trials`` was omitted;
        ``note``, carrying the caveats that would otherwise make these numbers
        look better than they are; and ``remedies``, concrete actions ordered by
        what actually caused the failure.

        Surface ``remedies`` to the user rather than inventing advice. They are
        dispatched on the cause — extending the backtest, switching to a model
        with an earlier cutoff, and measuring variant overlap are different
        fixes for different problems, and some do not apply.

    Raises:
        ValueError: on unparseable dates, an inverted range, or a trial count
        that cannot be true (fewer than one, or more independent trials than
        trials). These are caller errors and are not absorbed into a plausible
        number.
    """
    window = effective_window(
        cutoff, start, end,
        target_sharpe=target_sharpe,
        t_threshold=t_threshold,
        trials=trials,
        effective_trials=effective_trials,
        lang=lang,
    )
    result = window.to_dict()
    result["remedies"] = remedies(window)
    result["summary"] = window.summary()
    return result


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
