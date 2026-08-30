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

Both limits below are printed with the result rather than left in this
docstring, for the same reason ``neff.py`` prints its two:

* The length threshold uses t ≈ SR·√T (Lo 2002), which assumes i.i.d. returns.
  Monthly returns are typically positively autocorrelated, which inflates the
  naive t. **The requirement returned here is therefore a floor**: the real
  sample needed is longer, never shorter.
* It assumes the strategy was specified before anyone looked. If variants were
  screened on the open-book portion, choosing this one already used the
  contaminated data, and t = 2.0 is too low a bar (Harvey & Liu argue for ~3.0
  under multiple testing). Raise ``t_threshold`` yourself; this module will not
  guess how many variants you tried.

Stdlib only. No network. Nothing here reads a price series — it reads three
dates, which is the point: the disqualifying fact is available before any
performance number is computed.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

__all__ = [
    "EvidenceWindow",
    "effective_window",
    "months_for_power",
    "T_THRESHOLD",
    "TARGET_SHARPE",
]


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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        """One line that survives a projector."""
        return (
            f"{self.total_months} 个月的回测，"
            f"{self.open_book_months} 个月在模型的知识范围内（{self.open_book_share:.1%}），"
            f"剩下 {self.effective_months} 个月；"
            f"Sharpe {self.target_sharpe:g} 要在 t≥{self.t_threshold:g} 上成立需要 "
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
# neff.py: the two things that would make this number flattering travel with it.
LIMITS = (
    "阈值用 t ≈ SR·√T（Lo 2002），假设收益 i.i.d.；月度收益通常正自相关，"
    "会抬高朴素 t 值 —— 所以这里给出的所需长度是下限，真实需求只多不少。"
    " 且它假设策略是在看数据之前就定好的：若曾在开卷区间里筛选过变体，"
    "t=2.0 门槛偏低（多重检验下 Harvey & Liu 主张约 3.0），请自行调高 t_threshold。"
)


def effective_window(
    cutoff: str,
    start: str,
    end: str,
    *,
    target_sharpe: float = TARGET_SHARPE,
    t_threshold: float = T_THRESHOLD,
) -> EvidenceWindow:
    """Split a backtest at a model's knowledge cutoff and test the remainder for power.

    ``cutoff`` is the model's knowledge cutoff, ``start``/``end`` the backtest
    range, all as ``YYYY-MM``. The range is inclusive of both endpoints, which
    is how backtest ranges are quoted.

    Raises ``ValueError`` on unparseable dates or an inverted range. These are
    caller mistakes, not missing data — the library's usual "record it and lower
    confidence" path is for sources that failed to answer, and a malformed date
    is not a source.
    """
    c, s, e = _ym(cutoff, "cutoff"), _ym(start, "start"), _ym(end, "end")
    if e < s:
        raise ValueError(f"end {end!r} precedes start {start!r}")

    total = e - s + 1
    # The cutoff month itself counts as seen; clamp to the range on both sides
    # so a cutoff outside the backtest degenerates cleanly to 0 or total.
    open_book = max(0, min(c, e) - s + 1)
    effective = total - open_book
    required = months_for_power(target_sharpe, t_threshold)

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
        note=VERDICT_NOTE[verdict] + " " + LIMITS,
    )
