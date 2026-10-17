"""ERC-8004 evidence for a trading agent's Hyperliquid record: what a reputation or validation
entry would carry if Evidence Deflator wrote it. Builds files and call data; signs and sends nothing.

Usage:
    python tools/erc8004_evidence.py ADDRESS --agent-id ID --chain-id C --picked-from N --out DIR
        [--since YYYY-MM-DD] [--feedback-uri URI]

--since scores only the record from that day on (for an agent, its registration date: trading
before it need not have been the agent's).

ERC-8004 (eips.ethereum.org/EIPS/eip-8004) gives agents an on-chain identity and two places for
other parties to say something about them. Its reputation registry takes
    giveFeedback(agentId, int128 value, uint8 valueDecimals, tag1, tag2, endpoint, feedbackURI, bytes32 feedbackHash)
where feedbackHash is keccak256 of the file at feedbackURI; its validation registry takes
    validationResponse(bytes32 requestHash, uint8 response 0-100, responseURI, bytes32 responseHash, tag).
The spec's own example tags include `tradingYield`. A yield says what happened, not whether it
could be luck; this fills the same slots with the evidence instead:

  tag1 = "deflatedT", value = t x 100, valueDecimals = 2   (t from the wallet check's estimator)
  tag2 = "bestOf<N>" for an agent picked from N, or "single"
  validation response = min(100, round(100 x t / bar)), the share of the bar the record reaches

Out: DIR/evidence.json (the file to host at feedbackURI; its keccak256 is feedbackHash), DIR/portfolio.json
(the Hyperliquid response it was computed from, so anyone can recompute it),
DIR/feedback.json (giveFeedback arguments and ABI-encoded call data), DIR/validation.json.
The feedback must come from an address that does not own the agent (the spec forbids self-feedback).
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import hl_wallet as H  # noqa: E402

# ---------------------------------------------------------------- keccak-256 (Ethereum's, not SHA3-256)

_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B,
       0x0000000080000001, 0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088,
       0x0000000080008009, 0x000000008000000A, 0x000000008000808B, 0x800000000000008B, 0x8000000000008089,
       0x8000000000008003, 0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [[0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61], [28, 55, 25, 21, 56], [27, 20, 39, 8, 14]]
_M = (1 << 64) - 1


def _f(a):
    for rc in _RC:
        c = [a[x][0] ^ a[x][1] ^ a[x][2] ^ a[x][3] ^ a[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ (((c[(x + 1) % 5] << 1) | (c[(x + 1) % 5] >> 63)) & _M) for x in range(5)]
        a = [[a[x][y] ^ d[x] for y in range(5)] for x in range(5)]
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                r = _ROT[x][y]
                b[y][(2 * x + 3 * y) % 5] = ((a[x][y] << r) | (a[x][y] >> (64 - r))) & _M if r else a[x][y]
        a = [[b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) for y in range(5)] for x in range(5)]
        a[0][0] ^= rc
    return a


def keccak256(data: bytes) -> bytes:
    rate = 136
    fill = rate - len(data) % rate  # 1..rate bytes of padding: 0x01, zeros, 0x80 (one byte 0x81 if only one fits)
    p = bytearray(data) + (b"\x81" if fill == 1 else b"\x01" + b"\x00" * (fill - 2) + b"\x80")
    a = [[0] * 5 for _ in range(5)]
    for off in range(0, len(p), rate):
        blk = p[off:off + rate]
        for i in range(rate // 8):
            a[i % 5][i // 5] ^= int.from_bytes(blk[8 * i:8 * i + 8], "little")
        a = _f(a)
    return b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))


# ---------------------------------------------------------------- ABI encoding (just the types used here)

def _word(n: int) -> bytes:
    return (n % (1 << 256)).to_bytes(32, "big")


def abi_call(signature: str, args) -> str:
    """Call data for `signature` with args given as (type, value); types: uint256, int128, uint8, bytes32, string."""
    head, tail = b"", b""
    n = len(args)
    for typ, val in args:
        if typ == "string":
            raw = val.encode()
            head += _word(32 * n + len(tail))
            tail += _word(len(raw)) + raw + b"\x00" * ((-len(raw)) % 32)
        elif typ == "bytes32":
            head += bytes.fromhex(val[2:] if val.startswith("0x") else val).rjust(32, b"\x00")
        else:
            head += _word(int(val))
    return "0x" + keccak256(signature.encode())[:4].hex() + (head + tail).hex()


GIVE_FEEDBACK = "giveFeedback(uint256,int128,uint8,string,string,string,string,bytes32)"
VALIDATION_RESPONSE = "validationResponse(bytes32,uint8,string,bytes32,string)"


# ---------------------------------------------------------------- evidence

def portfolio_raw(address: str) -> bytes:
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("https_proxy", "http_proxy", "all_proxy")}
    body = json.dumps({"type": "portfolio", "user": address})
    return subprocess.run(["curl", "-s", "-m", "60", "--fail", "-X", "POST", H.INFO_URL, "-H", "Content-Type: application/json",
                           "-d", body], capture_output=True, env=env, check=True).stdout


def build(address: str, agent_id: int, picked_from: int, raw: bytes, fetched: str, feedback_uri: str = "",
          chain_id: int = 0, since: str = ""):
    pf = dict(json.loads(raw))
    res = H.check(address, picked_from=picked_from if picked_from > 1 else None, pf=pf)
    if since:
        # the same check, on the record from `since` on
        since_ms = int(datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
        rets, _, _, counted = H.weekly_returns(pf, since=since_ms)
        sc = H.score(rets)
        v = H.verdict(sc, picked_from if picked_from > 1 else None)
        months = H.months_to_clear(v["bar"], sc["sharpe"]) if sc.get("sharpe") else None
        have = (sc["weeks"] or 0) / 4.345 if sc.get("t") is not None else 0
        # pnl_outside_record compares PnL inside the window only; H.flags would count trading before `since`
        ph = [(t, float(x)) for t, x in pf["allTime"]["pnlHistory"]]
        before = [x for t, x in ph if t <= since_ms]
        total = ph[-1][1] - (before[-1] if before else ph[0][1]) if ph else 0.0
        fl = [f for f in H.flags(pf, rets, counted) if f != "pnl_outside_record"]
        if total > 0 and (total - counted) / total > 0.5:
            fl.append("pnl_outside_record")
        res = {**res, **sc, "verdict": v["key"], "bar": v["bar"], "flags": fl, "drawdown": H.drawdown(rets),
               "months_more_to_clear": None if months is None else round(max(months - have, 0), 1), "history_from": since}
    if res["t"] is None:
        raise SystemExit(f"{address}: record too short to score ({res['weeks']} intervals)")
    evidence = {
        "schema": "evidencedeflator.com/erc8004/v1",
        "subject": {"chainId": chain_id, "agentId": agent_id, "hyperliquid_address": address},
        "data": {"source": H.INFO_URL, "request": {"type": "portfolio", "user": address}, "fetched": fetched,
                 "response_keccak256": "0x" + keccak256(raw).hex(), "history_from": res["history_from"], "history_to": res["history_to"],
                 "window": f"from {since}" if since else "all history"},
        "method": {"estimator": "hl_wallet.score (Student t on weekly PnL / start-of-week account value, back on the normal scale)",
                   "bar": "Bonferroni best-of-N, one-sided, alpha = 1 - Phi(2)", "docs": "https://evidencedeflator.com/method/#wallets"},
        "result": {k: res[k] for k in ("t", "sharpe", "weeks", "dof", "verdict", "bar", "picked_from", "months_more_to_clear", "flags", "drawdown")},
        "reading": "t says how strong the record is once its length and the field it was picked from are allowed for. It is not a forecast and not what copying the agent would earn.",
    }
    blob = (json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    fhash = "0x" + keccak256(blob).hex()
    tag2 = f"bestOf{picked_from}" if picked_from > 1 else "single"
    value = round(res["t"] * 100)
    endpoint = f"https://evidencedeflator.com/wallet/?a={address}"
    feedback = {"function": GIVE_FEEDBACK,
                "args": {"agentId": agent_id, "value": value, "valueDecimals": 2, "tag1": "deflatedT", "tag2": tag2,
                         "endpoint": endpoint, "feedbackURI": feedback_uri, "feedbackHash": fhash},
                "note": "Send from an address that does not own or operate the agent. Host evidence.json at feedbackURI first."}
    feedback["calldata"] = abi_call(GIVE_FEEDBACK, [("uint256", agent_id), ("int128", value), ("uint8", 2), ("string", "deflatedT"),
                                                    ("string", tag2), ("string", endpoint), ("string", feedback_uri), ("bytes32", fhash)])
    response = max(0, min(100, round(100 * res["t"] / res["bar"])))
    validation = {"function": VALIDATION_RESPONSE,
                  "args": {"requestHash": None, "response": response, "responseURI": feedback_uri, "responseHash": fhash, "tag": "deflatedT"},
                  "note": "Only for a validationRequest naming this validator; requestHash comes from that request. 100 = clears the bar."}
    return blob, feedback, validation


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("address")
    ap.add_argument("--agent-id", type=int, required=True)
    ap.add_argument("--chain-id", type=int, required=True, help="chain of the ERC-8004 registry the agentId belongs to")
    ap.add_argument("--since", default="", help="score the record from this day (YYYY-MM-DD), e.g. the agent's registration")
    ap.add_argument("--picked-from", type=int, default=1, help="how many agents it was picked from (1 = not picked from a field)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--feedback-uri", default="")
    a = ap.parse_args()
    addr = a.address.lower()
    raw = portfolio_raw(addr)
    blob, fb, val = build(addr, a.agent_id, a.picked_from, raw, datetime.now(timezone.utc).isoformat(timespec="seconds"), a.feedback_uri,
                          a.chain_id, a.since)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "evidence.json"), "wb") as f:
        f.write(blob)
    with open(os.path.join(a.out, "portfolio.json"), "wb") as f:  # the API response itself; its keccak256 is in evidence.json
        f.write(raw)
    for name, obj in (("feedback.json", fb), ("validation.json", val)):
        with open(os.path.join(a.out, name), "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, indent=1)
    print(json.dumps({"t": json.loads(blob)["result"]["t"], "feedbackHash": fb["args"]["feedbackHash"],
                      "value": fb["args"]["value"], "tag2": fb["args"]["tag2"], "validation_response": val["args"]["response"]}, indent=1))


if __name__ == "__main__":
    main()
