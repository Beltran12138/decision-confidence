"""Audit 011: Recall's perps competitions, scored for luck, and checked for repeat winners.

Usage:
    python tools/audit_recall.py OUT.json [--cache DIR]

Recall (recall.network) runs short live-trading competitions for AI agents. Its docs say perps
competitions are ranked by the Calmar ratio: return compounded to a year over |max drawdown|
(docs.recall.network/raw/competitions/perps-guide.md). The API's evaluationMetric says which
rule each competition actually used: calmar_ratio for the first three, simple_return after. Everything here comes from its public
competition API (api.competitions.recall.network, no key):

  /api/competitions?status=ended               the list; perpetual_futures, not sandbox
  /api/competitions/{id}/agents                final rank, Calmar, return, drawdown
  /api/competitions/{id}/timeline?bucket=60    hourly total value per agent

Each agent's hourly values are turned into returns (interval in weeks, an hour = 1/168) and
scored with hl_wallet.score, the estimator behind evidencedeflator.com/wallet/. Two caveats,
stated in the audit: hourly perps returns are not independent, and the timeline is total value,
so a deposit during a competition would count as a gain (the docs do not say whether deposits
are allowed; agents joining late are scored on their own window, as Recall does).

Then the one test that needs no model: agents that entered more than one perps competition.
If the ranking measured skill, an agent's placement in one competition would predict its
placement in its next one. The statistic is the Spearman correlation of percentile ranks over
consecutive pairs. The same agent contributes several pairs, so the interval is a bootstrap over
agents (resampling whole agents), not over pairs; a pair-level permutation test would treat 96
pairs from 34 agents as independent and overstate the evidence.
"""
import argparse
import json
import math
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import hl_wallet as H  # noqa: E402

API = "https://api.competitions.recall.network/api"
HOUR_W = 1 / 168


def get(path, cache):
    fn = os.path.join(cache, path.strip("/").replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-") + ".json") if cache else None
    if fn and os.path.exists(fn):
        with open(fn, encoding="utf-8") as f:
            return json.load(f)
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("https_proxy", "http_proxy", "all_proxy")}
    out = subprocess.run(["curl", "-s", "-m", "120", "--fail", API + path], capture_output=True, env=env, check=True).stdout
    data = json.loads(out)
    if fn:
        os.makedirs(cache, exist_ok=True)
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(data, f)
    time.sleep(0.5)
    return data


def competitions(cache):
    out, off = [], 0
    while True:
        d = get(f"/competitions?status=ended&limit=50&offset={off}", cache)
        out += d["competitions"]
        if not d["pagination"]["hasMore"]:
            return out
        off += 50


def ts(s):
    return datetime.fromisoformat(s.replace(" ", "T").replace("+00", "+00:00")).timestamp()


def hourly_returns(points):
    vals = [(ts(p["timestamp"]), p["totalValue"]) for p in points if p.get("totalValue")]
    vals.sort()
    return [((b - a) / a, (tb - ta) / 3600 * HOUR_W) for (ta, a), (tb, b) in zip(vals, vals[1:]) if a > 0]


