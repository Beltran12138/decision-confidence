"""Properties any correct wallet estimator must have, whatever the true return distribution.

tools/check_hl_parity.py compares the Python and browser estimators with each other, so an error
they share passes it. These tests check both against properties that follow from the definitions:
t is built from weekly returns (PnL change / account value), so it cannot depend on account size,
on the order of the weeks, on when the record happened, or on deposits that earn nothing.
"""
import json
import math
import os
import random
import shutil
import statistics
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import hl_wallet as hw  # noqa: E402

W = hw.WEEK_MS
T0 = 1_700_000_000_000  # an arbitrary start, in ms


def portfolio(points):
    """points: [(t_ms, account_value, cumulative_pnl)] -> the shape the info API returns, as a dict."""
    return {"allTime": {"accountValueHistory": [[t, str(v)] for t, v, _ in points],
                        "pnlHistory": [[t, str(p)] for t, _, p in points]}}


def from_returns(rets, av=50_000.0, start=T0):
    """Constant account value (gains withdrawn, losses topped up): weekly return r adds r * av to PnL."""
    pts, pnl = [], 0.0
    for i, r in enumerate(rets):
        pts.append((start + i * W, av, pnl))
        pnl += r * av
    pts.append((start + len(rets) * W, av, pnl))
    return pts


def scored(points):
    rets, _, _, _ = hw.weekly_returns(portfolio(points))
    return hw.score(rets)


def sample(seed, n=40, mu=0.006, sd=0.02):
    rng = random.Random(seed)
    return [rng.gauss(mu, sd) for _ in range(n)]


SEEDS = range(12)


def close(a, b, rel=1e-9):
    return a is not None and b is not None and math.isclose(a, b, rel_tol=rel, abs_tol=1e-12)


@pytest.mark.parametrize("seed", SEEDS)
def test_account_size_does_not_matter(seed):
    base = from_returns(sample(seed))
    big = [(t, v * 7.3, p * 7.3) for t, v, p in base]
    a, b = scored(base), scored(big)
    assert close(a["t"], b["t"]) and close(a["sharpe"], b["sharpe"])


@pytest.mark.parametrize("seed", SEEDS)
def test_mirror_record_mirrors_t(seed):
    rets = sample(seed)
    a, b = scored(from_returns(rets)), scored(from_returns([-r for r in rets]))
    assert close(a["t"], -b["t"]) and close(a["sharpe"], -b["sharpe"])
    va, vb = hw.verdict(a, picked_from=47_000)["key"], hw.verdict(b, picked_from=47_000)["key"]
    mirror = {"clears_board": "loses", "clears_single": "loses", "loses": "clears_single", "luck": "luck"}
    if abs(a["t"]) >= 2 and a["t"] < hw.bar(47_000):
        assert vb == mirror[va]


@pytest.mark.parametrize("seed", SEEDS)
def test_order_of_weeks_does_not_matter(seed):
    rets = sample(seed)
    shuffled = rets[:]
    random.Random(seed + 1000).shuffle(shuffled)
    a, b = scored(from_returns(rets)), scored(from_returns(shuffled))
    assert close(a["t"], b["t"]) and close(a["sharpe"], b["sharpe"])


@pytest.mark.parametrize("seed", SEEDS)
def test_when_it_happened_does_not_matter(seed):
    base = from_returns(sample(seed))
    later = [(t + 137 * W + 3_600_000, v, p) for t, v, p in base]
    a, b = scored(base), scored(later)
    assert close(a["t"], b["t"]) and close(a["sharpe"], b["sharpe"])


def test_deposits_that_earn_nothing_score_nothing():
    rng = random.Random(7)
    pts, av = [], 20_000.0
    for i in range(30):
        pts.append((T0 + i * W, av, 0.0))
        av = max(2_000.0, av + rng.choice([-1, 1]) * rng.uniform(0, 15_000))  # deposits and withdrawals only
    sc = scored(pts)
    assert sc["t"] is None or sc["t"] == 0
    assert hw.verdict(sc, picked_from=47_000)["key"] in ("too_short", "luck")


