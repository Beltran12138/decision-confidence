# risk-normalize

**Agent Decision Confidence** — a small, dependency-free framework that turns
**heterogeneous risk signals from multiple external sources** into **one
comparable 0–100 basis**, detects **cross-source contradictions**, and returns
a **decision confidence** label with an **audit trail**.

> Read-only. Pure Python standard library. No network, no on-chain reads, no
> execution. Fetching is the caller's job; the value is a *repeatable,
> comparable basis* — not data freshness.

---

## Positioning: a meta-layer, not an oracle

Agents and tools increasingly call several external risk APIs (on-chain risk
scores, fraud / scam prediction, KYT-style compliance tiers, and similar).
Those APIs do not share units, scales, or failure modes. One source may look
"safe" while another looks like fraud — and a single composite without
**confidence** and **audit** invites false certainty.

This project sits **above** those APIs. It does **not** compete with them,
replace them, or claim to know the chain better than they do. It **consumes
their outputs** (caller-supplied) and adds three things:

1. **Normalization** — map each source onto one 0–100 risk basis (0 = safe /
   low risk, 100 = max risk)
2. **Contradiction detection** — flag when sources disagree in polarity or
   magnitude
3. **Decision confidence + audit** — how much to trust the composite, and why

Token multi-factor risk scoring is the **native instance** of the same
methodology (see below). A full MCP server surface is planned; this repo
already ships the library core and a local mock demo of the decision-confidence
pipeline.

```
  [ Risk API A ] [ Risk API B ] [ Risk API C ]  ...  (caller fetches)
           \           |           /
            v          v          v
         adapters → normalize → contradict → confidence → audit
                              (this layer)
```

---

## Why not "just one risk API"?

| Approach | Gap |
| --- | --- |
| Single vendor score | Silent failure when that vendor is wrong or down |
| Ad-hoc agent prompt over raw JSON | Non-repeatable; no shared basis across runs |
| Homegrown oracle that re-does on-chain DD | Competes with specialists; huge surface; no PMF for a thin library |

**Decision confidence as a meta-layer** assumes specialists exist and focuses
on **comparability, disagreement, and honest uncertainty** — what an agent
needs before it acts.

---

## Two surfaces

| Surface | Status | Entry |
| --- | --- | --- |
| **Library (token instance)** | Shipped | `score_token` / `TokenInputs` in `src/normalize.py` |
| **Decision-confidence (meta)** | Design + local mock | `docs/ARCHITECTURE.md`, `examples/decision_confidence_demo.py` |
| **MCP server** | Future | Not implemented in this release |

---

## Native instance: token risk-normalize

The same methodology was first applied to **heterogeneous token-risk inputs**
(holder concentration, contract authority, pool size, holder base, funding
extremity). That instance remains fully supported and is the stable public
API of this package.

### The problem (token domain)

Token risk signals come from many places and many units: a holder-share
percentage, a pool size in USD, a contract authority string, a holder count, a
per-venue funding rate. They are not directly comparable.

`score_token` does one thing well: **normalize every dimension to 0–100
(0 = safe, 100 = max risk), flag extremes, and combine them into one verdict
— while telling you how much to trust it.**

### Two paths (token domain)

**Path A — template hit (fast, no data).** Name a token covered by the
built-in snapshot table → get a qualitative baseline plus the date it was
captured. Explicitly *a baseline, not live truth*.

**Path B — caller-supplied (precise, data-bound).** Supply any subset of the
risk inputs → each dimension is normalized to 0–100, extremes flagged, and
combined. **Missing dimensions are never guessed** — they are marked unknown
and lower the confidence.

If neither path has data, the framework does **not** invent a number: it
returns a default-deny "extreme until proven otherwise" and asks for inputs.

### Install

Pure standard library, Python ≥ 3.8. No dependencies.

```bash
# editable install (optional)
pip install -e .

# or just put src/ on your path
```

### Quick start (token instance)

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

```bash
python examples/pepe_caller_supplied.py
```

### The five dimensions (token instance)

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

### Output schema (token instance)

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

---

## Decision-confidence surface (meta-layer)

### Idea

Treat each external risk API as one **source dimension**:

| Source class (examples) | Typical raw shape | Normalize toward |
| --- | --- | --- |
| On-chain risk score APIs | 0–100 safety or risk score | 0–100 risk (flip if vendor is "safety") |
| Fraud / scam prediction | probability or label | 0–100 risk |
| KYT / compliance-style tiers | LOW / MED / HIGH (or similar) | 0–100 risk |

Then: **normalize → detect contradictions across sources → synthesize
confidence → emit audit trail.**

Design detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

### Local mock demo (no network)

Three fictional providers — `MockAlphaRisk`, `MockBetaKYT`, `MockGammaFraud` —
emit heterogeneous payloads. The demo normalizes them, runs contradiction
rules, and prints a decision report for (1) agreeing sources and (2)
conflicting sources.

```bash
python examples/decision_confidence_demo.py
```

Logic lives entirely in the example (stdlib only). A production MCP tool
surface is **not** shipped yet; see Architecture for the intended tool sketch.

---

## Honest limitations

- **Read-only analysis, not investment advice, not a safety guarantee, not a
  compliance certification.**
- **Meta-layer dependency:** decision quality is bounded by upstream risk API
  availability, honesty, coverage, and latency. If sources are down, stale,
  or correlated (same underlying data), confidence and contradiction signals
  degrade — this library does not invent missing upstream truth.
- Token **snapshot table** is **dated and qualitative** — a fast triage, not
  live truth.
- **Caller-supplied only** — missing inputs are marked unknown, never guessed.
  The library performs **no** network I/O.
- Thresholds and contradiction rules are **rough heuristics**, not calibrated
  against any labeled dataset.
- The decision-confidence demo is a **local mock**, not a production MCP
  server and not a live multi-vendor integration.
- A general LLM with web access may see *more current* on-chain data than a
  sandboxed caller of this library. This project's edge is **repeatable,
  comparable verdicts and explicit uncertainty** — not data freshness.

---

## License

MIT. See [LICENSE](LICENSE).
