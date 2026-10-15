"""Audit 007 (second venue): Binance Futures copy-trading lead portfolios, rescored.

Usage:
    python tools/audit_binance_copy.py --cache DIR [--top 100] [--range 90D] [--out FILE]

Binance's copy-trading web pages read these public endpoints (no login, no key):
  POST /bapi/futures/v1/friendly/future/copy-trade/home-page/query-list        the public lead portfolios
  GET  /bapi/futures/v1/public/future/copy-trade/lead-portfolio/chart-data?dataType=ROI&portfolioId=X&timeRange=365D
They are not a documented API and may change. The ROI series is cumulative from the start of the
window, in percent, with zeros before the portfolio started; Binance does not document the base.
Weekly returns compound it: r = (1 + R_b/100) / (1 + R_a/100) - 1, anchored at the last day, from
the first non-zero day. Scoring is hl_wallet.score; the bar is best-of-N over the public portfolios.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import hl_wallet as H  # noqa: E402

BASE = "https://www.binance.com/bapi/futures/v1/"
DAY = 86400000


def curl(args):
    out = subprocess.run(["curl", "-s", "-m", "30", "--fail"] + args, capture_output=True)
    if out.returncode != 0:
        raise RuntimeError(f"curl {out.returncode}: {args[-1]}")
    return json.loads(out.stdout)


def cached(cache, name, fn):
    p = os.path.join(cache, name + ".json")
    if not os.path.exists(p):
        d = fn()
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f)
        time.sleep(0.6)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def page(cache, rng, n, size=18):
    body = json.dumps({"pageNumber": n, "pageSize": size, "timeRange": rng, "dataType": "PNL", "favoriteOnly": False,
                       "hideFull": False, "nickname": "", "order": "DESC", "userAsset": 0, "portfolioType": "PUBLIC"})
    return cached(cache, f"list_{rng}_{n}", lambda: curl(["-X", "POST", BASE + "friendly/future/copy-trade/home-page/query-list",
                                                         "-H", "Content-Type: application/json", "-d", body]))["data"]


def weekly(series):
    pts = sorted((int(x["dateTime"]), float(x["value"])) for x in series if x.get("value") is not None)
    first = next((i for i, (_, v) in enumerate(pts) if v != 0), None)
    if first is None:
        return []
    pts = pts[max(first - 1, 0):]  # keep the last zero: the start of the record
    # the last point is often intraday (not on the daily grid): each weekly node takes the last
    # sample at or before it, as the wallet check does
    nodes, i = [], 0
    for g in range(pts[0][0] + ((pts[-1][0] - pts[0][0]) % (7 * DAY)), pts[-1][0] + 1, 7 * DAY):
        while i + 1 < len(pts) and pts[i + 1][0] <= g:
            i += 1
        if pts[i][0] <= g and (not nodes or nodes[-1] != i):
            nodes.append(i)
    return [((1 + pts[b][1] / 100) / (1 + pts[a][1] / 100) - 1, (pts[b][0] - pts[a][0]) / (7 * DAY))
            for a, b in zip(nodes, nodes[1:]) if 1 + pts[a][1] / 100 > 0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--range", default="90D", help="window the list is ranked by (PnL)")
    ap.add_argument("--out")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    first = page(a.cache, a.range, 1)
    n_total = int(first["total"])
    rows, k = list(first["list"]), 2
    while len(rows) < a.top:
        rows += page(a.cache, a.range, k)["list"]
        k += 1
    rows = rows[: a.top]
    bar = H.bar(n_total)
    out = []
    for rank, r in enumerate(rows, 1):
        pid = r["leadPortfolioId"]
        try:
            ch = cached(a.cache, f"roi365_{pid}", lambda: curl([BASE + f"public/future/copy-trade/lead-portfolio/chart-data?dataType=ROI&portfolioId={pid}&timeRange=365D"]))["data"] or []
        except Exception as ex:
            print("skip", pid, ex, file=sys.stderr)
            continue
        sc = H.score(weekly(ch))
        out.append({"rank": rank, "portfolioId": pid, "pnl_window": r.get("pnl"), "roi_window_pct": r.get("roi"),
                    "aum": r.get("aum"), "copiers": r.get("currentCopyCount"), "listed_sharpe": r.get("sharpRatio"),
                    "t": sc["t"], "sharpe_weekly": sc["sharpe"], "weeks": sc["weeks"]})
    sc = [x for x in out if x["t"] is not None]
    summary = {"source": BASE, "ranked_by": f"PnL, {a.range}", "listed": n_total, "bar_best_of_n": round(bar, 2),
               "shown": len(out), "scored": len(sc), "t_ge_2": sum(x["t"] >= 2 for x in sc),
               "t_ge_bar": sum(x["t"] >= bar for x in sc), "t_le_minus2": sum(x["t"] <= -2 for x in sc),
               "too_short": len(out) - len(sc), "rows": out}
    s = json.dumps(summary, indent=1, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
