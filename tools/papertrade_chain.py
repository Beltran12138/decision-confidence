"""Papertrade trades for given wallets, read straight from HyperEVM event logs (audit 010).

The Exchange (proxy 0x6cd5…D0a2, implementation unverified) emits, per position:
  0x88451ea1… open   topics (positionId, trader)  data [market (0 BTC, 1 ETH), side (1 long, 0 short), 0,
                                                         entry price x100, margin (1e18 USDC), leverage]
  0x87902ed2… close  topics (positionId, trader)  data [exit price x100, gross PnL, PnL after the impact haircut,
                                                         0, fee]                       (signed, 1e18 USDC)
  0x0c859bc5… liquidation  topics (positionId, trader)  data [price, price, 0, margin, margin]
Realised PnL of a position = (PnL after haircut - fee) on a close, or -margin on a liquidation.

Calibrated on 0x2025…840e (2026-10-10/11), against figures published elsewhere: 307 closes with 296 winners,
median hold 98 s, 30 liquidated shorts at 2507.35 and 660x with $297.0M notional and $450,000 lost;
summed realised PnL $1,278,697 against Paperdash's $1,278,867.

  python tools/papertrade_chain.py OUT.json 0xWALLET [0xWALLET ...] [--from-block N] [--to-block N]
"""
import argparse, json, math, sys, time, urllib.error, urllib.request
from collections import defaultdict

RPC = "https://rpc.hyperliquid.xyz/evm"
RPC_LOGS = "https://rpc.hyperlend.finance"  # serves wide getLogs ranges; the official RPC caps them at 1,000 blocks
EXCHANGE = "0x6cd5661646289FB6E65EA5C032310fDEd797D0a2"
OPEN, CLOSE, LIQ = "0x88451ea1", "0x87902ed2", "0x0c859bc5"
LAUNCH_BLOCK = 48170000  # a little before 2026-10-10 14:00 UTC


def rpc(url, method, params, tries=8):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "evidence-deflator"})
            r = json.load(urllib.request.urlopen(req, timeout=120))
            if "error" in r and "rate" in str(r["error"]).lower():
                raise urllib.error.HTTPError(url, 429, "rate limited", None, None)
            return r
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(min(60, 5 * 2 ** i))
    raise RuntimeError(f"{method} failed after {tries} tries")


def logs(wallets, frm, to, span=50000):
    topics = ["0x" + "0" * 24 + w.lower()[2:] for w in wallets]
    out, b = [], frm
    while b <= to:
        e = min(b + span - 1, to)
        r = rpc(RPC_LOGS, "eth_getLogs", [{"address": EXCHANGE, "fromBlock": hex(b), "toBlock": hex(e),
                                           "topics": [None, None, topics]}])
        if "error" in r:  # too many results or too wide: halve the span
            if span <= 500:
                raise RuntimeError(r["error"])
            span //= 2
            continue
        out += [l for l in r["result"] if l["topics"][0][:10] in (OPEN, CLOSE, LIQ)]
        b = e + 1
        time.sleep(1.5)
    return out


def words(l):
    raw = [int(l["data"][2 + 64 * i: 2 + 64 * (i + 1)], 16) for i in range((len(l["data"]) - 2) // 64)]
    return [x - (1 << 256) if x >= 1 << 255 else x for x in raw]


def positions(log_list):
    op, cl, lq = {}, {}, {}
    for l in log_list:
        key = (l["topics"][2][-40:], int(l["topics"][1], 16))
        rec = (int(l["blockTimestamp"], 16), words(l))
        {OPEN: op, CLOSE: cl, LIQ: lq}[l["topics"][0][:10]][key] = rec
    out = []
    for (w, pid), (t0, o) in op.items():
        row = {"wallet": "0x" + w, "id": pid, "market": "ETH" if o[0] == 1 else "BTC", "side": "long" if o[1] == 1 else "short",
               "entry": o[3] / 100, "margin": o[4] / 1e18, "leverage": o[5], "opened": t0}
        if (w, pid) in cl:
            t1, c = cl[(w, pid)]
            row.update(closed=t1, exit=c[0] / 100, pnl=(c[2] - c[4]) / 1e18, how="close")
        elif (w, pid) in lq:
            t1, c = lq[(w, pid)]
            row.update(closed=t1, exit=c[0] / 100, pnl=-o[4] / 1e18, how="liquidated")
        else:
            row.update(how="open")
        out.append(row)
    return sorted(out, key=lambda r: (r["wallet"], r["opened"]))


def burst_t(rows, window=300):
    """t on independent bets: trades opened in the same window are summed into one bet (they ride the same move)."""
    g = defaultdict(float)
    for r in rows:
        if r["how"] != "open":
            g[r["opened"] // window] += r["pnl"]
    v = list(g.values())
    if len(v) < 3:
        return None, len(v)
    m = sum(v) / len(v); sd = math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))
    return (m / sd * math.sqrt(len(v)) if sd else None), len(v)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("wallets", nargs="+")
    ap.add_argument("--from-block", type=int, default=LAUNCH_BLOCK); ap.add_argument("--to-block", type=int)
    a = ap.parse_args()
    to = a.to_block or int(rpc(RPC, "eth_blockNumber", [])["result"], 16)
    rows = []
    for i in range(0, len(a.wallets), 50):
        rows += positions(logs(a.wallets[i:i + 50], a.from_block, to))
    json.dump({"from_block": a.from_block, "to_block": to, "positions": rows}, open(a.out, "w"), indent=1)
    by = defaultdict(list)
    for r in rows: by[r["wallet"]].append(r)
    for w, rs in by.items():
        done = [r for r in rs if r["how"] != "open"]
        t, k = burst_t(rs)
        print(w, len(done), "positions", f"pnl {sum(r['pnl'] for r in done):,.0f}", "t(5-min bets)", None if t is None else round(t, 2), "bets", k)
