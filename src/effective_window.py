"""The same discount, applied to time instead of to sources.

``decision_confidence.py`` asks how many of your sources are answering the same
question. This asks the other half of it: how much of your *backtest* is
answering a question the model has not already read the answer to.

A model with a knowledge cutoff has seen what happened before that date. A
backtest that runs mostly before the cutoff is therefore not testing whether a
strategy works — it is testing whether the model remembers. The overlap is
arithmetic, not an estimate, and it is usually larger than people expect: a
2020-01 to 2025-06 backtest against an October 2024 cutoff is 86% open book.

The part that is *not* arithmetic, and the reason this module exists rather
than a one-line share calculation, is what happens next. The clean remainder is
a sample, and a sample has to be long enough to reject anything. Nine months of
monthly returns cannot distinguish a Sharpe of 1.0 from zero at any conventional
threshold. So a backtest can fail here in two different ways, and they call for
different responses:

* ``no_holdout``   — nothing is out of sample. The result is recall.
* ``underpowered`` — something is, but too little to support an inference.
  The correct reading is neither "it works" nor "it does not"; it is that this
  backtest has no power to tell you.

There is a second way the clean remainder gets spent, and it is not visible on
a calendar. If several strategy variants were screened and the best one kept,
the survivor's t-statistic is the maximum of many draws, not one draw. The bar
it has to clear is higher, and the sample needed to clear that bar is larger —
quadratically. :func:`selection_penalty` turns "how many did you try" from a
sentence in a footnote into a number that moves the requirement.

The count of trials is discounted the same way sources and months are. Fifty
variants of one strategy are not fifty independent tests, any more than five
vendors reading one on-chain field are five independent reads. ``neff.py`` is
the instrument for that discount; this module accepts its output and will not
invent one.

Limits are printed with the result rather than left in this docstring, for the
same reason ``neff.py`` prints its two:

* The length threshold uses t ≈ SR·√T (Lo 2002), which assumes i.i.d. returns.
  Monthly returns are typically positively autocorrelated, which inflates the
  naive t. **The requirement returned here is therefore a floor**: the real
  sample needed is longer, never shorter.
* Bonferroni controls the family-wise error rate and assumes the trials are
  independent. Correlated variants make it conservative; that is what
  ``effective_trials`` is for, and it must be *measured*, not asserted.
* **Declaring no trials is not a neutral default — it is a claim** that the
  strategy was specified before anyone looked. Self-reported counts also run
  low: nobody counts the variant they glanced at and abandoned.

Stdlib only. No network. Nothing here reads a price series — it reads three
dates and a count, which is the point: the disqualifying fact is available
before any performance number is computed.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from statistics import NormalDist
from typing import Any, Dict, Optional

__all__ = [
    "EvidenceWindow",
    "SelectionPenalty",
    "effective_window",
    "months_for_power",
    "selection_penalty",
    "T_THRESHOLD",
    "TARGET_SHARPE",
]

_Z = NormalDist()


# Conventional two-sigma bar. Deliberately the *permissive* choice: see the
# second limit in the module docstring — under strategy screening this is too
# low, and the caller is told so rather than silently corrected.
T_THRESHOLD = 2.0

# The Sharpe a caller claims to be testing for. 1.0 is a strong equity strategy;
# it needs four clean years. Halving it quadruples the requirement, which is the
# single most surprising number this module produces.
TARGET_SHARPE = 1.0


def _ym(value: str, field: str) -> int:
    """Parse ``YYYY-MM`` (or ``YYYY-MM-DD``) into a month index.

    Days are discarded. This module's resolution is a month because that is the
    resolution at which knowledge cutoffs are published — a cutoff is announced
    as "October 2024", not as a timestamp, and pretending to day precision on a
    quantity that is only known to the month would be false precision.
    """
    if not isinstance(value, str):
        raise ValueError(f"{field}: expected a YYYY-MM string, got {type(value).__name__}")
    parts = value.strip().split("-")
    if len(parts) not in (2, 3):
        raise ValueError(f"{field}: expected YYYY-MM or YYYY-MM-DD, got {value!r}")
    try:
        year, month = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"{field}: non-numeric date part in {value!r}") from None
    if not 1 <= month <= 12:
        raise ValueError(f"{field}: month {month} out of range in {value!r}")
    return year * 12 + (month - 1)


def months_for_power(
    target_sharpe: float = TARGET_SHARPE,
    t_threshold: float = T_THRESHOLD,
) -> int:
    """Months of clean sample needed for the t-statistic to clear the bar.

    From t ≈ SR·√T with T in years (Lo, "The Statistics of Sharpe Ratios",
    2002), so T = (t/SR)² years. The quadratic is the whole story: an
    ambitious strategy is cheap to demonstrate and a merely good one is not.

        SR 2.0 → 12 months      SR 1.0 → 48 months      SR 0.5 → 192 months

    Rounded up, because a partial month buys nothing.
    """
    if target_sharpe <= 0:
        raise ValueError("target_sharpe must be > 0")
    if t_threshold <= 0:
        raise ValueError("t_threshold must be > 0")
    return int(math.ceil((t_threshold / target_sharpe) ** 2 * 12))


@dataclass
class SelectionPenalty:
    """What screening variants costs, expressed in months of clean sample.

    ``effective_trials`` is the count after discounting for how alike the
    variants were. It defaults to ``trials`` — the conservative end — because
    the alternative is to assume independence, which is the error this whole
    repo exists to catch.
    """
    trials: int
    effective_trials: float
    alpha_base: float
    alpha_adjusted: float
    t_base: float
    t_adjusted: float
    months_base: int
    months_adjusted: int
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def selection_penalty(
    trials: int,
    *,
    effective_trials: Optional[float] = None,
    t_base: float = T_THRESHOLD,
    target_sharpe: float = TARGET_SHARPE,
) -> SelectionPenalty:
    """Raise the t bar for having picked a winner out of several attempts.

    The surviving variant's t-statistic is the maximum of ``n`` draws, not one
    draw, so the bar it must clear is higher. Bonferroni sets it by dividing
    the error rate the caller already accepted:

        α_base = 1 − Φ(t_base)          the one-sided rate implied by t_base
        α_adj  = α_base / n_eff
        t_adj  = Φ⁻¹(1 − α_adj)

    Deriving α from ``t_base`` rather than fixing it at 0.05 is what keeps
    ``trials=1`` an exact identity — the caller's own bar comes back unchanged,
    and the months requirement does not move.

    ``effective_trials`` is the number of *independent* attempts among the
    ``trials``. Fifty parameter settings of one strategy are not fifty
    independent tests. Pass a measured value (``tools/neff.py`` computes the
    same Kish quantity on the variants' return series); omit it and the full
    count is used, which over-penalises. That asymmetry is deliberate: the
    common failure is not declaring trials at all, not declaring too many.
    """
    if trials < 1:
        raise ValueError("trials must be >= 1")
    if t_base <= 0:
        raise ValueError("t_base must be > 0")
    n_eff = float(trials) if effective_trials is None else float(effective_trials)
    if n_eff < 1:
        raise ValueError("effective_trials must be >= 1")
    if n_eff > trials:
        raise ValueError(
            f"effective_trials {n_eff} exceeds trials {trials} — "
            "attempts cannot be more independent than they are numerous"
        )

    alpha_base = 1.0 - _Z.cdf(t_base)
    alpha_adjusted = alpha_base / n_eff
    # n_eff == 1 must be an exact identity. Going through cdf and back returns
    # t_base to within ~1e-9, and ceil() turns that dust into a whole extra
    # month: (2.0 + 1e-9)^2 * 12 rounds up to 49 rather than 48.
    t_adjusted = t_base if n_eff <= 1.0 else _Z.inv_cdf(1.0 - alpha_adjusted)

    months_base = months_for_power(target_sharpe, t_base)
    months_adjusted = months_for_power(target_sharpe, t_adjusted)

    if trials == 1:
        note = (
            "申报只试过一个变体。这是一个**主张**，不是中性默认——"
            "它断言策略在看数据之前就定好了。"
        )
    else:
        shrunk = "" if effective_trials is None else (
            f"（{trials} 个变体按 {n_eff:g} 次独立试验计，折扣需为实测所得，不能自行声明）"
        )
        note = (
            f"筛选了 {trials} 个变体{shrunk}，胜出者的 t 值是多次抽样的最大值。"
            f"门槛由 t≥{t_base:g} 抬到 t≥{t_adjusted:.2f}，"
            f"所需干净区间从 {months_base} 个月增至 {months_adjusted} 个月"
            f"（×{months_adjusted / months_base:.1f}）。"
        )
    return SelectionPenalty(
        trials=trials,
        effective_trials=n_eff,
        alpha_base=alpha_base,
        alpha_adjusted=alpha_adjusted,
        t_base=t_base,
        t_adjusted=t_adjusted,
        months_base=months_base,
        months_adjusted=months_adjusted,
        note=note,
    )


@dataclass
class EvidenceWindow:
    """How much of a backtest is out of sample, and whether that much can carry an inference.

    ``open_book_months`` counts the cutoff month itself as seen: a model whose
    knowledge ends in October 2024 has read October 2024.
    """
    cutoff: str
    start: str
    end: str
    total_months: int
    open_book_months: int
    effective_months: int
    open_book_share: float
    months_required: int
    target_sharpe: float
    t_threshold: float
    verdict: str          # no_holdout | underpowered | sufficient
    power_ratio: float    # effective_months / months_required
    note: str = ""
    # Present only when the caller declared how many variants were screened.
    # ``None`` means undeclared, which is treated as one attempt *and said so*
    # in ``note`` — silence here would be the same as claiming a single try.
    selection: Optional[SelectionPenalty] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        """One line that survives a projector."""
        bar = (f"t≥{self.selection.t_adjusted:.2f}（{self.selection.trials} 个变体校正后）"
               if self.selection is not None and self.selection.trials > 1
               else f"t≥{self.t_threshold:g}")
        return (
            f"{self.total_months} 个月的回测，"
            f"{self.open_book_months} 个月在模型的知识范围内（{self.open_book_share:.1%}），"
            f"剩下 {self.effective_months} 个月；"
            f"Sharpe {self.target_sharpe:g} 要在 {bar} 上成立需要 "
            f"{self.months_required} 个月 → {self.verdict}"
        )


VERDICT_NOTE = {
    "no_holdout": (
        "回测区间完全落在知识截止日之前。这段区间检验的不是策略能否盈利，"
        "而是模型记不记得。任何由它得出的结论都不可采信。"
    ),
    "underpowered": (
        "有干净区间，但短于可做统计推断的长度。正确结论既不是「有效」也不是「无效」，"
        "而是「这个回测没有分辨能力」——它不能拒绝任何假设。"
    ),
    "sufficient": (
        "干净区间达到该 Sharpe 所需的长度。这只解除了「长度」这一条限制，"
        "不构成策略有效的证据。"
    ),
}

# Printed with every result, not buried in the docstring. Same discipline as
# neff.py: the things that would make this number flattering travel with it.
LIMITS = (
    "阈值用 t ≈ SR·√T（Lo 2002），假设收益 i.i.d.；月度收益通常正自相关，"
    "会抬高朴素 t 值 —— 所以这里给出的所需长度是下限，真实需求只多不少。"
    " 变体筛选用 Bonferroni 校正，它控制族错误率且假设各次试验独立；"
    "变体彼此相关时偏保守，折扣须由 effective_trials 给出且应为实测值。"
)

# Said when the caller declared nothing. Silence about screening is not a
# neutral default; it is the strongest claim available.
UNDECLARED_SELECTION = (
    "⚠ 未申报变体筛选次数，按「一次成型」处理。这不是中性默认，"
    "而是断言策略在看数据之前就定好了。自报次数还系统性偏低——"
    "看一眼就放弃的那个变体，通常不会被算进去。"
)


def effective_window(
    cutoff: str,
    start: str,
    end: str,
    *,
    target_sharpe: float = TARGET_SHARPE,
    t_threshold: float = T_THRESHOLD,
    trials: Optional[int] = None,
    effective_trials: Optional[float] = None,
) -> EvidenceWindow:
    """Split a backtest at a model's knowledge cutoff and test the remainder for power.

    ``cutoff`` is the model's knowledge cutoff, ``start``/``end`` the backtest
    range, all as ``YYYY-MM``. The range is inclusive of both endpoints, which
    is how backtest ranges are quoted.

    ``trials`` is how many strategy variants were screened before this one was
    kept. Declaring it raises the t bar (see :func:`selection_penalty`) and so
    raises ``months_required``. Leaving it out changes no arithmetic but is
    recorded in ``note`` as the claim it is — the requirement shown is then
    valid only for a strategy nobody went looking for.

    Raises ``ValueError`` on unparseable dates or an inverted range. These are
    caller mistakes, not missing data — the library's usual "record it and lower
    confidence" path is for sources that failed to answer, and a malformed date
    is not a source.
    """
    c, s, e = _ym(cutoff, "cutoff"), _ym(start, "start"), _ym(end, "end")
    if e < s:
        raise ValueError(f"end {end!r} precedes start {start!r}")
    if trials is None and effective_trials is not None:
        raise ValueError("effective_trials given without trials — nothing to discount")

    total = e - s + 1
    # The cutoff month itself counts as seen; clamp to the range on both sides
    # so a cutoff outside the backtest degenerates cleanly to 0 or total.
    open_book = max(0, min(c, e) - s + 1)
    effective = total - open_book

    penalty = None
    if trials is None:
        required = months_for_power(target_sharpe, t_threshold)
    else:
        penalty = selection_penalty(
            trials,
            effective_trials=effective_trials,
            t_base=t_threshold,
            target_sharpe=target_sharpe,
        )
        required = penalty.months_adjusted

    if effective <= 0:
        verdict = "no_holdout"
    elif effective < required:
        verdict = "underpowered"
    else:
        verdict = "sufficient"

    return EvidenceWindow(
        cutoff=cutoff,
        start=start,
        end=end,
        total_months=total,
        open_book_months=open_book,
        effective_months=effective,
        open_book_share=open_book / total,
        months_required=required,
        target_sharpe=target_sharpe,
        t_threshold=t_threshold,
        verdict=verdict,
        power_ratio=effective / required,
        note=" ".join([
            VERDICT_NOTE[verdict],
            penalty.note if penalty is not None else UNDECLARED_SELECTION,
            LIMITS,
        ]),
        selection=penalty,
    )
