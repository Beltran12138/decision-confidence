#!/usr/bin/env python3
"""Did the agent read its inputs, or recite an outcome it already knew?

You run the perturbations; this scores the table. Take a case the agent already
analysed, change one fact, re-ask, record whether the *conclusion* changed
(different wording for the same call is not a change), repeat.

    python tools/perturb.py --material 5/6 --cosmetic 0/6
    python tools/perturb.py --material 2/6 --cosmetic 1/6 --alpha 0.01 --lang zh

The two arguments are ``flipped/total``. Two kinds are required and they have
opposite expectations:

    material   good news to bad, policy reversed, a beat turned into a miss
               -> the conclusion SHOULD move
    cosmetic   renamed ticker, shifted dates, rescaled magnitudes
               -> the conclusion SHOULD NOT move

Only material perturbations cannot be scored: "never flips" and "reads nothing"
are the same observation without a control. Six is the floor — 3+3 split
perfectly gives p = 0.0500 exactly, and below that no result can be significant.

Reads two counts and writes nothing. No network. The details of each run belong
in your own notes; this tool needs only how many of each kind moved the answer.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from counterfactual import (  # noqa: E402  (path set above)
    COSMETIC, MATERIAL, Perturbation, minimum_perturbations,
    perturbation_audit, remedies,
)
from messages import LANGS, resolve_lang, text  # noqa: E402

CLOSERS = "」』）〉》”’。，；、！？%"


def ratio(value: str) -> "tuple[int, int]":
    """Parse ``flipped/total``, refusing the impossible rather than clamping."""
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", value)
    if not m:
        raise argparse.ArgumentTypeError(
            "expected flipped/total, e.g. 5/6 — got %r" % value)
    flipped, total = int(m.group(1)), int(m.group(2))
    if flipped > total:
        raise argparse.ArgumentTypeError(
            "%d flipped out of %d is impossible" % (flipped, total))
    return flipped, total


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--material", type=ratio, metavar="F/N", default=(0, 0),
                    help="material perturbations: how many flipped out of how many")
    ap.add_argument("--cosmetic", type=ratio, metavar="F/N", default=(0, 0),
                    help="cosmetic perturbations: flipped/total (the control)")
    ap.add_argument("--alpha", type=float, default=0.05,
                    help="significance bar for the one-sided Fisher test (default 0.05)")
    ap.add_argument("--lang", default=None, choices=list(LANGS),
                    help="output language (default en)")
    args = ap.parse_args()
    lang = resolve_lang(args.lang)

    (mf, mn), (cf, cn) = args.material, args.cosmetic
    runs = ([Perturbation(MATERIAL, "material %d" % (i + 1), i < mf) for i in range(mn)]
            + [Perturbation(COSMETIC, "cosmetic %d" % (i + 1), i < cf) for i in range(cn)])

    try:
        r = perturbation_audit(runs, alpha=args.alpha, lang=lang)
    except ValueError as exc:
        print(text("cli.bad_input", lang, err=exc), file=sys.stderr)
        return 1

    W = 76 if lang == "en" else 66
    need = minimum_perturbations(r.alpha)

    print()
    print("material  %d/%d flipped   %s" % (mf, mn, pct(r.material_rate, mn)))
    print("cosmetic  %d/%d flipped   %s" % (cf, cn, pct(r.cosmetic_rate, cn)))
    print("alpha     %g          floor  %d (%d + %d)"
          % (r.alpha, need["total"], need["material"], need["cosmetic"]))
    print()

    if r.p_value is not None:
        print("one-sided Fisher   p = %.4f" % r.p_value)
        print("best possible here p = %.4f%s"
              % (r.best_possible_p,
                 "   <- already the best this size can do"
                 if r.verdict == "no_power" else ""))
        print()

    rule = "─" * 56
    print(rule)
    print("  " + r.verdict)
    print(rule)
    print()
    for line in _wrap(text("cf.verdict." + r.verdict, lang), W - 2):
        print("  " + line)
    print()

    marks = "①②③④⑤⑥⑦⑧"
    for i, line in enumerate(remedies(r, lang)):
        mark = marks[i] if i < len(marks) else "·"
        wrapped = _wrap(line, W - 2)
        print("  %s %s" % (mark, wrapped[0]))
        for cont in wrapped[1:]:
            print("     " + cont)
    print()
    print("! " + "\n  ".join(_wrap(text("cf.limits", lang), W - 2)))
    print()
    return 0


def pct(rate: float, n: int) -> str:
    return "" if n == 0 else "(%.0f%%)" % (rate * 100)


def _cols(t: str) -> int:
    """Display columns, not characters — CJK glyphs take two cells."""
    return sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in t)


def _wrap(t: str, width: int):
    """Same wrapper as tools/window.py, and the same two thresholds.

    Chinese punctuation breaks early and reads fine; a space usually hugs a
    number, so it only breaks late — but it stays, because it is the one thing
    between a hard break and a bisected identifier.
    """
    out, line = [], ""
    soft_punct = max(1, int(width * 0.62))
    soft_space = max(1, int(width * 0.85))
    chars = list(t)
    for i, ch in enumerate(chars):
        line += ch
        cols = _cols(line)
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if (cols >= soft_punct and ch in "。，；、！？") or (cols >= soft_space and ch == " "):
            out.append(line.strip())
            line = ""
        elif cols >= width and nxt not in CLOSERS:
            out.append(line.strip())
            line = ""
    if line.strip():
        out.append(line.strip())
    return out


if __name__ == "__main__":
    raise SystemExit(main())
