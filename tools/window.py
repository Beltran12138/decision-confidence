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
    LIMITS, UNDECLARED_SELECTION, VERDICT_NOTE,
    effective_window, months_for_power, remedies,
)

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
                    help="how many of those were independent — a measured number "
                         "(tools/neff.py computes it on the variants' return series). "
                         "Omit to charge the full count")
    args = ap.parse_args()

    try:
        w = effective_window(
            args.cutoff, args.start, args.end,
            target_sharpe=args.sharpe, t_threshold=args.t_threshold,
            trials=args.trials, effective_trials=args.effective_trials,
        )
    except ValueError as exc:
        print(f"输入无效：{exc}", file=sys.stderr)
        return 1

    print()
    print(f"模型知识截止  {w.cutoff}        回测区间  {w.start} .. {w.end}")
    print(f"目标 Sharpe   {w.target_sharpe:g}           要求 t ≥ {w.t_threshold:g}")
    sel = w.selection
    t_eff = sel.t_adjusted if sel is not None else w.t_threshold

    print()

    print("回测区间构成")
    print(f"  总长                 {w.total_months:>4} 个月")
    print(f"  开卷（模型已见）     {w.open_book_months:>4} 个月    {w.open_book_share:>6.1%}")
    print(f"  干净（可用于检验）   {w.effective_months:>4} 个月    {1 - w.open_book_share:>6.1%}")
    print()

    print("干净区间够不够支撑一个推断")
    print(f"  所需长度             {w.months_required:>4} 个月"
          f"    （t ≈ SR·√T，SR={w.target_sharpe:g} 时 T=({t_eff:.2f}/{w.target_sharpe:g})² 年）")
    print(f"  实有                 {w.effective_months:>4} 个月"
          f"    {w.power_ratio:>6.0%} of requirement")
    print()

    # The second way the clean remainder gets spent. Printed whether or not the
    # caller declared anything: silence about screening is itself a claim, and
    # showing nothing here would let it pass as an absence rather than a choice.
    print("变体筛选校正")
    if sel is None:
        for line in _wrap(UNDECLARED_SELECTION, 68):
            print(f"  {line}")
        print(f"  按一次成型计，所需长度维持 {w.months_required} 个月。申报请加 --trials N。")
    else:
        shown = (f"{sel.effective_trials:g} 次（实测折扣）"
                 if sel.effective_trials != sel.trials
                 else f"{sel.effective_trials:g} 次（未折扣，按全额计）")
        print(f"  申报变体数           {sel.trials:>4} 个")
        print(f"  计入独立试验         {shown}")
        print(f"  t 门槛               {sel.t_base:.2f}  →  {sel.t_adjusted:.2f}"
              f"    （Bonferroni：α {sel.alpha_base:.2e} → {sel.alpha_adjusted:.2e}）")
        print(f"  所需长度             {sel.months_base}  →  {sel.months_adjusted} 个月"
              f"    ×{sel.months_adjusted / sel.months_base:.1f}")
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
    # Dispatch lives in the library: three surfaces need it, and the browser
    # copy already drifted once by being written from the pre-fix version.
    print("那要怎么办")
    marks = "①②③④⑤⑥⑦⑧"
    for i, line in enumerate(remedies(w)):
        mark = marks[i] if i < len(marks) else "·"
        wrapped = _wrap(line, 74)
        print(f"  {mark} {wrapped[0]}")
        for cont in wrapped[1:]:
            print(f"     {cont}")
    print()

    bar_note = (f"（门槛用筛选校正后的 t≥{t_eff:.2f}）" if sel is not None
                and sel.t_adjusted != sel.t_base else "")
    print("同一段区间，只换目标 Sharpe" + bar_note)
    for sr in COMPARISON_SHARPES:
        need = months_for_power(sr, t_eff)
        mark = "sufficient" if w.effective_months >= need else "underpowered"
        if w.effective_months == 0:
            mark = "no_holdout"
        print(f"  SR {sr:<5g} 需要 {need:>4} 个月   实有 {w.effective_months:>3} 个月   {mark}")
    print("  （所需长度随 Sharpe 平方反比增长：目标减半，样本要四倍。）")
    print()

    print("! " + "\n  ".join(_wrap(LIMITS, 72)))
    print()
    return 0



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
    # Two thresholds, because a space and a full stop are not equally good
    # places to break. Chinese punctuation breaks early and reads fine. A space
    # in this text is usually hugging a number ("推到 2034-02 才够") and
    # breaking there strands two characters — but it is also the only thing
    # standing between a hard break and a bisected `effective_trials`, so it
    # stays, just later.
    soft_punct = max(1, int(width * 0.62))
    soft_space = max(1, int(width * 0.85))
    chars = list(text)
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
