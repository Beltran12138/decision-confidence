"""Audit 006: score Alpha Arena season 1 from Nof1's own (archived) equity series.

Usage:
    python tools/audit_alpha_arena.py [FILE]

FILE is the gzip JSON that nof1.ai/api/account-totals served; without it the script downloads
the Wayback copy below. The live endpoint and the arena pages are gone (404 on 2026-10-12).

Each model started the season with $10,000 and traded crypto perps on Hyperliquid from
2025-10-17 22:00Z to the close on 2025-11-03 (5 pm ET = 22:00Z). The series is hourly
dollar_equity. It is put on a daily grid (last sample at or before each node) and scored with
hl_wallet.score, the estimator behind evidencedeflator.com/wallet/ (intervals in weeks, so a day
is 1/7). No deposits or withdrawals happened during the season, so equity changes are returns.
"""
import gzip
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import hl_wallet as H  # noqa: E402

ARCHIVE = "https://web.archive.org/web/20251112224724id_/https://nof1.ai/api/account-totals"
START_EQUITY = 10000.0
END = datetime(2025, 11, 3, 22, 0, tzinfo=timezone.utc).timestamp()
DAY = 86400


def load(path):
    if path:
        raw = open(path, "rb").read()
    else:
        raw = subprocess.run(["curl", "-sL", "-m", "120", "--fail", ARCHIVE], capture_output=True, check=True).stdout
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass
    return json.loads(raw)["accountTotals"]


def daily(series):
    """Daily returns (r, interval in weeks) from [(unix seconds, equity)], last sample at or before each node."""
    nodes, i, t = [], 0, series[0][0]
    while t <= series[-1][0]:
        while i + 1 < len(series) and series[i + 1][0] <= t:
            i += 1
        if not nodes or nodes[-1] != i:
            nodes.append(i)
        t += DAY
    if nodes[-1] != len(series) - 1:
        nodes.append(len(series) - 1)
    return [((series[b][1] - series[a][1]) / series[a][1], (series[b][0] - series[a][0]) / (7 * DAY))
            for a, b in zip(nodes, nodes[1:])]


def main():
    rows = {}
    for x in load(sys.argv[1] if len(sys.argv) > 1 else None):
        rows.setdefault(x["model_id"], []).append((x["timestamp"], float(x["dollar_equity"])))
    models = sorted(m for m in rows if m != "buynhold_btc")
    n = len(models)
    out = []
    for m in models:
        s = sorted(p for p in rows[m] if p[0] <= END + 3600)
        s.insert(0, (s[0][0] - 3600, START_EQUITY))  # the first hourly sample is an hour into the season
        sc = H.score(daily(s))
        days = (s[-1][0] - s[0][0]) / DAY
        out.append({"model": m, "end_equity": round(s[-1][1], 2), "return_pct": round(100 * (s[-1][1] / START_EQUITY - 1), 1),
                    "days": round(days, 1), "intervals": sc["intervals"], "sharpe": sc["sharpe"], "t": sc["t"],
                    "verdict": H.verdict(sc, n)["key"],
                    "months_to_t2": round(H.months_to_clear(2, sc["sharpe"]), 1) if sc["sharpe"] and sc["sharpe"] > 0 else None,
                    "months_to_best_of_n": round(H.months_to_clear(H.bar(n), sc["sharpe"]), 1) if sc["sharpe"] and sc["sharpe"] > 0 else None})
    out.sort(key=lambda r: -r["return_pct"])
    years = out[0]["days"] / 365
    print(json.dumps({"source": ARCHIVE, "models": n, "bar_best_of_n": round(H.bar(n), 2),
                      "sharpe_needed_for_t2": round(2 / years ** 0.5, 2),
                      "sharpe_needed_for_best_of_n": round(H.bar(n) / years ** 0.5, 2),
                      "rows": out}, indent=1))


if __name__ == "__main__":
    main()
