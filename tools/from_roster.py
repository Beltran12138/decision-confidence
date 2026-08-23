#!/usr/bin/env python3
"""A pre-scored equity roster → the corpus format the rest of the tools read.

The roster this was written against is a public 87-ticker AI-supply-chain
table with three hand-assigned dimensions. It is the ordinary case for this
tool: someone already has a score table and wants to know how many independent
sources it is worth. The conversion is mechanical and lossless — it invents no
scores and drops no subjects.

Two things it does *not* paper over:

* **No outcome label.** That roster's gate has no measurable outcome yet, so
  every row is written with ``label: 0``. With one stratum, the within-label
  correlation the other tools compute collapses to the plain rank correlation —
  the upper-bound reading, not the controlled one. Downstream output says so;
  silently emitting a fake label to get two strata would be worse than useless.
* **Mixed scales.** Two dimensions are 1–5 integers, the third is a 0–1
  fraction. They go in as two separate ``scores`` entries with their own
  declared scales rather than being forced onto one axis, which would clamp the
  fraction to zero.

Reads one JSON file, writes one JSONL file. No network.

    python tools/from_roster.py ../prophetmap/data/ab-track/frozen-2026-08-17.json \
        -o .data/equity-roster.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys

# (field, [lo, hi]) — the caller's own scale for each column, declared not guessed.
COLUMNS = [
    (["physicalConstraint", "moatCapture"], [1, 5]),
    (["aiContribution"], [0, 1]),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roster", help="frozen roster JSON with a 'roster' array")
    ap.add_argument("-o", "--out", required=True, help="output .jsonl")
    ap.add_argument("--id-field", default="symbol")
    ap.add_argument("--pairwise", action="store_true",
                    help="keep rows that are missing a column (default drops them). "
                         "Changes the answer — see the note printed at the end.")
    args = ap.parse_args()

    all_fields = [f for fields, _ in COLUMNS for f in fields]

    doc = json.load(open(args.roster, encoding="utf-8"))
    rows = doc.get("roster") or doc.get("rows") or []
    if not rows:
        print("no roster array in that file", file=sys.stderr)
        return 1

    written = skipped = 0
    with open(args.out, "w", encoding="utf-8") as fh:
        for t in rows:
            subject = str(t.get(args.id_field) or "").strip()
            if not subject:
                skipped += 1
                continue
            if not args.pairwise and not all(
                    isinstance(t.get(f), (int, float)) for f in all_fields):
                skipped += 1
                continue
            sources = []
            for fields, scale in COLUMNS:
                present = {f: t[f] for f in fields
                           if isinstance(t.get(f), (int, float))}
                if not present:
                    continue
                sources.append({
                    "vendor": "scores",
                    "source_id": f"roster:{'+'.join(fields)}",
                    "raw": {"scores": present, "scale": scale},
                })
            if not sources:
                skipped += 1
                continue
            fh.write(json.dumps({
                "subject": subject,
                "label": 0,              # no measurable outcome; see module docstring
                "title": t.get("name") or subject,
                "layer": t.get("layer"),
                "sources": sources,
            }, ensure_ascii=False) + "\n")
            written += 1

    meta = doc.get("_meta", {})
    print(f"{written} 行已写入 {args.out}"
          + (f"（跳过 {skipped} 行）" if skipped else ""))
    if meta.get("frozenAt"):
        print(f"源冻结于 {meta['frozenAt']}")
    print()
    print("两条必须跟着数字一起走的口径说明：")
    print("  1. 该 roster 没有结局标签，全部写为 label=0 —— 只有一个分层，")
    print("     下游算出的是未控制结局的上界读法，不是「控制标签后」的读法。")
    if args.pairwise:
        print("  2. --pairwise：保留了缺列的行，每一对用各自可用的样本。")
        print("     这会和逐行剔除的口径给出不同的数（本 roster 上是 2.20 对 2.14）。")
    else:
        print("  2. 默认逐行剔除三列不全的行，与 prophetmap/scripts/construct-check.js")
        print("     同口径，所以两边的数应当逐位一致。加 --pairwise 可看另一种口径。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
