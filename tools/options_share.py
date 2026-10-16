"""Trigger line for a tail flag on wallet verdicts: options + outcome notional as a share of perp volume on Hyperliquid.

t = Sharpe * sqrt(years) assumes roughly symmetric returns. Selling options or outcome contracts gives many small wins
and a rare large loss, which t reads as skill until the loss arrives. Once this kind of trading is a real share of
Hyperliquid volume, the wallet page needs a skew/tail flag. Trigger: share >= 2% over the last 30 days.

Sources, all public and re-runnable:
  options   DefiLlama options overview, chain Hyperliquid L1, dailyNotionalVolume (Rysk V12 and others).
            Hypercall is not tracked there; pass its self-reported figure with --extra if you want it counted.
  outcomes  DefiLlama dexs summary for hyperliquid-outcomes (HIP-4).
  perps     Hyperliquid info API, daily candles for every perp on the core dex and each HIP-3 dex, volume * close.

Usage: python tools/options_share.py [--days 30] [--extra LABEL=USD ...] [--out FILE.json]
"""
import argparse, datetime as dt, json, time, urllib.request

HL = "https://api.hyperliquid.xyz/info"
LLAMA = "https://api.llama.fi/"
TRIGGER = 0.02


def get(url, body=None, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "User-Agent": "evidence-deflator"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def window_sum(chart, start, end):
    """chart = [[unix_seconds, value], ...]; sum days in [start, end)."""
    return sum(v for t, v in chart if start <= t < end)


def perp_volume(start, end):
    dexs = [""] + [d["name"] for d in get(HL, {"type": "perpDexs"}) if d]
    total, by_dex = 0.0, {}
    for dex in dexs:
        meta = get(HL, {"type": "meta", **({"dex": dex} if dex else {})})
        s = 0.0
        for a in meta["universe"]:
            candles = get(HL, {"type": "candleSnapshot", "req": {"coin": a["name"], "interval": "1d",
                                                                 "startTime": start * 1000, "endTime": end * 1000 - 1}})
            s += sum(float(c["v"]) * float(c["c"]) for c in candles or [] if start * 1000 <= c["t"] < end * 1000)
            time.sleep(0.05)
        by_dex[dex or "core"] = s
        total += s
    return total, by_dex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--extra", action="append", default=[], help="LABEL=USD, e.g. hypercall_selfreported=536e6")
    ap.add_argument("--out")
    a = ap.parse_args()
    today = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    end = int(today.timestamp())  # whole UTC days only; today is partial
    start = end - a.days * 86400

    opt = get(LLAMA + "overview/options/hyperliquid-l1?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true"
              "&dataType=dailyNotionalVolume")
    options = window_sum(opt["totalDataChart"], start, end)
    out = get(LLAMA + "summary/dexs/hyperliquid-outcomes")
    outcomes = window_sum(out["totalDataChart"], start, end)
    extra = {k: float(v) for k, v in (e.split("=", 1) for e in a.extra)}
    perps, by_dex = perp_volume(start, end)

    num = options + outcomes + sum(extra.values())
    share = num / perps if perps else None
    res = {
        "window_utc": [dt.datetime.fromtimestamp(start, dt.timezone.utc).date().isoformat(),
                       dt.datetime.fromtimestamp(end, dt.timezone.utc).date().isoformat()],
        "options_notional_defillama": round(options), "options_protocols": [p["name"] for p in opt["protocols"]],
        "outcomes_notional_defillama": round(outcomes), "extra": extra,
        "perp_volume_hl_candles": round(perps), "perp_by_dex": {k: round(v) for k, v in by_dex.items()},
        "share": None if share is None else round(share, 5), "trigger": TRIGGER,
        "triggered": share is not None and share >= TRIGGER,
        "read_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    print(json.dumps(res, indent=1))
    if a.out:
        json.dump(res, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
