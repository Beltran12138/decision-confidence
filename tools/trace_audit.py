#!/usr/bin/env python3
"""Audit an agent's research trace: how many trials, and was the holdout sealed?

Reads a Claude Code session transcript (JSONL) and writes nothing.

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


def _ev(e):
    return None if e is None else {"ts": e.ts.isoformat(), "tool": e.tool,
                                   "excerpt": e.excerpt(160)}


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
    ap.add_argument("--lang", choices=LANGS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if bool(a.seal) != bool(a.holdout):
        ap.error("--seal and --holdout go together")
    if bool(a.gap_result) != bool(a.gap_start):
        ap.error("--gap-result and --gap-start go together")
    if not (a.unit or a.seal or a.gap_result):
        ap.error("nothing to do: give --unit, --seal/--holdout or --gap-result/--gap-start")
    lang = resolve_lang(a.lang)

    with open(a.transcript, encoding="utf-8") as fh:
        trace = ta.events_from_claude_code(fh)
    ev = [e for e in trace.events
          if (a.since is None or e.ts >= a.since) and (a.until is None or e.ts <= a.until)]
    trace = ta.Trace(ev, trace.skipped_lines)

    out = {"events": len(ev), "skipped_lines": trace.skipped_lines}
    lines = [f"{len(ev)} events" + (f", {trace.skipped_lines} unparsed lines"
                                    if trace.skipped_lines else "")]

    if a.unit:
        tab = ta.count_units(trace, a.unit, lang=lang)
        w = max(len(r.unit.name) for r in tab.rows)
        lines.append("")
        for r in tab.rows:
            n = str(r.trials.count) if r.trials else text("trace.no_match", lang)
            lines.append(f"  {r.unit.name:<{w}}  {n:>6}   /{r.unit.pattern}/ on {r.unit.kind}s")
        lines.append("")
        lines.append(tab.note(lang))
        first = next((r.trials for r in tab.rows if r.trials), None)
        if first and first.blind_to:
            lines.append(text("trials.blind_to", lang, items="; ".join(first.blind_to)))
        out["units"] = [{"name": r.unit.name, "kind": r.unit.kind, "pattern": r.unit.pattern,
                         "matches": r.matches,
                         "trials": r.trials.to_dict() if r.trials else None}
                        for r in tab.rows]
        out["spread"] = tab.spread

    if a.seal:
        rep = ta.seal_check(trace, seal=a.seal, holdout=a.holdout, lang=lang)
        lines.append("")
        lines.append(rep.note(lang))
        marks = sorted([("seal ", e) for e in rep.seals] + [("touch", e) for e in rep.touches],
                       key=lambda p: p[1].ts)
        for tag, e in marks:
            lines.append(f"  {e.ts.strftime('%H:%M:%S')}  {tag}  {e.tool:<6} {e.excerpt(90)}")
            o = rep.output_of(e) if tag == "touch" else None
            if o is not None and e in rep.touches_before_last_seal:
                lines.append(f"{'':>18}<- {o.excerpt(90)}")
        lines.append(rep.blind_to[0])
        out["seal"] = {"verdict": rep.verdict, "seals": [_ev(e) for e in rep.seals],
                       "touches": [dict(_ev(e), output=_ev(rep.output_of(e)))
                                   for e in rep.touches],
                       "touches_before_last_seal": [_ev(e) for e in rep.touches_before_last_seal],
                       "blind_to": rep.blind_to}

    if a.gap_result:
        gs = ta.gaps(trace, result=a.gap_result, start=a.gap_start)
        lines.append("")
        for g in gs:
            s = "-" if g.seconds is None else f"{g.seconds:.0f}s"
            nxt = g.next_call.excerpt(60) if g.next_call else "-"
            lines.append(f"  {g.result.ts.strftime('%H:%M:%S')}  {s:>7}  {g.result_line[:50]}  ->  {nxt}")
        out["gaps"] = [{"result": _ev(g.result), "line": g.result_line,
                        "next_call": _ev(g.next_call), "seconds": g.seconds} for g in gs]

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str) if a.json
          else "\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
