# risk-normalize

A small, dependency-free framework that maps **heterogeneous token-risk
inputs** onto **one comparable 0–100 basis**, flags extremes, and returns a
single composite verdict with an honest confidence label.

> Read-only. Pure Python standard library. No network, no on-chain reads, no
> execution. Originally built for a sandboxed agent runtime with no outbound
> network, where fetching is the caller's job and the value is a *repeatable,
> comparable basis* — not data freshness.

---

## The problem it solves

Token risk signals come from many places and many units: a holder-share
percentage, a pool size in USD, a contract authority string, a holder count, a
per-venue funding rate. They are not directly comparable, and a human (or an
agent) staring at raw inputs easily over- or under-weights one dimension.

`risk-normalize` does one thing well: **normalize every dimension to 0–100
(0 = safe, 100 = max risk), flag extremes, and combine them into one verdict
you can act on — while telling you, honestly, how much to trust it.**

The normalization framework itself is domain-general: only the per-dimension
inputs change between use cases. Token risk is the first instance.

## Two paths

**Path A — template hit (fast, no data).** Name a token covered by the
built-in snapshot table → get a qualitative baseline plus the date it was
captured. Explicitly *a baseline, not live truth*.

**Path B — caller-supplied (precise, data-bound).** Supply any subset of the
risk inputs → each dimension is normalized to 0–100, extremes flagged, and
combined. **Missing dimensions are never guessed** — they are marked unknown
and lower the confidence.

If neither path has data, the framework does **not** invent a number: it
returns a default-deny "extreme until proven otherwise" and asks for inputs.

## Install

Pure standard library, Python ≥ 3.8. No dependencies.

```bash
# editable install (optional)
pip install -e .

# or just put src/ on your path
```

## Quick start

```python
from normalize import score_token, TokenInputs

# Path A: template lookup
print(score_token("BTC").to_dict())

# Path B: caller-supplied multi-dimension score
v = score_token("PEPE", TokenInputs(
    top10_pct=62.0,
    pool_usd=800_000,
    mint_authority="retained",
    holder_count=42_000,
    funding_rates=[
        {"venue": "binance", "rate": 0.0008},
        {"venue": "hyperliquid", "rate": -0.0004},
    ],
))
print(v.verdict, v.composite, v.confidence, v.red_flags)
# high 70 high ['mint/freeze authority retained by deployer']
```

Run the bundled demo:

```bash
python examples/pepe_caller_supplied.py
```

## The five dimensions

Each dimension is normalized to 0–100. Thresholds are **rough heuristics, not
calibrated** against any dataset — tweak them to taste.

| Dimension | Weight | Key input | Notes |
| --- | --- | --- | --- |
| Concentration | 0.30 | top-10 / top-1 holder % | highest weight — biggest rug vector; top-1 > 50% is a red flag |
| Contract | 0.25 | mint/freeze authority, source verified, honeypot | retained authority / honeypot = hard red flag |
| Liquidity | 0.20 | main pool size (USD) | < 100K flagged thin |
| Holders | 0.15 | total holder count | thin base = riskier |
| Funding | 0.10 | per-venue funding rates | extremity signal, **not** free money |

Weights are re-normalized at runtime over whichever dimensions actually have
data, so partial inputs still produce a defensible composite.

**Composite bands:** `< 30` low · `30–55` moderate · `55–80` high · `> 80` extreme.

**Confidence:** `high` when ≥ 4 dimensions present and agree · `medium` 2–3 ·
`low` when < 2 dimensions, or a low composite alongside a hard red flag.

### Funding-rate annualization

Per-interval funding rates are annualized before comparison:

```
annualizedPct ≈ rate × (24 / intervalHours) × 365 × 100
```

Venue interval defaults: Binance / OKX / Gate = 8h, Hyperliquid / dYdX = 1h.
Override per-rate with `intervalHours`. The reported signal is the annualized
gap between the most-negative long-funding venue and the most-positive
short-funding venue — a **squeeze / positioning indicator, not free money**.

## Output schema

```jsonc
{
  "token": "PEPE",
  "source": "caller-supplied",
  "snapshot_date": null,
  "dimensions": { /* per-dimension score / raw / flag */ },
  "composite": 70,
  "verdict": "high",
  "confidence": "high",
  "red_flags": ["mint/freeze authority retained by deployer"],
  "note": "Caller-supplied only - the normalizer does no fetching. ..."
}
```

`score_token(...).to_dict()` returns this shape as a plain dict, ready to
serialize or hand to another agent.

## Honest limitations

- **Read-only analysis, not investment advice, not a safety guarantee.**
- The snapshot table is **dated and qualitative** — a fast triage, not live truth.
- The caller-supplied path is **bounded by the data supplied**; missing
  dimensions are marked unknown, never guessed.
- Thresholds are **rough heuristics**, not calibrated against any dataset.
- A general LLM with web access may see *more current* on-chain data than a
  sandboxed caller of this library. This library's edge is **repeatable,
  comparable verdicts** — a consistent risk basis — not data freshness. Use it
  when you want a comparable basis across tokens, not the latest on-chain state.

## License

MIT. See [LICENSE](LICENSE).
