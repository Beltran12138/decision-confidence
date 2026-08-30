#!/usr/bin/env python3
"""How much of your backtest was the model allowed to read?

``neff.py`` asks how many of your sources are independent. This asks the same
question of your calendar: a backtest that ran mostly before the model's
knowledge cutoff is worth fewer independent months than its length suggests,
and the overlap is arithmetic — available before any performance number is
computed, and not an estimate.

Reads three dates and writes nothing. No network, no price series.

    python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06
    python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06 --trials 20
    python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06 --lang zh

The dates are required rather than defaulted. A default here would be a
fabricated parameter that later gets quoted as if someone had supplied it.

Output is English by default; ``--lang zh`` switches it. Strings live in
``src/messages.py`` so this file holds layout and the library holds argument.
Column widths are computed from the rendered labels rather than hardcoded,
because an English label is longer than its Chinese counterpart and a table
padded for one language comes apart in the other.

Two honest limits, printed with the result rather than buried here — the same
discipline ``neff.py`` applies to its two:

* The length requirement uses t ~ SR*sqrt(T) (Lo 2002), which assumes i.i.d.
  returns. Positive autocorrelation, normal in monthly returns, inflates the
  naive t — so the requirement shown is a floor, never generous.
* It assumes the strategy was specified before anyone looked. Variants screened
  on the open-book portion raise the bar; declare them with ``--trials``. This
  tool will not guess how many variants you tried, and omitting the flag is a
  claim rather than a neutral default.
"""

from __future__ import annotations

import argparse
import os
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from effective_window import (  # noqa: E402  (path set above)
    effective_window, months_for_power, remedies,
)
from messages import LANGS, resolve_lang, text  # noqa: E402

# Alternative targets shown alongside the caller's own, because the quadratic
# is the part nobody has internalised: halving the Sharpe you claim to be
# testing for quadruples the sample you need to show it.
COMPARISON_SHARPES = (2.0, 1.0, 0.5)

