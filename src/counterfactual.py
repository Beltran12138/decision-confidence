"""The same discount, applied to the inputs.

``decision_confidence.py`` asks how many of your sources answer the same
question. ``effective_window.py`` asks how much of your backtest the model had
already read. This asks the third version: **is the agent reading its inputs at
all, or reciting an outcome it already knows?**

The method is counterfactual perturbation — change a fact and see whether the
conclusion follows. Published work has measured this and the number is worse
than people expect: perturbing key market inputs left the worst model's
predictions unchanged 82.13% of the time (Li et al., *Profit Mirage*,
arXiv:2510.07920).

**But a flip rate on its own is not a verdict, and that is what this module is
for.** Perturbations come in two kinds with opposite expectations:

* **material** — good news to bad, policy reversed, a beat turned into a miss.
  The conclusion *should* move.
* **cosmetic** — a renamed ticker, shifted dates, rescaled magnitudes, reworded
  narration. The conclusion *should not*.

Averaging those into one "unchanged 82%" throws away the only part that
discriminates. An agent that flips on everything scores identically to one that
reads carefully, and an agent that flips on nothing is indistinguishable from a
subject where nothing needed to change.

So the test is **material against the agent's own cosmetic rate**, one-sided
Fisher. Not against 0.5, and not against any assumed rate: how often a genuinely
reading agent ought to flip is not knowable in advance, but its own response to
meaningless changes is measurable and is exactly the right baseline. This is the
same move ``carry_cost`` makes in the sources axis — a control case is what
turns a refusal into a measurement.

Two consequences worth stating before the code:

* **Both kinds are required.** With only material perturbations, "never flips"
  and "reads nothing" are the same observation. With only cosmetic ones, you
  learn the agent is stable and nothing else.
* **Six perturbations is the floor.** Three material and three cosmetic, split
  perfectly, give p = 0.0500 exactly. Below that, no result of any shape can
  clear α = 0.05 — which is a ``no_power`` verdict, not a pass.

Caller-supplied only. Deciding whether two conclusions differ needs judgement
this library does not have and will not fake; the caller brings the verdicts and
the labels, and the honest limit is that neither can be checked here.

Stdlib only. No network.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import comb
from typing import Any, Dict, List, Optional, Sequence

from messages import DEFAULT_LANG, resolve_lang, text

__all__ = [
    "Perturbation",
    "PerturbationReport",
    "perturbation_audit",
    "minimum_perturbations",
    "fisher_one_sided",
    "MATERIAL",
    "COSMETIC",
    "ALPHA",
]

MATERIAL = "material"
COSMETIC = "cosmetic"
KINDS = (MATERIAL, COSMETIC)

# Conventional bar, and the same one the window axis starts from. It is the
# caller's to move; everything downstream reads it rather than assuming 0.05.
ALPHA = 0.05


@dataclass
class Perturbation:
    """One altered input and what the agent concluded from it.

    ``flipped`` is the caller's judgement that the conclusion changed, and
    ``kind`` is the caller's judgement that the change was or was not material.
    Both are unverifiable here — see the limits carried in every report.
    """
    kind: str
    detail: str = ""
    flipped: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerturbationReport:
    verdict: str            # no_control | no_power | memorised | unstable | responsive
    n_material: int
    n_cosmetic: int
    material_flips: int
    cosmetic_flips: int
    material_rate: float
    cosmetic_rate: float
    p_value: Optional[float]        # one-sided Fisher; None when not computable
    best_possible_p: Optional[float]  # p under a perfect split at this size
    alpha: float
    perturbations_required: int     # smallest total that can clear alpha at all
    lang: str = DEFAULT_LANG
    note: str = ""
    perturbations: List[Perturbation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self, lang: str = None) -> str:
        lang = resolve_lang(lang or self.lang)
        return text("cf.summary", lang, verdict=self.verdict, alpha=self.alpha,
                    n_material=self.n_material, n_cosmetic=self.n_cosmetic,
                    material_flips=self.material_flips,
                    cosmetic_flips=self.cosmetic_flips,
                    material_rate=self.material_rate,
                    cosmetic_rate=self.cosmetic_rate,
                    p_value=self.p_value if self.p_value is not None else 1.0)


def fisher_one_sided(a: int, b: int, c: int, d: int) -> float:
    """P(material flips at least this often | no association), exact.

    The 2x2 is ``[[a, b], [c, d]]`` = material flipped / did not, cosmetic
    flipped / did not. Summing the hypergeometric tail from ``a`` upward gives
    the one-sided probability of a split at least this extreme by chance.

    Exact rather than chi-square on purpose: the counts here are single digits,
    which is where the approximation is worst and where every audit will live.
    """
    n, row1, col1 = a + b + c + d, a + b, a + c
    if n == 0 or row1 == 0 or col1 == 0 or row1 == n or col1 == n:
        return 1.0
    hi = min(row1, col1)
    total = comb(n, row1)
    return sum(comb(col1, x) * comb(n - col1, row1 - x)
               for x in range(a, hi + 1)) / total


def minimum_perturbations(alpha: float = ALPHA) -> Dict[str, int]:
    """The smallest perturbation set that can reach ``alpha`` under a perfect split.

    Returned as the balanced answer, because a lopsided set that happens to
    clear the bar is a worse thing to recommend: it buys significance with an
    asymmetry the caller did not choose. At α = 0.05 this is 3 + 3 = 6, where a
    perfect split gives p = 0.0500 exactly.

    This is a floor in the same sense as ``months_for_power``: it assumes the
    cleanest result you could possibly get. Real audits are not perfectly split
    and need more.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    for k in range(1, 60):
        if fisher_one_sided(k, 0, 0, k) <= alpha:
            return {"material": k, "cosmetic": k, "total": 2 * k}
    raise ValueError(f"no balanced set under 60+60 reaches alpha={alpha}")


