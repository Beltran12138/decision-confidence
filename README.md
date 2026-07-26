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
methodology (see below). The decision-confidence layer ships as a library
module, as **three adapters for real, key-free risk APIs**, and as an **MCP
server** (stdio, two tools) so an agent can call it directly.

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
| **Decision-confidence (meta)** | Shipped | `build_report` / `observe_from_raw` in `src/decision_confidence.py` |
| **Real vendor adapters** | Shipped — 3 vendors, no API keys | `src/adapters/` |
| **MCP server** | Shipped (reference impl) | 2 tools in `src/mcp_server.py` |
| **Calibration** | Harness shipped, never run | `tools/calibrate.py` — no labelled data in hand |

Dependencies: the core library is **pure standard library**. Only the MCP
server needs an extra (`pip install -e ".[mcp]"`).

Not built on purpose: HTTP fetching inside the library, auth, multi-tenancy.
The library holds no credentials and reaches nothing; those are host concerns,
and inventing them here would be scope theatre. Reasoning in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

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

### Three real sources, no API keys

```bash
python examples/live_multi_source.py 0xdAC17F958D2ee523a2206206994597C13D831ec7
python examples/live_multi_source.py --offline usdt     # replay stored captures
```

| Vendor | What it measures | Key needed |
| --- | --- | --- |
| [GoPlus Token Security](https://docs.gopluslabs.io/reference/api-overview) | contract authority flags, holder concentration | no |
| [honeypot.is v2](https://honeypot.is/) | buy/sell simulation — tradability | no |
| [DexScreener](https://docs.dexscreener.com/api/reference) | pool liquidity depth | no |

`examples/live_multi_source.py` is the **only** file in this repo that touches
the network. Adapters are pure functions of `(subject, raw)`; the caller
fetches. Real captures from 2026-07-26 are frozen in `tests/fixtures/`, so the
tests and the `--offline` walkthrough never depend on three third-party
services staying up.

### What the real run actually shows

Ethereum USDT, three sources:

```
source                    risk  status      construct
goplus                      69  ok          authority_control     mint, pause, blacklist, balance-change
goplus:concentration        45  ok          holder_concentration  top-1 holder 19.30%
honeypot_is                  1  ok          tradability           buy and sell both simulate fine
dexscreener                  -  unavailable liquidity_depth       no pairs on chain 'ethereum'

composite : 38   verdict: moderate   confidence: medium
  [range/medium]              spread 68 — but one measures tradability and the other
                              authority_control; the disagreement may be definitional
  [construct_mismatch/medium] the composite mixes 3 distinct constructs, so the
                              weighted mean is not a like-for-like average
```

Three things in that output are the whole argument for the layer:

1. **The sources disagree by 68 points and neither is wrong.** USDT genuinely
   can be frozen and minted by its issuer, and it genuinely trades fine. A
   single blended score would have hidden both facts.
2. **`unavailable` is not `safe`.** DexScreener's token endpoint is keyed by
   address rather than by (chain, address): querying the Ethereum USDT address
   returns **PulseChain** pools, the same address on a fork chain. Taking
   `pairs[0]` — or even `max(liquidity)` — reports six figures of liquidity for
   the largest stablecoin in existence. The adapter refuses to guess and says
   so; the report carries the gap instead of papering over it.
3. **Confidence drops without the verdict moving.** `moderate` still reads
   `moderate`; what changed is how much an agent should act on it.

None of this says USDT is unsafe. It says three sources answered three
different questions, and averaging them into one number without saying so is
the failure this layer exists to prevent.

### Local mock demo (no network)

Three fictional providers — `MockAlphaRisk`, `MockBetaKYT`, `MockGammaFraud` —
emit heterogeneous payloads. The demo normalizes them, runs contradiction
rules, and prints a decision report for (1) agreeing sources and (2)
conflicting sources.

```bash
python examples/decision_confidence_demo.py
python -m unittest discover tests
```

The second case is the point of the whole layer: the composite alone reads
`40 / moderate`, but one source calls it fraud while two call it safe — so
`confidence` collapses to `low` and the disagreement is reported explicitly
rather than being averaged away.

### MCP server

```bash
pip install -e ".[mcp]"
python src/mcp_server.py          # stdio; or: risk-normalize-mcp
```

Two tools:

- `list_supported_vendors()` → `{vendor_id: description}` for every registered
  adapter.
- `decision_confidence(subject, sources, weights?)` → the full report:
  observations, composite, verdict, confidence, contradictions, audit.

Each entry in `sources` is
`{"source_id": ..., "raw": <vendor payload as received>, "vendor": <optional>}`.
With `vendor`, the payload is parsed by that vendor's real adapter and may
expand into several observations. Without it, generic shapes are recognised by
their keys: `{"fraud_probability": 0..1}`, `{"tier": "LOW|MEDIUM|HIGH"}`,
`{"score": 0..100, "scale": "safety_0_100"}` (flipped), `{"score": 0..100}`
(already risk).

**The host keeps what the host should keep**: API keys, HTTP, rate limits,
caching, PII policy. The tool is a pure transform of what it is given.

---

## Why this layer should exist

**The gap is structural, not a market-size claim.** Agents increasingly call
several external risk sources — on-chain risk scores, fraud/scam prediction,
KYT-style compliance tiers. Those sources disagree in scale and, often, in
substance. Today an agent either trusts one vendor (silent failure when that
vendor is wrong or down) or eyeballs raw JSON through an LLM (non-repeatable
across runs). Neither leaves anything you can audit afterwards.

This is demonstrated rather than asserted: three real key-free APIs, asked
about the most widely held stablecoin on Ethereum, return a 68-point spread and
one unscoreable result — and the unscoreable one fails *silently* in any
implementation that trusts the vendor's default ordering. See the walkthrough
above.

No risk vendor will close this gap. A vendor's product is *its own* score; it
has no incentive to ship "our competitor disagrees with us, and here is how
much to trust the combination." A neutral layer that consumes several vendors
and reports **disagreement and confidence** is structurally something the
vendors themselves will not build.

**Where this sits.** Below: the risk APIs — we consume them, we don't compete
with them. Above: the agent that has to act. Between them sits the thing
nobody owns — *how much should this agent trust what it just read, and can it
show why afterwards.*

**Monetization: candidate paths, none validated.**

1. Open-source core plus a hosted audit/attestation service — the audit trail
   is the part teams cannot casually self-host.
2. Per-call MCP tool for agent runtimes that need decision provenance.
3. Compliance-adjacent: decision audit trails as evidence for teams that must
   justify automated actions.

We are not claiming revenue, users, or validated willingness to pay. At this
stage this is a **primitive**, and its first job is to be correct and reusable,
not to bill.

**What would prove this wrong** — stated here rather than left for a reviewer
to find:

- A major risk vendor ships native cross-vendor confidence and contradiction
  reporting.
- Agent frameworks absorb this as a built-in utility, leaving no room for a
  separate layer.
- In practice agents call exactly one risk source and never hit the
  disagreement problem at all.

**Why it fits one-person companies.** A solo builder cannot staff a
vendor-evaluation desk. The organisations that can — funds, exchanges, large
protocols — already have internal risk teams. Solo builders get the same
disagreement problem with none of the headcount.

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
  against any labeled dataset. `tools/calibrate.py` is the instrument for
  fixing that; it has never been run against real labels, and running it on the
  bundled synthetic sample proves nothing about accuracy.
- The three shipped adapters cover **EVM tokens only**. Solana, addresses as
  subjects, and compliance/KYT vendors go through the generic fallback.
- GoPlus contributes two of the four default observations, so it carries double
  weight unless the caller passes `weights`.
- The MCP server is a **reference implementation**. No auth, no multi-tenant
  isolation, no HTTP inside the library — deliberately, since the library holds
  no credentials and reaches nothing.
- Fixtures are **snapshots**. Vendors change scoring and pair lists churn; a
  failing fixture test may be a refresh signal rather than a code bug.
- A general LLM with web access may see *more current* on-chain data than a
  sandboxed caller of this library. This project's edge is **repeatable,
  comparable verdicts and explicit uncertainty** — not data freshness.

---

## License

MIT. See [LICENSE](LICENSE).
