"""Build the evidence-adjusted leaderboard data file from raw board responses.

Usage:
  python tools/build_leaderboard.py --la DIR --aitrader FILE --out docs/leaderboard/2026-10.json

--la        directory holding p1.json, p2.json, p3.json from the Liquidity Arena
            official ranking endpoint (client-web-api/official/tracka/ranking/list?phase=PHASE_I)
--aitrader  ai4trade.ai /api/profit/history?days=365&limit=50&include_history=true response
"""
import argparse, json, math, os, statistics as st, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from effective_window import selection_penalty  # noqa: E402


def months_to_bar(t_bar, sharpe):
    """Months of clean history for a true annualised Sharpe to reach t_bar (t = SR * sqrt(years))."""
    return round((t_bar / sharpe) ** 2 * 12, 1)


def liquidity_arena(la_dir):
    rows = []
    for i in (1, 2, 3):
        with open(os.path.join(la_dir, f"p{i}.json"), encoding="utf-8") as f:
            rows += json.load(f)["data"]["list"]
    pen = selection_penalty(len(rows))
    out = []
    for r in rows:
        by = {}
        for p in r["equityCurve"]:  # hourly points; keep the last of each UTC day
            by[p["dt"] // 86400000] = float(p["equity"])
        eq = [by[d] for d in sorted(by)]
        rets = [eq[k] / eq[k - 1] - 1 for k in range(1, len(eq)) if eq[k - 1] > 0]
        e = {"rank": r["rankNo"], "name": r["teamName"], "return_pct": round(float(r["roi"]) * 100, 2),
             "days": len(rets), "sharpe": None, "t": None}
        if len(rets) >= 5 and st.pstdev(rets) > 0:
            sr = st.mean(rets) / st.stdev(rets) * math.sqrt(365)
            e["sharpe"] = round(sr, 2)
            e["t"] = round(sr * math.sqrt(len(rets) / 365), 3)
        out.append(e)
    out.sort(key=lambda e: e["rank"])
    ts = [e for e in out if e["t"] is not None]
    best = max(ts, key=lambda e: e["t"])
    return {
        "id": "liquidity-arena-2026-phase-1",
        "board": "Liquidity Arena 2026 Track A, Phase I",
        "source": "arena.liquiditytech.com/client-web-api/official/tracka/ranking/list?phase=PHASE_I",
        "ranked_by": "composite score",
        "entries": len(out),
        "window": "about 30 trading days per team (2026-07-20 to 2026-08-21)",
        "annualisation_days": 365,
        "t_bar_single": 2.0,
        "t_bar_best_of_n": round(pen.t_adjusted, 2),
        "reaching_t2": sum(e["t"] >= 2 for e in ts),
        "reaching_bar": sum(e["t"] >= pen.t_adjusted for e in ts),
        "max_t": best["t"], "max_t_name": best["name"], "max_t_rank": best["rank"],
        "months_to_winner": {"sharpe_5": months_to_bar(pen.t_adjusted, 5),
                             "sharpe_2": months_to_bar(pen.t_adjusted, 2),
                             "closest_at_observed_sharpe": months_to_bar(pen.t_adjusted, best["sharpe"])},
        "rows": out,
    }


def ai_trader(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    A, N = d["top_agents"], d["total"]
    pen = selection_penalty(N)
    INIT = 100000.0
    out, frozen_n, frozen_moved, frozen_early = [], 0, 0, 0
    for rk, a in enumerate(A, 1):
        h = a["history"]
        e = {"rank": rk, "name": a["name"], "return_pct": round(a["total_profit_percent"], 2),
             "trades": a["trade_count"], "history_points": len(h), "days": None, "sharpe": None, "t": None,
             "share_of_return_at_first_record": None, "move_since_jul24_pp": None}
        if len(h) >= 2:
            frozen_n += 1
            cur = a["total_profit_percent"]
            first = h[0]["profit_percent"]
            jul = [p for p in h if p["recorded_at"][:10] <= "2026-07-24"]
            if cur:
                e["share_of_return_at_first_record"] = round(first / cur, 3)
                frozen_early += first / cur >= 0.9
            if jul:
                e["move_since_jul24_pp"] = round(cur - jul[-1]["profit_percent"], 2)
                frozen_moved += abs(cur - jul[-1]["profit_percent"]) < 1
        if len(h) >= 20:
            by = {}
            for p in h:
                if p["recorded_at"][:10] < "2026-08-01":  # July history only; the rest is one live snapshot
                    by[p["recorded_at"][:10]] = INIT + (a["deposited"] or 0) + p["profit"]
            eq = [by[x] for x in sorted(by)]
            r = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq)) if eq[i - 1] > 0]
            e["days"] = len(r)
            if len(r) >= 10 and st.stdev(r) > 0:
                sr = st.mean(r) / st.stdev(r) * math.sqrt(252)
                e["sharpe"] = round(sr, 2)
                e["t"] = round(sr * math.sqrt(len(r) / 252), 3)
        out.append(e)
    ts = [e for e in out if e["t"] is not None]
    best = max(ts, key=lambda e: e["t"])
    return {
        "id": "hkuds-ai-trader",
        "board": "HKUDS AI-Trader (ai4trade.ai), top 50 by return",
        "source": "ai4trade.ai/api/profit/history?days=365&limit=50&include_history=true",
        "ranked_by": "cumulative return",
        "entries": N,
        "entries_scored": len(out),
        "with_series": len(ts),
        "window": "16 return days (2026-07-08 to 2026-07-24) for agents with history",
        "annualisation_days": 252,
        "t_bar_single": 2.0,
        "t_bar_best_of_n": round(pen.t_adjusted, 2),
        "reaching_t2": sum(e["t"] >= 2 for e in ts),
        "reaching_bar": sum(e["t"] >= pen.t_adjusted for e in ts),
        "max_t": best["t"], "max_t_name": best["name"], "max_t_rank": best["rank"],
        "months_to_winner": {"sharpe_5": months_to_bar(pen.t_adjusted, 5),
                             "sharpe_2": months_to_bar(pen.t_adjusted, 2)},
        "frozen": {"with_any_history": frozen_n, "moved_under_1pp_since_jul24": frozen_moved,
                   "had_90pct_of_return_at_first_record": frozen_early},
        "rows": out,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--la", required=True)
    ap.add_argument("--aitrader", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fetched", default="2026-10-12")
    a = ap.parse_args()
    data = {
        "edition": "2026-10", "fetched": a.fetched,
        "method": "daily returns -> annualised Sharpe -> t = Sharpe * sqrt(years); "
                  "best-of-N bar = one-sided Bonferroni on N entries",
        "license": "CC BY 4.0; cite as Evidence Deflator leaderboard, 2026-10",
        "boards": [liquidity_arena(a.la), ai_trader(a.aitrader)],
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    for b in data["boards"]:
        print(b["id"], "N", b["entries"], "bar", b["t_bar_best_of_n"], "t>=2", b["reaching_t2"],
              "max", b["max_t"], b["max_t_name"], b["months_to_winner"], b.get("frozen", ""))


if __name__ == "__main__":
    main()
