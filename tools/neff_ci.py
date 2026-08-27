#!/usr/bin/env python3
"""How much measurement error does n_eff itself carry?

``neff.py`` reports a point estimate. A tool that sells "your confidence is
overstated" has no standing to report its own number without one, so this
resamples subjects with replacement and reports the percentile interval.

The resample is over *subjects*, not over the correlation matrix: a subject is
the unit that was sampled from the world, and every construct on it moves
together. Resampling cells instead would break that and give an interval that
is too narrow — the flattering direction, which is the one to avoid here.

Everything downstream of the resample is the same code path ``neff.py`` uses:
within-label Spearman, Fisher-z pooling, Kish n_eff. No new estimator.

Reads a corpus and writes nothing. No network.

    python tools/neff_ci.py .data/captured.jsonl
    python tools/neff_ci.py corpus/okx-live.jsonl --draws 2000
"""

from __future__ import annotations

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from redundancy import collect, load_rows  # noqa: E402
from neff import build_rho, neff  # noqa: E402


def neff_of(per_subject, names):
    """Point n_eff for one (possibly resampled) set of subjects.

    Unmeasurable pairs are decided in ``neff.build_rho``, not here. Inside a
    bootstrap draw the label is dropped on purpose — a resample missing a
    stratum is sampling noise, and it is the point estimate on the real data
    that has to be disclosed. ``main`` does that below.
    """
    rho, _pair_n, _unmeasured = build_rho(per_subject, names)
    return neff(names, rho)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--subset", nargs="*", default=None,
                    help="restrict to these constructs (default: all)")
    args = ap.parse_args()

    rows = load_rows(args.corpus)
    per_subject, _missing = collect(rows)

    names = sorted({c for scores, _m, _l in per_subject for c in scores})
    if args.subset:
        names = [n for n in names if n in set(args.subset)]
    if len(names) < 2:
        print("need at least two constructs", file=sys.stderr)
        return 1

    rho, _pair_n, unmeasured = build_rho(per_subject, names)
    point = neff(names, rho)

    rng = random.Random(args.seed)
    n = len(per_subject)
    draws = []
    for _ in range(args.draws):
        sample = [per_subject[rng.randrange(n)] for _ in range(n)]
        try:
            draws.append(neff_of(sample, names))
        except ZeroDivisionError:
            continue
    draws.sort()

    def pct(p):
        i = min(len(draws) - 1, max(0, int(round(p * (len(draws) - 1)))))
        return draws[i]

    lo, hi = pct(0.025), pct(0.975)
    med = pct(0.50)

    print()
    if unmeasured:
        print("! 以下配对没有足够大的层可测，按 0 计入——这会高估下面每一个数字：")
        for a, b in unmeasured:
            print(f"    {a} ~ {b}")
        print()
    print(f"语料 {args.corpus}  ·  {n} 个标的  ·  {len(names)} 个构念")
    print(f"重抽样 {len(draws)} 次（对标的重抽，不对格子重抽） · seed {args.seed}")
    print()
    print(f"  点估计            n_eff = {point:.2f} / {len(names)}")
    print(f"  bootstrap 中位数         {med:.2f}")
    print(f"  95% 区间          [{lo:.2f}, {hi:.2f}]     宽度 {hi - lo:.2f}")
    print(f"  相对宽度          ±{100 * (hi - lo) / 2 / point:.1f}%")
    print()
    ceiling = len(names)
    if hi < ceiling:
        print(f"  区间上界 {hi:.2f} < 源数 {ceiling}——"
              f"「这些源等价于 {ceiling} 个独立源」在 95% 水平上被排除。")
    else:
        print(f"  区间上界触到 {ceiling}——本语料无法排除「它们确实互不相干」。")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
