#!/usr/bin/env python3
"""How much of your backtest was the model allowed to read?

``neff.py`` asks how many of your sources are independent. This asks the same
question of your calendar: a backtest that ran mostly before the model's
knowledge cutoff is worth fewer independent months than its length suggests,
and the overlap is arithmetic — available before any performance number is
computed, and not an estimate.

Reads three dates and writes nothing. No network, no price series.

    python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06
    python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06 --sharpe 0.5

The dates are required rather than defaulted. A default here would be a
fabricated parameter that later gets quoted as if someone had supplied it.

Two honest limits, printed with the result rather than buried here — the same
discipline ``neff.py`` applies to its two:

* The length requirement uses t ~ SR*sqrt(T) (Lo 2002), which assumes i.i.d.
  returns. Positive autocorrelation, normal in monthly returns, inflates the
  naive t — so the requirement shown is a floor, never generous.
* It assumes the strategy was specified before anyone looked. Variants screened
  on the open-book portion make t = 2.0 too low a bar; raise ``--t`` yourself.
  This tool will not guess how many variants you tried.
"""

from __future__ import annotations

import argparse
import os
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from effective_window import (  # noqa: E402  (path set above)
    LIMITS, VERDICT_NOTE, effective_window, months_for_power,
)

# Alternative targets shown alongside the caller's own, because the quadratic
# is the part nobody has internalised: halving the Sharpe you claim to be
# testing for quadruples the sample you need to show it.
COMPARISON_SHARPES = (2.0, 1.0, 0.5)

# Characters that must not start a line.
CLOSERS = "」』）〉》”’。，；、！？%"


def month_add(ym: str, months: int) -> str:
    """Shift a ``YYYY-MM`` string forward. Presentation only — no library state."""
    year, month = int(ym.split("-")[0]), int(ym.split("-")[1])
    total = year * 12 + (month - 1) + months
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


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
    args = ap.parse_args()

    try:
        w = effective_window(
            args.cutoff, args.start, args.end,
            target_sharpe=args.sharpe, t_threshold=args.t_threshold,
        )
    except ValueError as exc:
        print(f"输入无效：{exc}", file=sys.stderr)
        return 1

    print()
    print(f"模型知识截止  {w.cutoff}        回测区间  {w.start} .. {w.end}")
    print(f"目标 Sharpe   {w.target_sharpe:g}           要求 t ≥ {w.t_threshold:g}")
    print()

    print("回测区间构成")
    print(f"  总长                 {w.total_months:>4} 个月")
    print(f"  开卷（模型已见）     {w.open_book_months:>4} 个月    {w.open_book_share:>6.1%}")
    print(f"  干净（可用于检验）   {w.effective_months:>4} 个月    {1 - w.open_book_share:>6.1%}")
    print()

    print("干净区间够不够支撑一个推断")
    print(f"  所需长度             {w.months_required:>4} 个月"
          f"    （t ≈ SR·√T，SR={w.target_sharpe:g} 时 T=({w.t_threshold:g}/{w.target_sharpe:g})² 年）")
    print(f"  实有                 {w.effective_months:>4} 个月"
          f"    {w.power_ratio:>6.0%} of requirement")
    print()

    # The one line that has to survive a projector. Rules rather than a box:
    # CJK cell width varies by terminal, and a box that comes apart is worse
    # than no box. Same choice as neff.py.
    rule = "─" * 56
    print(rule)
    if w.verdict == "no_holdout":
        print(f"  ▶  {w.total_months} 个月的回测，没有一个月是模型没见过的")
    else:
        print(f"  ▶  {w.total_months} 个月的回测，能用来检验的是 {w.effective_months} 个月，"
              f"而你需要 {w.months_required} 个月")
    print(rule)
    print()

    print(f"判决  {w.verdict}")
    for line in _wrap(VERDICT_NOTE[w.verdict], 64):
        print(f"      {line}")
    print()

    # "Not comparable" without "so what do I do" is refusal dressed as
    # judgement — the failure this repo already caught in itself once. The
    # remedy is arithmetic too, so it costs nothing to state.
    print("那要怎么办")
    if w.verdict == "sufficient":
        for line in _wrap(
            f"干净区间已达 {w.months_required} 个月。长度这一条不再是限制"
            f"——但这不是策略有效的证据，只是它现在有资格被检验。", 70):
            print(f"  {line}")
    else:
        # Every line here is kept inside the rule above. A remedy that wraps on
        # a projector is read as a paragraph and skipped.
        need = w.months_required - w.effective_months
        print(f"  ① 只报干净段，把 {w.start} .. {w.cutoff} 标为开卷，不计入结论。")
        print(f"  ② 还差 {need} 个月：回测终点推到 {month_add(w.end, need)} 才够。")
        print(f"  ③ 或换知识截止更早的模型：截止 {month_add(w.cutoff, -need)} 及更早即够。")
        print(f"  ④ 或改声明——{w.effective_months} 个月只够证明 SR "
              f"{_sharpe_for(w.effective_months, w.t_threshold):.2f} 的策略。")
        print(f"     但那是要先兑现的主张，不是事后挑的档位。")
    print()

    print("同一段区间，只换目标 Sharpe")
    for sr in COMPARISON_SHARPES:
        need = months_for_power(sr, w.t_threshold)
        mark = "sufficient" if w.effective_months >= need else "underpowered"
        if w.effective_months == 0:
            mark = "no_holdout"
        print(f"  SR {sr:<5g} 需要 {need:>4} 个月   实有 {w.effective_months:>3} 个月   {mark}")
    print("  （所需长度随 Sharpe 平方反比增长：目标减半，样本要四倍。）")
    print()

    print("! " + "\n  ".join(_wrap(LIMITS, 72)))
    print()
    return 0


def _sharpe_for(months: int, t_threshold: float) -> float:
    """The Sharpe that the clean sample *would* be long enough to demonstrate."""
    if months <= 0:
        return float("inf")
    return t_threshold / ((months / 12.0) ** 0.5)


def _cols(text: str) -> int:
    """Display columns, not characters.

    A CJK character occupies two cells, so wrapping on ``len()`` produced lines
    that measured 46 by the counter and 82 on the screen. Ambiguous-width
    characters are charged two, which is what they cost in a CJK locale — the
    conservative side, since over-charging wraps early and under-charging
    overflows.
    """
    return sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in text)


def _wrap(text: str, width: int):
    """Wrap on display columns, since CJK has no spaces to break on.

    Breaks at the first punctuation past 70% of the width, and hard-breaks at
    the width itself. Punctuation-only breaking is what the first version did,
    and a sentence whose only full stop is at the end came out as one line
    longer than the rule above it.
    """
    out, line = [], ""
    soft = max(1, int(width * 0.7))
    chars = list(text)
    for i, ch in enumerate(chars):
        line += ch
        cols = _cols(line)
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if cols >= soft and ch in "。，；、！？ ":
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
