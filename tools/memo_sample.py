"""Numbers for the sample evidence memo (docs/memo/sample/): one public record, read the way a paid memo would read it.

Fetches the account's portfolio and vault details from Hyperliquid's public API, scores it with the same code as the
wallet page (src/hl_wallet.py), and adds what the free page does not show: the record's worst weeks and drawdown,
how many months it would still need, and the vault's structure.

Usage: python tools/memo_sample.py ADDRESS OUT.json --board-n 47310
"""
import argparse
import json
import math
import os
import statistics
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import hl_wallet as hw  # noqa: E402

INFO = "https://api.hyperliquid.xyz/info"


def info(body):
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("https_proxy", "http_proxy", "all_proxy")}
    out = subprocess.run(["curl", "-s", "-m", "60", "--fail", "-X", "POST", INFO, "-H", "Content-Type: application/json",
                          "-d", json.dumps(body)], capture_output=True, env=env, check=True)
    return json.loads(out.stdout)


def day(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("address")
    ap.add_argument("out")
    ap.add_argument("--board-n", type=int, required=True, help="accounts on the board the record was picked from")
    a = ap.parse_args()
    addr = a.address.lower()

    pf = dict(info({"type": "portfolio", "user": addr}))
    vault = info({"type": "vaultDetails", "vaultAddress": addr})
    rets, start, end, counted = hw.weekly_returns(pf)
    sc = hw.score(rets)
    fl = hw.flags(pf, rets, counted)

    # the week-by-week series, with the date each week ends, for the tail figures
    av = [(t, float(v)) for t, v in pf["allTime"]["accountValueHistory"]]
    r = [x for x, _ in rets]
    worst = sorted(r)[:3]
    wealth, peak, mdd = 1.0, 1.0, 0.0
    for x in r:
        wealth *= 1 + x
        peak = max(peak, wealth)
        mdd = min(mdd, wealth / peak - 1)
    m, sd = statistics.mean(r), statistics.pstdev(r)
    skew = sum((x - m) ** 3 for x in r) / len(r) / sd ** 3 if sd else None

    bars = {"single": 2.0, "board_independent": round(hw.bar(a.board_n), 2), "board_correlated_rough": 2.6}
    years = sc["weeks"] / 52.0
    months_more = {k: (None if not sc["sharpe"] or sc["sharpe"] <= 0 else
                       round(max((b / sc["sharpe"]) ** 2 * 12 - years * 12, 0), 1)) for k, b in bars.items()}

    out = {
        "address": addr,
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "history_from": day(start) if start else None,
        "history_to": day(end) if end else None,
        "account_value": round(av[-1][1], 2),
        "pnl_all_time": round(float(pf["allTime"]["pnlHistory"][-1][1]), 2),
        "score": sc,
        "flags": fl,
        "bars": bars,
        "clears": {k: sc["t"] is not None and sc["t"] >= b for k, b in bars.items()},
        "months_more_at_this_sharpe": months_more,
        "weeks_positive_share": round(sum(x > 0 for x in r) / len(r), 3),
        "worst_weeks": [round(x, 4) for x in worst],
        "best_week": round(max(r), 4),
        "max_drawdown_compounded": round(mdd, 4),
        "weekly_mean": round(m, 5),
        "weekly_sd": round(sd, 5),
        "skew": None if skew is None else round(skew, 2),
        "board_n": a.board_n,
        "vault": None if not isinstance(vault, dict) else {
            "name": vault.get("name"), "leader": vault.get("leader"), "description": vault.get("description"),
            "leader_fraction": vault.get("leaderFraction"), "leader_commission": vault.get("leaderCommission"),
            "apr": vault.get("apr"), "allow_deposits": vault.get("allowDeposits"), "is_closed": vault.get("isClosed"),
            "relationship": vault.get("relationship"),
        },
    }
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({k: out[k] for k in ("score", "clears", "months_more_at_this_sharpe", "worst_weeks",
                                          "max_drawdown_compounded", "weeks_positive_share", "skew")}, indent=1))


if __name__ == "__main__":
    main()
