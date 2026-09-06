"""Where the trial count came from.

``selection_penalty`` takes an integer, and that integer is load-bearing: it is
the difference between a 48-month requirement and a 112-month one. Until now the
library could not tell a counted twenty from a remembered one. Both arrive as
``trials=20``, both move the bar the same distance, and only one of them is
evidence.

That gap is not cosmetic. Bailey and López de Prado made the case for declaring
the trial count in 2014 and called withholding it a form of fraud; a decade on,
the standard objection to the Deflated Sharpe Ratio is still that its honesty
depends entirely on honestly counting N. Asking the person with the incentive to
under-count is a design choice, not a physical constraint — and it is the one
this module removes.

Three provenances, in increasing order of what they can be checked against:

``declared``
    A human typed it. Nothing can verify it. It runs low for a structural
    reason: the variant you glanced at and abandoned does not feel like a trial.

``grid``
    Derived from the shape of the search — configurations times evaluation
    windows times scenarios. Checkable against the code that ran the search,
    because the same numbers appear there. Blind to anything tried outside the
    grid.

``log``
    Counted from an execution record. Checkable against the record. Blind to
    whatever the record does not cover: runs before logging was switched on,
    runs that crashed before writing, runs on another machine.

**All three are lower bounds, and the object says so.** Deriving the count does
not make it true; it makes its basis inspectable, and it moves the uncounted
remainder from "unknown" to "named". A ``grid`` count that misses two hand-tuned
attempts is still wrong — but wrong in a way a reader can see and argue with,
which a declared integer never is.

The point of separating these is not to rank them. It is that ``months_required``
should not be reported the same way when the count behind it cannot be checked.

Stdlib only. No network, no filesystem — callers pass records in. The counting
is deliberately dumb: this module decides *what counts as one trial* and refuses
to guess when the caller has not said.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence

from messages import DEFAULT_LANG, resolve_lang, text

__all__ = [
    "TrialCount",
    "declared",
    "from_grid",
    "from_runs",
    "PROVENANCES",
]

PROVENANCES = ("declared", "grid", "log")


@dataclass
class TrialCount:
    """A trial count together with the thing it can be checked against.

    ``count`` is what ``selection_penalty`` consumes. ``provenance`` and
    ``derivation`` are what a reader consumes: the first says what kind of
    number it is, the second reproduces the arithmetic that produced it.

    ``blind_to`` is the part that matters most and is easiest to leave out. It
    names what this counting method structurally cannot see. An empty list here
    would be a claim of completeness, so the constructors always populate it.
    """
    count: int
    provenance: str
    derivation: str
    blind_to: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    lang: str = DEFAULT_LANG

    def __post_init__(self) -> None:
        if self.provenance not in PROVENANCES:
            raise ValueError(
                f"provenance must be one of {PROVENANCES}, got {self.provenance!r}")
        if self.count < 1:
            raise ValueError("count must be >= 1")

    @property
    def checkable(self) -> bool:
        """Is there an artefact a third party could recount from?"""
        return self.provenance != "declared"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["checkable"] = self.checkable
        return d

    def note(self, lang: str = None) -> str:
        """One sentence naming the basis and what it misses."""
        lang = resolve_lang(lang or self.lang)
        head = text("trials." + self.provenance, lang,
                    count=self.count, derivation=self.derivation)
        if not self.blind_to:
            return head
        return head + " " + text("trials.blind_to", lang,
                                 items="; ".join(self.blind_to))


def declared(count: int, *, lang: str = None) -> TrialCount:
    """The number as given. Recorded as unverifiable, because it is.

    This exists so that a declared count and a derived one travel through the
    same field and print differently, rather than a declared count being the
    unmarked default.
    """
    lang = resolve_lang(lang)
    return TrialCount(
        count=int(count),
        provenance="declared",
        derivation=text("trials.derivation_declared", lang, count=int(count)),
        blind_to=[text("trials.blind_declared", lang)],
        evidence={},
        lang=lang,
    )


def from_grid(*, lang: str = None, **dimensions: int) -> TrialCount:
    """Multiply out the shape of the search.

        from_grid(configs=6, windows=4, scenarios=2)   # -> 48

    This is the disclosure template used by published work that reports a
    Deflated Sharpe Ratio without asking anyone to remember: total effective
    trials are bounded by the product of the search dimensions, and the product
    is reproducible from the code that ran it.

    Every keyword becomes a factor and appears in ``derivation``, so a reader
    can see which dimensions were counted — and, more usefully, which were not.
    Passing a single dimension is allowed and is not the same as ``declared``:
    it still names *what* was varied.
    """
    if not dimensions:
        raise ValueError("from_grid needs at least one dimension")
    for name, n in dimensions.items():
        if not isinstance(n, int) or isinstance(n, bool):
            raise ValueError(f"dimension {name!r}: expected an int, got {type(n).__name__}")
        if n < 1:
            raise ValueError(f"dimension {name!r}: must be >= 1, got {n}")
    lang = resolve_lang(lang)
    total = 1
    for n in dimensions.values():
        total *= n
    parts = " x ".join(f"{name}={n}" for name, n in dimensions.items())
    return TrialCount(
        count=total,
        provenance="grid",
        derivation=f"{parts} = {total}",
        blind_to=[text("trials.blind_grid", lang)],
        evidence={"dimensions": dict(dimensions)},
        lang=lang,
    )


def from_runs(
    records: Iterable[Mapping[str, Any]],
    *,
    key: Optional[Callable[[Mapping[str, Any]], Any]] = None,
    fields: Optional[Sequence[str]] = None,
    coverage: Optional[str] = None,
    lang: str = None,
) -> TrialCount:
    """Count distinct configurations in an execution record.

        from_runs(runs, fields=["lookback", "threshold"])
        from_runs(runs, key=lambda r: r["params"])

    One of ``key`` or ``fields`` is required. That is deliberate: what counts as
    "the same trial" is a modelling decision — two runs of one configuration on
    different seeds may be one trial or two — and a default here would make that
    decision silently, on the caller's behalf, in the direction that flatters.

    Records missing a requested field are counted as **distinct** rather than
    dropped, and their number is reported in ``evidence["incomplete_records"]``.
    Dropping them would shrink the count, and a count that shrinks when the log
    is patchy is the wrong error to make in this direction.

    ``coverage`` is a free-text description of what the log spans — "MLflow,
    experiment 4, from 2026-07-01" — and is appended to ``blind_to``. Omitting
    it is allowed and produces the generic warning instead; there is no way for
    this function to know what the log does not contain.
    """
    if (key is None) == (fields is None):
        raise ValueError("pass exactly one of key= or fields=")
    lang = resolve_lang(lang)

    rows = list(records)
    if not rows:
        raise ValueError("no records — an empty log is not a count of zero trials")

    seen: List[str] = []
    incomplete = 0
    for i, r in enumerate(rows):
        if key is not None:
            k = key(r)
        else:
            missing = [f for f in fields if f not in r]
            if missing:
                incomplete += 1
                k = {"__incomplete_record__": i}
            else:
                k = {f: r[f] for f in fields}
        seen.append(json.dumps(k, sort_keys=True, default=str))

    distinct = len(set(seen))
    by = "key=<callable>" if key is not None else "fields=" + ",".join(fields)
    blind = [coverage] if coverage else [text("trials.blind_log_generic", lang)]
    if incomplete:
        blind.append(text("trials.blind_log_incomplete", lang, n=incomplete))
    return TrialCount(
        count=distinct,
        provenance="log",
        derivation=f"{len(rows)} records, {distinct} distinct by {by}",
        blind_to=blind,
        evidence={
            "records": len(rows),
            "distinct": distinct,
            "incomplete_records": incomplete,
            "grouped_by": by,
        },
        lang=lang,
    )
