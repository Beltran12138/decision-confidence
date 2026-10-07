#!/usr/bin/env python3
"""How many independent tries was the winner really chosen from?

``record.py --trials`` charges for the size of a leaderboard, and
``window.py --trials`` for the number of strategy variants screened. Wallets
that rode the same rally, or parameter settings of one idea, are not that many
independent tries; this measures the discount instead of letting anyone assert
it — the number to pass as ``--effective-trials`` to either tool.

Two inputs, both already on disk, nothing written, no network:

    python tools/record_neff.py data/hl/pf_*.json --universe 47419   # Hyperliquid wallets
    python tools/record_neff.py --table variants.csv                 # any return series

``--table`` is a wide CSV or TSV: a header row, the first column a date, every
other column one variant's (or one wallet's) return on that date. Blank cells
are missing, not zero.

**Not ``neff.py``.** That one counts sources, where a lower count is the
cautious answer. Here a lower count shrinks a screening charge, so its two
conventions both flatter the strategy: |rho| counts a long/short mirror pair as
one try when the selector had two, and on short series noise reads as overlap.
This tool uses the positive part of rho and subtracts the noise floor. See
``track_record.effective_records``.

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


def read_table(path: str):
    """Wide CSV/TSV → ``{column: {date: return}}``. Blank cells are skipped."""
    import csv
    with open(path, encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        dialect = csv.excel_tab if sample.count("\t") > sample.count(",") else csv.excel
        rows = list(csv.reader(fh, dialect))
    if len(rows) < 2 or len(rows[0]) < 3:
        raise ValueError(f"{path}: need a header, a date column and at least two series")
    names = [h.strip() for h in rows[0][1:]]
    out = {n: {} for n in names}
    for line, row in enumerate(rows[1:], start=2):
        date = row[0].strip() if row else ""
        if not date:
            continue
        for name, cell in zip(names, row[1:]):
            cell = cell.strip()
            if cell == "":
                continue
            try:
                out[name][date] = float(cell.rstrip("%")) / (100.0 if cell.endswith("%") else 1.0)
            except ValueError:
                raise ValueError(f"{path}:{line}: {name} is not a number: {cell!r}") from None
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="Hyperliquid portfolio JSON files, one per wallet")
    ap.add_argument("--table", default=None, metavar="FILE",
                    help="wide CSV/TSV of return series instead: date column, then one column each")
    ap.add_argument("--window", default="perpMonth", choices=list(WINDOWS))
    ap.add_argument("--min-overlap", type=int, default=20, dest="min_overlap",
                    help="shared days a pair needs to be measured (default 20)")
    ap.add_argument("--universe", type=int, default=None, metavar="N",
                    help="size of the board they were drawn from, for the extrapolation")
    args = ap.parse_args()

    if bool(args.files) == bool(args.table):
        ap.error("give either portfolio files or --table, not both and not neither")
    series, unreadable = {}, []
    if args.table:
        try:
            series = read_table(args.table)
        except (OSError, ValueError) as exc:
            print(f"Invalid input: {exc}", file=sys.stderr)
            return 1
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
    print(f"Series measured      {o.n}" + (f"   ({len(empty)} empty, skipped)" if empty else ""))
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
    print(f"! {o.days} shared observations per pair: the correlations are noisy,")
    print("  and every bias named here points toward a smaller screening charge.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
