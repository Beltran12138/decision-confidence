"""Demo: caller-supplied scoring for a recent meme token (PEPE-style inputs).

Run from the repo root:

    python examples/pepe_caller_supplied.py
"""

import json
import os
import sys

# Make ``src/`` importable when running the demo directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from normalize import TokenInputs, score_token, snapshot_lookup  # noqa: E402


def main() -> None:
    # --- Path A: template hit, no data needed ---
    print("== Path A: BTC template lookup ==")
    print(json.dumps(snapshot_lookup("BTC"), indent=2))
    print()

    # --- Path B: caller-supplied multi-dimension score ---
    print("== Path B: PEPE caller-supplied composite ==")
    verdict = score_token(
        "PEPE",
        TokenInputs(
            top10_pct=62.0,
            pool_usd=800_000,
            mint_authority="retained",
            holder_count=42_000,
            funding_rates=[
                {"venue": "binance", "rate": 0.0008},
                {"venue": "hyperliquid", "rate": -0.0004},
            ],
        ),
    )
    print(json.dumps(verdict.to_dict(), indent=2))


if __name__ == "__main__":
    main()
