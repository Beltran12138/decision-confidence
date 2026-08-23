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
from itertools import combinations

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from redundancy import collect, load_rows  # noqa: E402
from neff import key, neff, within_label_rho  # noqa: E402


def neff_of(per_subject, names):
    """Point n_eff for one (possibly resampled) set of subjects."""
    rho = {}
    for a, b in combinations(names, 2):
        r, _n = within_label_rho(per_subject, a, b)
        rho[key(a, b)] = 0.0 if r is None else r
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

    point = neff_of(per_subject, names)

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
