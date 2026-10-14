"""src/hl_wallet.py: verdict keys and the offline check() path used by the MCP tool."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import hl_wallet as hw  # noqa: E402

W = hw.WEEK_MS


def portfolio(points):
    return {"allTime": {"accountValueHistory": [[t, str(v)] for t, v, _ in points],
                        "pnlHistory": [[t, str(p)] for t, _, p in points]}}


def test_verdict_keys_match_the_browser():
    assert hw.verdict({"t": None})["key"] == "too_short"
    assert hw.verdict({"t": 1.0})["key"] == "luck"
    assert hw.verdict({"t": -2.5})["key"] == "loses"
    assert hw.verdict({"t": 3.0})["key"] == "clears_single"
    assert hw.verdict({"t": 3.0}, picked_from=47_153)["key"] == "clears_single"
    assert hw.verdict({"t": 5.5}, picked_from=47_153) == {"key": "clears_board", "bar": 4.9}
    # without a board size there is no board bar to clear
    assert hw.verdict({"t": 5.5})["key"] == "clears_single"


def test_check_scores_a_given_portfolio_without_the_network():
    # weekly returns alternate +2.2% / -0.2%: mean 1%, sd 1.2%, 59 intervals, t about 6.4
    pts, pnl = [], 0.0
    for i in range(60):
        pts.append((i * W, 50_000.0, pnl))
        pnl += 50_000.0 * (0.022 if i % 2 == 0 else -0.002)
    r = hw.check("0x" + "0" * 40, picked_from=47_153, pf=portfolio(pts))
    assert r["intervals"] == 59 and r["dof"] == 58
    assert r["verdict"] == "clears_board" and r["bar"] == 4.9
    assert r["history_from"] == "1970-01-01" and r["flags"] == []
