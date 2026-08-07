"""Calibrate RANGE_SPREAD without labels, by measuring what vendors actually do.

``RANGE_SPREAD = 40`` decides when two sources measuring the same construct are
reported as contradicting each other. It is the executing threshold of the
whole construct rule and, like every other number in this package, it was
chosen by judgement.

Unlike the verdict bands it can be calibrated **without any labelled data**,
because the question it answers is not "was this token a scam" but "how far
apart do two vendors asked the same question normally land". That distribution
is observable from any corpus of real payloads.

What to look for, in order of how much it would change the design:

1. **Where the mass is.** If ninety-odd percent of pairs sit under 15 and the
   cut is 40, the rule fires almost never and is decorative. If the median is
   already 35, the cut is inside the noise and the rule fires on nothing
   meaningful.
2. **Whether there is a knee.** A threshold is defensible when the distribution
   separates into ordinary vendor noise and a distinct tail. A smooth
   distribution means any cut is arbitrary, and the honest response is to say
   so rather than to pick the prettiest number.
3. **Whether disagreement carries subject information.** If scam and legitimate
   tokens produce the same spread distribution, then within-construct
   disagreement is telling you about the vendors, not about the subject — and
   "a spread inside one construct is a factual disagreement about the subject"
   is weaker than this library claims. That comparison needs labels, so it is
   reported only when the corpus has them.

Usage::

    python tools/agreement.py .data/captured.jsonl
    python tools/agreement.py .data/captured.jsonl --construct tradability

Caveat that limits every number below: two sources are only comparable when
they are genuinely independent. GoPlus and honeypot.is both reach `tradability`
by simulating a buy and a sell, so their agreement is partly a shared method
agreeing with itself. Correlated sources understate disagreement, and this
script cannot detect that — it is stated here so the result is not read as
stronger than it is.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from adapters import observe_vendor  # noqa: E402
from decision_confidence import RANGE_SPREAD, build_report  # noqa: E402


def collect(rows: List[Dict[str, Any]]):
    """Per construct: every subject where at least two sources produced a score."""
    pairs: Dict[str, List[Tuple[int, int, str, List[Tuple[str, int]]]]] = {}
    coverage: Dict[str, Dict[str, int]] = {}

    for row in rows:
        observations = []
        for entry in row.get("sources", []):
            vendor = entry.get("vendor")
            observations.extend(observe_vendor(
                vendor, entry.get("source_id") or vendor or "source",
                row["subject"], entry.get("raw") or {},
            ))
        report = build_report(row["subject"], observations)
        label = int(row.get("label", -1))

        for g in report.constructs:
            cov = coverage.setdefault(g.construct, {})
            cov[str(g.n_ok)] = cov.get(str(g.n_ok), 0) + 1
            if g.n_ok < 2:
                continue
            scored = [(o.source_id, o.normalized_0_100) for o in report.observations
                      if o.construct == g.construct and o.status == "ok"
                      and o.normalized_0_100 is not None]
            pairs.setdefault(g.construct, []).append(
                (g.spread, label, row["subject"], scored))
    return pairs, coverage


def _pct(sorted_vals: List[int], q: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, int(round(q * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def report_construct(construct: str, entries, cut: int) -> None:
    spreads = sorted(e[0] for e in entries)
    n = len(spreads)
    print()
    print(f"### {construct} — {n} subjects with two or more scoring sources")
    print(f"    min {spreads[0]}  p25 {_pct(spreads,.25)}  median {_pct(spreads,.5)}  "
          f"p75 {_pct(spreads,.75)}  p90 {_pct(spreads,.9)}  p95 {_pct(spreads,.95)}  "
          f"max {spreads[-1]}")

    print()
    print("    spread   count  share  cumulative")
    buckets = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 40), (40, 60), (60, 101)]
    cum = 0
    for lo, hi in buckets:
        c = sum(1 for s in spreads if lo <= s < hi)
        cum += c
        bar = "#" * int(round(40 * c / n)) if n else ""
        print(f"    {lo:>3}-{hi-1:<3} {c:>7} {c/n:>6.1%} {cum/n:>10.1%}  {bar}")

    print()
    print(f"    {'cut':>4} {'fires':>7} {'rate':>8}")
    for t in (10, 15, 20, 25, 30, 40, 50, 60):
        fires = sum(1 for s in spreads if s >= t)
        mark = "  <- current RANGE_SPREAD" if t == cut else ""
        print(f"    {t:>4} {fires:>7} {fires/n:>7.1%}{mark}")

    labelled = [e for e in entries if e[1] in (0, 1)]
    if labelled and len({e[1] for e in labelled}) == 2:
        bad = sorted(e[0] for e in labelled if e[1] == 1)
        good = sorted(e[0] for e in labelled if e[1] == 0)
        print()
        print("    does disagreement carry subject information?")
        print(f"      bad  n={len(bad):<5} median {_pct(bad,.5):>3}  p90 {_pct(bad,.9):>3}  "
              f"mean {sum(bad)/len(bad):.1f}")
        print(f"      good n={len(good):<5} median {_pct(good,.5):>3}  p90 {_pct(good,.9):>3}  "
              f"mean {sum(good)/len(good):.1f}")
        gap = abs(sum(bad)/len(bad) - sum(good)/len(good))
        if gap < 3:
            print(f"      means differ by {gap:.1f} — the spread is about the vendors,")
            print("      not about the subject. 'Within-construct disagreement is factual'")
            print("      is weaker than the README claims on this corpus.")
        else:
            print(f"      means differ by {gap:.1f}")

    worst = sorted(entries, key=lambda e: -e[0])[:5]
    print()
    print("    widest disagreements (check these by hand — that is the point):")
    for spread, label, subject, scored in worst:
        detail = "  ".join(f"{sid}={v}" for sid, v in scored)
        print(f"      spread {spread:>3}  label={label}  {subject[:20]}…  {detail}")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dataset", help="JSONL corpus of captured payloads")
    ap.add_argument("--construct", help="restrict to one construct")
    args = ap.parse_args(argv)

    rows = []
    with open(args.dataset, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                rows.append(json.loads(line))

    pairs, coverage = collect(rows)

    print(f"corpus: {len(rows)} subjects")
    print()
    print("### how many sources actually scored each construct")
    print(f"    {'construct':<24}{'0 sources':>11}{'1':>8}{'2+':>8}")
    for construct in sorted(coverage):
        cov = coverage[construct]
        zero = cov.get("0", 0)
        one = cov.get("1", 0)
        multi = sum(v for k, v in cov.items() if k.isdigit() and int(k) >= 2)
        print(f"    {construct:<24}{zero:>11}{one:>8}{multi:>8}")
    print()
    print("    A construct scored by one source has no second opinion, so the")
    print("    contradiction machinery never runs on it. That is a fact about")
    print("    this corpus's vendor set, not about the constructs.")

    targets = [args.construct] if args.construct else sorted(pairs)
    for construct in targets:
        if construct not in pairs:
            print(f"\n### {construct} — no subject had two scoring sources")
            continue
        report_construct(construct, pairs[construct], RANGE_SPREAD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
