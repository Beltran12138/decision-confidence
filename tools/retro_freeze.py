"""Retrospective freeze: does t, read at a past date, predict the record after that date?

Usage:
    python tools/retro_freeze.py --snapshots DIR --cache DIR [--out FILE]

Pre-registered in docs/data/hl/retro/PREREG.md before any of this was computed.

DIR holds archived copies of Hyperliquid's public leaderboard, named <wayback timestamp>.json
(web.archive.org/web/<ts>id_/https://stats-data.hyperliquid.xyz/Mainnet/leaderboard). For each
snapshot the cohort is picked with the same rule as the 2026-10-14 frozen cohort (all-time PnL
top 100 plus 30-day ROI top 100 among accounts >= $10k). Each wallet's portfolio is fetched today;
t_before scores the history up to the snapshot time, t_after the history after it
(weekly_returns(since=...)), both with the estimator behind the wallet check.
"""
import argparse
import glob
import json
import os
import random
import statistics
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from hl_wallet import MIN_WEEKS, fetch_portfolio as fetch_live, score, weekly_returns  # noqa: E402


def num_window(row, name, key):
    for k, v in row["windowPerformances"]:
        if k == name:
            try:
                return float(v.get(key, 0))
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def fetch_portfolio(cache, addr):
    """Today's portfolio for addr, cached (urllib, so it goes through the shell's proxy settings)."""
    p = os.path.join(cache, addr + ".json")
    if not os.path.exists(p):
        pf = fetch_live(addr)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(pf, f)
        time.sleep(0.2)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def pick(rows, top=100):
    by_pnl = sorted(rows, key=lambda r: -num_window(r, "allTime", "pnl"))[:top]
    by_roi = sorted((r for r in rows if float(r["accountValue"]) >= 10000),
                    key=lambda r: -num_window(r, "month", "roi"))[:top]
    seen, out = set(), []
    for board, picked in (("pnl", by_pnl), ("roi30", by_roi)):
        for rank, r in enumerate(picked, 1):
            if r["ethAddress"] not in seen:
                seen.add(r["ethAddress"])
                out.append({"address": r["ethAddress"], "board": board, "rank": rank,
                            "pnl_all_time": num_window(r, "allTime", "pnl")})
    return out


def truncate(pf, until_ms):
    """The portfolio as it stood at until_ms: history samples at or before it."""
    at = pf["allTime"]
    return {"allTime": {"accountValueHistory": [p for p in at["accountValueHistory"] if p[0] <= until_ms],
                        "pnlHistory": [p for p in at["pnlHistory"] if p[0] <= until_ms]}}


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(xs, ys):
    if len(xs) < 3:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.fmean(rx), statistics.fmean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else None


def boot_ci(pairs, reps=2000, seed=7):
    rnd = random.Random(seed)
    vals = []
    for _ in range(reps):
        s = [pairs[rnd.randrange(len(pairs))] for _ in pairs]
        v = spearman([a for a, _ in s], [b for _, b in s])
        if v is not None:
            vals.append(v)
    vals.sort()
    return round(vals[int(0.025 * len(vals))], 3), round(vals[int(0.975 * len(vals))], 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshots", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    results, pooled = [], []
    for path in sorted(glob.glob(os.path.join(a.snapshots, "*.json"))):
        ts = os.path.basename(path)[:14]
        freeze = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        freeze_ms = int(freeze.timestamp() * 1000)
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)["leaderboardRows"]
        cohort = pick(rows)
        scored = []
        for m in cohort:
            try:
                pf = fetch_portfolio(a.cache, m["address"])
            except Exception as ex:
                print("skip", m["address"], ex, file=sys.stderr)
                continue
            before = score(weekly_returns(truncate(pf, freeze_ms))[0])
            after = score(weekly_returns(pf, since=freeze_ms)[0])
            scored.append({**m, "t_before": before["t"], "t_after": after["t"], "weeks_after": after["weeks"]})
        both = [r for r in scored if r["t_before"] is not None and r["t_after"] is not None]
        rho_t = spearman([r["t_before"] for r in both], [r["t_after"] for r in both])
        rho_pnl = spearman([r["pnl_all_time"] for r in both], [r["t_after"] for r in both])
        hi = [r["t_after"] for r in both if r["t_before"] >= 2]
        lo = [r["t_after"] for r in both if r["t_before"] < 2]
        results.append({
            "snapshot": freeze.strftime("%Y-%m-%dT%H:%MZ"), "board_size": len(rows), "cohort": len(cohort),
            "fetched": len(scored), "scored_both": len(both),
            "rho_t": None if rho_t is None else round(rho_t, 3),
            "rho_pnl": None if rho_pnl is None else round(rho_pnl, 3),
            "t_before_ge_2": len(hi), "median_t_after_if_t_before_ge_2": round(statistics.median(hi), 3) if hi else None,
            "median_t_after_if_t_before_lt_2": round(statistics.median(lo), 3) if lo else None,
            "share_t_after_ge_2": round(sum(t >= 2 for t in (r["t_after"] for r in both)) / len(both), 3) if both else None,
            "rows": scored,
        })
        pooled += [(r["t_before"], r["t_after"]) for r in both]
    rho = spearman([p[0] for p in pooled], [p[1] for p in pooled])
    wins = sum(1 for r in results if r["rho_t"] is not None and r["rho_pnl"] is not None and r["rho_t"] > r["rho_pnl"])
    ci = boot_ci(pooled) if len(pooled) > 10 else None
    if rho is not None and rho <= 0 or wins < 2:
        verdict = "lose"
    elif ci and ci[0] > 0 and wins >= 2:
        verdict = "win"
    else:
        verdict = "uncertain"
    summary = {"prereg": "docs/data/hl/retro/PREREG.md", "min_weeks": MIN_WEEKS, "pooled_n": len(pooled),
               "pooled_rho_t": None if rho is None else round(rho, 3), "pooled_rho_t_ci95": ci,
               "snapshots_rho_t_beats_rho_pnl": wins, "verdict": verdict, "snapshots": results}
    s = json.dumps(summary, indent=1, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
    print(json.dumps({k: v for k, v in summary.items() if k != "snapshots"}, indent=1))
    for r in results:
        print({k: v for k, v in r.items() if k != "rows"})


if __name__ == "__main__":
    main()
