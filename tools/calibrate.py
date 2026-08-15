"""Threshold calibration harness — the instrument, not the result.

Every threshold in this package (verdict bands, contradiction spreads, adapter
penalties) is a rough heuristic chosen by judgement. That is stated plainly in
the README and it remains true. What has been missing is the *means* to fix it:
a repeatable way to point the pipeline at labelled subjects and read off what
each cut-off actually buys.

**Calibration is per construct.** Sweeping a cut-off on the blended composite
is exactly what this library argues against, and once constructs are declared
there is usually no composite to sweep — a subject scored by GoPlus,
honeypot.is and DexScreener spans three constructs and returns ``None``. So
each construct is calibrated on its own scale, against the same labels, and
reported separately. What that buys, beyond correctness, is the question a
blended sweep cannot ask: **which construct actually carries the signal?**

This script does **not** ship a calibrated model, and running it on the bundled
sample proves nothing about real-world accuracy — the sample is synthetic and
exists only to exercise the harness.

Input format — one JSON object per line::

    {"subject": "0x…", "label": 1,
     "sources": [{"vendor": "goplus", "raw": { …payload as received… }},
                 {"vendor": "honeypot_is", "raw": { … }}]}

``label``: 1 = known bad (rug / scam / honeypot), 0 = known good. Payloads are
whatever the vendors returned when the subject was captured — the harness does
no fetching, same rule as the library.

Usage::

    python tools/calibrate.py tools/calibration_sample.jsonl
    python tools/calibrate.py mydata.jsonl --step 5

Candidate labelled datasets, none of them bundled here (licences and sizes
differ, and each needs payloads re-captured per subject):

* **TM-RugPull** (arXiv 2602.21529) — 1,028 projects across five EVM chains,
  2016-2025, built specifically to resist temporal leakage by cutting features
  at a project-midpoint boundary. The most defensible option for this use.
* **RPHunter** (arXiv 2506.18398) — 645 manually analysed rug-pull incidents,
  plus ~4.8k weaker labels from its own detector.
* **Solana rug-pull benchmark** (arXiv 2603.24625) — 117 manually verified
  tokens (Benchmark-117) and 76,469 pipeline-labelled candidates.

READ ``LEAKAGE`` BELOW BEFORE REPORTING ANY NUMBER FROM THIS SCRIPT. Those
label sets are assembled *after* the fact from on-chain outcomes, and payloads
captured today describe a token that has already died. Most constructs are
contaminated by that; one is not.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from adapters import observe_vendor  # noqa: E402
from decision_confidence import build_report  # noqa: E402

# ---------------------------------------------------------------------------
# Temporal leakage, per construct — the thing that decides which of these
# numbers may be quoted.
#
# Labels come from outcomes that already happened. Payloads are captured now.
# For a construct whose value *changes when a project dies*, a today-capture of
# a 2023 rug is not a measurement of what a scanner would have seen before the
# rug — it is a measurement of the corpse. Such a construct will look almost
# perfectly predictive, and the performance will be entirely label leakage.
#
# `authority_control` is the exception that makes the exercise worth running:
# whether the deployer retained mint/pause/blacklist rights is a property of
# the contract, and a dead project's contract still reports what it always
# reported. Judgement, not measurement — stated so it can be argued with.
#
# That exception only became true on 2026-08-07. Until then the GoPlus adapter
# emitted `is_honeypot` / `cannot_sell_all` / `cannot_buy` — three simulation
# verdicts, scored 100/95/90 — under `authority_control`. Those are exactly the
# fields a vendor backfills once a token is known dead, so the one construct
# that survives a post-mortem was being contaminated by the three that do not,
# at top-of-scale weight. They now form a separate `tradability` observation.
# Applying the construct rule to this library's own adapter is what found it.
# ---------------------------------------------------------------------------

# The grades below were written first as predictions; running the harness
# corrected the mechanism. The leak is not in the scores. It is in
# **availability** — whether a construct has any usable data at all moves with
# the label, and a threshold sweep cannot see it. Any pipeline that drops
# unavailable sources silently inherits that skew, which is the practical case
# for reporting `unavailable` as an outcome rather than as absence.
#
# NO MEASURED NUMBER APPEARS IN THIS DICT. It holds a grade and the reasoning
# behind it — the parts that are judgement and do not change when the corpus
# does. Every figure printed next to a construct is computed by
# `compute_skew()` on the run in front of you.
#
# That rule exists because this file broke it. The entries once carried figures
# with the word "measured" attached. A second source was later wired into
# `liquidity_depth`, availability moved, and the static text kept reporting the
# pre-fix number to anyone reading the output — in the same run whose own skew
# table disagreed with it. Two entries were still correct, which is worse than
# all of them being wrong: a reader who spot-checks one believes the rest.
#
# It is the exact failure this library exists to catch — a stale value wearing
# the costume of a fresh measurement — committed by the tool that catches it.
# Hence: a number lives in exactly one place, and everywhere else reads it.
LEAKAGE = {
    "authority_control": ("clean",
                          "contract rights do not change when a project dies"),
    "holder_concentration": ("partial",
                             "supply burned to zero makes the vendor's share arithmetic "
                             "meaningless"),
    "holder_base": ("partial",
                    "holders exit after a rug, so the count is post-mortem; also GoPlus "
                    "returns 0 for some dead tokens where honeypot.is returns thousands, "
                    "and every such case was labelled scam"),
    "tradability": ("severe",
                    "predicted severe on the reasoning that a dead token cannot be sold. "
                    "The measured skew runs the other way, so the prediction is "
                    "unconfirmed rather than supported — GoPlus returns is_honeypot=0 "
                    "for these tokens rather than 1, and whether that means 'simulated "
                    "fine' or 'could not simulate, defaulted to 0' is not established "
                    "here and should not be assumed"),
    "liquidity_depth": ("severe",
                        "a dead token has no pool. A second source later closed the "
                        "availability gap without removing the leak: on the subjects only "
                        "that source covers, the median scam pool is under a dollar. The "
                        "skew moved out of availability and into the values, where a "
                        "sweep can see it — the grade stays severe for that reason, not "
                        "for the original one"),
    "carry_cost": ("severe",
                   "a dead token has no perp market to quote — untested"),
    "fraud_prediction": ("severe",
                         "vendors backfill known scams into their own classifiers — untested"),
    "compliance_exposure": ("severe",
                            "sanctions/KYT lists are updated after incidents — untested"),
}
LEAKAGE_MARK = {"clean": "  ", "partial": " ~", "severe": " !"}


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
            row.setdefault("_lineno", lineno)
            rows.append(row)
    return rows


def report_corpus_integrity(rows: List[Dict[str, Any]]) -> None:
    """Duplicate subjects and contradictory labels, reported rather than fixed.

    A corpus is an instrument too, and this one was described as "203 scam /
    203 legitimate, perfectly balanced" for as long as nobody counted distinct
    addresses rather than lines.

    **Nothing is de-duplicated here, deliberately.** Silently collapsing rows
    would move every figure this harness has ever printed — the same silent
    re-rating the library argues against everywhere else. A duplicate is
    reported so a human can decide whether it is a capture artefact or two
    genuine observations of one subject; the counts below say exactly what the
    denominators contain.

    A subject carrying both labels is worse than a duplicate: it enters the
    confusion matrix as a true positive and a false positive for the same
    threshold, so every precision figure in the run is internally inconsistent
    by that much.
    """
    by_subject: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_subject.setdefault(row["subject"], []).append(row)

    dupes = {s: rs for s, rs in by_subject.items() if len(rs) > 1}
    conflicts = {s: rs for s, rs in by_subject.items()
                 if len({int(r["label"]) for r in rs}) > 1}
    if not dupes and not conflicts:
        return

    print()
    print("### corpus integrity — the labels are an instrument too")
    n_rows, n_subj = len(rows), len(by_subject)
    lab_rows = [int(r["label"]) for r in rows]
    uniq_first = [int(rs[0]["label"]) for rs in by_subject.values()]
    print(f"    rows {n_rows}  distinct subjects {n_subj}  duplicated {len(dupes)}")
    print(f"    by row      positives {sum(lab_rows)}  negatives {len(lab_rows) - sum(lab_rows)}")
    print(f"    by subject  positives {sum(uniq_first)}  negatives {len(uniq_first) - sum(uniq_first)}"
          f"   <- the balance an unqualified 'n=' implies")
    print("    Every figure in this run is computed by row, duplicates included.")

    if conflicts:
        print()
        for subject, rs in sorted(conflicts.items()):
            labels = sorted({int(r["label"]) for r in rs})
            lines = ", ".join(str(r.get("_lineno", "?")) for r in rs)
            title = next((r.get("title") for r in rs if r.get("title")), "")
            print(f"    ! {subject} carries labels {labels} on lines {lines}"
                  + (f"  — {title}" if title else ""))
        print("    A subject cannot be both. Precision in this run is inconsistent")
        print("    by that many subjects until the label is resolved upstream.")


def score_rows(rows: List[Dict[str, Any]]):
    """Returns ``(per_construct, per_subject, status_counts)``.

    ``per_construct`` maps a construct to ``[(score, label)]`` — the pairs that
    can legitimately be swept, because within a construct the scale means one
    thing. ``per_subject`` keeps every subject's construct→score map so that
    combination rules can be measured without re-running the pipeline.
    """
    per_construct: Dict[str, List[Tuple[int, int]]] = {}
    per_subject: List[Tuple[Dict[str, int], int]] = []
    status_counts: Dict[str, Dict[str, int]] = {}
    availability: Dict[str, Dict[Tuple[int, bool], int]] = {}
    # Which subjects lack usable data, per construct. Kept so that two skew
    # rows can be checked for whether they are two findings or one.
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
        label = int(row["label"])

        scores: Dict[str, int] = {}
        for g in report.constructs:
            bucket = availability.setdefault(g.construct, {})
            key = (label, g.n_ok > 0)
            bucket[key] = bucket.get(key, 0) + 1
            if g.n_ok == 0:
                missing.setdefault(g.construct, set()).add(row["subject"])
            if g.score is None:
                continue
            scores[g.construct] = g.score
            per_construct.setdefault(g.construct, []).append((g.score, label))
        per_subject.append((scores, label))

        for o in report.observations:
            bucket = status_counts.setdefault(o.source_id, {})
            bucket[o.status] = bucket.get(o.status, 0) + 1

    return per_construct, per_subject, status_counts, availability, missing


def compute_skew(availability) -> Dict[str, Tuple[float, float, float]]:
    """The single source of truth for availability skew: ``{construct: (pb, pg, skew)}``.

    Whether a construct *has data at all* correlates with the label. That is
    where leakage actually lives, and it is invisible to a threshold sweep —
    nothing about the *scores* is contaminated, the contamination is in which
    subjects have a score at all.

    Everything that prints a skew figure calls this. Nothing writes one down.
    """
    out: Dict[str, Tuple[float, float, float]] = {}
    for construct, c in (availability or {}).items():
        b_ok, b_no = c.get((1, True), 0), c.get((1, False), 0)
        g_ok, g_no = c.get((0, True), 0), c.get((0, False), 0)
        pb = _ratio(b_ok, b_ok + b_no)
        pg = _ratio(g_ok, g_ok + g_no)
        out[construct] = (pb, pg, pb - pg)
    return out


def report_availability_skew(skews: Dict[str, Tuple[float, float, float]]) -> None:
    """Print the skew table computed by :func:`compute_skew`.

    Historical note, because the original finding is what motivated the check:
    when DexScreener was the only source for ``liquidity_depth``, that construct
    had usable data for 4.9% of scams and 61.6% of legitimate tokens on a
    400-subject rug-pull sample — a dead token has no pool. Those two figures
    describe a configuration this repo no longer runs and are deliberately not
    reprinted as if they were current; the table below is this run.

    Any pipeline that drops unavailable sources silently inherits whatever skew
    is in the table and will never see it, which is the practical argument for
    reporting ``unavailable`` as a first-class outcome rather than as absence.
    """
    if not skews:
        return
    print()
    print("### availability skew — does having data at all predict the label?")
    print("    (a leak a threshold sweep cannot see)")
    print(f"    {'construct':<24}{'bad w/ data':>14}{'good w/ data':>15}{'skew':>10}")
    worst = []
    for construct in sorted(skews):
        pb, pg, skew = skews[construct]
        mark = " !" if abs(skew) >= 0.20 else ("  ~" if abs(skew) >= 0.10 else "")
        print(f"    {construct:<24}{pb:>13.1%}{pg:>15.1%}{skew:>+9.1%}{mark}")
        if abs(skew) >= 0.20:
            worst.append((construct, skew))
    if worst:
        print()
        for construct, skew in sorted(worst, key=lambda kv: -abs(kv[1])):
            print(f"    {construct}: presence of data alone moves {abs(skew):.0%} with the label.")
        print("    Treat any performance on those constructs as unearned.")


JACCARD_DEPENDENT = 0.80  # judgement, not a measurement — see below


def report_skew_dependence(missing: Dict[str, set],
                           skews: Dict[str, Tuple[float, float, float]]) -> None:
    """Are two skew rows two findings, or one finding printed twice?

    Availability skew is driven entirely by *which subjects lack data*. If two
    constructs lack data on the same subjects, their skews are not independent
    evidence that leakage is widespread — they are one gap, counted twice. The
    table above cannot show this, because each row is computed alone.

    On the corpus this was written for, three constructs printed an identical
    skew and two of them missed the same 18 of 19 subjects.

    ``JACCARD_DEPENDENT = 0.80`` is a judgement, in the same class as every
    other threshold here: it marks a pair as *worth not double-counting*, not
    as proven redundant. The overlap figure is printed for every pair above
    0.50 so the cut-off can be argued with rather than trusted.
    """
    pairs = []
    names = sorted(c for c in skews if missing.get(c))
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            sa, sb = missing[a], missing[b]
            union = sa | sb
            if not union:
                continue
            j = len(sa & sb) / len(union)
            if j >= 0.50:
                pairs.append((j, a, b, len(sa & sb), len(union)))
    if not pairs:
        return

    print()
    print("### are these skews independent? (overlap of the missing-data sets)")
    print("    two constructs blind on the same subjects produce one finding, not two")
    for j, a, b, inter, union in sorted(pairs, reverse=True):
        mark = " <- treat as one" if j >= JACCARD_DEPENDENT else ""
        print(f"    {a:<22} ∩ {b:<22} {inter:>4}/{union:<4} overlap {j:>5.2f}{mark}")
    if any(j >= JACCARD_DEPENDENT for j, *_ in pairs):
        print(f"    Rows overlapping at or above {JACCARD_DEPENDENT:.2f} share a cause.")
        print("    Counting them as separate evidence overstates how many places")
        print("    the leak was found.")


def _ratio(num: int, den: int) -> float:
    return num / den if den else 0.0


def _prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * precision * recall, precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def confusion(pairs: List[Tuple[int, int]], threshold: int) -> Tuple[int, int, int, int]:
    tp = fp = tn = fn = 0
    for score, label in pairs:
        predicted_bad = score >= threshold
        if predicted_bad and label == 1:
            tp += 1
        elif predicted_bad and label == 0:
            fp += 1
        elif not predicted_bad and label == 1:
            fn += 1
        else:
            tn += 1
    return tp, fp, tn, fn


def sweep_construct(construct: str, pairs: List[Tuple[int, int]], step: int,
                    n_subjects: int,
                    skews: Optional[Dict[str, Tuple[float, float, float]]] = None,
                    ) -> Optional[Tuple[float, int]]:
    grade, why = LEAKAGE.get(construct, ("unknown", "no leakage assessment for this construct"))
    n_bad = sum(1 for _, lab in pairs if lab == 1)
    print()
    print(f"### {construct}   [leakage: {grade}] — {why}")
    # The figure comes from this run, never from the dict above.
    measured = (skews or {}).get(construct)
    if measured:
        print(f"    availability skew {measured[2]:+.1%} — measured on this corpus, "
              f"not carried over")
    print(f"    coverage {len(pairs)}/{n_subjects} subjects "
          f"({_ratio(len(pairs), n_subjects):.0%})   positives {n_bad}")
    if len(pairs) < 2 or n_bad == 0 or n_bad == len(pairs):
        print("    not sweepable — needs both labels present in the covered subset")
        return None

    print(f"    {'cut':>4} {'TP':>4} {'FP':>4} {'TN':>4} {'FN':>4} "
          f"{'precision':>10} {'recall':>8} {'F1':>7}")
    best = (0.0, 0)
    for threshold in range(0, 101, step):
        tp, fp, tn, fn = confusion(pairs, threshold)
        precision, recall, f1 = _prf(tp, fp, fn)
        print(f"    {threshold:>4} {tp:>4} {fp:>4} {tn:>4} {fn:>4} "
              f"{precision:>10.3f} {recall:>8.3f} {f1:>7.3f}")
        if f1 > best[0]:
            best = (f1, threshold)
    print(f"    best F1 {best[0]:.3f} at {construct} >= {best[1]}")
    return best


def sweep_any_construct(per_subject, step: int) -> None:
    """The combination rule the construct split implies: OR, not average.

    'These are not comparable' does not mean 'no decision is possible'. It
    means the decision is a logical combination of per-construct cut-offs
    rather than a mean. This measures the simplest such rule — flag a subject
    when *any* construct clears its cut-off — as a baseline for whatever
    replaces it.
    """
    print()
    print("### combination rule: flag when ANY construct >= cut")
    print("    (the split forbids averaging; it does not forbid deciding)")
    print(f"    {'cut':>4} {'TP':>4} {'FP':>4} {'TN':>4} {'FN':>4} "
          f"{'precision':>10} {'recall':>8} {'F1':>7}")
    best = (0.0, 0)
    for threshold in range(0, 101, step):
        tp = fp = tn = fn = 0
        for scores, label in per_subject:
            if not scores:
                continue
            predicted_bad = any(v >= threshold for v in scores.values())
            if predicted_bad and label == 1:
                tp += 1
            elif predicted_bad and label == 0:
                fp += 1
            elif not predicted_bad and label == 1:
                fn += 1
            else:
                tn += 1
        precision, recall, f1 = _prf(tp, fp, fn)
        print(f"    {threshold:>4} {tp:>4} {fp:>4} {tn:>4} {fn:>4} "
              f"{precision:>10.3f} {recall:>8.3f} {f1:>7.3f}")
        if f1 > best[0]:
            best = (f1, threshold)
    print(f"    best F1 {best[0]:.3f} at any-construct >= {best[1]}")


def rank(results: Dict[str, Optional[Tuple[float, int]]]) -> None:
    scored = {k: v for k, v in results.items() if v}
    if not scored:
        return
    print()
    print("### which construct carries the signal")
    print("    (a question a blended sweep cannot ask)")
    print(f"    {'construct':<24}{'best F1':>9}{'at cut':>8}  leakage")
    for construct, (f1, cut) in sorted(scored.items(), key=lambda kv: -kv[1][0]):
        grade = LEAKAGE.get(construct, ("unknown", ""))[0]
        print(f"    {construct:<24}{f1:>9.3f}{cut:>8}{LEAKAGE_MARK.get(grade, '  ')} {grade}")
    clean = [c for c in scored if LEAKAGE.get(c, ("unknown",))[0] == "clean"]
    print()
    if clean:
        print(f"    Only {', '.join(clean)} is quotable without a leakage caveat.")
    else:
        print("    No leakage-clean construct in this run — nothing here is quotable")
        print("    as predictive performance.")
    print("    ! severe  ~ partial   — see LEAKAGE in this file for the reasoning.")


def report_coverage(status_counts: Dict[str, Dict[str, int]]) -> None:
    if not status_counts:
        return
    print("\n### per-source status counts (how often each source was usable at all)")
    for source_id in sorted(status_counts):
        counts = status_counts[source_id]
        total = sum(counts.values())
        parts = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        ok_rate = _ratio(counts.get("ok", 0), total)
        print(f"    {source_id:<26} ok-rate {ok_rate:>6.1%}   {parts}")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dataset", help="JSONL file of labelled subjects with captured payloads")
    ap.add_argument("--step", type=int, default=10, help="threshold step (default 10)")
    args = ap.parse_args(argv)

    rows = load_rows(args.dataset)
    per_construct, per_subject, status_counts, availability, missing = score_rows(rows)
    step = max(1, args.step)

    n_bad = sum(1 for _, lab in per_subject if lab == 1)
    print(f"subjects: {len(per_subject)}  positives: {n_bad}  "
          f"constructs observed: {len(per_construct)}")

    skews = compute_skew(availability)
    results = {
        construct: sweep_construct(construct, pairs, step, len(per_subject), skews)
        for construct, pairs in sorted(per_construct.items())
    }
    sweep_any_construct(per_subject, step)
    rank(results)
    report_availability_skew(skews)
    report_skew_dependence(missing, skews)
    report_coverage(status_counts)
    report_corpus_integrity(rows)

    print()
    print("Read this as a diagnostic, not a verdict. Thresholds tuned here are "
          "tuned for\npost-mortem recognition, which is not the same problem as "
          "pre-commitment warning.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
