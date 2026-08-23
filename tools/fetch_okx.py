#!/usr/bin/env python3
"""Pull one live OKX spot snapshot into the corpus format redundancy.py reads.

This is the *only* networked step. It writes a JSONL file and stops; every
number downstream is computed from that file with no further network access,
so a run can be repeated from the saved snapshot and get the same answer.

    python tools/fetch_okx.py --out corpus/okx-live.jsonl
    python tools/redundancy.py corpus/okx-live.jsonl

**The stratifier.** ``redundancy.py`` measures correlation *within* a label,
because two metrics that both track one common cause will look independent
until that cause is held fixed. On this data the obvious common cause is how
large and well-supported the instrument is: spread, depth, turnover, range and
the 24h move are all partly a restatement of "is this a major coin".

So the label here is how many quote currencies OKX lists the base asset
against — a listing decision made by the exchange, not a quantity computed
from any of the five metrics. Using turnover or depth to stratify would be
circular; this is not. The cut sits at 4, where the distribution has its own
gap (12 assets at three quotes, 148 at four).

The label is *not* an outcome. Nothing here predicts anything. It is a
stratum, and the numbers downstream should be read as "within a tier of
listing support, do these five metrics still say different things".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from collections import defaultdict
from typing import Any, Dict, List

TICKERS_URL = "https://www.okx.com/api/v5/market/tickers?instType=SPOT"

# Quote-currency count at or above which an asset counts as broadly listed.
# Chosen at the gap in the observed distribution, not optimised against any
# downstream number.
BROAD_LISTING_CUT = 4

# Only these are scored; the adapter refuses anything else, and carrying the
# refusals into the corpus would fill every construct with unavailable rows.
QUOTE = "USDT"


def fetch(url: str, timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "decision-confidence/okx"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def build(tickers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    quotes_per_base: Dict[str, set] = defaultdict(set)
    for t in tickers:
        inst = str(t.get("instId") or "")
        if "-" not in inst:
            continue
        base, quote = inst.rsplit("-", 1)
        quotes_per_base[base].add(quote)

    rows: List[Dict[str, Any]] = []
    for t in tickers:
        inst = str(t.get("instId") or "")
        if not inst.endswith("-" + QUOTE):
            continue
        base = inst.rsplit("-", 1)[0]
        n_quotes = len(quotes_per_base[base])
        rows.append({
            "subject": inst,
            "label": 1 if n_quotes >= BROAD_LISTING_CUT else 0,
            "label_meaning": f"listed against >= {BROAD_LISTING_CUT} quote currencies",
            "n_quote_currencies": n_quotes,
            "sources": [{"vendor": "okx", "source_id": "okx_spot_ticker", "raw": t}],
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="corpus/okx-live.jsonl", help="JSONL to write")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    print(f"GET {TICKERS_URL}", file=sys.stderr)
    payload = fetch(TICKERS_URL, args.timeout)
    if str(payload.get("code")) != "0":
        print(f"OKX returned code={payload.get('code')} msg={payload.get('msg')!r}",
              file=sys.stderr)
        return 1

    tickers = payload.get("data") or []
    rows = build(tickers)
    if not rows:
        print("no USD-quoted instruments in response", file=sys.stderr)
        return 1

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # OKX stamps every ticker with its own millisecond timestamp; report the
    # newest so a stale snapshot is visible rather than assumed fresh.
    newest = max((int(t.get("ts") or 0) for t in tickers), default=0)
    n1 = sum(1 for r in rows if r["label"] == 1)
    print(f"{len(tickers)} instruments -> {len(rows)} {QUOTE} pairs", file=sys.stderr)
    print(f"strata: {n1} broadly listed / {len(rows) - n1} single-quote", file=sys.stderr)
    print(f"venue timestamp: {newest}", file=sys.stderr)
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
