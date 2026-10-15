"""Audit 008: Polymarket's profit leaderboard, tested position by position.

Usage:
    python tools/audit_polymarket.py --cache DIR [--top 50] [--max-positions 1000] [--out FILE]

A prediction-market record has no capital series to turn into returns, so this audit does not use
the wallet check's t. It asks a different question of each resolved position: was the price paid
too low for how things turned out? Under no skill, a share bought at price p pays 1 with
probability p, so edge = outcome - p has mean 0 and variance p(1 - p).

  z_naive   = sum(edge) / sqrt(sum p(1-p))          positions treated as independent
  z_cluster = sum(edge) / sqrt(sum_e (sum edge in event e)^2)   positions in one event share an outcome

z_cluster is the headline: bets on the same event (an election, a season) are one bet, not many.
Positions are equal-weighted (one position, one observation); the dollar-weighted edge is reported
alongside. avgPrice is the average buy price, so positions partly sold before resolution are
scored on what was bought. Resolved positions come from two lists: closed-positions (sold or
redeemed) and positions with redeemable = true (resolved, never redeemed: mostly losers). A wallet
counts only if neither list hit --max-positions; capped wallets are reported and excluded.

Public endpoints (no key): data-api.polymarket.com/v1/leaderboard and /closed-positions.
The leaderboard reaches about 10,050 wallets and reports no total, so the best-of-N bar is computed
for N = 10,050, a floor: the true N is larger and its bar higher.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import hl_wallet as H  # noqa: E402

API = "https://data-api.polymarket.com/"
N_FLOOR = 10050


def cached(cache, name, url):
    p = os.path.join(cache, name + ".json")
    if not os.path.exists(p):
        out = subprocess.run(["curl", "-s", "-m", "30", "--fail", url], capture_output=True)
        if out.returncode != 0:
            raise RuntimeError(f"curl {out.returncode}: {url}")
        with open(p, "wb") as f:
            f.write(out.stdout)
        time.sleep(0.3)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def unredeemed(cache, wallet, cap):
    """Resolved positions never redeemed: losing shares are worth 0 and usually stay here, not in
    closed-positions. Leaving them out makes every record look like a winner (checked 2026-10-15:
    one top-50 wallet had 500+ such positions, 476 of them losses)."""
    out, off = [], 0
    while len(out) < cap:
        page = cached(cache, f"op_{wallet}_{off}", f"{API}positions?user={wallet}&limit=500&offset={off}&sizeThreshold=0")
        if not page:
            break
        out += page
        if len(page) < 500:
            break
        off += 500
    return [p for p in out[:cap] if p.get("redeemable") and p.get("curPrice") in (0, 1)], len(out) >= cap


def positions(cache, wallet, cap):
    out, off = [], 0
    while len(out) < cap:
        page = cached(cache, f"cp_{wallet}_{off}",
                      f"{API}closed-positions?user={wallet}&limit=50&offset={off}&sortBy=TIMESTAMP&sortDirection=DESC")
        if not page:
            break
        out += page
        if len(page) < 50:
            break
        off += 50
    return out[:cap]


def test(pos):
    seen, res = set(), []
    for p in pos:  # a partly sold position can sit in both lists: count each asset once
        if p.get("curPrice") in (0, 1) and 0 < float(p.get("avgPrice") or 0) < 1 and p.get("asset") not in seen:
            seen.add(p.get("asset"))
            res.append(p)
    if not res:
        return None
    edge = [p["curPrice"] - float(p["avgPrice"]) for p in res]
    var = sum(float(p["avgPrice"]) * (1 - float(p["avgPrice"])) for p in res)
    by_event = defaultdict(float)
    for p, e in zip(res, edge):
        by_event[p.get("eventSlug") or p.get("conditionId")] += e
    clus = sum(v * v for v in by_event.values())
    w = [float(p.get("totalBought") or 0) * float(p["avgPrice"]) for p in res]  # dollars spent
    return {"resolved": len(res), "events": len(by_event), "won": sum(p["curPrice"] == 1 for p in res),
            "mean_price": round(sum(float(p["avgPrice"]) for p in res) / len(res), 3),
            "mean_edge": round(sum(edge) / len(res), 4),
            "dollar_weighted_edge": round(sum(e * x for e, x in zip(edge, w)) / sum(w), 4) if sum(w) else None,
            "z_naive": round(sum(edge) / math.sqrt(var), 2) if var else None,
            "z_cluster": round(sum(edge) / math.sqrt(clus), 2) if clus else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--max-positions", type=int, default=1000)
    ap.add_argument("--out")
    a = ap.parse_args()
    os.makedirs(a.cache, exist_ok=True)
    board = cached(a.cache, "lb_all", f"{API}v1/leaderboard?timePeriod=ALL&orderBy=PNL&limit={a.top}&offset=0")
    bar = H.bar(N_FLOOR)
    out = []
    for r in board[: a.top]:
        w = r["proxyWallet"]
        try:
            closed = positions(a.cache, w, a.max_positions)
            unred, unred_capped = unredeemed(a.cache, w, a.max_positions)
        except Exception as ex:
            print("skip", w, ex, file=sys.stderr)
            continue
        t = test(closed + unred)
        t_closed_only = test(closed)
        out.append({"rank": int(r["rank"]), "wallet": w, "name": r.get("userName"), "pnl": round(float(r["pnl"]), 2),
                    "closed_fetched": len(closed), "unredeemed_resolved": len(unred),
                    "complete": len(closed) < a.max_positions and not unred_capped,
                    "z_cluster_closed_only": (t_closed_only or {}).get("z_cluster"), **(t or {})})
    sc = [x for x in out if x.get("z_cluster") is not None and x["complete"]]
    big = [x for x in sc if x["events"] >= 30]
    summary = {"source": API, "ranked_by": "all-time PnL", "n_floor": N_FLOOR, "bar_best_of_n_floor": round(bar, 2),
               "shown": len(out), "complete_and_scored": len(sc),
               "incomplete_excluded": sum(1 for x in out if not x["complete"]),
               "closed_only_z_cluster_ge_bar_all": sum(1 for x in out if (x.get("z_cluster_closed_only") or 0) >= bar),
               "z_cluster_ge_2": sum(x["z_cluster"] >= 2 for x in sc), "z_cluster_ge_bar": sum(x["z_cluster"] >= bar for x in sc),
               "z_naive_ge_2": sum(x["z_naive"] >= 2 for x in sc), "z_naive_ge_bar": sum(x["z_naive"] >= bar for x in sc),
               "with_30plus_events": len(big), "of_those_z_cluster_ge_bar": sum(x["z_cluster"] >= bar for x in big),
               "rows": out}
    s = json.dumps(summary, indent=1, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
