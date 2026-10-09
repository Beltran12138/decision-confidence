#!/usr/bin/env python3
"""Audit an agent's research trace: how many trials, and was the holdout sealed?

Reads an agent transcript and writes nothing. Claude Code session JSONL and
Codex CLI rollouts are detected automatically; any other harness can export the
generic one-event-per-line schema documented in ``src/trace_audit.py`` and pass
``--format events``. Patterns are harness-specific: tool names and the JSON a
call is serialised to differ between formats.

    python tools/trace_audit.py SESSION.jsonl \\
        --since 2026-10-07T15:00 --until 2026-10-07T17:30 \\
        --unit 'runs:call:python \\S*(backtest|replication)\\.py' \\
        --unit 'verdicts:output:=> [A-Z]|-> +(FALSIFY|SUPPORT)' \\
        --seal '"file_path": "[^"]*PREREG|>> *"?[^ ]*PREREG' \\
        --holdout 'captured-fresh' \\
        --gap-result '(FALSIFY|SUPPORT|REPLICATED)' --gap-start '"file_path"|cat >'

Every pattern is required rather than defaulted. What counts as one trial,
what seals a plan and what the holdout is are decisions about *this* study; a
default would make them on the caller's behalf and print the result as if
someone had.

``--unit`` takes ``NAME:KIND:REGEX`` and may be repeated; KIND is ``call`` (tool
calls) or ``output`` (lines of tool output). Times are UTC, as the transcript
records them. ``--json`` prints the full result, matched events included.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import trace_audit as ta  # noqa: E402  (path set above)
from messages import LANGS, resolve_lang, text  # noqa: E402


def _when(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _unit(s: str) -> ta.Unit:
    parts = s.split(":", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(f"--unit wants NAME:KIND:REGEX, got {s!r}")
    try:
        return ta.Unit(*parts)
    except Exception as e:  # bad kind or bad regex
        raise argparse.ArgumentTypeError(str(e))


def _hms(iso: str) -> str:
    return iso[11:19]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("transcript")
    ap.add_argument("--since", type=_when)
    ap.add_argument("--until", type=_when)
    ap.add_argument("--unit", type=_unit, action="append", default=[])
    ap.add_argument("--seal")
    ap.add_argument("--holdout")
    ap.add_argument("--gap-result")
    ap.add_argument("--gap-start")
    ap.add_argument("--format", choices=ta.FORMATS,
                    help="transcript format; detected from the first lines if omitted")
    ap.add_argument("--lang", choices=LANGS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    lang = resolve_lang(a.lang)
    try:  # check the arguments before reading what may be a very large file
        ta.audit(ta.Trace([]), units=a.unit, seal=a.seal, holdout=a.holdout,
                 gap_result=a.gap_result, gap_start=a.gap_start, lang=lang)
    except ValueError as e:
        ap.error(str(e))

    with open(a.transcript, encoding="utf-8") as fh:
        trace = ta.window(ta.load_trace(fh, a.format), a.since, a.until)
    try:
        out = ta.audit(trace, units=a.unit, seal=a.seal, holdout=a.holdout,
                       gap_result=a.gap_result, gap_start=a.gap_start, lang=lang)
    except ValueError as e:
        ap.error(str(e))
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    # Text is rendered from the same dict --json prints, so the two cannot differ.
    lines = [f"{out['format']}: {out['events']} events"
             + (f", {out['human_turns']} human turns" if out["human_turns"] is not None else "")
             + (f", {out['skipped_lines']} unparsed lines" if out["skipped_lines"] else "")]
    if "units" in out:
        w = max(len(u["name"]) for u in out["units"])
        lines.append("")
        for u in out["units"]:
            n = str(u["trials"]["count"]) if u["trials"] else u["note"]
            lines.append(f"  {u['name']:<{w}}  {n:>6}   /{u['pattern']}/ on {u['kind']}s")
        lines.append("")
        lines.append(out["units_note"])
        first = next((u["trials"] for u in out["units"] if u["trials"]), None)
        if first and first["blind_to"]:
            lines.append(text("trials.blind_to", lang, items="; ".join(first["blind_to"])))
    if "seal" in out:
        s = out["seal"]
        lines.append("")
        lines.append(s["note"])
        marks = sorted([("seal ", e) for e in s["seals"]] + [("touch", e) for e in s["touches"]],
                       key=lambda p: p[1]["ts"])
        for tag, e in marks:
            lines.append(f"  {_hms(e['ts'])}  {tag}  {e['tool']:<6} {e['excerpt'][:90]}")
            if tag == "touch" and e.get("before_last_seal") and e.get("output"):
                lines.append(f"{'':>18}<- {e['output']['excerpt'][:90]}")
        lines.append(s["blind_to"][0])
    if "gaps" in out:
        lines.append("")
        for g in out["gaps"]:
            sec = "-" if g["seconds"] is None else f"{g['seconds']:.0f}s"
            nxt = g["next_call"]["excerpt"][:60] if g["next_call"] else "-"
            who = {True: "human", False: "agent", None: "?"}[g["human_between"]]
            lines.append(f"  {_hms(g['result']['ts'])}  {sec:>7}  {who:<5}  {g['line'][:50]}  ->  {nxt}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
