#!/usr/bin/env python3
"""Is this track record long enough to mean anything — as shown, and since you picked it?

``window.py`` splits a backtest at a model's knowledge cutoff. A leaderboard
wallet, a vault or a fund factsheet has no model, but it has the same split at
a different date: the day it was picked. See ``src/track_record.py``.

    python tools/record.py --start 2026-03 --end 2026-08 --sharpe 3 --trials 4800
    python tools/record.py --start 2026-03-01 --end 2026-09-30 --picked 2026-06-30 --sharpe 2
    python tools/record.py --start 2026-03 --end 2026-08 --sharpe 3 --lang zh

No cutoff, no network, no return series. ``--trials`` is the number of records
this one was chosen from; for a leaderboard, every wallet it ranked.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, HERE)

from messages import LANGS, resolve_lang, text  # noqa: E402
from track_record import track_record  # noqa: E402
from window import _wrap  # noqa: E402  (same column-aware wrapping)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", required=True, metavar="DATE",
                    help="first day or month of the record (YYYY-MM or YYYY-MM-DD)")
    ap.add_argument("--end", required=True, metavar="DATE",
                    help="last day or month of the record (inclusive)")
    ap.add_argument("--picked", default=None, metavar="DATE",
                    help="when it was chosen; omit and there is no out-of-sample reading")
    ap.add_argument("--sharpe", type=float, default=1.0,
                    help="the annualised Sharpe being tested for (default 1.0)")
    ap.add_argument("--t", type=float, default=2.0, dest="t_threshold",
                    help="t-statistic bar (default 2.0)")
    ap.add_argument("--trials", type=int, default=None, metavar="N",
                    help="how many records this one was chosen from. Omitting it is "
                         "a claim that it was the only one looked at")
    ap.add_argument("--effective-trials", type=float, default=None, metavar="K",
                    dest="effective_trials",
                    help="how many of those were independent — a measured number")
    ap.add_argument("--lang", default=None, choices=list(LANGS),
                    help="output language (default en)")
    args = ap.parse_args()
    lang = resolve_lang(args.lang)

    try:
        r = track_record(args.start, args.end, picked=args.picked,
                         target_sharpe=args.sharpe, t_threshold=args.t_threshold,
                         trials=args.trials, effective_trials=args.effective_trials,
                         lang=lang)
    except ValueError as exc:
        print(text("cli.bad_input", lang, err=exc), file=sys.stderr)
        return 1

    W = 76 if lang == "en" else 66

    def para(key, indent="  ", **kw):
        for line in _wrap(text(key, lang, **kw), W):
            print(indent + line)

    print()
    print(text("record.cli.header", lang, start=r.start, end=r.end,
               total_months=r.total_months, precision=r.precision))
    if r.picked:
        print(text("record.cli.picked", lang, picked=r.picked))
    print(text("record.cli.target", lang, target_sharpe=r.target_sharpe,
               t_threshold=r.t_threshold))
    print()

    for reading, title in ((r.as_shown, "record.cli.as_shown"),
                           (r.since_picked, "record.cli.since_picked")):
        if reading is None:
            continue
        print(text(title, lang))
        print(text("record.cli.row", lang, months=reading.months,
                   months_required=reading.months_required, t_bar=reading.t_bar,
                   power_ratio=reading.power_ratio, verdict=reading.verdict))
        sel = reading.selection
        if sel is not None and sel.trials > 1:
            print(text("record.cli.screened", lang, trials=sel.trials,
                       effective_trials=sel.effective_trials, t_base=sel.t_base,
                       t_adjusted=sel.t_adjusted, months_base=sel.months_base,
                       months_adjusted=sel.months_adjusted))
        print()

    para("record.verdict." + r.as_shown.verdict)
    if r.as_shown.selection is None:
        para("record.undeclared_universe")
    if r.since_picked is not None:
        para("record.since." + r.since_picked.verdict)
        para("record.cli.no_combined")
    else:
        para("record.no_pick")
    print()
    print("! " + "\n  ".join(_wrap(text("record.limits", lang), W - 2)))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
