#!/usr/bin/env python3
"""How many independent sources did you actually buy?

``redundancy.py`` answers this one pair at a time. This answers it for the set:
it reduces the whole correlation matrix to a single count of effective sources,
using Kish's effective sample size,

    n_eff = n^2 / sum(rho_ij)          over the full matrix, diagonal included

which is the standard sampling-theory quantity for the same situation — an
average over correlated estimators is worth fewer independent draws than it has
terms. Apple's judge-panel paper reports the same statistic on nine frontier
models; using it here means the two numbers are directly comparable rather than
two house metrics that happen to rhyme.

Correlations are taken **within a label stratum**, the same as
``redundancy.py``: two metrics driven by one common cause look independent
until that cause is held fixed, and the resulting n_eff would be flattering.

Reads a corpus and writes nothing. No network.

    python tools/neff.py .data/captured.jsonl
    python tools/neff.py corpus/okx-live.jsonl

Two honest limits, printed with the result rather than buried here:

* A negative within-label rho *raises* n_eff above the number of sources. That
  is arithmetically correct — two anti-correlated estimators do carry more
  information than two independent ones — but it is also where a small-sample
  fluke does the most damage, so the pair is named in the output.
* Constructs on a coarse scale cannot reach a high rho, because most pairs are
  ties. Their independence is partly an artefact of resolution, and they are
  flagged the same way ``redundancy.py`` flags them.
"""

from __future__ import annotations

import argparse
import os
import sys
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from redundancy import (  # noqa: E402  (path set above)
    MECHANISM_PRIOR, MIN_STRATUM_N, THIN_SCALE, collect, fisher_pool, load_rows, spearman,
)


def within_label_rho(
    per_subject: Sequence[Tuple[Dict[str, int], Dict[str, str], int]],
    a: str,
    b: str,
) -> Tuple[Optional[float], int]:
    """Spearman between two constructs, computed inside each label and pooled.

    Pooling is Fisher-z weighted by stratum size — the same path
    ``redundancy.py`` takes, so the numbers here match the ones printed there.
    """
    strata: Dict[int, Tuple[List[float], List[float]]] = {}
    n_total = 0
    for scores, _verdicts, label in per_subject:
        if a in scores and b in scores:
            xs, ys = strata.setdefault(label, ([], []))
            xs.append(scores[a])
            ys.append(scores[b])
            n_total += 1
    pooled: List[Tuple[float, int]] = []
    for _label, (xs, ys) in strata.items():
        if len(xs) < MIN_STRATUM_N:
            continue
        r = spearman(xs, ys)
        if r is not None:
            pooled.append((r, len(xs)))
    return fisher_pool(pooled), n_total


def neff(names: Sequence[str], rho: Dict[Tuple[str, str], float]) -> float:
    n = len(names)
    if n == 0:
        return 0.0
    total = float(n)                       # diagonal: rho(i, i) = 1
    for a, b in combinations(names, 2):
        total += 2.0 * rho[key(a, b)]
    if total <= 0:
        return float("inf")
    return (n * n) / total