# Characters that must not start a line.
CLOSERS = "」』）〉》”’。，；、！？%"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--cutoff", required=True, metavar="YYYY-MM",
                    help="the model's knowledge cutoff")
    ap.add_argument("--start", required=True, metavar="YYYY-MM",
                    help="backtest start (inclusive)")
    ap.add_argument("--end", required=True, metavar="YYYY-MM",
                    help="backtest end (inclusive)")
    ap.add_argument("--sharpe", type=float, default=1.0,
                    help="the annualised Sharpe being tested for (default 1.0)")
    ap.add_argument("--t", type=float, default=2.0, dest="t_threshold",
                    help="t-statistic bar the clean sample must clear (default 2.0)")
    ap.add_argument("--trials", type=int, default=None, metavar="N",
                    help="how many strategy variants were screened before this one "
                         "was kept. Omitting it is a claim, not a neutral default")
    ap.add_argument("--effective-trials", type=float, default=None, metavar="K",
                    dest="effective_trials",
                    help="how many of those were independent — a measured number. "
                         "Omit to charge the full count")
    ap.add_argument("--lang", default=None, choices=list(LANGS),
                    help="output language (default en)")
    args = ap.parse_args()
    lang = resolve_lang(args.lang)

    try:
        w = effective_window(
            args.cutoff, args.start, args.end,
            target_sharpe=args.sharpe, t_threshold=args.t_threshold,
            trials=args.trials, effective_trials=args.effective_trials,
            lang=lang,
        )
    except ValueError as exc:
        print(text("cli.bad_input", lang, err=exc), file=sys.stderr)
        return 1

    sel = w.selection
    t_eff = sel.t_adjusted if sel is not None else w.t_threshold
    months = text("cli.unit_months", lang)
    # English glyphs are one cell where Chinese are two, so the same column
    # budget holds noticeably fewer ideas in English. Widths follow the script.
    W = 76 if lang == "en" else 66
    arrow = text("cli.arrow", lang)

    def table(rows):
        """Pad the label column to the widest rendered label, not to a constant."""
        pad = max(_cols(r[0]) for r in rows)
        for label, value, note in rows:
            gap = " " * (pad - _cols(label))
            line = f"  {label}{gap}   {value:>13}"
            print(f"{line}   {note}" if note else line)

    print()
    print(text("cli.header_dates", lang, cutoff=w.cutoff, start=w.start, end=w.end))
    print(text("cli.header_target", lang,
               target_sharpe=w.target_sharpe, t_threshold=w.t_threshold))
    print()

    print(text("cli.section_split", lang))
    table([
        (text("cli.row_total", lang), f"{w.total_months} {months}", ""),
        (text("cli.row_open", lang), f"{w.open_book_months} {months}",
         f"{w.open_book_share:>6.1%}"),
        (text("cli.row_clean", lang), f"{w.effective_months} {months}",
         f"{1 - w.open_book_share:>6.1%}"),
    ])
    print()

    print(text("cli.section_power", lang))
    table([
        (text("cli.row_required", lang), f"{w.months_required} {months}",
         text("cli.formula", lang, target_sharpe=w.target_sharpe, t_eff=t_eff)),
        (text("cli.row_have", lang), f"{w.effective_months} {months}",
         f"{w.power_ratio:>4.0%} " + text("cli.of_requirement", lang)),
    ])
    print()

    # Printed whether or not the caller declared anything: silence about
    # screening is itself a claim, and showing nothing here would let it pass
    # as an absence rather than a choice.
    print(text("cli.section_selection", lang))
    if sel is None:
        for line in _wrap(text("undeclared_selection", lang), W):
            print(f"  {line}")
        for line in _wrap(text("cli.sel_undeclared_tail", lang,
                               months_required=w.months_required), W):
            print(f"  {line}")
    else:
        counted_note = text("cli.sel_discounted" if sel.effective_trials != sel.trials
                            else "cli.sel_full", lang)
        table([
            (text("cli.sel_declared", lang), str(sel.trials), ""),
            (text("cli.sel_counted", lang), f"{sel.effective_trials:g}", counted_note),
            (text("cli.sel_bar", lang),
             f"{sel.t_base:.2f} {arrow} {sel.t_adjusted:.2f}",
             text("cli.sel_bonferroni", lang, alpha_base=sel.alpha_base,
                  alpha_adjusted=sel.alpha_adjusted)),
            (text("cli.row_required", lang),
             f"{sel.months_base} {arrow} {sel.months_adjusted}",
             f"x{sel.months_adjusted / sel.months_base:.1f}"),
        ])
    print()

    # The one line that has to survive a projector. Rules rather than a box:
    # CJK cell width varies by terminal, and a box that comes apart is worse
    # than no box. Same choice as neff.py.
    rule = "─" * 56
    print(rule)
    # Deliberately not wrapped: this is the line that has to read as one line.
    key = "cli.headline_no_holdout" if w.verdict == "no_holdout" else "cli.headline"
    print(text(key, lang, total_months=w.total_months,
               effective_months=w.effective_months,
               months_required=w.months_required))
    print(rule)
    print()

    print(f"{text('cli.section_verdict', lang)}  {w.verdict}")
    for line in _wrap(text("verdict." + w.verdict, lang), W - 6):
        print(f"      {line}")
    print()

    # Dispatch lives in the library: three surfaces need it, and the browser
    # copy already drifted once by being written from the pre-fix version.
    print(text("cli.section_remedies", lang))
    marks = "①②③④⑤⑥⑦⑧"
    for i, line in enumerate(remedies(w, lang)):
        mark = marks[i] if i < len(marks) else "·"
        wrapped = _wrap(line, W - 2)
        print(f"  {mark} {wrapped[0]}")
        for cont in wrapped[1:]:
            print(f"     {cont}")
    print()

    corrected = (text("cli.sweep_corrected", lang, t_eff=t_eff)
                 if sel is not None and sel.t_adjusted != sel.t_base else "")
    print(text("cli.section_sweep", lang) + corrected)
    for sr in COMPARISON_SHARPES:
        need = months_for_power(sr, t_eff)
        mark = ("no_holdout" if w.effective_months == 0
                else "sufficient" if w.effective_months >= need else "underpowered")
        print(text("cli.sweep_row", lang, sr=sr, need=need,
                   have=w.effective_months, verdict=mark))
    for line in _wrap(text("cli.sweep_note", lang), W):
        print(line if line.startswith(" ") else "  " + line)
    print()

    print("! " + "\n  ".join(_wrap(text("limits", lang), W - 2)))
    print()
    return 0


def _cols(text_: str) -> int:
    """Display columns, not characters.

    A CJK character occupies two cells, so wrapping on ``len()`` produced lines
    that measured 46 by the counter and 82 on the screen. Ambiguous-width
    characters are charged two, which is what they cost in a CJK locale — the
    conservative side, since over-charging wraps early and under-charging
    overflows.
    """
    return sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in text_)


def _wrap(text_: str, width: int):
    """Wrap on display columns, since CJK has no spaces to break on.

    Two thresholds, because a space and a full stop are not equally good places
    to break. Chinese punctuation breaks early and reads fine. A space is
    usually hugging a number ("run to 2034-02 to be") and breaking there strands
    two characters — but it is also the only thing standing between a hard break
    and a bisected `effective_trials`, so it stays, just later. English has no
    CJK punctuation, so it falls through to the space rule, which is correct for
    it.
    """
    out, line = [], ""
    soft_punct = max(1, int(width * 0.62))
    soft_space = max(1, int(width * 0.85))
    chars = list(text_)
    for i, ch in enumerate(chars):
        line += ch
        cols = _cols(line)
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if (cols >= soft_punct and ch in "。，；、！？") or (cols >= soft_space and ch == " "):
            out.append(line.strip())
            line = ""
        elif cols >= width and nxt not in CLOSERS:
            # Hard-breaking one character early strands a closing bracket at
            # the head of the next line, which reads as a typo.
            out.append(line.strip())
            line = ""
    if line.strip():
        out.append(line.strip())
    return out


if __name__ == "__main__":
    raise SystemExit(main())
