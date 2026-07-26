"""Threshold calibration harness — the instrument, not the result.

Every threshold in this package (verdict bands, contradiction spreads, adapter
penalties) is a rough heuristic chosen by judgement. That is stated plainly in
the README and it remains true. What has been missing is the *means* to fix it:
a repeatable way to point the pipeline at labelled subjects and read off what
each cut-off actually buys.

This script is that means. It does **not** ship a calibrated model, and running
it on the bundled sample proves nothing about real-world accuracy — the sample
is synthetic and exists only to exercise the harness.

Input format — one JSON object per line::

    {"subject": "0x…", "label": 1,
     "sources": [{"vendor": "goplus", "raw": { …payload as received… }},
                 {"vendor": "honeypot_is", "raw": { … }}]}

``label``: 1 = known bad (rug / scam / honeypot), 0 = known good. Payloads are
whatever the vendors returned when the subject was captured — the harness does
no fetching, same rule as the library.

Usage::

    python tools/calibrate.py tools/calibration_sample.jsonl
    python tools/calibrate.py mydata.jsonl --step 5

Candidate labelled datasets, none of them bundled here (licences and sizes
differ, and each needs payloads re-captured per subject):

* **TM-RugPull** (arXiv 2602.21529) — 1,028 projects across five EVM chains,
  2016-2025, built specifically to resist temporal leakage by cutting features
  at a project-midpoint boundary. The most defensible option for this use.
* **RPHunter** (arXiv 2506.18398) — 645 manually analysed rug-pull incidents,
  plus ~4.8k weaker labels from its own detector.
* **Solana rug-pull benchmark** (arXiv 2603.24625) — 117 manually verified
  tokens (Benchmark-117) and 76,469 pipeline-labelled candidates.

A caveat worth stating before anyone reports numbers from this: those label sets
are assembled *after* the fact from on-chain outcomes, so they are biased toward
scams that completed. Calibrating against them tunes for post-mortem
recognition, which is not the same problem as pre-commitment warning.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from adapters import observe_vendor  # noqa: E402
from decision_confidence import build_report  # noqa: E402


def load_rows(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: {exc}") from exc
            if "label" not in row or "subject" not in row:
                raise SystemExit(f"{path}:{lineno}: row needs 'subject' and 'label'")
            rows.append(row)
    return rows


def score_rows(rows: List[Dict[str, Any]]) -> Tuple[List[Tuple[Optional[int], int]], Dict[str, Dict[str, int]]]:
    """Returns ``([(composite, label)], per-source status counts)``."""
    scored: List[Tuple[Optional[int], int]] = []
    status_counts: Dict[str, Dict[str, int]] = {}
    for row in rows:
        observations = []
        for entry in row.get("sources", []):
            vendor = entry.get("vendor")
            observations.extend(observe_vendor(
                vendor, entry.get("source_id") or vendor or "source",
                row["subject"], entry.get("raw") or {},
            ))
        report = build_report(row["subject"], observations)
        scored.append((report.composite, int(row["label"])))
        for o in report.observations:
            bucket = status_counts.setdefault(o.source_id, {})
            bucket[o.status] = bucket.get(o.status, 0) + 1
    return scored, status_counts


def confusion(scored, threshold: int) -> Tuple[int, int, int, int]:
    tp = fp = tn = fn = 0
    for composite, label in scored:
        if composite is None:
            # Unscoreable is not a prediction. Counted separately, never
            # silently folded into "predicted safe".
            continue
        predicted_bad = composite >= threshold
        if predicted_bad and label == 1:
            tp += 1
        elif predicted_bad and label == 0:
            fp += 1
        elif not predicted_bad and label == 1:
            fn += 1
        else:
            tn += 1
    return tp, fp, tn, fn


def _ratio(num: int, den: int) -> float:
    return num / den if den else 0.0


def sweep(scored, step: int) -> None:
    unscoreable = sum(1 for c, _ in scored if c is None)
    usable = len(scored) - unscoreable
    print(f"subjects: {len(scored)}  scoreable: {usable}  unscoreable: {unscoreable}")
    if not usable:
        print("nothing to sweep — every subject was unscoreable")
        return
    print()
    print(f"{'cut':>4} {'TP':>4} {'FP':>4} {'TN':>4} {'FN':>4} "
          f"{'precision':>10} {'recall':>8} {'F1':>7}")
    print("-" * 56)
    best = (0.0, None)
    for threshold in range(0, 101, step):
        tp, fp, tn, fn = confusion(scored, threshold)
        precision = _ratio(tp, tp + fp)
        recall = _ratio(tp, tp + fn)
        f1 = _ratio(2 * precision * recall, precision + recall) if (precision + recall) else 0.0
        print(f"{threshold:>4} {tp:>4} {fp:>4} {tn:>4} {fn:>4} "
              f"{precision:>10.3f} {recall:>8.3f} {f1:>7.3f}")
        if f1 > best[0]:
            best = (f1, threshold)
    print("-" * 56)
    if best[1] is not None:
        print(f"best F1 {best[0]:.3f} at composite >= {best[1]}")
    print()
    print("Read this as a diagnostic, not a verdict. A single cut-off on the "
          "composite\nignores confidence and contradictions, which is exactly "
          "what the layer argues\nagainst — it is here because it is the "
          "conventional first thing to measure.")


def report_coverage(status_counts: Dict[str, Dict[str, int]]) -> None:
    if not status_counts:
        return
    print("\nper-source status counts (how often each source was usable at all):")
    for source_id in sorted(status_counts):
        counts = status_counts[source_id]
        total = sum(counts.values())
        parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        ok_rate = _ratio(counts.get("ok", 0), total)
        print(f"  {source_id:<26} ok-rate {ok_rate:>6.1%}   {parts}")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dataset", help="JSONL file of labelled subjects with captured payloads")
    ap.add_argument("--step", type=int, default=10, help="threshold step (default 10)")
    args = ap.parse_args(argv)

    rows = load_rows(args.dataset)
    scored, status_counts = score_rows(rows)
    sweep(scored, max(1, args.step))
    report_coverage(status_counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
