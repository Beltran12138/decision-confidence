"""Diff docs/assets/hl.js against tools/build_hl_board.py on cached portfolios.

    python tools/check_hl_parity.py --cache DIR

DIR is the --cache directory of build_hl_board.py (portfolio/*.json). Needs node.
Exits 1 on any mismatch in weeks, Sharpe, t, flags or the best-of-N bar.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_hl_board as py  # noqa: E402

JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "assets", "hl.js")
NODE = r"""
const HL = require(process.argv[1]);
const files = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const f of files) {
  const pf = JSON.parse(require('fs').readFileSync(f, 'utf8'));
  const w = HL.weeklyReturns(pf);
  out[f] = Object.assign(HL.score(w.rets), {flags: HL.flags(pf, w.rets, w.counted)});
}
out.__bars = [1, 41, 47254, 23376].map(n => Math.round(HL.bar(n) * 100) / 100);
console.log(JSON.stringify(out));
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.cache, "portfolio", "*.json")))
    if not files:
        sys.exit("no cached portfolios")
    res = subprocess.run(["node", "-e", NODE, os.path.abspath(JS)], input=json.dumps(files),
                         capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    bad = 0
    for f in files:
        with open(f, encoding="utf-8") as fh:
            pf = dict(json.load(fh))
        rets, _, _, counted = py.weekly_returns(pf)
        p, j = dict(py.score(rets), flags=py.flags(pf, rets, counted)), js[f]
        for k in ("weeks", "sharpe", "t_student", "dof", "t", "flags"):
            if p.get(k) != j.get(k):
                bad += 1
                print("MISMATCH", os.path.basename(f), k, p.get(k), j.get(k))
                break
    pb = [round(py.bar(n), 2) for n in (1, 41, 47254, 23376)]
    if pb != js["__bars"]:
        bad += 1
        print("MISMATCH bars", pb, js["__bars"])
    print(f"{len(files)} portfolios, bars {pb}: {'OK' if not bad else str(bad) + ' mismatches'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
