"""Capture vendor payloads for a labelled address list. **This file makes network calls.**

The library never fetches; that rule is architectural and holds. This is
calibration tooling, not part of the package — it stands where
``examples/live_multi_source.py`` stands, on the caller's side of the line, and
its whole job is to turn a list of labelled addresses into the JSONL that
``tools/calibrate.py`` consumes.

Input — JSON array of ``{"address", "chain", "class", "title"}``, e.g. the
address list extracted from a rug-pull dataset. ``class`` is mapped to the
harness label: anything matching ``--bad-class`` becomes 1, everything else 0.

Output — one JSON object per line, appended, resumable::

    {"subject": "0x…", "label": 1, "title": "…", "chain": "ETH",
     "sources": [{"vendor": "goplus", "raw": {…}}, …]}

Usage::

    python tools/capture_payloads.py .data/tm_rugpull_addresses.json \\
        --out .data/captured.jsonl --vendors goplus,dexscreener

Resumable by design: subjects already present in ``--out`` are skipped, so an
interrupted run is restarted by re-issuing the same command. Rate limits and
transient failures are recorded as ``{"error": …}`` payloads rather than
dropped — a vendor that could not answer must reach the engine as
``unavailable``, never as absence.

**On honeypot.is and DexScreener:** capturing them is worth doing even though
``tradability`` and ``liquidity_depth`` are graded as severe-leakage in
``calibrate.py``. That grade is a judgement; capturing the sources lets the
sweep either confirm it (near-perfect F1 on the leaky constructs, mediocre on
the clean one) or refute it. Assuming the answer would defeat the purpose.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple

UA = "decision-confidence-calibration/0.2 (+https://github.com/Beltran12138/decision-confidence)"
TIMEOUT = 25

# Dataset chain label → (GoPlus numeric chain id, DexScreener slug).
# Absent from this map means "we do not know how to ask about that chain", which
# is recorded rather than guessed.
CHAINS: Dict[str, Tuple[str, str]] = {
    "ETH": ("1", "ethereum"),
    "BSC": ("56", "bsc"),
    "POLYGON": ("137", "polygon"),
    "ARBI": ("42161", "arbitrum"),
    "FANTOM": ("250", "fantom"),
    "FTM": ("250", "fantom"),
    "CRONO": ("25", "cronos"),
    "BASE": ("8453", "base"),
}

# honeypot.is simulates against a live pool; it only covers a few chains, and a
# chain it does not cover is not a failure of the token.
HONEYPOT_CHAINS = {"1", "56", "8453"}

# GoPlus documents `contract_addresses` as comma-separated, and on the free tier
# it accepts the list, returns code=1, and silently answers for the **first
# address only**. Verified 2026-08-07: one address → 39 fields; the same address
# plus a second → the same single entry, no error, no warning.
#
# Batching it is therefore worse than slow — it is quietly wrong. Every address
# after the first comes back as an empty result, the adapter correctly reports
# `unavailable`, and a calibration run ends up 95% blank while looking exactly
# like "the vendor does not cover these tokens". One address per request.
GOPLUS_BATCH = 1

# DexScreener does honour multi-address queries; the returned `pairs` array
# mixes all of them, so each subject keeps only the pairs whose baseToken is
# its own address.
DEXSCREENER_BATCH = 30


def get_json(url: str) -> Tuple[Optional[Dict[str, Any]], str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8")), ""
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def chunks(seq: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def capture_goplus(rows: List[Dict[str, Any]], pause: float) -> Dict[str, Dict[str, Any]]:
    """Batched by chain. Returns subject → payload shaped as the adapter expects."""
    out: Dict[str, Dict[str, Any]] = {}
    by_chain: Dict[str, List[str]] = {}
    for r in rows:
        chain = CHAINS.get(r["chain"].upper())
        if not chain:
            out[r["address"]] = {"error": f"no GoPlus chain id for {r['chain']!r}"}
            continue
        by_chain.setdefault(chain[0], []).append(r["address"])

    for chain_id, addresses in by_chain.items():
        for batch in chunks(addresses, GOPLUS_BATCH):
            joined = urllib.parse.quote(",".join(batch))
            url = f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={joined}"
            payload, err = get_json(url)
            if err or not isinstance(payload, dict):
                for a in batch:
                    out[a] = {"error": f"fetch failed ({err or 'bad payload'})"}
            else:
                result = payload.get("result") or {}
                for a in batch:
                    entry = result.get(a.lower())
                    # Re-wrap per subject so each stored payload is exactly what
                    # a single-address call would have returned.
                    out[a] = ({"code": payload.get("code", 1), "result": {a.lower(): entry}}
                              if entry is not None
                              else {"code": payload.get("code", 1), "result": {}})
            print(f"  goplus chain {chain_id}: +{len(batch)} ({len(out)} done)", file=sys.stderr)
            time.sleep(pause)
    return out


def capture_dexscreener(rows: List[Dict[str, Any]], pause: float) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    addresses = [r["address"] for r in rows]
    slug = {r["address"]: CHAINS.get(r["chain"].upper(), ("", ""))[1] for r in rows}
    for batch in chunks(addresses, DEXSCREENER_BATCH):
        url = "https://api.dexscreener.com/latest/dex/tokens/" + ",".join(batch)
        payload, err = get_json(url)
        if err or not isinstance(payload, dict):
            for a in batch:
                out[a] = {"error": f"fetch failed ({err or 'bad payload'})", "_chain": slug[a]}
        else:
            pairs = payload.get("pairs") or []
            for a in batch:
                mine = [p for p in pairs if isinstance(p, dict)
                        and str((p.get("baseToken") or {}).get("address", "")).lower() == a.lower()]
                # `_chain` is the hint the adapter needs to refuse fork-chain
                # pools; without it a wrong-chain match reads as real liquidity.
                out[a] = {"pairs": mine, "_chain": slug[a]}
        print(f"  dexscreener: +{len(batch)} ({len(out)} done)", file=sys.stderr)
        time.sleep(pause)
    return out


def capture_honeypot(rows: List[Dict[str, Any]], pause: float) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for i, r in enumerate(rows, 1):
        chain_id = CHAINS.get(r["chain"].upper(), ("", ""))[0]
        if chain_id not in HONEYPOT_CHAINS:
            out[r["address"]] = {"error": f"honeypot.is does not cover chain {r['chain']}"}
            continue
        url = (f"https://api.honeypot.is/v2/IsHoneypot?address={urllib.parse.quote(r['address'])}"
               f"&chainID={chain_id}")
        payload, err = get_json(url)
        out[r["address"]] = payload if payload is not None else {"error": f"fetch failed ({err})"}
        if i % 25 == 0:
            print(f"  honeypot_is: {i}/{len(rows)}", file=sys.stderr)
        time.sleep(pause)
    return out


CAPTURERS = {
    "goplus": capture_goplus,
    "dexscreener": capture_dexscreener,
    "honeypot_is": capture_honeypot,
}


def already_done(path: str) -> set:
    if not os.path.exists(path):
        return set()
    done = set()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    done.add(json.loads(line)["subject"].lower())
                except Exception:
                    continue
    return done


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("addresses", help="JSON array of {address, chain, class, title}")
    ap.add_argument("--out", required=True, help="JSONL output (appended, resumable)")
    ap.add_argument("--vendors", default="goplus,dexscreener",
                    help="comma-separated subset of " + ", ".join(CAPTURERS))
    ap.add_argument("--bad-class", default="scam", help="class value that maps to label 1")
    ap.add_argument("--limit", type=int, default=0, help="stop after N new subjects (0 = all)")
    ap.add_argument("--pause", type=float, default=1.5, help="seconds between requests")
    args = ap.parse_args(argv)

    vendors = [v.strip() for v in args.vendors.split(",") if v.strip()]
    unknown = [v for v in vendors if v not in CAPTURERS]
    if unknown:
        raise SystemExit(f"unknown vendor(s): {', '.join(unknown)}")

    with open(args.addresses, encoding="utf-8") as fh:
        rows = json.load(fh)
    done = already_done(args.out)
    todo = [r for r in rows if r["address"].lower() not in done]
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(rows)} subjects, {len(done)} already captured, {len(todo)} to fetch",
          file=sys.stderr)
    if not todo:
        return 0

    captured = {}
    for vendor in vendors:
        print(f"[{vendor}]", file=sys.stderr)
        captured[vendor] = CAPTURERS[vendor](todo, args.pause)

    with open(args.out, "a", encoding="utf-8") as fh:
        for r in todo:
            fh.write(json.dumps({
                "subject": r["address"],
                "label": 1 if str(r.get("class", "")).lower() == args.bad_class else 0,
                "title": r.get("title"),
                "chain": r.get("chain"),
                "sources": [{"vendor": v, "raw": captured[v].get(r["address"], {"error": "not captured"})}
                            for v in vendors],
            }, ensure_ascii=False) + "\n")
    print(f"wrote {len(todo)} rows to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
