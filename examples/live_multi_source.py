"""Three real risk sources, one decision report. **The only networked file here.**

The library performs no network I/O by design: fetching, keys, retries, rate
limits and caching belong to the caller. This script *is* that caller, kept in
``examples/`` so the boundary stays visible.

All three sources are public and need no API key:

* GoPlus Token Security  — contract authority flags + holder concentration
* honeypot.is v2         — buy/sell simulation (tradability)
* DexScreener            — pool liquidity depth

Usage::

    python examples/live_multi_source.py 0x6982508145454ce325ddbe47a25d4ec3d2311933
    python examples/live_multi_source.py 0xdAC17F958D2ee523a2206206994597C13D831ec7
    python examples/live_multi_source.py --offline usdt     # replay stored fixtures

``--offline`` replays payloads captured on 2026-07-26 (``tests/fixtures/``), so
the walkthrough is reproducible without network and without depending on three
third-party services staying up.

Nothing here is investment advice, and the thresholds are uncalibrated.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from adapters import observe_vendor  # noqa: E402
from decision_confidence import DecisionReport, SourceObservation, build_report  # noqa: E402

TIMEOUT = 20
UA = "decision-confidence/0.2 (+https://github.com/Beltran12138/decision-confidence)"

FIXTURES = {
    "pepe": ("0x6982508145454ce325ddbe47a25d4ec3d2311933", "pepe"),
    "usdt": ("0xdAC17F958D2ee523a2206206994597C13D831ec7", "usdt"),
}


def _get_json(url: str) -> Tuple[Dict[str, Any], str]:
    """Fetch and parse. Returns ``(payload, error)`` — never raises."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8")), ""
    except urllib.error.HTTPError as exc:
        return {}, f"HTTP {exc.code}"
    except Exception as exc:  # network down, DNS, TLS, bad JSON
        return {}, f"{type(exc).__name__}: {exc}"


def fetch_live(address: str, chain_id: str, chain: str) -> List[Tuple[str, Dict[str, Any]]]:
    addr = urllib.parse.quote(address)
    calls = [
        ("goplus",
         f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}?contract_addresses={addr}"),
        ("honeypot_is",
         f"https://api.honeypot.is/v2/IsHoneypot?address={addr}"),
        ("dexscreener",
         f"https://api.dexscreener.com/latest/dex/tokens/{addr}"),
    ]
    out: List[Tuple[str, Dict[str, Any]]] = []
    for vendor, url in calls:
        payload, err = _get_json(url)
        if err:
            # An unreachable vendor must reach the engine as *unavailable*,
            # never be dropped — a silently missing source is how a pipeline
            # ends up confident on two sources while believing it had three.
            payload = {"error": f"fetch failed ({err})"}
        if vendor == "dexscreener":
            payload["_chain"] = chain
        print(f"  fetched {vendor:12} {'ok' if not err else err}", file=sys.stderr)
        out.append((vendor, payload))
    return out


def load_fixtures(key: str, chain: str) -> List[Tuple[str, Dict[str, Any]]]:
    out: List[Tuple[str, Dict[str, Any]]] = []
    for vendor in ("goplus", "honeypot_is", "dexscreener"):
        path = os.path.join(ROOT, "tests", "fixtures", f"{vendor}_{key}.json")
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        if vendor == "dexscreener":
            payload["_chain"] = chain
        out.append((vendor, payload))
    return out


def to_observations(subject: str, payloads) -> List[SourceObservation]:
    observations: List[SourceObservation] = []
    for vendor, payload in payloads:
        observations.extend(observe_vendor(vendor, vendor, subject, payload))
    return observations


def render(report: DecisionReport) -> None:
    print("\n" + "=" * 78)
    print(f"subject: {report.subject}")
    print("=" * 78)
    print(f"{'source':<24}{'risk':>6}  {'status':<12}{'construct':<22}note")
    print("-" * 78)
    for o in report.observations:
        score = "-" if o.normalized_0_100 is None else str(o.normalized_0_100)
        print(f"{o.source_id:<24}{score:>6}  {o.status:<12}{str(o.construct or '-'):<22}{o.note}")
    print("-" * 78)

    print(f"\n{'construct':<24}{'risk':>6}  {'verdict':<14}{'sources':<10}spread")
    print("-" * 78)
    for g in report.constructs:
        score = "-" if g.score is None else str(g.score)
        cover = f"{g.n_ok}/{g.n_ok + g.n_unusable}"
        spread = f"{g.spread}" if g.n_ok >= 2 else ""
        print(f"{g.construct:<24}{score:>6}  {g.verdict:<14}{cover:<10}{spread}")
        if g.note:
            print(f"{'':<24}{'':>6}  └─ {g.note}")
    print("-" * 78)

    if report.composite is None and report.verdict == "not_comparable":
        # Stating the absence is the point. A reader who scrolls looking for
        # "the number" should find a sentence explaining why there isn't one,
        # not a blank field they will fill in with the blended value.
        print("composite : none — these constructs measure different things.")
        print(f"            (blended_composite_unsafe={report.blended_composite_unsafe} "
              "exists only for callers who insist; it is a category error)")
    else:
        print(f"composite : {report.composite}   verdict: {report.verdict}")
    print(f"confidence: {report.confidence}")

    if report.contradictions:
        print("\ncontradictions:")
        for c in report.contradictions:
            print(f"  [{c.kind}/{c.severity}] {c.detail}")
    else:
        print("\ncontradictions: none")
    print(f"\naudit steps: {len(report.audit)}")
    print(f"note: {report.note}")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="token contract address, or a fixture key with --offline")
    ap.add_argument("--chain-id", default="1", help="GoPlus numeric chain id (default 1 = Ethereum)")
    ap.add_argument("--chain", default="ethereum", help="DexScreener chain slug (default ethereum)")
    ap.add_argument("--offline", action="store_true", help="replay stored fixtures, no network")
    ap.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = ap.parse_args(argv)

    if args.offline:
        key = args.target.lower()
        if key not in FIXTURES:
            print(f"unknown fixture {key!r}; available: {', '.join(FIXTURES)}", file=sys.stderr)
            return 2
        subject, fixture_key = FIXTURES[key]
        payloads = load_fixtures(fixture_key, args.chain)
        print(f"replaying fixtures captured 2026-07-26 for {key}", file=sys.stderr)
    else:
        subject = args.target
        print(f"fetching live for {subject}", file=sys.stderr)
        payloads = fetch_live(subject, args.chain_id, args.chain)

    report = build_report(subject, to_observations(subject, payloads))
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        render(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
