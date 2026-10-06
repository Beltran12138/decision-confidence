"""The time-axis discount for a track record nobody's model had read.

``effective_window`` splits a backtest at a model's knowledge cutoff. A copy-
trading leaderboard, a vault's history or a fund's factsheet has no model and
no cutoff — but it has the same split, at a different date: **the day you
picked it.** Everything up to that day is the record that got it picked. It was
in front of the person choosing, the way pre-cutoff months were in front of the
model. Only what happened after the pick tests the choice.

So a record can be read two ways, and they are not interchangeable:

* **As shown** — judge the record that got it chosen. That is a legitimate
  test only if you charge for the choosing: a wallet that tops a list of 4,800
  is the maximum of 4,800 draws, and the bar rises accordingly. Same Bonferroni
  correction as :func:`effective_window.selection_penalty`, same refusal to
  treat an undeclared count as one.
* **Since picked** — judge only what happened after. No screening charge,
  because nothing after the pick was used to make it. Usually short.

Both are printed. Neither is promoted over the other, and there is no combined
verdict: taking whichever reading passes is itself a choice between two tests.

Dates are ``YYYY-MM`` or ``YYYY-MM-DD``. A leaderboard record is often measured
in weeks, and month resolution — right for a cutoff announced as "October
2024" — would floor a 45-day record to one month. Day precision is used only
when *every* supplied date has a day; mixing the two falls back to months
rather than inventing the missing days.

Limits travel with the result, as everywhere else in this repo. One is new
here and it does not point the safe way: on-chain books earn in bursts. A
market-making vault can make a large share of its lifetime profit on two days,
and t ≈ SR·√T assumes nothing like that. **The requirement is a floor, and for
this kind of record it is a generous one.**

Stdlib only. No network. Reads dates and a count, never a return series.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from effective_window import (
    T_THRESHOLD, TARGET_SHARPE, SelectionPenalty, months_for_power, selection_penalty,
)
from messages import DEFAULT_LANG, resolve_lang, text
from trial_count import TrialCount

__all__ = ["Reading", "RecordOverlap", "TrackRecord", "effective_records", "track_record"]

# Average Gregorian month in days. Used only to express a day-precision length
# in the same unit as ``months_for_power``.
_MONTH_DAYS = 365.2425 / 12


def _parse(value: str, field: str) -> Tuple[int, int, Optional[int]]:
    if not isinstance(value, str):
        raise ValueError(f"{field}: expected YYYY-MM or YYYY-MM-DD, got {type(value).__name__}")
    parts = value.strip().split("-")
    if len(parts) not in (2, 3):
        raise ValueError(f"{field}: expected YYYY-MM or YYYY-MM-DD, got {value!r}")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        raise ValueError(f"{field}: non-numeric date part in {value!r}") from None
    year, month = nums[0], nums[1]
    if not 1 <= month <= 12:
        raise ValueError(f"{field}: month {month} out of range in {value!r}")
    day = nums[2] if len(nums) == 3 else None
    if day is not None:
        try:
            _dt.date(year, month, day)
        except ValueError as exc:
            raise ValueError(f"{field}: {exc} in {value!r}") from None
    return year, month, day


@dataclass
class Reading:
    """One way of reading the record: which span, against which bar."""
    name: str               # as_shown | since_picked
    months: float
    months_required: int
    t_bar: float
    verdict: str            # no_holdout | underpowered | sufficient
    power_ratio: float
    selection: Optional[SelectionPenalty] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrackRecord:
    start: str
    end: str
    picked: Optional[str]
    precision: str          # day | month
    total_months: float
    target_sharpe: float
    t_threshold: float
    as_shown: Reading
    since_picked: Optional[Reading]
    note: str = ""
    lang: str = DEFAULT_LANG

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def readings(self) -> List[Reading]:
        return [self.as_shown] + ([self.since_picked] if self.since_picked else [])


def _verdict(months: float, required: int) -> str:
    if months <= 0:
        return "no_holdout"
    return "sufficient" if months >= required else "underpowered"


def track_record(
    start: str,
    end: str,
    *,
    picked: Optional[str] = None,
    target_sharpe: float = TARGET_SHARPE,
    t_threshold: float = T_THRESHOLD,
    trials: Optional[Union[int, TrialCount]] = None,
    effective_trials: Optional[float] = None,
    lang: str = None,
) -> TrackRecord:
    """Read a record as shown and, if ``picked`` is given, since it was picked.

    ``trials`` is how many records the shown one was chosen from — for a
    leaderboard, every wallet it ranked, including the ones that blew up and
    dropped off. It applies to the *as shown* reading only. ``picked`` is the
    date the choice was made; that day or month counts as seen.

    Raises ``ValueError`` on malformed dates, an inverted range, or a pick date
    outside the record — caller mistakes, not missing data.
    """
    lang = resolve_lang(lang)
    if trials is None and effective_trials is not None:
        raise ValueError("effective_trials given without trials — nothing to discount")
    s, e = _parse(start, "start"), _parse(end, "end")
    p = _parse(picked, "picked") if picked is not None else None
    dates = [s, e] + ([p] if p else [])
    precision = "day" if all(d[2] is not None for d in dates) else "month"

    if precision == "day":
        def idx(d):  # days since epoch, inclusive arithmetic below
            return _dt.date(*d).toordinal()
        unit = 1.0 / _MONTH_DAYS
    else:
        def idx(d):
            return d[0] * 12 + d[1] - 1
        unit = 1.0

    si, ei = idx(s), idx(e)
    if ei < si:
        raise ValueError(f"end {end!r} precedes start {start!r}")
    total = (ei - si + 1) * unit
    if p is not None:
        pi = idx(p)
        if not si <= pi <= ei:
            raise ValueError(f"picked {picked!r} is outside the record {start!r}..{end!r}")
        shown_months = (pi - si + 1) * unit
        after_months = (ei - pi) * unit
    else:
        shown_months = total

    penalty = None
    if trials is not None:
        penalty = selection_penalty(trials, effective_trials=effective_trials,
                                    t_base=t_threshold, target_sharpe=target_sharpe,
                                    lang=lang)
        shown_req, shown_bar = penalty.months_adjusted, penalty.t_adjusted
    else:
        shown_req, shown_bar = months_for_power(target_sharpe, t_threshold), t_threshold

    as_shown = Reading("as_shown", round(shown_months, 1), shown_req, shown_bar,
                       _verdict(shown_months, shown_req), shown_months / shown_req,
                       selection=penalty)
    since = None
    if p is not None:
        req = months_for_power(target_sharpe, t_threshold)
        since = Reading("since_picked", round(after_months, 1), req, t_threshold,
                        _verdict(after_months, req), after_months / req)

    note = " ".join(
        [text("record.verdict." + as_shown.verdict, lang)]
        + [penalty.note if penalty is not None else text("record.undeclared_universe", lang)]
        + ([text("record.since." + since.verdict, lang)] if since
           else [text("record.no_pick", lang)])
        + [text("record.limits", lang)]
    )
    return TrackRecord(
        start=start, end=end, picked=picked, precision=precision,
        total_months=round(total, 1), target_sharpe=target_sharpe,
        t_threshold=t_threshold, as_shown=as_shown, since_picked=since,
        note=note, lang=lang,
    )


# ---- how many independent records was it chosen from? ------------------

@dataclass
class RecordOverlap:
    """Kish n_eff over a set of return series, with the noise floor named.

    Overlap is the **positive part** of rho, not |rho| as in ``tools/neff.py``.
    There the question is whether two columns answer the same question, and a
    mirror image does. Here it is how many chances the selector had, and two
    wallets that are long and short the same thing are two chances — whichever
    way the market goes, one of them tops the board. Counting -0.8 as overlap
    would shrink the screening charge for exactly the pair that inflates it.

    On short series even the positive part has a bias with a direction: for two
    *independent* series it averages half of sqrt(2 / (pi * (T - 1))) — 0.075 on
    30 days — so noise alone makes the records look alike, shrinks n_eff, and
    shrinks the charge. ``n_eff_floor`` subtracts that expectation first, and is
    the one to pass as ``effective_trials``. ``mean_abs_rho`` and ``null_floor``
    are reported on the |rho| scale for comparison with ``neff.py``.

    ``universe_n_eff`` extrapolates to the whole universe the records were
    drawn from, *if* the measured mean |rho| held across it. It is not a
    measurement, and the sample is usually the top of a leaderboard, whose
    members are more alike than the board — so it errs low, the flattering way.
    """
    n: int
    days: int               # median overlap per pair
    mean_abs_rho: float
    null_floor: float
    n_eff: float
    n_eff_floor: float
    unmeasured: List[Tuple[str, str]]
    universe: Optional[int] = None
    universe_n_eff: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ranks(xs: List[float]) -> List[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2.0
        i = j + 1
    return ranks


def _spearman(xs: List[float], ys: List[float]) -> Optional[float]:
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return None
    return sxy / (sxx * syy) ** 0.5


def _kish(n: int, total_offdiag: float) -> float:
    return (n * n) / (n + total_offdiag)


def effective_records(
    returns: Dict[str, Dict[str, float]],
    *,
    min_overlap: int = 20,
    universe: Optional[int] = None,
) -> RecordOverlap:
    """Effective number of independent records among ``returns``.

    ``returns`` maps a record's name to ``{date: return}``. Pairs are compared
    on the dates both have; a pair with fewer than ``min_overlap`` shared dates
    is not measured and is charged as **independent** (rho = 0).

    That is the opposite of ``tools/neff.py``, and deliberately. There, n_eff
    counts sources, a lower count is the cautious answer, and an unmeasured
    pair is charged as identical. Here n_eff discounts a screening charge, a
    lower count is the *flattering* answer, and charging an unmeasured pair as
    identical would hand the record a discount nobody measured. Same rule —
    an unmeasured pair must not buy a discount — opposite sign.
    """
    import math
    from itertools import combinations

    names = sorted(k for k, v in returns.items() if v)
    if len(names) < 2:
        raise ValueError("need at least two non-empty return series")
    abs_rhos: List[float] = []
    floors: List[float] = []
    overlaps: List[int] = []
    unmeasured: List[Tuple[str, str]] = []
    raw_total = floor_total = 0.0
    for a, b in combinations(names, 2):
        shared = sorted(set(returns[a]) & set(returns[b]))
        r = (_spearman([returns[a][d] for d in shared], [returns[b][d] for d in shared])
             if len(shared) >= min_overlap else None)
        if r is None:
            unmeasured.append((a, b))
            continue
        null = math.sqrt(2.0 / (math.pi * (len(shared) - 1)))
        abs_rhos.append(abs(r))
        floors.append(null)
        overlaps.append(len(shared))
        pos = max(0.0, r)
        raw_total += 2.0 * pos
        # Subtract per pair, clip only the total. Clipping each pair at zero
        # keeps the above-null half of the noise and drops the below-null half,
        # which still reads noise as overlap: ten independent series came out
        # at 6.7 effective that way.
        floor_total += 2.0 * (pos - null / 2.0)
    floor_total = max(0.0, floor_total)
    n = len(names)
    mean_abs = sum(abs_rhos) / len(abs_rhos) if abs_rhos else 0.0
    null_floor = sum(floors) / len(floors) if floors else 0.0
    n_eff_floor = _kish(n, floor_total)
    uni = None
    if universe is not None:
        if universe < n:
            raise ValueError(f"universe {universe} is smaller than the {n} records measured")
        # Kish with a constant off-diagonal: N / (1 + (N - 1) * rho_bar), using
        # the floor-corrected mean so it agrees with n_eff_floor at N = n.
        rho_bar = (floor_total / (n * (n - 1)))
        uni = universe / (1.0 + (universe - 1) * rho_bar)
    overlaps.sort()
    return RecordOverlap(
        n=n,
        days=overlaps[len(overlaps) // 2] if overlaps else 0,
        mean_abs_rho=mean_abs,
        null_floor=null_floor,
        n_eff=_kish(n, raw_total),
        n_eff_floor=n_eff_floor,
        unmeasured=unmeasured,
        universe=universe,
        universe_n_eff=uni,
    )
