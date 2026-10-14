"""tools/build_hl_board.py: weekly grid, merging, forward window, estimator, flags."""
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import build_hl_board as hb  # noqa: E402

W = hb.WEEK_MS


def portfolio(points):
    """points: list of (t_ms, account_value, cumulative_pnl)."""
    return {"allTime": {"accountValueHistory": [[t, str(v)] for t, v, _ in points],
                        "pnlHistory": [[t, str(p)] for t, _, p in points]}}


def weekly(n, r=0.01, av=10_000.0, t0=0):
    pts, pnl = [], 0.0
    for i in range(n + 1):
        pts.append((t0 + i * W, av, pnl))
        pnl += av * r
    return pts


def test_returns_use_pnl_not_account_value():
    # account value doubles from a deposit in week 3; PnL is flat, so returns are zero
    pts = [(i * W, 10_000.0 if i < 3 else 20_000.0, 0.0) for i in range(10)]
    rets, _, _, counted = hb.weekly_returns(portfolio(pts))
    assert all(r == 0 for r, _ in rets) and counted == 0


def test_week_without_new_sample_is_merged_not_zeroed():
    # samples every two weeks: five intervals of two weeks, not ten with five zeros
    pts = [(i * 2 * W, 10_000.0, i * 100.0) for i in range(6)]
    rets, _, _, _ = hb.weekly_returns(portfolio(pts))
    assert len(rets) == 5 and all(abs(w - 2) < 1e-9 for _, w in rets)
    assert all(r > 0 for r, _ in rets)


def test_small_starting_balance_is_skipped():
    pts = [(0, 0.0, 0.0), (W, 500.0, 1_000_000.0)] + [(i * W, 10_000.0, 1_000_000.0 + i) for i in range(2, 12)]
    rets, _, _, counted = hb.weekly_returns(portfolio(pts))
    assert counted < 100  # the million booked on a $0 start is not a return
    assert "pnl_outside_record" in hb.flags(portfolio(pts), rets, counted)


def test_equal_intervals_match_textbook_t():
    # textbook one-sample t uses the sample sd (n - 1), not the population sd
    random.seed(7)
    rs = [random.gauss(0.01, 0.04) for _ in range(40)]
    sc = hb.score([(r, 1.0) for r in rs])
    assert abs(sc["t_student"] - statistics.mean(rs) / statistics.stdev(rs) * math.sqrt(len(rs))) < 1e-3
    assert sc["dof"] == 39


def test_t_to_z_matches_printed_t_tables():
    # 97.5% quantiles of Student's t (any printed table) map to the normal 1.959964
    for t, dof in ((12.706205, 1), (2.364624, 7), (2.228139, 10), (2.042272, 30)):
        assert abs(hb.t_to_z(t, dof) - 1.959964) < 1e-4
    assert abs(hb.t_to_z(-2.364624, 7) + 1.959964) < 1e-4


def test_too_short_has_no_t():
    rets, _, _, _ = hb.weekly_returns(portfolio(weekly(5)))
    assert hb.score(rets)["t"] is None


def test_forward_window_ignores_record_before_freeze():
    # strong gains before the freeze, losses after: forward t must be negative
    before = [(i * W, 10_000.0, i * 500.0) for i in range(20)]
    after = [((20 + i) * W, 10_000.0, 19 * 500.0 - i * 50.0 + (i % 2) * 20) for i in range(1, 12)]
    pf = portfolio(before + after)
    full, _, _, _ = hb.weekly_returns(pf)
    fwd, _, _, _ = hb.weekly_returns(pf, since=19 * W)
    assert sum(r for r, _ in full) > 0
    assert len(fwd) == 11 and sum(r for r, _ in fwd) < 0


def test_bars_match_library_values():
    assert round(hb.bar(1), 2) == 2.0
    assert round(hb.bar(41), 2) == 3.26
    assert round(hb.bar(23_376), 2) == 4.76


