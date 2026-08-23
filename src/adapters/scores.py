"""Caller-supplied score table — the input the tool actually claims to take.

Every other adapter in this package turns one vendor's *raw* payload into
observations. That covers the case where the caller has API responses. It does
not cover the far more common one: the caller already has a table of scores,
one row per subject, one column per dimension, produced by whatever mix of
models, vendors and human judgement they happen to run. Those scores are the
thing the redundancy question is actually asked about, and until this adapter
existed there was no way to feed them in without inventing a fake vendor
payload for each one.

Payload shape::

    {"scores": {"physicalConstraint": 5, "moatCapture": 4},
     "scale":  [1, 5],                      # optional, default [0, 100]
     "polarity": "high_is_risk"}            # optional, default as-is

``scale`` is the caller's own range; scores are mapped linearly onto 0–100 so
they sit on the same axis as the vendor adapters. ``polarity`` flips the axis
for tables where a *high* number means *good* rather than *risky* — the
correlation magnitude is unaffected by a flip, but the reported scores are, and
a report whose numbers read backwards is worse than no report.

**Construct names are the caller's, verbatim.** ``CONSTRUCTS`` in
``decision_confidence`` is this repo's own on-chain vocabulary; a caller
scoring semiconductor supply chains has different dimensions and there is no
reason to force them through a translation table. The engine treats a construct
as an opaque grouping key, so an unfamiliar name costs nothing — and pretending
to recognise it would be worse, because the whole question the tool answers is
whether two *named* things are measuring one thing.

Pure function of ``(subject, raw)``. No network.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from decision_confidence import SourceObservation

SOURCE_ID = "scores"

DEFAULT_SCALE = (0.0, 100.0)


def _to_0_100(value: float, lo: float, hi: float, flip: bool) -> Optional[int]:
    if hi == lo:
        return None
    frac = (value - lo) / (hi - lo)
    frac = min(1.0, max(0.0, frac))
    if flip:
        frac = 1.0 - frac
    return int(round(frac * 100))


def parse(subject: str, raw: Dict[str, Any]) -> List[SourceObservation]:
    """One score table row → one observation per declared column.

    A column present in the row but holding ``None`` is emitted as ``missing``
    rather than dropped: a dimension that quietly disappears on the subjects it
    could not score would bias the redundancy check toward the easy ones, which
    is the same failure this adapter is meant to help detect.
    """
    out: List[SourceObservation] = []
    if not isinstance(raw, dict):
        return out

    scores = raw.get("scores")
    if not isinstance(scores, dict):
        return out

    scale = raw.get("scale") or DEFAULT_SCALE
    try:
        lo, hi = float(scale[0]), float(scale[1])
    except (TypeError, ValueError, IndexError):
        lo, hi = DEFAULT_SCALE

    flip = str(raw.get("polarity", "")).lower() in ("high_is_good", "flip", "invert")

    for construct, value in scores.items():
        name = str(construct)
        if value is None:
            out.append(SourceObservation(
                f"{SOURCE_ID}:{name}", subject, {"scores": scores},
                None, "missing", "caller supplied no score for this column",
                construct=name,
            ))
            continue
        try:
            num = float(value)
        except (TypeError, ValueError):
            out.append(SourceObservation(
                f"{SOURCE_ID}:{name}", subject, {"scores": scores},
                None, "malformed", f"score {value!r} is not a number",
                construct=name,
            ))
            continue

        note = f"caller-supplied, scale {lo:g}–{hi:g}"
        if flip:
            note += ", polarity flipped"
        if not (lo <= num <= hi):
            note += f"; {num:g} is outside the declared scale and was clamped"
        out.append(SourceObservation(
            f"{SOURCE_ID}:{name}", subject, {"scores": scores},
            _to_0_100(num, lo, hi, flip), "ok", note, construct=name,
        ))

    return out