def perturbation_audit(
    perturbations: Sequence[Perturbation],
    *,
    alpha: float = ALPHA,
    lang: str = None,
) -> PerturbationReport:
    """Did material changes move the conclusion more than meaningless ones?

    Verdicts, and why each is separate:

    * ``no_control``  — one kind missing. Not a result, a missing control.
    * ``no_power``    — even a perfect split could not clear ``alpha`` at this
      size. Says nothing about the agent, only about the audit.
    * ``memorised``   — no significant difference and no cosmetic flip at all: the
      agent is stable, and it is stable through changes it should have noticed.
    * ``unstable``    — no significant difference and at least one cosmetic flip:
      something moves this output, but not the part of the input that matters.
    * ``responsive``  — material significantly above cosmetic. The shape a
      reading agent should have, and nothing more than that.

    ``memorised`` and ``unstable`` split on whether any cosmetic change moved the
    conclusion at all — zero versus non-zero, not a rate against a cutoff.
    Comparing the two rates was the first attempt and it inverted both extremes:
    with 0% and 0% the "cosmetic >= material" test fires and calls a completely
    unresponsive agent unstable, while 100% and 100% falls through to memorised.
    A threshold on "too unstable" would have been an uncalibrated number of
    exactly the kind this repo refuses elsewhere; one cosmetic flip is a real
    problem on its own, so the bar is one.
    """
    lang = resolve_lang(lang)
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    for p in perturbations:
        if p.kind not in KINDS:
            raise ValueError(
                f"unknown perturbation kind {p.kind!r}; expected one of {KINDS}"
            )

    mat = [p for p in perturbations if p.kind == MATERIAL]
    cos = [p for p in perturbations if p.kind == COSMETIC]
    a = sum(1 for p in mat if p.flipped)
    b = len(mat) - a
    c = sum(1 for p in cos if p.flipped)
    d = len(cos) - c

    m_rate = a / len(mat) if mat else 0.0
    c_rate = c / len(cos) if cos else 0.0
    need = minimum_perturbations(alpha)

    if not mat or not cos:
        verdict, p_value, best = "no_control", None, None
    else:
        p_value = fisher_one_sided(a, b, c, d)
        # The cleanest result this many perturbations could have produced.
        best = fisher_one_sided(len(mat), 0, 0, len(cos))
        if best > alpha:
            verdict = "no_power"
        elif p_value <= alpha:
            verdict = "responsive"
        elif c:
            verdict = "unstable"
        else:
            verdict = "memorised"

    return PerturbationReport(
        verdict=verdict,
        n_material=len(mat), n_cosmetic=len(cos),
        material_flips=a, cosmetic_flips=c,
        material_rate=m_rate, cosmetic_rate=c_rate,
        p_value=p_value, best_possible_p=best, alpha=alpha,
        perturbations_required=need["total"],
        lang=lang,
        note=text("cf.verdict." + verdict, lang) + " " + text("cf.limits", lang),
        perturbations=list(perturbations),
    )


def remedies(report: PerturbationReport, lang: str = None) -> List[str]:
    """What to do about a verdict, dispatched on which part is missing.

    Kept parallel to ``effective_window.remedies``: plain sentences, ordered,
    no numbering — and dispatched on cause rather than printed as a fixed list,
    because "add cosmetic perturbations" is useless advice to someone who
    already has six of them.
    """
    r = report
    lang = resolve_lang(lang or r.lang)
    out: List[str] = []

    def say(key, **kw):
        out.append(text(key, lang, **kw))

    if r.n_cosmetic == 0:
        say("cf.remedy.add_cosmetic")
    if r.n_material == 0:
        say("cf.remedy.add_material")

    if r.verdict == "no_power":
        need = minimum_perturbations(r.alpha)
        short = max(need["total"] - (r.n_material + r.n_cosmetic), 1)
        say("cf.remedy.need_more", shortfall=short, best_p=r.best_possible_p,
            min_material=need["material"], min_cosmetic=need["cosmetic"],
            alpha=r.alpha)

    if r.verdict in ("memorised", "unstable") and r.n_material:
        unflipped = r.n_material - r.material_flips
        if unflipped:
            say("cf.remedy.inspect_unflipped", unflipped=unflipped)
    if r.cosmetic_flips:
        say("cf.remedy.inspect_flipped_cosmetic", flipped=r.cosmetic_flips)

    if r.verdict == "responsive":
        say("cf.remedy.not_a_pass")
    say("cf.remedy.labels_are_yours")
    return out