def spearman(x, y):
    def rank(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx, syy = sum((a - mx) ** 2 for a in rx), sum((b - my) ** 2 for b in ry)
    return sxy / math.sqrt(sxx * syy) if sxx and syy else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--cache", default=None)
    a = ap.parse_args()

    comps = [c for c in competitions(a.cache) if c["type"] == "perpetual_futures" and not c.get("sandboxMode")]
    comps.sort(key=lambda c: c["startDate"])
    rows, history = [], {}
    for c in comps:
        cid = c["id"]
        ag = get(f"/competitions/{cid}/agents?limit=100", a.cache)["agents"]
        tl = {x["agentId"]: x["timeline"] for x in get(f"/competitions/{cid}/timeline?bucket=60", a.cache)["timeline"]}
        days = (ts(c["endDate"].replace("Z", "+00")) - ts(c["startDate"].replace("Z", "+00"))) / 86400
        n = len(ag)
        scored = []
        for x in ag:
            sc = H.score(hourly_returns(tl.get(x["id"], [])))
            scored.append({"agent": x["id"], "name": x["name"], "rank": x["rank"], "calmar": x.get("calmarRatio"),
                           "return": x.get("simpleReturn"), "max_drawdown": x.get("maxDrawdown"),
                           "portfolio_value": x.get("portfolioValue"), "t": sc["t"], "hours": round(sc["weeks"] * 168) if sc.get("t") is not None else None})
            if x.get("rank"):
                history.setdefault(x["id"], []).append((c["startDate"], (x["rank"] - 1) / max(n - 1, 1), x["name"]))
        bar = H.bar(n) if n > 1 else 2.0
        win = min(scored, key=lambda s: s["rank"] or 10 ** 9)
        ts_ = [s["t"] for s in scored if s["t"] is not None]
        rows.append({"id": cid, "name": c["name"], "start": c["startDate"][:10], "end": c["endDate"][:10], "days": round(days, 1),
                     "ranked_by": c.get("evaluationMetric"), "arena": c.get("arenaId"),
                     "agents": n, "bar_best_of_n": round(bar, 2), "scored": len(ts_),
                     "t_ge_2": sum(t >= 2 for t in ts_), "t_ge_bar": sum(t >= bar for t in ts_),
                     "winner": win, "all_lost_money": all((s["return"] or 0) < 0 for s in scored),
                     "winner_drawdown_under_1pct": win["max_drawdown"] is not None and abs(win["max_drawdown"]) < 0.01,
                     "median_portfolio_value": sorted(s["portfolio_value"] or 0 for s in scored)[n // 2] if n else None,
                     "agents_detail": scored})

    # repeat entrants: placement in one competition vs the next one they entered (0 = first, 1 = last)
    by_agent = {}
    for aid, h in history.items():
        h.sort()
        if len(h) > 1:
            by_agent[aid] = [(p, q) for (_, p, _), (_, q, _) in zip(h, h[1:])]
    pairs = [x for v in by_agent.values() for x in v]
    rho = spearman([p for p, _ in pairs], [q for _, q in pairs]) if len(pairs) > 2 else None
    rng, boot, keys = random.Random(11), [], list(by_agent)
    for _ in range(4000 if rho is not None else 0):
        smp = [x for k in (rng.choice(keys) for _ in keys) for x in by_agent[k]]
        boot.append(spearman([p for p, _ in smp], [q for _, q in smp]))
    boot.sort()
    top = [(p, q) for p, q in pairs if p <= 1 / 3]
    out = {
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": API,
        "ranking_rule": "Calmar = ((1 + simple return)^(365/days) - 1) / |max drawdown|; docs.recall.network/raw/competitions/perps-guide.md",
        "competitions": rows,
        "repeat": {"agents_in_2_plus": sum(len(h) > 1 for h in history.values()), "pairs": len(pairs),
                   "spearman_next": None if rho is None else round(rho, 3),
                   "ci95_by_agent": None if rho is None else [round(boot[int(0.025 * len(boot))], 3), round(boot[int(0.975 * len(boot))], 3)],
                   "share_of_resamples_le_0": None if rho is None else round(sum(b <= 0 for b in boot) / len(boot), 3),
                   "top_third_pairs": len(top),
                   "top_third_again": sum(q <= 1 / 3 for _, q in top)},
    }
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
    for r in rows:
        w = r["winner"]
        print(f"{r['start']} {r['days']:>4}d n={r['agents']:>2} bar={r['bar_best_of_n']:.2f} t>=2:{r['t_ge_2']:>2} t>=bar:{r['t_ge_bar']} | "
              f"#1 {w['name'][:18]:18} calmar={w['calmar']} ret={w['return']} dd={w['max_drawdown']} t={w['t']} $={w['portfolio_value']}")
    print(json.dumps(out["repeat"]))


if __name__ == "__main__":
    main()
