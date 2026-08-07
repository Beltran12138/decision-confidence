"""The whole argument in one command: not all disagreement is the same kind.

Case A — four sources, four constructs. GoPlus says USDT's issuer can mint,
pause and blacklist; honeypot.is says it trades perfectly. Both are true. The
68-point gap between them is **definitional**: they answered different
questions, so there is no composite to compute and no contradiction to report.

Case B — several venues, one construct. Every perp venue is answering the same
question — what does holding this cost — and they return different numbers.
That gap is **factual**, so it averages legally, and the spread is reported as
a real contradiction.

A library that only produced Case A would be unfalsifiable: "not comparable"
as a universal answer is a refusal, not a judgment. Case B is what makes the
rule mean something.

Run::

    python examples/two_kinds_of_disagreement.py

No network, no keys. Case A replays vendor payloads captured 2026-07-26
(``tests/fixtures/``). Case B uses **illustrative** funding rates — they are
not live and are not a market claim; the point is the shape of the output.
"""

from __future__ import annotations

import json
import os
import sys
from typing import List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from adapters import observe_vendor  # noqa: E402
from decision_confidence import DecisionReport, SourceObservation, build_report  # noqa: E402

USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"

# Illustrative only — chosen to show a wide but plausible cross-venue spread.
ILLUSTRATIVE_RATES = [
    {"venue": "binance", "rate": 0.00001},
    {"venue": "okx", "rate": 0.00008},
    {"venue": "gate", "rate": 0.00012},
    {"venue": "hyperliquid", "rate": 0.00004},
    {"venue": "dydx", "rate": -0.00002},
]


def _fixture(vendor: str, key: str):
    with open(os.path.join(ROOT, "tests", "fixtures", f"{vendor}_{key}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def case_a() -> DecisionReport:
    observations: List[SourceObservation] = []
    for vendor in ("goplus", "honeypot_is", "dexscreener"):
        payload = _fixture(vendor, "usdt")
        if vendor == "dexscreener":
            payload["_chain"] = "ethereum"
        observations.extend(observe_vendor(vendor, vendor, USDT, payload))
    return build_report(USDT, observations)


def case_b() -> DecisionReport:
    obs = observe_vendor("funding", "funding", "PEPE", {"rates": ILLUSTRATIVE_RATES})
    return build_report("PEPE", obs)


def render(title: str, subtitle: str, report: DecisionReport) -> None:
    print("\n" + "=" * 78)
    print(title)
    print(subtitle)
    print("=" * 78)
    print(f"{'construct':<22}{'risk':>6}  {'verdict':<14}{'sources':<9}spread")
    print("-" * 78)
    for g in report.constructs:
        score = "-" if g.score is None else str(g.score)
        cover = f"{g.n_ok}/{g.n_ok + g.n_unusable}"
        spread = str(g.spread) if g.n_ok >= 2 else ""
        print(f"{g.construct:<22}{score:>6}  {g.verdict:<14}{cover:<9}{spread}")
    print("-" * 78)
    if report.composite is None and report.verdict == "not_comparable":
        print(f"composite : none  (blended_composite_unsafe={report.blended_composite_unsafe} "
              "— a category error, exposed under a name that says so)")
    else:
        print(f"composite : {report.composite}   verdict: {report.verdict}")
    print(f"confidence: {report.confidence}")
    for c in report.contradictions:
        print(f"  [{c.kind}/{c.severity}] {c.detail}")


def main() -> int:
    render(
        "CASE A — definitional disagreement (four constructs)",
        "real vendor payloads, captured 2026-07-26",
        case_a(),
    )
    render(
        "CASE B — factual disagreement (one construct, many venues)",
        "ILLUSTRATIVE funding rates — not live, not a market claim",
        case_b(),
    )
    print("\n" + "-" * 78)
    print("Same engine, opposite outcomes. A is refused a composite because the")
    print("sources answered different questions. B is given one, and its spread")
    print("is reported as a real contradiction, because they answered the same")
    print("question differently. That asymmetry is the product.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
