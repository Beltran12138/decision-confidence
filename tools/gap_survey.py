#!/usr/bin/env python3
"""Where the gap numbers in ``trace_audit.gaps`` come from.

For every transcript under the given roots: each time an agent wrote a new
Python file, take the most recent script output before it, and record the gap
and whether a human turn fell in between. Then ask whether a seconds threshold
could stand in for that flag.

    python tools/gap_survey.py ~/.claude/projects ~/.codex/sessions

The transcripts are the author's own and are not in this repository, so the
figures quoted in the docstring cannot be reproduced from a clone — only the
method can. Run it on your own transcripts and compare. One user's working
style is one population; expect different numbers from another.

"A new analysis" is proxied by "a new .py file" and "a result" by the output
of a call that ran Python. Both proxies are stated here because both are
choices: an agent that iterates inside one notebook never trips the first.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import trace_audit as ta  # noqa: E402

RUN = r'python[0-9.]*(\.exe)?"? +(-c|-|[^ ]*\.py)'
NEW_PY = {
    "claude_code": r'"file_path": "[^"]*\.py"',
    "codex": r"Add File: [^\n]*\.py|(>|Set-Content|Out-File)[^|;\n]*\.py",
}
NEW_TOOL = {"claude_code": ("Write",), "codex": ("apply_patch", "exec_command", "shell_command", "exec")}


def transitions(trace: ta.Trace):
    """(gap_seconds, human_between) per new script, nearest preceding run output."""
    rx_run, rx_new = re.compile(RUN), re.compile(NEW_PY[trace.format])
    calls = {e.call_id: e for e in trace.events if e.kind == "call"}
    is_new = lambda e: (e.kind == "call" and e.tool in NEW_TOOL[trace.format]
                        and rx_new.search(e.text))
    best = {}
    ev = trace.events
    for i, e in enumerate(ev):
        if e.kind != "output":
            continue
        c = calls.get(e.call_id)
        if c is None or not rx_run.search(c.text) or is_new(c):
            continue
        nxt = next((x for x in ev[i + 1:] if is_new(x)), None)
        if nxt is None or nxt.ts < e.ts:
            continue
        gap = (nxt.ts - e.ts).total_seconds()
        if nxt.call_id not in best or gap < best[nxt.call_id][0]:
            human = any(x.kind == "prompt" and e.ts < x.ts < nxt.ts for x in ev)
            best[nxt.call_id] = (gap, human)
    return list(best.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("roots", nargs="+")
    a = ap.parse_args(argv)
    files = []
    for root in a.roots:
        files += glob.glob(os.path.join(os.path.expanduser(root), "**", "*.jsonl"), recursive=True)
    rows, sessions = [], set()
    for f in files:
        with open(f, encoding="utf-8", errors="replace") as fh:
            try:
                tr = ta.load_trace(fh)
            except ValueError:
                continue
        if tr.format not in NEW_PY:
            continue
        got = transitions(tr)
        if got:
            sessions.add(f)
        rows += got
    if not rows:
        print("no transitions found")
        return 1
    agent = sorted(g for g, h in rows if not h)
    human = sorted(g for g, h in rows if h)

    def line(name, xs):
        if not xs:
            return f"  {name:<14} n=0"
        q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
        return (f"  {name:<14} n={len(xs):4d}  p10={q(.1):7.0f}s  "
                f"median={statistics.median(xs):7.0f}s  p90={q(.9):9.0f}s")

    print(f"{len(files)} transcripts, {len(sessions)} with transitions, {len(rows)} transitions")
    print(line("no human turn", agent))
    print(line("human turn", human))
    cands = sorted({g for g, _ in rows})
    err = lambda t: sum((g <= t) == h for g, h in rows)
    t = min(cands, key=err)
    print(f"  best single threshold {t:.0f}s misclassifies {err(t)}/{len(rows)} "
          f"= {err(t) / len(rows):.1%} against the human-turn flag it would stand in for")
    return 0


if __name__ == "__main__":
    sys.exit(main())