@pytest.mark.parametrize("seed", SEEDS)
def test_more_of_the_same_record_raises_t(seed):
    rets = sample(seed, mu=0.01)
    a, b = scored(from_returns(rets)), scored(from_returns(rets + rets))
    if a["t"] > 0:
        assert b["t"] > a["t"]
    assert abs(a["sharpe"] - b["sharpe"]) < 0.05 * abs(a["sharpe"]) + 0.05


@pytest.mark.parametrize("seed", SEEDS)
def test_returns_not_dollars(seed):
    # The same weekly returns on an account that grows and shrinks: dollar PnL differs week to week,
    # returns do not, so t must not change. (With a constant account value, dividing by the wrong
    # amount only rescales every return and t cannot notice; this case can.)
    rets, rng = sample(seed), random.Random(seed + 2000)
    pts, pnl = [], 0.0
    for i, r in enumerate(rets):
        av = rng.uniform(5_000, 500_000)
        pts.append((T0 + i * W, av, pnl))
        pnl += r * av
    pts.append((T0 + len(rets) * W, 50_000.0, pnl))
    a, b = scored(from_returns(rets)), scored(pts)
    assert close(a["t"], b["t"]) and close(a["sharpe"], b["sharpe"])


def test_sharpe_against_a_direct_computation():
    # Properties cannot see a wrong constant (t ignores annualisation; Sharpe does not).
    # Anchor Sharpe to mean / sd * sqrt(52) computed here, outside the module.
    import statistics
    for seed in SEEDS:
        rets = sample(seed)
        expect = statistics.mean(rets) / statistics.stdev(rets) * math.sqrt(52)
        assert abs(scored(from_returns(rets))["sharpe"] - expect) < 1e-3


def test_bar_starts_at_two_and_rises_with_the_board():
    assert math.isclose(hw.bar(1), 2.0, abs_tol=1e-9)
    ns = [1, 2, 5, 10, 100, 1_000, 10_000, 47_000, 450_853, 10**6]
    bars = [hw.bar(n) for n in ns]
    assert all(x < y for x, y in zip(bars, bars[1:]))


# The browser and Worker run docs/assets/hl.js. Run the same properties on it through node.

JS = r"""
const HL = require(process.argv[2]);
const cases = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = cases.map(pts => {
  const pf = [['allTime', {accountValueHistory: pts.map(([t, v]) => [t, String(v)]),
                           pnlHistory: pts.map(([t, , p]) => [t, String(p)])}]];
  const s = HL.score(HL.weeklyReturns(pf).rets);
  return [s.t, s.sharpe];
});
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_estimator_has_the_same_properties(tmp_path):
    script = tmp_path / "run.js"
    script.write_text(JS)
    cases, checks = [], []
    for seed in SEEDS:
        rets = sample(seed)
        base = from_returns(rets)
        shuffled = rets[:]
        random.Random(seed + 1000).shuffle(shuffled)
        i = len(cases)
        rng, varied, pnl = random.Random(seed + 2000), [], 0.0
        for k, r in enumerate(rets):
            av = rng.uniform(5_000, 500_000)
            varied.append((T0 + k * W, av, pnl))
            pnl += r * av
        varied.append((T0 + len(rets) * W, 50_000.0, pnl))
        cases += [base, [(t, v * 7.3, p * 7.3) for t, v, p in base], from_returns([-r for r in rets]),
                  from_returns(shuffled), [(t + 137 * W + 3_600_000, v, p) for t, v, p in base], varied]
        checks.append((i, statistics.mean(rets) / statistics.stdev(rets) * math.sqrt(52)))
    res = subprocess.run(["node", str(script), os.path.abspath(os.path.join(ROOT, "docs", "assets", "hl.js"))],
                         input=json.dumps(cases), capture_output=True, text=True, check=True)
    out = json.loads(res.stdout)
    for i, expect_sharpe in checks:
        t, sharpe = out[i]
        # hl.js rounds to 3 decimals, so compare at that precision
        for j in (1, 3, 4, 5):  # size, order, timing, account path
            assert abs(out[i + j][0] - t) <= 1e-3
        assert abs(out[i + 2][0] + t) <= 1e-3 and abs(out[i + 2][1] + sharpe) <= 1e-3
        assert abs(sharpe - expect_sharpe) <= 2e-3
