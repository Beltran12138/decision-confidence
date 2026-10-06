#!/usr/bin/env python3
"""How many independent wallets was the winner really chosen from?

``record.py --trials`` charges for the size of the leaderboard. Wallets that
all rode the same rally are not that many independent tries, and this measures
the discount instead of letting anyone assert it — the number to pass as
``--effective-trials``.

Reads Hyperliquid ``portfolio`` payloads already on disk (one JSON file per
wallet, fetched by you), writes nothing, no network:

    python tools/record_neff.py data/hl/pf_*.json
    python tools/record_neff.py data/hl/pf_*.json --universe 47419 --window perpMonth

Limits, printed with the result:

* About a month of daily returns per wallet. |rho| on 30 points is noisy, and
  the noise makes wallets look alike; the floor-corrected figure removes the
  null expectation and is the one to use.
* The wallets measured are whoever you fetched, usually the top of the board.
  Extrapolating to ``--universe`` assumes the board is as alike as its top,
  which it is not — the extrapolated count errs low, i.e. in the record's favour.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from adapters.hyperliquid import WINDOWS, daily_returns  # noqa: E402
from track_record import effective_records  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="portfolio JSON files, one per wallet")
    ap.add_argument("--window", default="perpMonth", choices=list(WINDOWS))
    ap.add_argument("--min-overlap", type=int, default=20, dest="min_overlap",
                    help="shared days a pair needs to be measured (default 20)")
    ap.add_argument("--universe", type=int, default=None, metavar="N",
                    help="size of the board they were drawn from, for the extrapolation")
    args = ap.parse_args()

    series, unreadable = {}, []
    for path in args.files:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, encoding="utf-8") as fh:
                series[name] = daily_returns(json.load(fh), args.window)
        except (ValueError, TypeError, AttributeError):
            # An error body saved as .json (rate limit, bad address) is not a
            # wallet with no trades; name it rather than measuring it as empty.
            unreadable.append(path)
    empty = sorted(k for k, v in series.items() if not v)
    try:
        o = effective_records(series, min_overlap=args.min_overlap, universe=args.universe)
    except ValueError as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"Wallets measured     {o.n}" + (f"   ({len(empty)} empty, skipped)" if empty else ""))
    if unreadable:
        print(f"Unreadable files     {len(unreadable)}   (not JSON payloads, e.g. "
              f"{os.path.basename(unreadable[0])})")
    print(f"Median shared days   {o.days}")
    print(f"Mean |rho|           {o.mean_abs_rho:.3f}   (noise alone gives ~{o.null_floor:.3f})")
    print(f"Unmeasured pairs     {len(o.unmeasured)}   (charged as independent: no unmeasured discount)")
    print()
    print(f"n_eff, raw rho+            {o.n_eff:7.1f}   flatters: noise counted as overlap")
    print(f"n_eff, noise floor removed  {o.n_eff_floor:7.1f}   <- pass as --effective-trials "
          f"for these {o.n}")
    if o.universe is not None:
        print(f"Extrapolated to {o.universe:<10,} {o.universe_n_eff:7.1f}   not measured; "
              f"errs low (top of a board is more alike than the board)")
    print()
    print("! About a month of daily returns per wallet: the correlations are noisy,")
    print("  and every bias named here points toward a smaller screening charge.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
