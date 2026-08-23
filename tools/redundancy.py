"""Are two constructs two votes, or one vote wearing two names?

``calibrate.py`` already answers a narrow version of this: if two constructs
lack data on the same subjects, their availability skews are one finding
printed twice (``report_skew_dependence``, Jaccard on the missing sets). That
catches a shared *gap*.

It does not catch the commoner case, and the one that matters off-chain: two
constructs that both **have** data on a subject and always say the same thing
about it. Price-to-earnings and PEG both print a number, both say "cheap", and
both divide by the same earnings estimate. Nothing is missing. Nothing
contradicts. The portfolio still holds one piece of evidence, not two.

So this script measures overlap in the *values*, on the subjects where both
constructs scored.

---

**Why a high correlation is not the finding.**

The obvious test — correlate the two constructs and call anything above 0.8
redundant — is wrong, and wrong in the direction that matters. If two
constructs are both measuring real risk *well*, they are supposed to correlate:
they are both tracking the label. Killing one of them because they agree
discards a genuinely independent vote.

The distinguishing question is what remains after the label is held fixed:

* correlated **within** each label stratum → the shared variance is not the
  truth, because the truth is constant inside a stratum. What is left is shared
  method, shared vendor, shared parsing path, shared upstream field. That is
  redundancy: **one vote**.
* correlated overall but **not** within strata → the two constructs look alike
  only because both are right. That is convergent evidence: **two votes**.

Same arithmetic as a partial correlation controlling for the label; done by
stratification so it stays legible and needs no linear-model assumption.

This is also where a *mechanism-based* redundancy check goes wrong, in both
directions. Grouping metrics by how they are computed is a prior: it is
available before any data, which is its whole appeal. But
``authority_control`` (contract permission fields) and ``tradability``
(buy/sell simulation) are mechanically unrelated and were still found to be
one finding on this corpus, while two metrics sharing a mechanism can come
apart on the subjects that actually matter. ``MECHANISM_PRIOR`` below states
the prior explicitly so the script can print where the data disagrees with it.
Neither wins by default — a conflict is a thing to investigate, not a verdict.

---

Usage::

    python tools/redundancy.py .data/captured.jsonl
    python tools/redundancy.py .data/captured.jsonl --min-n 30

Reads the same JSONL as ``calibrate.py``: one object per line with ``subject``,
``label`` (1 = known bad) and ``sources``. Labels are required — the entire
argument above depends on stratifying by them, so unlike ``agreement.py`` this
one cannot run label-free.

Everything the ``calibrate.py`` header says about temporal leakage applies here
unchanged and is worse, not better: if a construct's score is contaminated by
outcome knowledge, so is its correlation with anything else. A pair flagged
redundant may be sharing a leak rather than a method. That distinction is not
decidable from this corpus, and the script says so rather than guessing.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from adapters import observe_vendor  # noqa: E402
from decision_confidence import build_report  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calibrate import (  # noqa: E402  (one number, one home)
    JACCARD_DEPENDENT, LEAKAGE, LEAKAGE_MARK,
)

# ---------------------------------------------------------------------------
# Thresholds. Judgement, in the same class as every other number in this repo:
# they mark a pair as worth not double-counting, not as proven identical.
# ---------------------------------------------------------------------------

RHO_REDUNDANT = 0.80    # within-label rank correlation at or above this: one vote
# Below this, the residual shared variance is under 4% (0.20²) and calling the
# pair independent is defensible. 0.40 was tried first and rejected: it leaves
# 16% of the variance shared after the label is held fixed, which is not
# independence, and it put rho_within = 0.38 and rho_within = 0.01 in the same
# bucket. Both numbers are judgement. See ``report_knee``: on a distribution
# with no knee, any cut here is arbitrary and the script says so.
RHO_INDEPENDENT = 0.20
MIN_PAIR_N = 20         # fewer overlapping subjects than this and nothing is claimed
MIN_STRATUM_N = 8       # a stratum smaller than this is not correlated at all

# Below this many distinct scores, a construct cannot produce a high rank
# correlation with anything, because most pairs are ties. Reported so a low rho
# on such a construct is not read as evidence of independence.
THIN_SCALE = 8

# A construct whose own correlation with the label is weaker than this carries
# too little signal for "are these two votes?" to be a meaningful question —
# two constructs that both measure nothing are not two votes, they are none.
# At n≈400 the significance floor is around 0.10 (1.96/sqrt(n)); 0.15 sits
# above it so the bar is substance rather than mere significance.
MIN_SIGNAL = 0.15

# What each construct is computed *from*, as a prior — asserted from the
# adapter code, not measured. Constructs sharing a token here share a
# mechanism, so a mechanism-based check would merge them and split everything
# else. Printed against the measured result to expose where the prior fails.
#
# Sourced from src/adapters/: goplus.py, honeypot_is.py, dexscreener.py.
MECHANISM_PRIOR: Dict[str, str] = {
    "authority_control": "contract_permission_fields",
    "tradability": "buy_sell_simulation",
    "liquidity_depth": "pool_reserves",
    "holder_concentration": "holder_distribution",
    "holder_base": "holder_distribution",
    "compliance_exposure": "sanctions_lists",
    "fraud_prediction": "vendor_classifier",
    "carry_cost": "perp_funding_rates",
    # From src/adapters/okx.py. Note the limit this table has: it is keyed by
    # construct alone, so ``liquidity_depth`` keeps the DEX mechanism above even
    # when OKX measures it off the order book instead of a pool. The prior is
    # therefore wrong for venue data by construction, and is printed anyway —
    # a prior that quietly re-keys itself to match the data is not a prior.
    "execution_cost": "orderbook_top",
    "trading_activity": "trade_tape",
    "price_volatility": "price_series",
    "price_momentum": "price_series",
}


# ---------------------------------------------------------------------------
# Statistics, standard library only
# ---------------------------------------------------------------------------

def _ranks(values: Sequence[float]) -> List[float]:
    """Ranks with ties averaged. Ties are the normal case here: these scores
    come off a handful of discrete bands, so integer ranking would invent an
    ordering the data does not contain."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None  # one side is constant: no ordering to compare
    return num / (dx * dy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    if len(xs) < 3:
        return None
    return _pearson(_ranks(xs), _ranks(ys))


def cohen_kappa(a: Sequence[str], b: Sequence[str]) -> Optional[float]:
    """Agreement above what the two base rates would produce by themselves.

    Raw agreement is unusable for comparing one pair against another, and this
    script printed it that way before the corpus made the problem visible:
    ``authority_control`` reads *low* on 70% of subjects and ``tradability`` on
    71%, so those two agree 57% of the time by arithmetic alone;
    ``holder_concentration`` is *extreme*-heavy and agrees with ``tradability``
    13% of the time for the same reason. 57% and 13% look six times apart and
    are both approximately chance.

    Kappa subtracts the chance rate. It is the same category error this package
    exists to catch, one level down: a number that is not comparable across the
    rows it is printed next to.
    """
    if len(a) != len(b) or not a:
        return None
    n = len(a)
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    ca: Dict[str, int] = {}
    cb: Dict[str, int] = {}
    for x in a:
        ca[x] = ca.get(x, 0) + 1
    for y in b:
        cb[y] = cb.get(y, 0) + 1
    expected = sum((ca.get(v, 0) / n) * (cb.get(v, 0) / n)
                   for v in set(ca) | set(cb))
    if expected >= 1.0:
        return None  # both sides constant and identical: kappa undefined
    return (observed - expected) / (1 - expected)


def fisher_pool(rs: Sequence[Tuple[float, int]]) -> Optional[float]:
    """Combine per-stratum correlations, weighted by n-3 in Fisher z space.

    Averaging correlation coefficients directly understates the pooled value;
    z-transforming first is the standard fix. Clamped at ±0.999 because a
    stratum can legitimately return exactly 1.0 on discrete scores, and atanh
    of 1 is infinite.
    """
    usable = [(r, n) for r, n in rs if n > 3 and r is not None]
    if not usable:
        return None
    zs = 0.0
    ws = 0.0
    for r, n in usable:
        r = max(-0.999, min(0.999, r))
        w = n - 3
        zs += w * math.atanh(r)
        ws += w
    if ws == 0:
        return None
    return math.tanh(zs / ws)


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------

def load_rows(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{lineno}: {exc}") from exc
            if "label" not in row or "subject" not in row:
                raise SystemExit(f"{path}:{lineno}: row needs 'subject' and 'label'")
            rows.append(row)
    return rows


def collect(rows: List[Dict[str, Any]]):
    """Per subject: the score and verdict each construct produced, plus the label.

    Same path as ``calibrate.py`` — adapters, then ``build_report`` — so the
    numbers here and there describe the same pipeline.
    """
    per_subject: List[Tuple[Dict[str, int], Dict[str, str], int]] = []
    # Which subjects a construct had nothing usable on — the same set
    # ``calibrate.py`` runs its Jaccard over, kept here so the two kinds of
    # overlap can be put side by side instead of across two scripts.
    missing: Dict[str, set] = {}
    for row in rows:
        observations = []
        for entry in row.get("sources", []):
            vendor = entry.get("vendor")
            observations.extend(observe_vendor(
                vendor, entry.get("source_id") or vendor or "source",
                row["subject"], entry.get("raw") or {},
            ))
        report = build_report(row["subject"], observations)
        scores: Dict[str, int] = {}
        verdicts: Dict[str, str] = {}
        for g in report.constructs:
            if g.n_ok == 0:
                missing.setdefault(g.construct, set()).add(row["subject"])
            if g.score is None:
                continue
            scores[g.construct] = g.score
            verdicts[g.construct] = g.verdict
        per_subject.append((scores, verdicts, int(row["label"])))
    return per_subject, missing


# ---------------------------------------------------------------------------
# The pairwise measurement
# ---------------------------------------------------------------------------

class Pair:
    def __init__(self, a: str, b: str):
        self.a = a
        self.b = b
        self.n = 0
        self.rho_marginal: Optional[float] = None
        self.rho_within: Optional[float] = None
        self.strata: List[Tuple[int, int, Optional[float]]] = []  # label, n, rho
        self.verdict_agree: Optional[float] = None   # raw, kept for the record
        self.kappa: Optional[float] = None           # the comparable one
        self.thin: List[str] = []                    # constructs on a coarse scale
        self.signal_a: Optional[float] = None        # rho(a, label)
        self.signal_b: Optional[float] = None        # rho(b, label)

    @property
    def same_mechanism(self) -> bool:
        return (MECHANISM_PRIOR.get(self.a) is not None
                and MECHANISM_PRIOR.get(self.a) == MECHANISM_PRIOR.get(self.b))

    @property
    def weak_side(self) -> List[str]:
        """Which of the two carries too little signal for the question to apply."""
        out = []
        for name, s in ((self.a, self.signal_a), (self.b, self.signal_b)):
            if s is None or abs(s) < MIN_SIGNAL:
                out.append(name)
        return out

    @property
    def call(self) -> str:
        """One vote, two votes, or not answerable on this corpus.

        The ordering matters. ``one vote`` is checked first because a pair that
        still correlates with the label held fixed is redundant regardless of
        how much signal either side carries — shared method is shared method.

        ``two votes`` requires three things at once: the shared variance
        disappears inside a label stratum, *and* each side independently tracks
        the label. Dropping the third condition is the mistake this check was
        rewritten to avoid: two constructs that measure nothing are also
        uncorrelated within a stratum, and calling them two independent votes
        would be the loudest possible way to be wrong.
        """
        if self.n < MIN_PAIR_N:
            return "too few"
        if self.rho_within is None:
            return "unresolved"
        if self.rho_within >= RHO_REDUNDANT:
            return "one vote"
        if abs(self.rho_within) < RHO_INDEPENDENT:
            if self.weak_side:
                return "no signal"
            return "two votes"
        return "partial"


def scale_width(per_subject) -> Dict[str, int]:
    """How many distinct scores each construct ever emitted on this corpus."""
    seen: Dict[str, set] = {}
    for scores, _, _ in per_subject:
        for c, sc in scores.items():
            seen.setdefault(c, set()).add(sc)
    return {c: len(v) for c, v in seen.items()}


def label_signal(per_subject) -> Dict[str, Optional[float]]:
    """Each construct's own rank correlation with the label.

    Not a performance claim — ``calibrate.py`` owns that, with the leakage
    grades attached. It is here only to answer whether a construct carries
    enough signal for "is this an independent vote?" to mean anything.
    """
    out: Dict[str, Optional[float]] = {}
    constructs = {c for scores, _, _ in per_subject for c in scores}
    for c in sorted(constructs):
        xs = [(s[c], lab) for s, _, lab in per_subject if c in s]
        if len(xs) < 3:
            out[c] = None
            continue
        out[c] = spearman([x[0] for x in xs], [float(x[1]) for x in xs])
    return out


def measure(per_subject) -> List[Pair]:
    constructs = sorted({c for scores, _, _ in per_subject for c in scores})
    widths = scale_width(per_subject)
    signals = label_signal(per_subject)
    pairs: List[Pair] = []

    for i, a in enumerate(constructs):
        for b in constructs[i + 1:]:
            both = [(s[a], s[b], v.get(a), v.get(b), lab)
                    for s, v, lab in per_subject if a in s and b in s]
            if not both:
                continue
            p = Pair(a, b)
            p.n = len(both)
            p.thin = [c for c in (a, b) if widths.get(c, 0) < THIN_SCALE]
            p.signal_a = signals.get(a)
            p.signal_b = signals.get(b)
            p.rho_marginal = spearman([x[0] for x in both], [x[1] for x in both])
            agree = sum(1 for x in both if x[2] is not None and x[2] == x[3])
            p.verdict_agree = agree / len(both)
            va = [x[2] for x in both if x[2] is not None and x[3] is not None]
            vb = [x[3] for x in both if x[2] is not None and x[3] is not None]
            p.kappa = cohen_kappa(va, vb)

            per_stratum: List[Tuple[float, int]] = []
            for label in sorted({x[4] for x in both}):
                sub = [x for x in both if x[4] == label]
                if len(sub) < MIN_STRATUM_N:
                    p.strata.append((label, len(sub), None))
                    continue
                r = spearman([x[0] for x in sub], [x[1] for x in sub])
                p.strata.append((label, len(sub), r))
                if r is not None:
                    per_stratum.append((r, len(sub)))
            p.rho_within = fisher_pool(per_stratum)
            pairs.append(p)
    return pairs


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _fmt(x: Optional[float]) -> str:
    return "   --" if x is None else f"{x:+5.2f}"


def report_signals(signals: Dict[str, Optional[float]]) -> None:
    """What each construct does on its own, before any pair is discussed."""
    print("### does each construct carry signal at all?  (rho with the label)")
    print("    a pair of constructs that both measure nothing is not two votes")
    print()
    print(f"    {'construct':<24}{'rho':>7}   leakage")
    for c in sorted(signals):
        s = signals[c]
        grade, why = LEAKAGE.get(c, ("unknown", "not graded"))
        mark = LEAKAGE_MARK.get(grade, "  ")
        weak = "" if (s is not None and abs(s) >= MIN_SIGNAL) else "   << below MIN_SIGNAL"
        print(f"    {c:<24}{_fmt(s):>7}{mark} {grade}{weak}")
    print()
    print("    ! severe / ~ partial leakage, imported from calibrate.py. On a graded")
    print("    construct the rho above is inflated by outcome knowledge, so a strong")
    print("    number there is not evidence the construct works — only that it is")
    print("    entangled with how the labels were assembled.")
    print()


def report(pairs: List[Pair], n_subjects: int,
           missing: Optional[Dict[str, set]] = None) -> None:
    print(f"### value overlap between constructs   ({n_subjects} labelled subjects)")
    print("    rho on the subjects where both scored; within = label held fixed")
    print()
    print(f"    {'pair':<46}{'n':>5}{'rho':>7}{'within':>8}"
          f"{'raw=':>7}{'kappa':>7}   call")

    ordered = sorted(pairs, key=lambda p: (
        p.rho_within is None, -(abs(p.rho_within) if p.rho_within is not None else 0)))
    for p in ordered:
        name = f"{p.a} ~ {p.b}"
        if p.thin:
            name += " *"
        agree = "   --" if p.verdict_agree is None else f"{p.verdict_agree:4.0%}"
        print(f"    {name:<46}{p.n:>5}{_fmt(p.rho_marginal):>7}"
              f"{_fmt(p.rho_within):>8}{agree:>7}{_fmt(p.kappa):>7}   {p.call}")

    print()
    print("    raw= is the share of subjects where both verdicts matched. It is")
    print("    printed for the record and must not be compared across rows: two")
    print("    constructs with the same dominant verdict agree most of the time by")
    print("    arithmetic. kappa is that number with the base rates removed.")

    thin_all = sorted({c for p in pairs for c in p.thin})
    if thin_all:
        print()
        print(f"    * scale narrower than {THIN_SCALE} distinct scores on this corpus: "
              f"{', '.join(thin_all)}.")
        print("      Most pairs involving these are ties, which caps how high rho can")
        print("      go. A low rho on a starred row is weak evidence of independence.")

    print()
    one = [p for p in ordered if p.call == "one vote"]
    two = [p for p in ordered if p.call == "two votes"]
    none = [p for p in ordered if p.call == "no signal"]

    if none:
        print("    no signal — the shared variance vanishes inside a label stratum, but")
        print(f"    at least one side does not track the label to {MIN_SIGNAL:.2f} either, so")
        print("    'independent votes' does not apply. Two blind sources are not two:")
        for p in none:
            print(f"        {p.a} ~ {p.b}: weak side "
                  f"{', '.join(p.weak_side)}")
        print()

    if one:
        print(f"    one vote  (within-label rho >= {RHO_REDUNDANT:.2f}) — the agreement")
        print("              survives holding the truth fixed, so it is not the truth:")
        for p in one:
            print(f"        {p.a} + {p.b}: count once, not twice")
    if two:
        print(f"    two votes (within < {RHO_INDEPENDENT:.2f}, both sides track the label")
        print("              to at least "
              f"{MIN_SIGNAL:.2f}) — they resemble each other only because")
        print("              both are right. Keep both:")
        for p in two:
            print(f"        {p.a} + {p.b}")
    if not one and not two and not none:
        print("    Nothing at either extreme. Every pair is partially shared, which")
        print("    is the honest and least actionable outcome: no pair can be merged")
        print("    or split on this evidence alone.")

    if missing:
        report_scope(ordered, missing)
    report_knee(ordered)
    _report_prior_conflicts(ordered)
    _report_caveats(ordered)


def report_scope(pairs: List[Pair], missing: Dict[str, set]) -> None:
    """The same two constructs, judged on two different things.

    ``calibrate.py`` asks whether two constructs are blind on the same
    subjects. This file asks whether they say the same thing about the subjects
    they can see. Those are different questions, and on this corpus they give
    different answers for the same pair — which means "these two are really one"
    is not a property of the pair. It is a property of the pair *plus the
    dimension you asked about*.

    That matters beyond bookkeeping. The natural response to finding a
    redundant metric is to delete it. If the redundancy only holds on one
    dimension, deleting the metric throws away the dimension where it was
    independent. The correct move is narrower: merge them where they overlap,
    keep them apart where they do not.
    """
    rows = []
    for p in pairs:
        sa, sb = missing.get(p.a), missing.get(p.b)
        if not sa or not sb:
            continue
        union = sa | sb
        if not union:
            continue
        j = len(sa & sb) / len(union)
        if j >= JACCARD_DEPENDENT and p.call in ("two votes", "partial"):
            rows.append((p, j, len(sa & sb), len(union)))
    if not rows:
        return

    print()
    print("### redundancy has a scope")
    print("    pairs that are one finding on missing-data and two votes on values")
    for p, j, inter, union in sorted(rows, key=lambda r: -r[1]):
        print(f"    {p.a} ~ {p.b}")
        print(f"        blind on the same subjects : {inter}/{union} "
              f"Jaccard {j:.2f}  -> one finding")
        print(f"        agree about the subjects   : within-label rho "
              f"{p.rho_within:+.2f}  -> {p.call}")
    print()
    print("    Both readings are correct about their own dimension. What is wrong is")
    print("    the unqualified sentence — 'these two are one piece of evidence' — with")
    print("    no dimension named. Availability and value are separate channels, and")
    print("    a pair can share one while carrying independent information on the")
    print("    other. Merge the channel that overlaps; do not delete the construct.")


def report_knee(pairs: List[Pair]) -> None:
    """Is there a gap in the within-label distribution, or is the cut arbitrary?

    ``agreement.py`` sets the standard this follows: a threshold is defensible
    when the distribution separates into two populations, and when it does not,
    saying so beats picking the prettiest number. The same test has to apply to
    the cut-offs in this file, including when the answer is unflattering.

    Reported as the largest gap between consecutive sorted values, against the
    average gap. A ratio near 1 means evenly spread — no natural boundary
    exists, so ``one vote`` / ``two votes`` is a grid laid over a continuum and
    every borderline pair is a coin flip.
    """
    vals = sorted((p.rho_within for p in pairs if p.rho_within is not None),
                  reverse=True)
    if len(vals) < 4:
        return
    gaps = [(vals[i] - vals[i + 1], vals[i], vals[i + 1])
            for i in range(len(vals) - 1)]
    widest, hi, lo = max(gaps, key=lambda g: g[0])
    mean_gap = sum(g[0] for g in gaps) / len(gaps)
    ratio = widest / mean_gap if mean_gap else 0.0

    print()
    print("### is there a knee to cut at?")
    print(f"    within-label rho spans {vals[-1]:+.2f} .. {vals[0]:+.2f} over "
          f"{len(vals)} pairs")
    print(f"    widest gap {widest:.3f} (between {hi:+.2f} and {lo:+.2f}), "
          f"mean gap {mean_gap:.3f}, ratio {ratio:.1f}x")
    if ratio < 2.5:
        print("    No knee. The values are spread evenly, so the cut-offs above are a")
        print("    grid over a continuum, not a boundary the data contains. Read the")
        print("    column, not the label in the last column: a pair at 0.22 and a pair")
        print("    at 0.18 differ by nothing except which side of a chosen number they")
        print("    fell on.")
    else:
        print(f"    A gap {ratio:.1f}x the average sits between {hi:+.2f} and {lo:+.2f}.")
        print("    That is where a threshold would be defensible on this corpus —")
        print(f"    compare it against RHO_INDEPENDENT = {RHO_INDEPENDENT:.2f}, which was")
        print("    chosen by argument rather than from this distribution.")


def _report_prior_conflicts(pairs: List[Pair]) -> None:
    """Where does grouping-by-mechanism give a different answer from the data?"""
    resolved = [p for p in pairs if p.call in ("one vote", "two votes")]
    conflicts = [p for p in resolved
                 if (p.same_mechanism and p.call == "two votes")
                 or (not p.same_mechanism and p.call == "one vote")]
    if not conflicts:
        return
    print()
    print("### where the mechanism prior and the corpus disagree")
    print("    a prior groups metrics by how they are computed; this groups them by")
    print("    what they did to these subjects. Both are fallible.")
    for p in conflicts:
        if p.same_mechanism:
            print(f"    {p.a} ~ {p.b}")
            print(f"        prior: same mechanism ({MECHANISM_PRIOR[p.a]}) -> merge")
            print("        corpus: two votes -> a mechanism-based check would have")
            print("                discarded a construct that carried its own signal")
        else:
            print(f"    {p.a} ~ {p.b}")
            print(f"        prior: {MECHANISM_PRIOR.get(p.a)} vs "
                  f"{MECHANISM_PRIOR.get(p.b)} -> keep both")
            print("        corpus: one vote -> a mechanism-based check would have")
            print("                counted one piece of evidence twice")
    print()
    print("    Neither side is authoritative. The prior can be wrong about what a")
    print("    vendor actually reads; the corpus can be too small, or the pair can")
    print("    be sharing a leak rather than a method. Investigate, do not merge.")


def _report_caveats(pairs: List[Pair]) -> None:
    thin = [p for p in pairs if p.n < MIN_PAIR_N]
    unresolved = [p for p in pairs if p.call == "unresolved"]
    if not thin and not unresolved:
        return
    print()
    print("### not claimed")
    for p in thin:
        print(f"    {p.a} ~ {p.b}: only {p.n} subjects scored by both "
              f"(< {MIN_PAIR_N}); no call made")
    for p in unresolved:
        detail = ", ".join(
            f"label {lab}: n={n}" + ("" if r is not None else " (constant or too small)")
            for lab, n, r in p.strata)
        print(f"    {p.a} ~ {p.b}: within-label rho unavailable — {detail}")


def main(argv: List[str]) -> int:
    global MIN_PAIR_N

    ap = argparse.ArgumentParser(
        description="Do two constructs carry one vote or two?")
    ap.add_argument("corpus", help="JSONL of captured payloads with labels")
    ap.add_argument("--min-n", type=int, default=MIN_PAIR_N,
                    help=f"overlapping subjects required per pair (default {MIN_PAIR_N})")
    args = ap.parse_args(argv)

    MIN_PAIR_N = args.min_n

    rows = load_rows(args.corpus)
    per_subject, missing = collect(rows)
    if not per_subject:
        print("no usable rows")
        return 1

    labels = {lab for _, _, lab in per_subject}
    if len(labels) < 2:
        print("this check needs both labels present; stratifying by a constant")
        print("label measures nothing.")
        return 1

    pairs = measure(per_subject)
    if not pairs:
        print("no construct pair was scored on a common subject")
        return 1

    report_signals(label_signal(per_subject))
    report(pairs, len(per_subject), missing)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