def key(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def greedy_order(names: Sequence[str], rho: Dict[Tuple[str, str], float]) -> List[str]:
    """Buy in the order that adds the most effective sources at each step.

    This is the best case for the buyer, not the average one: it assumes you
    already knew which source to add next, which you did not. The saturation it
    still shows is therefore a floor on the problem, not the worst case.
    """
    chosen: List[str] = []
    remaining = list(names)
    while remaining:
        best, best_val = None, float("-inf")
        for c in remaining:
            val = neff(chosen + [c], rho)
            if val > best_val:
                best, best_val = c, val
        chosen.append(best)
        remaining.remove(best)
    return chosen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("corpus", help="JSONL of captured payloads with labels")
    ap.add_argument("--subset-size", type=int, default=3,
                    help="size of the best/worst subset comparison (default 3)")
    args = ap.parse_args()

    rows = load_rows(args.corpus)
    per_subject, _missing = collect(rows)

    names = sorted({c for scores, _v, _l in per_subject for c in scores})
    if len(names) < 2:
        print("need at least two constructs with scores", file=sys.stderr)
        return 1

    rho: Dict[Tuple[str, str], float] = {}
    pair_n: Dict[Tuple[str, str], int] = {}
    unmeasured: List[Tuple[str, str]] = []
    for a, b in combinations(names, 2):
        r, n = within_label_rho(per_subject, a, b)
        pair_n[key(a, b)] = n
        if r is None:
            # No stratum large enough. Treating it as 0 would silently claim
            # independence, which is the error this whole repo exists to catch.
            unmeasured.append((a, b))
            rho[key(a, b)] = 0.0
        else:
            rho[key(a, b)] = r

    # Coarse scales, same test redundancy.py applies.
    thin = [c for c in names
            if len({s[c] for s, _v, _l in per_subject if c in s}) < THIN_SCALE]

    print()
    print(f"语料 {args.corpus}  ·  {len(rows)} 行  ·  {len(names)} 个构念")
    labels = sorted({l for _s, _v, l in per_subject})
    counts = {l: sum(1 for _s, _v, x in per_subject if x == l) for l in labels}
    print("分层 " + " / ".join(f"label={l}: {counts[l]}" for l in labels)
          + "   （相关性在层内计算后合并）")
    print()

    print("两两残余相关  (within-label)")
    for a, b in sorted(combinations(names, 2), key=lambda p: -rho[key(*p)]):
        r = rho[key(a, b)]
        mark = ""
        if (a, b) in unmeasured:
            mark = "   ! 无足够大的层，按 0 计入"
        elif r < 0:
            mark = "   ! 负相关，会把 n_eff 抬到源数之上"
        shared = (MECHANISM_PRIOR.get(a) and
                  MECHANISM_PRIOR.get(a) == MECHANISM_PRIOR.get(b))
        if shared:
            mark += f"   [先验：共享机制 {MECHANISM_PRIOR[a]}]"
        print(f"  {a:<20} ~ {b:<20} {r:+.2f}   n={pair_n[key(a, b)]}{mark}")
    print()

    total = neff(names, rho)
    n = len(names)
    print("有效源数  (Kish n_eff)")
    print(f"  全部 {n} 个        n_eff = {total:.2f} / {n}      效率 {total / n * 100:.0f}%")
    print()

    # The one line that has to survive a projector. Rules rather than a box:
    # CJK cell width varies by terminal, and a box that comes apart is worse
    # than no box.
    rule = "─" * 56
    print(rule)
    print(f"  ▶  买了 {n} 个源，实际拿到 {total:.2f} 个")
    print(rule)
    print()

    print("按最优顺序逐个买入")
    order = greedy_order(names, rho)
    prev = 0.0
    for i, c in enumerate(order, 1):
        val = neff(order[:i], rho)
        print(f"  {i} 个源  {c:<20} n_eff = {val:.2f}   增量 {val - prev:+.2f}")
        prev = val
    print("  （这是买方的最好情形：假设每一步都恰好选对了下一个。真实采购只会更差。）")
    print()

    k = args.subset_size
    if 2 <= k < n:
        subsets = [(neff(list(c), rho), list(c)) for c in combinations(names, k)]
        subsets.sort(reverse=True)
        best_v, best_s = subsets[0]
        worst_v, worst_s = subsets[-1]
        print(f"同样是 {k} 个源，选法决定一切")
        print(f"  最好  {best_v:.2f}   " + " + ".join(best_s))
        print(f"  最差  {worst_v:.2f}   " + " + ".join(worst_s))
        if worst_v > 0:
            print(f"  差 {best_v / worst_v:.2f} 倍——而两份账单上都写着「{k} 个数据源」。")
        print()

    if thin:
        print("! 以下构念的分档过粗（不同取值少于 "
              f"{THIN_SCALE} 个），它们的低相关部分是分辨率造成的：")
        print("    " + ", ".join(thin))
        print()
    if unmeasured:
        print("! 以下配对没有足够大的层可测，按 0 计入——这会高估 n_eff：")
        for a, b in unmeasured:
            print(f"    {a} ~ {b}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
