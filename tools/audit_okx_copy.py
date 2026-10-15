"""Audit 007: OKX copy-trading lead traders, rescored.

Usage:
    python tools/audit_okx_copy.py --cache DIR [--top 100] [--out FILE]

Uses OKX's documented public API (no key):
  GET /api/v5/copytrading/public-lead-traders?instType=SWAP&sortType=pnl&page=N   the listed lead traders
  GET /api/v5/copytrading/public-pnl?instType=SWAP&uniqueCode=X&lastDays=4        daily cumulative PnL ratio, 365 days
  GET /api/v5/copytrading/public-weekly-pnl?instType=SWAP&uniqueCode=X            weekly PnL ratio, last 12 weeks

OKX does not document the base of pnlRatio. The primary series treats the daily value as a
cumulative return over the 365-day window and compounds it into weekly returns, anchored at the
last day: r = (1 + R_end) / (1 + R_start) - 1. The weekly endpoint is scored separately as a
check; the two disagree in some weeks (reported in the output), so a verdict counts only where
the conclusion does not depend on which series is used.
Scoring is hl_wallet.score (the wallet check's estimator); the bar is best-of-N over the
number of lead traders OKX lists.
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import hl_wallet as H  # noqa: E402

API = "https://www.okx.com/api/v5/copytrading/"
DAY = 86400000


def get(cache, name, path):
    p = os.path.join(cache, name + ".json")
    if not os.path.exists(p):
        out = subprocess.run(["curl", "-s", "-m", "30", "--fail", API + path], capture_output=True)
        if out.returncode != 0:
            raise RuntimeError(f"curl {out.returncode}: {path}")
        d = json.loads(out.stdout)
        if d.get("code") != "0":
            raise RuntimeError(f"okx {d.get('code')} {d.get('msg')}: {path}")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f)
        time.sleep(0.35)
    with open(p, encoding="utf-8") as f:
        return json.load(f)["data"]


def listed(cache):
    first = get(cache, "list_1", "public-lead-traders?instType=SWAP&sortType=pnl&page=1")[0]
    rows = list(first["ranks"])
    for page in range(2, int(first["totalPage"]) + 1):
        rows += get(cache, f"list_{page}", f"public-lead-traders?instType=SWAP&sortType=pnl&page={page}")[0]["ranks"]
    return rows, first["dataVer"]


def weekly_from_daily(daily):
    """Weekly compounded returns from the cumulative daily ratio, anchored at the last day."""
    pts = sorted((int(x["beginTs"]), float(x["pnlRatio"])) for x in daily)
    by_ts = dict(pts)
    end = pts[-1][0]
    nodes = [t for t in range(end, pts[0][0] - 1, -7 * DAY) if t in by_ts][::-1]
    return [((1 + by_ts[b]) / (1 + by_ts[a]) - 1, 1.0) for a, b in zip(nodes, nodes[1:]) if 1 + by_ts[a] > 0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--out")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    rows, ver = listed(a.cache)
    n = len(rows)
    bar = H.bar(n)
    out = []
    for rank, r in enumerate(rows[: a.top], 1):
        u = r["uniqueCode"]
        try:
            daily = get(a.cache, f"d_{u}", f"public-pnl?instType=SWAP&uniqueCode={u}&lastDays=4")
            weekly = get(a.cache, f"w_{u}", f"public-weekly-pnl?instType=SWAP&uniqueCode={u}")
        except Exception as ex:
            print("skip", u, ex, file=sys.stderr)
            continue
        sd = H.score(weekly_from_daily(daily)) if len(daily) > 14 else {"t": None, "sharpe": None, "weeks": 0}
        sw = H.score([(float(x["pnlRatio"]), 1.0) for x in weekly])
        out.append({"rank": rank, "uniqueCode": u, "lead_days": int(r["leadDays"]), "pnl": round(float(r["pnl"]), 2),
                    "aum": round(float(r["aum"]), 2), "copiers": int(r["copyTraderNum"]), "copiers_ever": int(r["accCopyTraderNum"]),
                    "win_ratio": float(r["winRatio"]),
                    "t_daily365": sd["t"], "sharpe_daily365": sd["sharpe"], "weeks_daily365": sd["weeks"],
                    "t_weekly12": sw["t"], "weeks_weekly12": sw["weeks"]})
    sc = [x for x in out if x["t_daily365"] is not None]
    both = [x for x in sc if x["t_weekly12"] is not None]
    agree = sum((x["t_daily365"] >= 2) == (x["t_weekly12"] >= 2) for x in both)
    summary = {
        "source": API, "data_ver": ver, "listed": n, "bar_best_of_n": round(bar, 2), "shown": len(out), "scored": len(sc),
        "daily365_t_ge_2": sum(x["t_daily365"] >= 2 for x in sc), "daily365_t_ge_bar": sum(x["t_daily365"] >= bar for x in sc),
        "daily365_t_le_minus2": sum(x["t_daily365"] <= -2 for x in sc),
        "weekly12_t_ge_2": sum(x["t_weekly12"] >= 2 for x in both), "weekly12_t_ge_bar": sum(x["t_weekly12"] >= bar for x in both),
        "series_agree_on_t_ge_2": f"{agree}/{len(both)}",
        "rows": out,
    }
    s = json.dumps(summary, indent=1, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
