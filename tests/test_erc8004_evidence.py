"""tools/erc8004_evidence.py: keccak-256 and ABI encoding against published values, and the evidence it builds."""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import erc8004_evidence as E  # noqa: E402


def test_keccak_against_published_values():
    # keccak256("") and two function selectors every Ethereum tool agrees on
    assert E.keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert E.keccak256(b"transfer(address,uint256)")[:4].hex() == "a9059cbb"
    assert E.keccak256(b"balanceOf(address)")[:4].hex() == "70a08231"
    # not SHA3-256, which differs only in the padding byte
    import hashlib
    assert E.keccak256(b"abc") != hashlib.sha3_256(b"abc").digest()


def test_keccak_padding_edges():
    # lengths around the 136-byte rate, where the padding bytes share or spill into a block
    import hashlib
    for n in (0, 1, 134, 135, 136, 137, 271, 272):
        d = bytes(range(256)) * 2
        d = d[:n]
        # SHA3-256 is the same sponge with padding byte 0x06; swapping the domain byte reproduces it
        rate, fill = 136, 136 - n % 136
        p = bytearray(d) + (b"\x86" if fill == 1 else b"\x06" + b"\x00" * (fill - 2) + b"\x80")
        a = [[0] * 5 for _ in range(5)]
        for off in range(0, len(p), rate):
            blk = p[off:off + rate]
            for i in range(rate // 8):
                a[i % 5][i // 5] ^= int.from_bytes(blk[8 * i:8 * i + 8], "little")
            a = E._f(a)
        out = b"".join(a[i % 5][i // 5].to_bytes(8, "little") for i in range(4))
        assert out == hashlib.sha3_256(d).digest(), n


def test_abi_encoding_of_strings_and_words():
    cd = E.abi_call("f(uint256,string,bytes32)", [("uint256", 7), ("string", "ab"), ("bytes32", "0x" + "11" * 32)])
    body = bytes.fromhex(cd[10:])
    words = [body[i:i + 32] for i in range(0, len(body), 32)]
    assert int.from_bytes(words[0], "big") == 7
    assert int.from_bytes(words[1], "big") == 96  # offset of the string after three head words
    assert words[2] == bytes.fromhex("11" * 32)
    assert int.from_bytes(words[3], "big") == 2 and words[4] == b"ab" + b"\x00" * 30
    # negative int128 is two's complement over 256 bits
    neg = bytes.fromhex(E.abi_call("g(int128)", [("int128", -32)])[10:])
    assert int.from_bytes(neg, "big") == (1 << 256) - 32


def _portfolio(rets, av=50_000.0):
    t0, w = 1_700_000_000_000, 7 * 24 * 3600 * 1000
    pts, pnl = [], 0.0
    for i, r in enumerate(rets):
        pts.append((t0 + i * w, av, pnl))
        pnl += r * av
    pts.append((t0 + len(rets) * w, av, pnl))
    pf = [["allTime", {"accountValueHistory": [[t, str(v)] for t, v, _ in pts], "pnlHistory": [[t, str(p)] for t, _, p in pts]}]]
    return json.dumps(pf).encode()


def test_evidence_commits_to_the_file_and_the_data():
    import random
    rng = random.Random(5)
    raw = _portfolio([rng.gauss(0.01, 0.02) for _ in range(60)])
    blob, fb, val = E.build("0x" + "ab" * 20, 42, 47310, raw, "2026-10-17T00:00:00+00:00", "https://example.org/e.json")
    ev = json.loads(blob)
    assert fb["args"]["feedbackHash"] == "0x" + E.keccak256(blob).hex()
    assert ev["data"]["response_keccak256"] == "0x" + E.keccak256(raw).hex()
    assert fb["args"]["value"] == round(ev["result"]["t"] * 100) and fb["args"]["valueDecimals"] == 2
    assert fb["args"]["tag1"] == "deflatedT" and fb["args"]["tag2"] == "bestOf47310"
    assert fb["calldata"].startswith("0x" + E.keccak256(E.GIVE_FEEDBACK.encode())[:4].hex())
    assert 0 <= val["args"]["response"] <= 100
    assert val["args"]["response"] == min(100, max(0, round(100 * ev["result"]["t"] / ev["result"]["bar"])))
    # the same inputs give the same bytes, so anyone can recompute the hash
    assert E.build("0x" + "ab" * 20, 42, 47310, raw, "2026-10-17T00:00:00+00:00", "https://example.org/e.json")[0] == blob
