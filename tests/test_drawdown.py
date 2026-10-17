"""The drawdown reading on the wallet page: where a record stands against its own peak, and the share
of time a record with its measured edge spends at least that far down.

The share comes from a formula (reflected Brownian motion with Siegmund's correction for weekly
sampling), so it is checked against a simulation that does not use it, as well as against a hand-built
record and the browser copy in docs/assets/hl.js.
"""
import json
import math
import os
import random
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import hl_wallet as hw  # noqa: E402


def share_formula(m, s, d):
    return math.exp(-2 * m * (d + hw.SIEGMUND * s) / s ** 2)


@pytest.mark.parametrize("sharpe", [0.7, 1.5, 3.0])
def test_share_matches_a_simulated_walk(sharpe):
    # Independent baseline: walk log wealth week by week and count the weeks spent at least d below the peak.
    rng, s = random.Random(int(sharpe * 10)), 0.02
    m = sharpe / math.sqrt(52) * s
    x = peak = 0.0
    depths = (1 * s, 3 * s, 6 * s)
    hits, n = [0] * len(depths), 400_000
    for _ in range(n):
        x += rng.gauss(m, s)
        peak = max(peak, x)
        for i, d in enumerate(depths):
            hits[i] += peak - x >= d
    for d, h in zip(depths, hits):
        emp = h / n
        if emp > 0.01:
            assert abs(share_formula(m, s, d) / emp - 1) < 0.08, (sharpe, d, emp)
        # the uncorrected formula is too high by a margin that grows with the Sharpe
        assert math.exp(-2 * m * d / s ** 2) > emp


def test_hand_built_record():
    # +10%, +10%, then -20% and -5%: peak after week 2, then 25 points of returns below it,
    # and the last four weeks (+1 -1 +1 -1) leave it there.
    rets = [(0.1, 1.0), (0.1, 1.0), (-0.2, 1.0), (-0.05, 1.0)] + [(0.01, 1.0), (-0.01, 1.0)] * 2
    dd = hw.drawdown(rets)
    assert math.isclose(dd["now"], 0.25, abs_tol=1e-4)
    assert dd["deepest"] == dd["now"]
    assert dd["weeks_below"] == 6.0


def test_share_uses_the_records_own_edge():
    rng = random.Random(7)
    rets = [(rng.gauss(0.01, 0.03), 1.0) for _ in range(60)] + [(-0.04, 1.0)] * 3
    dd = hw.drawdown(rets)
    r = [x for x, _ in rets]
    mu = sum(r) / len(r)
    v = sum((x - mu) ** 2 for x in r) / (len(r) - 1)
    path = [0.0]
    for x in r:
        path.append(path[-1] + x)
    d = max(path) - path[-1]
    assert math.isclose(dd["share_if_real"], round(share_formula(mu, math.sqrt(v), d), 4), abs_tol=1e-4)


def test_a_volatile_account_with_a_positive_mean_still_gets_a_reading():
    # Compounded, +60% / -45% weeks shrink wealth; added up, the record gains 7.5 points a fortnight.
    rets = [(0.6, 1.0), (-0.45, 1.0)] * 10 + [(-0.45, 1.0)]
    dd = hw.drawdown(rets)
    assert dd["share_if_real"] is not None and 0 < dd["share_if_real"] < 1
    assert math.isclose(dd["now"], 0.9, abs_tol=1e-4)  # the last +60% is followed by two -45% weeks


def test_edges_of_the_reading():
    up = [(0.01 + 0.001 * (i % 3), 1.0) for i in range(20)]
    assert hw.drawdown(up)["share_if_real"] == 1.0 and hw.drawdown(up)["now"] == 0.0
    assert hw.drawdown(up[:hw.MIN_WEEKS - 1]) is None
    down = [(-0.01 - 0.001 * (i % 3), 1.0) for i in range(20)]
    assert hw.drawdown(down)["share_if_real"] is None  # no positive edge to judge the drawdown against
    # deeper now -> rarer, for the same edge
    base = [(0.02 * (1 if i % 2 else -0.5), 1.0) for i in range(40)]
    a = hw.drawdown(base + [(-0.03, 1.0)])["share_if_real"]
    b = hw.drawdown(base + [(-0.03, 1.0), (-0.03, 1.0)])["share_if_real"]
    assert b < a < 1
    # a week that loses everything is one point of return below the peak, not an error
    assert math.isclose(hw.drawdown(base + [(-1.0, 1.0)])["now"] - hw.drawdown(base)["now"], 1.0, abs_tol=1e-3)


JS = r"""
const HL = require(process.argv[2]);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(cases.map(c => HL.drawdown(c))));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_copy_agrees(tmp_path):
    script = tmp_path / "run.js"
    script.write_text(JS)
    cases = []
    for seed in range(20):
        rng = random.Random(seed)
        n = rng.randint(5, 120)
        cases.append([[rng.gauss(rng.uniform(-0.01, 0.02), rng.uniform(0.005, 0.08)), rng.choice([1.0, 1.0, 2.0, 3.5])]
                      for _ in range(n)])
    res = subprocess.run(["node", str(script), os.path.abspath(os.path.join(ROOT, "docs", "assets", "hl.js"))],
                         input=json.dumps(cases), capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    for c, j in zip(cases, js):
        p = hw.drawdown([tuple(x) for x in c])
        assert (p is None) == (j is None)
        if p:
            for k in p:
                assert (p[k] is None) == (j[k] is None), k
                if p[k] is not None:
                    assert abs(p[k] - j[k]) <= 1e-4, (k, p[k], j[k])
