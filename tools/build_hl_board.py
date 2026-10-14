"""Evidence board for the Hyperliquid public leaderboard.

Usage:
    python tools/build_hl_board.py --cache DIR [--top 100] [--refresh] [--out FILE] [--cohort FILE]

Fetches the public leaderboard (no key), picks the top accounts by all-time
PnL and by 30-day ROI, pulls each account's portfolio history, and scores it.

Returns come from the PnL history, not the account-value history: account
value moves with deposits and withdrawals, PnL does not. Each week's return
is the change in cumulative PnL divided by account value at the start of the
interval. History is resampled to a weekly grid because older points are a
week or two apart and recent ones minutes apart; mixing the two would let the
dense tail dominate. Weeks with no new source sample are merged, not zeroed.

t = Sharpe * sqrt(years), estimated for unequal intervals (see score()). The bar for the top of a board ranked from N accounts
is the same best-of-N bar the library uses (alpha = 1 - Phi(2), Bonferroni).
"""
import argparse
import hashlib
import json
import math
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from hl_wallet import (  # noqa: E402,F401  (re-exported for tests and tools/check_hl_parity.py)
    ALPHA, INFO_URL, MIN_AV, MIN_WEEKS, N, WEEK_MS, bar, flags, months_to_clear, score, t_to_z,
    weekly_returns, _betacf, _betai,
)

LB_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"


def curl(args):
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("https_proxy", "http_proxy", "all_proxy")}
    out = subprocess.run(["curl", "-s", "-m", "60", "--fail"] + args, capture_output=True, env=env)
    if out.returncode != 0:
        raise RuntimeError(f"curl failed ({out.returncode}): {args[-1]}")
    return out.stdout


def fetch_leaderboard(cache, refresh):
    p = os.path.join(cache, "leaderboard.json")
    if refresh or not os.path.exists(p):
        with open(p, "wb") as f:
            f.write(curl([LB_URL]))
    with open(p, encoding="utf-8") as f:
        return json.load(f)["leaderboardRows"]


def fetch_portfolio(cache, addr, refresh):
    p = os.path.join(cache, "portfolio", addr + ".json")
    if refresh or not os.path.exists(p):
        body = json.dumps({"type": "portfolio", "user": addr})
        data = curl(["-X", "POST", INFO_URL, "-H", "Content-Type: application/json", "-d", body])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        time.sleep(0.25)
    with open(p, encoding="utf-8") as f:
        return dict(json.load(f))


def window(row, name):
    for k, v in row["windowPerformances"]:
        if k == name:
            return v
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--cohort", help="frozen cohort file: created from today's picks if missing, "
                                     "otherwise scored on the record after its freeze time")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)

    rows = fetch_leaderboard(a.cache, a.refresh)
    n_accounts = len(rows)

    def num(r, w, k):
        try:
            return float(window(r, w).get(k, 0))
        except (TypeError, ValueError):
            return 0.0

    by_pnl = sorted(rows, key=lambda r: -num(r, "allTime", "pnl"))[: a.top]
    by_roi = sorted((r for r in rows if float(r["accountValue"]) >= 10000),
                    key=lambda r: -num(r, "month", "roi"))[: a.top]

    boards = {}
    for key, picked, label in (("pnl", by_pnl, "Top by all-time PnL"),
                               ("roi30", by_roi, "Top by 30-day ROI (account value >= $10k)")):
        b = bar(n_accounts)
        out = []
        for rank, r in enumerate(picked, 1):
            addr = r["ethAddress"]
            try:
                pf = fetch_portfolio(a.cache, addr, a.refresh)
                rets, s, e, counted = weekly_returns(pf)
                fl = flags(pf, rets, counted)
            except Exception as ex:  # one bad account should not sink the board
                print("skip", addr, ex, file=sys.stderr)
                rets, s, e, fl = [], None, None, []
            sc = score(rets)
            out.append({
                "rank": rank,
                "address": addr,
                "display": r.get("displayName"),
                "account_value": round(float(r["accountValue"]), 2),
                "pnl_all_time": round(num(r, "allTime", "pnl"), 2),
                "roi_30d": round(num(r, "month", "roi"), 4),
                **sc,
                "months_to_clear": (round(months_to_clear(b, sc["sharpe"]), 1)
                                    if sc["sharpe"] and sc["sharpe"] > 0 else None),
                "flags": fl,
                "history_from": datetime.fromtimestamp(s / 1000, timezone.utc).strftime("%Y-%m-%d") if s else None,
            })
        scored = [x for x in out if x["t"] is not None]
        boards[key] = {
            "board": label,
            "ranked_from": n_accounts,
            "shown": len(out),
            "scored": len(scored),
            "t_bar_single": 2.0,
            "t_bar_best_of_n": round(b, 2),
            "n_t_ge_2": sum(x["t"] >= 2 for x in scored),
            "n_t_ge_bar": sum(x["t"] >= b for x in scored),
            "rows": out,
        }

    fetched_ms = int(os.path.getmtime(os.path.join(a.cache, "leaderboard.json")) * 1000)
    cohort = None
    if a.cohort:
        if not os.path.exists(a.cohort):
            seen, members = set(), []
            for key, b in boards.items():
                for r in b["rows"]:
                    if r["address"] not in seen:
                        seen.add(r["address"])
                        members.append({"address": r["address"], "board": key, "rank": r["rank"],
                                        "t_before": r["t"], "pnl_all_time_before": r["pnl_all_time"]})
            frozen = {
                "frozen_at_ms": fetched_ms,
                "frozen_at": datetime.fromtimestamp(fetched_ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
                "rule": "every address in today's two top-100 boards; scored only on PnL after frozen_at",
                "method": "tools/build_hl_board.py weekly_returns(since=frozen_at_ms) + score(); min %d weeks" % MIN_WEEKS,
                "members": members,
            }
            with open(a.cohort, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(frozen, indent=1, ensure_ascii=False))
        with open(a.cohort, "rb") as f:
            raw = f.read()
        frozen = json.loads(raw)
        since = frozen["frozen_at_ms"]
        fwd = []
        for m in frozen["members"]:
            try:
                rets, _, _, _ = weekly_returns(fetch_portfolio(a.cache, m["address"], False), since=since)  # boards above already refreshed today's files
            except Exception as ex:
                print("skip", m["address"], ex, file=sys.stderr)
                rets = []
            fwd.append({"address": m["address"], "board": m["board"], "rank": m["rank"],
                        "t_before": m["t_before"], **score(rets)})
        scored = [x for x in fwd if x["t"] is not None]
        cohort = {
            "file": os.path.basename(a.cohort),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "frozen_at": frozen["frozen_at"],
            "first_readings": datetime.fromtimestamp((since + MIN_WEEKS * WEEK_MS) / 1000, timezone.utc).strftime("%Y-%m-%d"),
            "members": len(fwd),
            "scored": len(scored),
            "n_t_ge_2": sum(x["t"] >= 2 for x in scored),
            "rows": fwd,
        }

    result = {
        "source": LB_URL,
        # when the leaderboard was fetched (the cache may be reused across builds)
        "fetched": datetime.fromtimestamp(fetched_ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "method": "weekly returns = delta cumulative PnL / account value at week start; t = Sharpe*sqrt(years)",
        "boards": boards,
        "cohort": cohort,
    }
    s = json.dumps(result, indent=1, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(s)
    for k, v in boards.items():
        print(k, {kk: vv for kk, vv in v.items() if kk != "rows"})


if __name__ == "__main__":
    main()
