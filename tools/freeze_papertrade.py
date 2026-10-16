"""Freeze Papertrade's PnL leaderboard and recheck it later (audit 010).

Papertrade (synthetic perps on HyperEVM, up to 1000x) has no public API of its own for traders.
Paperdash (paperdash.xyz), a third-party dashboard, server-renders the full leaderboard, 100 rows a page.

  python tools/freeze_papertrade.py freeze            # full board + three frozen groups
  python tools/freeze_papertrade.py recheck FROZEN    # full board again, PnL earned since the freeze

Frozen groups (fixed before any outcome is seen):
  top_all   all-time PnL top 100
  top_24h   24-hour PnL top 100
  control   100 accounts drawn with seed 20261016 from the rest of the all-time board
            (accounts with at least $1M of volume, so the control is people who actually trade)

Outcome: PnL after the freeze = all-time PnL at recheck - all-time PnL at freeze (USDC, realised + unrealised).
PAPER rewards are recorded but not counted as PnL.
"""
import argparse, csv, gzip, hashlib, io, json, random, re, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://paperdash.xyz/leaderboard"
OUT = Path(__file__).resolve().parent.parent / "docs" / "data" / "papertrade"
UA = {"User-Agent": "Mozilla/5.0 (evidence-deflator audit; github.com/Beltran12138/evidence-deflator)"}
FIELDS = ["totalWindowedPnl", "realizedPnl", "currentUnrealizedPnl", "totalVolume", "currentBalance",
          "currentQueued", "paperTotal", "currentOpenNotional", "stakingRewards"]
SEED = 20261016


def fetch_page(window, page, tries=4):
    url = f"{BASE}?sort=pnl&window={window}&size=100&page={page}"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            text = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
            break
        except Exception as e:  # network hiccup: back off and retry
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))
    text = text.replace('\\"', '"')
    k = text.find('"rows":[')
    if k < 0:
        raise RuntimeError(f"no rows on {url}")
    rows, _ = json.JSONDecoder().raw_decode(text, k + len('"rows":'))
    m = re.search(r'"window":"%s"[^{}]{0,200}?"count":(\d+)' % window, text) or re.search(r'"count":(\d+)', text)
    return rows, int(m.group(1)) if m else None


def flat(r):
    out = {"rank": r["rank"], "address": r["address"].lower(), "username": r.get("username"),
           "lastActiveAt": r.get("lastActiveAt")}
    for f in FIELDS:
        v = r.get(f)
        out[f] = float(v["value"]) if isinstance(v, dict) else (float(v) if v is not None else None)
    return out


def full_board(window="all", pause=1.0):
    rows, count = fetch_page(window, 1)
    allrows = [flat(r) for r in rows]
    pages = -(-count // 100)
    for p in range(2, pages + 1):
        time.sleep(pause)
        rows, _ = fetch_page(window, p)
        allrows += [flat(r) for r in rows]
        if p % 20 == 0:
            print(f"  page {p}/{pages}", file=sys.stderr)
    return allrows, count


def write_board(rows, path):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
    w.writeheader(); w.writerows(rows)
    data = buf.getvalue().encode("utf-8")
    with gzip.GzipFile(path, "wb", mtime=0) as g:
        g.write(data)
    return hashlib.sha256(data).hexdigest()


def freeze(args):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    day = now[:10]
    print("fetching 24h top 100", file=sys.stderr)
    top24, count24 = fetch_page("24h", 1)
    top24 = [flat(r) for r in top24]
    print("fetching all-time board", file=sys.stderr)
    board, count = full_board("all")
    seen = {r["address"] for r in board}
    top_all = board[:100]
    pool = [r for r in board[100:] if (r["totalVolume"] or 0) >= 1e6]
    control = random.Random(SEED).sample(pool, 100)
    OUT.mkdir(parents=True, exist_ok=True)
    board_sha = write_board(board, OUT / f"board-{day}.csv.gz")
    frozen = {
        "frozen_at": now, "source": BASE + "?sort=pnl&window=all", "board_count": count, "board_rows": len(board),
        "board_unique": len(seen), "board_file": f"board-{day}.csv.gz", "board_csv_sha256": board_sha,
        "board_24h_count": count24, "seed": SEED, "control_pool": len(pool),
        "rule": "top_all = all-time PnL top 100; top_24h = 24h PnL top 100; control = 100 drawn with the seed "
                "from all-time ranks 101+ with volume >= $1M. Outcome = all-time PnL at recheck minus at freeze.",
        "groups": {"top_all": top_all, "top_24h": top24, "control": control},
    }
    body = json.dumps(frozen, indent=1, ensure_ascii=False) + "\n"
    path = OUT / f"frozen-{day}.json"
    path.write_bytes(body.encode("utf-8"))
    print(f"wrote {path} sha256 {hashlib.sha256(body.encode('utf-8')).hexdigest()}  board {len(board)}/{count}")


def median(xs):
    s = sorted(xs); n = len(s)
    return None if not n else (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def recheck(args):
    frozen = json.loads(Path(args.frozen).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    board, count = full_board("all")
    by = {r["address"]: r for r in board}
    OUT.mkdir(parents=True, exist_ok=True)
    sha = write_board(board, OUT / f"board-{now[:10]}.csv.gz")
    res = {"frozen_at": frozen["frozen_at"], "rechecked_at": now, "board_count": count,
           "board_file": f"board-{now[:10]}.csv.gz", "board_csv_sha256": sha, "groups": {}}
    for g, members in frozen["groups"].items():
        after, missing = [], []
        for m in members:
            r = by.get(m["address"])
            if r is None:
                missing.append(m["address"]); continue
            after.append({"address": m["address"], "pnl_before": m["totalWindowedPnl"],
                          "pnl_after_freeze": r["totalWindowedPnl"] - m["totalWindowedPnl"],
                          "volume_after_freeze": r["totalVolume"] - (m["totalVolume"] or 0)})
        active = [a for a in after if a["volume_after_freeze"] > 0]
        d = [a["pnl_after_freeze"] for a in active]
        res["groups"][g] = {
            "members": len(members), "found": len(after), "missing": missing, "traded_since": len(active),
            "positive_since": sum(x > 0 for x in d), "median_since": median(d), "sum_since": sum(d),
            "rows": after}
    path = OUT / f"recheck-{now[:10]}.json"
    path.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for g, v in res["groups"].items():
        print(g, {k: v[k] for k in v if k not in ("rows", "missing")}, "missing", len(v["missing"]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("freeze")
    r = sp.add_parser("recheck"); r.add_argument("frozen")
    a = ap.parse_args()
    freeze(a) if a.cmd == "freeze" else recheck(a)