# --- sampling invariance (property tests) -------------------------------------
# The same record, sampled more sparsely or cut on a different weekday, must not
# read as stronger evidence. Hyperliquid keeps old history about weekly and recent
# history minutes apart, so the score has to hold up to how the path was sampled.
# Each check is also run on the estimator it replaced, which must fail it.

D = W // 7


def old_t(rets):
    """The estimator before 2026-10-14: population variance, normal bar."""
    tot = sum(r for r, _ in rets)
    mu = tot / sum(w for _, w in rets)
    return tot / math.sqrt(sum((r - mu * w) ** 2 for r, w in rets))


def false_positive_rate(t_fn, intervals, seed, trials=4000):
    rng, hits = random.Random(seed), 0
    for _ in range(trials):
        dts = intervals(rng)
        hits += t_fn([(rng.gauss(0, 0.02 * math.sqrt(w)), w) for w in dts]) >= 2
    return hits / trials


NULL_CASES = {
    "8 equal weeks": lambda rng: [1] * 8,
    "12 irregular": lambda rng: [rng.choice([1, 1, 1, 2, 3, 6]) for _ in range(12)],
    "30 irregular": lambda rng: [rng.choice([1, 1, 1, 2, 3, 6]) for _ in range(30)],
}
NOMINAL, SE = hb.ALPHA, math.sqrt(hb.ALPHA * (1 - hb.ALPHA) / 4000)


def test_no_skill_passes_t2_at_the_nominal_rate_whatever_the_sampling():
    for k, (name, iv) in enumerate(NULL_CASES.items()):
        rate = false_positive_rate(lambda rets: hb.score(rets)["t"], iv, seed=k)
        assert abs(rate - NOMINAL) < 3 * SE, (name, rate)


def test_false_positive_check_catches_the_old_estimator():
    rate = false_positive_rate(old_t, NULL_CASES["8 equal weeks"], seed=0)
    assert rate > NOMINAL + 3 * SE, rate  # about 5%, not 2.3%


def daily_path(rng, weeks=104, mu=0.004, sd=0.02, av=100_000.0):
    pts, pnl = [], 0.0
    for d in range(weeks * 7 + 1):
        pts.append((d * D, av, pnl))
        pnl += av * rng.gauss(mu / 7, sd / math.sqrt(7))
    return pts


def thinned(rng, pts, keep):
    return [pts[0]] + [p for p in pts[1:-1] if rng.random() < keep] + [pts[-1]]


def shift_z(deltas):
    """Mean shift in standard errors."""
    return statistics.mean(deltas) / (statistics.stdev(deltas) / math.sqrt(len(deltas)))


def thinning_shift(t_fn, seed, paths=80, keep=0.05):
    # keep ~1 daily sample in 20, so most weeks have no new sample
    rng, out = random.Random(seed), []
    for _ in range(paths):
        pts = daily_path(rng)
        full = t_fn(hb.weekly_returns(portfolio(pts))[0])
        out.append(t_fn(hb.weekly_returns(portfolio(thinned(rng, pts, keep)))[0]) - full)
    return shift_z(out)


def test_thinning_never_makes_a_record_look_stronger():
    for seed in (1, 2, 3):
        assert thinning_shift(lambda rets: hb.score(rets)["t"], seed) < 3


def test_thinning_check_catches_the_old_estimator():
    assert thinning_shift(old_t, seed=1, paths=400) >= 3  # 5-7 standard errors across seeds


def test_t_does_not_drift_with_the_grid_anchor():
    # the grid is anchored on the last sample; ending the record 1-6 days earlier
    # changes which weekday the weeks are cut on, not the evidence
    rng, deltas = random.Random(11), []
    for _ in range(40):
        pts = daily_path(rng)
        full = hb.score(hb.weekly_returns(portfolio(pts))[0])["t"]
        for k in range(1, 7):
            deltas.append(hb.score(hb.weekly_returns(portfolio(pts[:-k]))[0])["t"] - full)
    assert abs(shift_z(deltas)) < 3
