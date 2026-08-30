#!/usr/bin/env python3
"""Do the browser and the library still agree?

``docs/index.html`` reimplements ``src/effective_window.py`` in JavaScript so
the page can run with no backend. Two implementations of one rule drift, and
the drift is silent: nothing fails, the page just quietly answers a different
question than the CLI. The footer states a checkable default for a human to
eyeball, which catches a rewrite but not a rounding change.

This runs both and compares them. It extracts the pure functions from the
page's ``<script>`` — no DOM is touched — evaluates them under Node, and
diffs against the Python for a grid of inputs.

    python tools/check_js_parity.py            # exit 0 if they agree
    python tools/check_js_parity.py --verbose  # print every row

Node is optional. Without it this skips rather than fails, because the library
does not depend on it and a missing dev tool is not a broken library.

**What "agree" means here.** The months requirement must match exactly — it is
the number anyone acts on. The t bar is allowed to differ by ``T_TOL``: the
page's normal CDF is the Abramowitz & Stegun 7.1.26 approximation (|ε| < 1.5e-7)
where Python has the real thing, and the error is largest where alpha is
smallest. Observed worst case across this grid is ~1.5e-5, which is invisible
at the two decimals the page prints — but it *could* flip a ceil() at a
boundary, so the months comparison is the one that is strict.

**Remedies are compared verbatim.** They are where the drift actually happened:
the page's advice was written from the CLI's *pre-fix* version and carried four
wrong lines for a while — an inverted date range, a remedy that could not work,
one that applied to a segment that did not exist, and a Sharpe of infinity.
Numbers agreeing while advice diverges is the worse failure, because the advice
is what a reader acts on. This is also why the page emits plain sentences with
no ``<b>`` markup: a formatted copy cannot be diffed against a plain one, and
being checkable beat being bold.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from effective_window import (  # noqa: E402
    effective_window, remedies, selection_penalty,
)

T_TOL = 1e-4

# trials, effective_trials — spanning the identity case, the ordinary range,
# the published-factor end, and every shape of discount.
GRID = [(1, None), (2, None), (5, None), (10, None), (17, None), (20, None),
        (50, None), (100, None), (316, None), (50, 5), (20, 4), (100, 2.5),
        (7, 7), (3, 1)]
BARS = [2.0, 3.0]

# Date shapes for the remedy comparison: every verdict, with and without an
# open-book span, and both sides of "could an earlier model fix this".
RANGES = [
    ("2024-10", "2020-01", "2025-06"),   # underpowered, open book, earlier model helps
    ("2026-01", "2020-01", "2025-06"),   # no_holdout
    ("2015-01", "2020-01", "2025-06"),   # entirely clean
    ("2015-01", "2010-01", "2025-06"),   # entirely clean and long
    ("2022-06", "2020-01", "2025-06"),   # cutoff mid-range
    ("2020-01", "2020-01", "2020-01"),   # single month, fully seen
]
REMEDY_TRIALS = [None, 1, 20, 200]


def extract_js() -> str:
    """The pure functions from the page, up to the first DOM-touching one."""
    page = os.path.join(ROOT, "docs", "index.html")
    with open(page, encoding="utf-8") as fh:
        html = fh.read()
    script = re.search(r"<script>(.*)</script>", html, re.S)
    if script is None:
        raise SystemExit("no <script> block in docs/index.html")
    js = script.group(1)
    try:
        return js[js.index("function ymIdx"):js.index("function runWindow")]
    except ValueError:
        raise SystemExit(
            "docs/index.html no longer contains ymIdx..runWindow — "
            "this extractor is pinned to that layout and needs updating"
        )


def run_node(core: str):
    cases = json.dumps([[n, k, t] for n, k in GRID for t in BARS])
    harness = core + """
