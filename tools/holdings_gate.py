#!/usr/bin/env python3
"""What are the five desk columns worth on the assets someone actually holds?

The crypto counterpart to prophetmap's ``portfolio-gate.js``: it takes a plain
list of symbols and reports what a trading desk's five columns say about each
one. Like that script, it reads **symbols only** — no quantity, no cost basis,
no P&L. Those are not inputs to the question, and carrying them here would put
them in the output.

The number that matters is deliberately *not* estimated from the holdings. A
handful of positions cannot support a correlation estimate: with ten subjects
the bootstrap interval on n_eff is wide enough to be worthless, and a tool
whose whole argument is "do not overstate your evidence" cannot open by
overstating its own. So the redundancy figure is taken from the venue-wide run
(``tools/fetch_okx.py`` → ``tools/neff.py``, several hundred pairs) and applied
to the holdings, which is the honest direction: estimate on the large sample,
read on the small one.

    python tools/holdings_gate.py BTC ETH SOL
    python tools/holdings_gate.py --file holdings.txt --neff 2.86
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from adapters import observe_vendor  # noqa: E402

TICKERS_URL = "https://www.okx.com/api/v5/market/tickers?instType=SPOT"
QUOTE = "USDT"

COLUMNS = [
    ("execution_cost", "价差"),
    ("liquidity_depth", "盘口薄侧"),
    ("trading_activity", "成交额"),
    ("price_volatility", "日内振幅"),
    ("price_momentum", "24h 涨跌"),
]


def read_symbols(argv) -> List[str]:
    idx = argv.index("--file") if "--file" in argv else -1
    if idx != -1:
        text = open(argv[idx + 1], encoding="utf-8").read()
    else:
        inline = [a for a in argv if not a.startswith("--")
                  and not re.fullmatch(r"[\d.]+", a)]
        text = " ".join(inline) if inline else sys.stdin.read()
    seen, out = set(), []
    for tok in re.split(r"[^A-Za-z0-9]+", text):
        t = tok.strip().upper()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def fetch(url: str, timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "decision-confidence/okx"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("symbols", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--neff", type=float, default=None,
                    help="venue-wide effective source count for the five columns; "
                         "run tools/demo_okx.sh to get today's")
    ap.add_argument("--timeout", type=float, default=15.0)
    ap.add_argument("-h", "--help", action="help")
    args = ap.parse_args()

    symbols = read_symbols(sys.argv[1:])
    if not symbols:
        print("给我一组代码：python tools/holdings_gate.py BTC ETH SOL", file=sys.stderr)
        return 1

    doc = fetch(TICKERS_URL, args.timeout)
    by_base = {}
    for t in doc.get("data", []):
        inst = str(t.get("instId") or "")
        if inst.endswith("-" + QUOTE):
            by_base[inst[: -(len(QUOTE) + 1)].upper()] = t

    print()
    print(f"交易台五列 · 对 {len(symbols)} 个代码逐个读")
    print(f"  数据：OKX 公开行情 {TICKERS_URL.split('?')[0]}（无需 key、无需账户）")
    print("  只读代码，不读数量、成本、盈亏。")
    print("  注：「盘口薄侧」读的是最优价档较薄的一侧，不是整个盘口深度。")
    print()

    pad = max(6, max(len(s) for s in symbols)) + 2
    hdr = "".join(f"{lbl:>10}" for _c, lbl in COLUMNS)
    print(f"  {'代码'.ljust(pad - 2)}{hdr}")
    print("  " + "─" * (pad + 10 * len(COLUMNS)))

    hit = 0
    for sym in symbols:
        t = by_base.get(sym)
        if not t:
            print(f"  {sym.ljust(pad)}  OKX 上没有 {sym}-{QUOTE} 现货对，跳过")
            continue
        hit += 1
        obs = {o.construct: o for o in
               observe_vendor("okx", "okx", sym, t)}
        cells = []
        for c, _lbl in COLUMNS:
            o = obs.get(c)
            cells.append("—" if not o or o.normalized_0_100 is None
                         else str(o.normalized_0_100))
        print(f"  {sym.ljust(pad)}" + "".join(f"{v:>10}" for v in cells))

    print()
    print(f"  取到 {hit} / {len(symbols)} 个。数字是 0–100 的风险分，越高越该留意。")
    print()

    rule = "─" * 56
    print(rule)
    print(f"  ▶  每一行都是 5 列，读起来像 5 重确认")
    if args.neff:
        print(f"     而这 5 列在全市场几百个交易对上量出来，只值 {args.neff:.2f} 个源")
        print(f"     所以每个持仓的「5 重确认」，实际是 {args.neff:.2f} 重")
    else:
        print("     这 5 列实际值几个源，跑 tools/demo_okx.sh 得到今天的数，")
        print("     再用 --neff 传进来。这里不用持仓本身去估——样本太小，估不出。")
    print(rule)
    print()
    print("注：有效源数不是在这几个持仓上估的。几个标的支撑不起相关估计，")
    print("    区间会宽到没有意义。估计取自全市场那一跑，这里只是把它读到持仓上。")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
