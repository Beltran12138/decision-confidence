"""Diff the Worker bundle against src/hl_wallet.py on cached portfolios, then smoke-test its routes.

Usage:
    python tools/build_worker.py && python tools/check_worker.py --cache DIR [--live]

--cache holds portfolio/<address>.json from tools/build_hl_board.py. --live also calls the
bundle's fetch handler for /api/wallet and an MCP initialize/tools/list/tools/call round trip
(this hits Hyperliquid's public API).
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import hl_wallet  # noqa: E402

KEYS = ("weeks", "intervals", "sharpe", "t_student", "dof", "t", "verdict", "bar",
        "months_more_to_clear", "flags", "history_from", "history_to")

NODE = r"""
import {pathToFileURL} from 'node:url';
import fs from 'node:fs';
const [bundle, files, live] = process.argv.slice(2);
const W = await import(pathToFileURL(bundle).href);
const out = {};
for (const f of JSON.parse(fs.readFileSync(files, 'utf8'))) {
  const pf = JSON.parse(fs.readFileSync(f, 'utf8')), a = f.split(/[\\/]/).pop().replace('.json', '');
  out[a] = {blind: W.checkWallet(a, null, pf), board: W.checkWallet(a, 47153, pf)};
}
if (live === '1') {
  const h = W.default.fetch, base = 'https://api.evidencedeflator.com';
  const a = Object.keys(out)[0];
  const r1 = await h(new Request(`${base}/api/wallet?a=${a}&picked_from=47153`));
  const post = b => h(new Request(base + '/mcp', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(b)}));
  const init = await (await post({jsonrpc: '2.0', id: 1, method: 'initialize', params: {protocolVersion: '2025-06-18'}})).json();
  const note = await post({jsonrpc: '2.0', method: 'notifications/initialized'});
  const list = await (await post({jsonrpc: '2.0', id: 2, method: 'tools/list'})).json();
  const call = await (await post({jsonrpc: '2.0', id: 3, method: 'tools/call', params: {name: 'hyperliquid_wallet', arguments: {address: a, picked_from: 47153}}})).json();
  const bad = await (await post({jsonrpc: '2.0', id: 4, method: 'tools/call', params: {name: 'hyperliquid_wallet', arguments: {address: '0x12'}}})).json();
  out.__live = {api_status: r1.status, api: await r1.json(), init: init.result?.serverInfo, notification_status: note.status,
                tools: list.result?.tools?.map(t => t.name), call_t: call.result?.structuredContent?.t, bad_isError: bad.result?.isError};
}
console.log(JSON.stringify(out));
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.cache, "portfolio", "*.json")))
    tmp = tempfile.mkdtemp()
    try:
        bundle = os.path.join(tmp, "worker.mjs")
        shutil.copy(os.path.join(ROOT, "worker", "dist", "worker.js"), bundle)
        with open(os.path.join(tmp, "run.mjs"), "w", encoding="utf-8") as f:
            f.write(NODE)
        with open(os.path.join(tmp, "files.json"), "w", encoding="utf-8") as f:
            json.dump(files, f)
        res = subprocess.run(["node", os.path.join(tmp, "run.mjs"), bundle, os.path.join(tmp, "files.json"),
                              "1" if a.live else "0"], capture_output=True, text=True, encoding="utf-8")
        if res.returncode:
            sys.exit(res.stderr)
        js = json.loads(res.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = 0
    for f in files:
        addr = os.path.basename(f)[:-5]
        with open(f, encoding="utf-8") as fh:
            pf = dict(json.load(fh))
        for mode, n in (("blind", None), ("board", 47153)):
            p, j = hl_wallet.check(addr, picked_from=n, pf=pf), js[addr][mode]
            for k in KEYS:
                pv, jv = p.get(k), j.get(k)
                same = (abs(pv - jv) <= 0.0011 if isinstance(pv, (int, float)) and isinstance(jv, (int, float))
                        and not isinstance(pv, bool) else pv == jv)
                if not same:
                    bad += 1
                    print("DIFF", addr, mode, k, pv, jv)
    print(f"{len(files)} portfolios x 2 modes: {'OK' if not bad else str(bad) + ' differences'}")
    if a.live:
        print(json.dumps(js["__live"], indent=1)[:1500])
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