const out = [];
for (const [n, k, tb] of %s) {
  const p = selectionPenalty(n, k, tb, 1.0);
  out.push({n: n, k: k, tb: tb, t: p.tAdj, months: p.monthsAdj});
}
console.log(JSON.stringify(out));
""" % cases
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(harness)
        res = subprocess.run(["node", path], capture_output=True, text=True)
    finally:
        os.unlink(path)
    if res.returncode != 0:
        raise SystemExit("node failed:\n" + res.stderr[:2000])
    return json.loads(res.stdout)


def run_node_remedies(core: str):
    """Same extraction, exercising the advice rather than the arithmetic."""
    cases = json.dumps([[c, s, e, t] for (c, s, e) in RANGES for t in REMEDY_TRIALS])
    harness = core + """
const out = [];
for (const [c, s, e, t] of %s) {
  const w = evaluateWindow(c, s, e, 1.0, 2.0, t, null);
  if (w.error) { out.push({cutoff: c, start: s, end: e, trials: t,
                           verdict: "ERROR:" + w.error, remedies: []}); continue; }
  out.push({cutoff: c, start: s, end: e, trials: t,
            verdict: w.verdict, remedies: remediesFor(w)});
}
console.log(JSON.stringify(out));
""" % cases
    fd, path = tempfile.mkstemp(suffix=".js")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(harness)
        res = subprocess.run(["node", path], capture_output=True,
                             text=True, encoding="utf-8")
    finally:
        os.unlink(path)
    if res.returncode != 0:
        raise SystemExit("node failed (remedies):\n" + res.stderr[:2000])
    return json.loads(res.stdout)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        print("node not found — skipping parity check (not a failure)")
        return 0

    core = extract_js()
    rows = run_node(core)
    worst_t, mismatches = 0.0, []

    if args.verbose:
        print(f"{'trials':>7}{'n_eff':>8}{'t_bar':>7} | "
              f"{'JS t':>10}{'PY t':>10}{'diff':>11} | {'JS':>5}{'PY':>5}")
    for r in rows:
        p = selection_penalty(r["n"], effective_trials=r["k"],
                              t_base=r["tb"], target_sharpe=1.0)
        dt = abs(r["t"] - p.t_adjusted)
        worst_t = max(worst_t, dt)
        same = r["months"] == p.months_adjusted and dt <= T_TOL
        if not same:
            mismatches.append((r, p, dt))
        if args.verbose:
            print(f'{r["n"]:>7}{str(r["k"]):>8}{r["tb"]:>7.1f} | '
                  f'{r["t"]:>10.6f}{p.t_adjusted:>10.6f}{dt:>11.2e} | '
                  f'{r["months"]:>5}{p.months_adjusted:>5}'
                  f'{"" if same else "   <<<"}')

    rem_rows = run_node_remedies(core)
    rem_bad = []
    for r in rem_rows:
        w = effective_window(r["cutoff"], r["start"], r["end"], trials=r["trials"])
        want = remedies(w)
        if w.verdict != r["verdict"] or want != r["remedies"]:
            rem_bad.append((r, w.verdict, want))

    print()
    print(f"{len(rows)} 组数值组合  ·  月数不一致 {len(mismatches)}  ·  "
          f"t 最大偏差 {worst_t:.2e}（容差 {T_TOL:.0e}）")
    print(f"{len(rem_rows)} 组处方组合  ·  逐字不一致 {len(rem_bad)}")
    if rem_bad:
        print()
        print("处方文本已漂移：")
        for r, verdict, want in rem_bad:
            print(f'  cutoff={r["cutoff"]} {r["start"]}..{r["end"]} trials={r["trials"]}')
            if verdict != r["verdict"]:
                print(f'    verdict  PY {verdict}  vs  JS {r["verdict"]}')
            for a, b in zip(want + [""] * 9, r["remedies"] + [""] * 9):
                if a != b:
                    print(f"    PY: {a}")
                    print(f"    JS: {b}")
        return 1
    if mismatches:
        print()
        print("docs/index.html 与 src/effective_window.py 数值已漂移：")
        for r, p, dt in mismatches:
            print(f'  trials={r["n"]} n_eff={r["k"]} t_bar={r["tb"]}: '
                  f'JS {r["months"]} 个月 / t={r["t"]:.6f}  vs  '
                  f'PY {p.months_adjusted} 个月 / t={p.t_adjusted:.6f}  Δt={dt:.2e}')
        return 1
    print("两处实现一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
