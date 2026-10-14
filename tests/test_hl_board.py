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
    random.seed(7)
    rs = [random.gauss(0.01, 0.04) for _ in range(40)]
    rets = [(r, 1.0) for r in rs]
    t = hb.score(rets)["t"]
    assert abs(t - statistics.mean(rs) / statistics.pstdev(rs) * math.sqrt(len(rs))) < 1e-3


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
