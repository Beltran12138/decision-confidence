# decision-confidence

**Agent Decision Confidence** — a small, dependency-free framework that turns
**heterogeneous risk signals from multiple external sources** into **comparable
scores**, separates **disagreement that is factual** from **disagreement that is
definitional**, and returns a **confidence** label with an **audit trail**.

> Read-only. Pure Python standard library. No network, no on-chain reads, no
> execution. Fetching is the caller's job; the value is a *repeatable,
> comparable basis* — not data freshness.

---

## The thirty-second version

Two commands, no keys, no setup beyond Python ≥ 3.8:

```bash
python examples/two_kinds_of_disagreement.py          # the whole argument
python examples/live_multi_source.py --offline usdt   # three real vendors, replayed
```

The first prints these two blocks from the same engine:

```
CASE A — definitional disagreement (four constructs)
real vendor payloads, captured 2026-07-26
construct               risk  verdict       sources  spread
authority_control         69  high          1/1
holder_concentration      45  moderate      1/1
tradability                8  low           2/2      14
liquidity_depth            -  unknown       0/1
composite : none  (blended_composite_unsafe=32 — a category error, exposed under a name that says so)
confidence: medium

CASE B — factual disagreement (one construct, many venues)
ILLUSTRATIVE funding rates — not live, not a market claim
construct               risk  verdict       sources  spread
carry_cost                36  moderate      5/5      40
composite : 36   verdict: moderate
confidence: medium
  [range/medium] spread 40 ≥ 40 within carry_cost: funding:binance=20 vs
                 funding:hyperliquid=60 — same question, different answers
```

**A is refused a composite. B is given one.** That asymmetry is the product.

---

## Positioning: a meta-layer, not an oracle

Agents increasingly call several external risk APIs (on-chain risk scores,
fraud / scam prediction, KYT-style compliance tiers, and similar). Those APIs
do not share units, scales, or failure modes. One source may look "safe" while
another looks like fraud — and a single composite without **confidence** and
**audit** invites false certainty.

This project sits **above** those APIs. It does **not** compete with them,
replace them, or claim to know the chain better than they do. It **consumes
their outputs** (caller-supplied) and adds four things:

1. **Normalization** — map each source onto one 0–100 risk basis (0 = safe /
   low risk, 100 = max risk)
2. **Construct grouping** — partition sources by *what they actually measure*,
   and average only within a group
3. **Contradiction detection** — flag when sources that were asked the same
   question give different answers
4. **Decision confidence + audit** — how much to trust the result, and why

```
  [ Risk API A ] [ Risk API B ] [ Risk API C ]  ...  (caller fetches)
           \           |           /
            v          v          v
      adapters → normalize → group by construct → contradict
                                → confidence → audit
                              (this layer)
```

---

## The construct rule

This is the part that is load-bearing, so it gets its own section.

**A construct is what a source actually measures.** `authority_control` is
"what can the issuer still do to you". `tradability` is "can you sell right
now". `liquidity_depth` is "how much does selling move the price".
`carry_cost` is "what does holding this cost". Six vendors can all return a
number between 0 and 100 and still be answering six different questions.

When they are, **averaging them is not a noisy estimate of one truth — it is a
category error**, and no amount of extra sources or cleverer weighting fixes
it. Ethereum USDT is the clean case: its issuer genuinely can mint, pause and
blacklist, and it genuinely trades fine. `69` and `1` are both correct. `32` is
not a compromise between them; it is a number about nothing.

So the rule:

| Situation | What happens |
| --- | --- |
| All usable sources share one construct | Weighted mean → `composite`, `verdict` band |
| Usable sources span several constructs | **No composite.** `verdict = "not_comparable"`, read `constructs[]` |
| Spread ≥ 40 *within* one construct | `range` contradiction — this disagreement is real |
| Spread across *different* constructs | Nothing. They cannot contradict; the split is reported structurally |
| A fraud classifier fires while a peer reads safe | `hard_flag` — this one **does** cross constructs |
| A construct has zero usable sources | Confidence capped at `medium` — `unavailable` is not `safe` |

The blended number still exists as `blended_composite_unsafe`. A caller who
genuinely wants it can have it; the name is the warning.

**Why `carry_cost` is in this repo.** A layer that only ever answered "not
comparable" would be unfalsifiable — a refusal dressed as a judgment. Perp
funding is the control case: five venues, one construct, five different
numbers, all answering *the same* question. That spread averages legally and is
reported as a genuine contradiction. Having both cases in one engine is what
makes the rule mean something.

**Sources with no declared construct behave exactly as before** — one group,
one composite. Adopting the rule is opt-in per adapter.

---

## Why not "just one risk API"?

| Approach | Gap |
| --- | --- |
| Single vendor score | Silent failure when that vendor is wrong or down |
| Ad-hoc agent prompt over raw JSON | Non-repeatable; no shared basis across runs |
| Blend several vendors into one number | Hides both facts when the vendors measured different things |
| Homegrown oracle that re-does on-chain DD | Competes with specialists; huge surface; no PMF for a thin library |

---

## Two surfaces

| Surface | Status | Entry |
| --- | --- | --- |
| **Decision-confidence (meta)** | Shipped | `build_report` / `group_by_construct` in `src/decision_confidence.py` |
| **Library (token instance)** | Shipped | `score_token` / `TokenInputs` in `src/normalize.py` |
| **Real vendor adapters** | Shipped — 4 registered, no API keys | `src/adapters/` |
| **MCP server** | Shipped (reference impl) | 2 tools in `src/mcp_server.py` |
| **Calibration** | Harness shipped **per construct**, never run on real labels | `tools/calibrate.py` — no labelled data in hand |

Dependencies: the core library is **pure standard library**. Only the MCP
server needs an extra (`pip install -e ".[mcp]"`).

Not built on purpose: HTTP fetching inside the library, auth, multi-tenancy.
The library holds no credentials and reaches nothing; those are host concerns,
and inventing them here would be scope theatre. Reasoning in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## What the real run actually shows

Ethereum USDT, three real key-free vendors, replayed from captures:

```
source                    risk  status      construct
goplus                      69  ok          authority_control     mint, pause, blacklist, balance-change
goplus:concentration        45  ok          holder_concentration  top-1 holder 19.30%
goplus:tradability          15  ok          tradability           clean on is_honeypot, cannot_buy;
                                                                  cannot_sell_all absent — unknown, not safe
honeypot_is                  1  ok          tradability           summary.riskLevel=1
dexscreener                  -  unavailable liquidity_depth       no pairs on chain 'ethereum'

construct               risk  verdict       sources  spread
authority_control         69  high          1/1
holder_concentration      45  moderate      1/1
tradability                8  low           2/2      14
liquidity_depth            -  unknown       0/1   └─ dexscreener: unavailable

composite : none — these constructs measure different things.
            (blended_composite_unsafe=32 exists only for callers who insist)
confidence: medium
```

Four things in that output are the whole argument:

1. **The sources differ by 68 points and neither is wrong.** USDT genuinely can
   be frozen and minted by its issuer, and it genuinely trades fine. A blended
   score would have hidden both facts — and the earlier version of this library
   *did* blend them, then apologised for it in a footnote.
2. **`unavailable` is not `safe`.** DexScreener's token endpoint is keyed by
   address rather than by (chain, address): querying the Ethereum USDT address
   returns **PulseChain** pools, the same address on a fork chain. Taking
   `pairs[0]` — or even `max(liquidity)` — reports six figures of liquidity for
   the largest stablecoin in existence. The adapter refuses to guess, the blind
   construct stays in the table, and it caps confidence.
3. **Two vendors landed in the same group, and that is the point.** GoPlus and
   honeypot.is both simulate a buy and a sell, so they are comparable and the
   engine compares them: one group, `2/2` sources, spread 14. Here they agree.
   When they do not, that gap is a `range` contradiction — a real one, unlike
   the 68-point gap above.
4. **Confidence is about evidence, not about the verdict.** Reliable sources
   covering four constructs are *strong* evidence and *still* have no single
   composite. Conflating those two things is the mistake this layer exists to
   avoid, so `construct_mismatch` is `info` severity and does not lower
   confidence — only the blind construct does.

None of this says USDT is unsafe. It says the sources answered four different
questions, and averaging them into one number is the failure this layer exists
to prevent.

---

## Vendors with a dedicated adapter

No API keys for any of them. Adapters are pure functions of `(subject, raw)` —
**the caller fetches**.

| Vendor | Construct(s) | Key needed |
| --- | --- | --- |
| [GoPlus Token Security](https://docs.gopluslabs.io/reference/api-overview) | `authority_control`, `holder_concentration`, `tradability` | no |
| [honeypot.is v2](https://honeypot.is/) | `tradability` | no |
| [DexScreener](https://docs.dexscreener.com/api/reference) | `liquidity_depth` | no |
| Perp funding (any source) | `carry_cost` — **one observation per venue** | no |

`examples/live_multi_source.py` is the **only** file in this repo that touches
the network. Real captures from 2026-07-26 are frozen in `tests/fixtures/`, so
the tests and the `--offline` walkthrough never depend on third-party services
staying up.

Anything not listed still works — it falls back to shape recognition
(`{"fraud_probability": …}`, `{"tier": …}`, `{"score": …, "scale": …}`) and the
observation says so in its note. Unlisted sources carry no construct, so they
join the `undeclared` group.

---

## Native instance: token risk scoring

The same methodology was first applied to **heterogeneous token-risk inputs**
(holder concentration, contract authority, pool size, holder base, funding
extremity). That instance remains fully supported and is a stable public API.

> Note the tension, stated rather than hidden: `normalize.score_funding`
> collapses every venue into one extremity score *before* any meta-layer sees
> it — the same mistake the construct rule exists to prevent, committed inside
> this package. It stays because that module is a frozen public API. The
> `carry_cost` adapter is the corrected version.

### Two paths

**Path A — template hit (fast, no data).** Name a token covered by the built-in
snapshot table → a qualitative baseline plus the date it was captured.
Explicitly *a baseline, not live truth*.

**Path B — caller-supplied (precise, data-bound).** Supply any subset of the
risk inputs → each dimension normalized to 0–100, extremes flagged, combined.
**Missing dimensions are never guessed** — they are marked unknown and lower
confidence.

If neither path has data, the framework does **not** invent a number: it
returns a default-deny "extreme until proven otherwise" and asks for inputs.

### Quick start

```python
from normalize import score_token, TokenInputs

print(score_token("BTC").to_dict())                      # Path A

v = score_token("PEPE", TokenInputs(                     # Path B
    top10_pct=62.0, pool_usd=800_000,
    mint_authority="retained", holder_count=42_000,
    funding_rates=[{"venue": "binance", "rate": 0.0008},
                   {"venue": "hyperliquid", "rate": -0.0004}],
))
print(v.verdict, v.composite, v.confidence, v.red_flags)
# high 70 high ['mint/freeze authority retained by deployer']
```

### The five dimensions

Each normalized to 0–100. Thresholds are **rough heuristics, not calibrated**.

| Dimension | Weight | Key input | Notes |
| --- | --- | --- | --- |
| Concentration | 0.30 | top-10 / top-1 holder % | highest weight — biggest rug vector; top-1 > 50% is a red flag |
| Contract | 0.25 | mint/freeze authority, source verified, honeypot | retained authority / honeypot = hard red flag |
| Liquidity | 0.20 | main pool size (USD) | < 100K flagged thin |
| Holders | 0.15 | total holder count | thin base = riskier |
| Funding | 0.10 | per-venue funding rates | extremity signal, **not** free money |

Weights are re-normalized at runtime over whichever dimensions have data.

**Composite bands:** `< 30` low · `30–55` moderate · `55–80` high · `> 80` extreme.

### Funding-rate annualization

```
annualizedPct ≈ rate × (24 / intervalHours) × 365 × 100
```

Venue interval defaults: Binance / OKX / Gate = 8h, Hyperliquid / dYdX = 1h.
Override per-rate with `intervalHours`. **This is not cosmetic:** the same raw
`0.0008` is 87.6% annualized on Binance and 700.8% on Hyperliquid. Comparing
the raw numbers would call two venues in agreement when they are 613 points
apart.

---

## Decision-confidence surface (meta-layer)

Treat each external risk API as one **source dimension**:

| Source class (examples) | Typical raw shape | Normalize toward |
| --- | --- | --- |
| On-chain risk score APIs | 0–100 safety or risk score | 0–100 risk (flip if vendor is "safety") |
| Fraud / scam prediction | probability or label | 0–100 risk |
| KYT / compliance-style tiers | LOW / MED / HIGH | 0–100 risk |
| Perp funding | per-interval rate per venue | 0–100 risk (extremity, annualized) |

Then: **normalize → group by construct → detect contradictions within a group
→ synthesize confidence → emit audit trail.**

### Local mock demo (no network)

```bash
python examples/decision_confidence_demo.py
python -m unittest discover tests
```

Three fictional providers emit heterogeneous payloads; the demo normalizes
them, runs the contradiction rules, and prints a report for agreeing and for
conflicting sources. The second case is the point: the composite alone reads
`40 / moderate`, but one source calls it fraud while two call it safe — so
confidence collapses to `low` and the disagreement is reported explicitly
rather than averaged away.

### MCP server

```bash
pip install -e ".[mcp]"
python src/mcp_server.py          # stdio; or: decision-confidence-mcp
```

Two tools:

- `list_supported_vendors()` → `{vendor_id: description}` for every registered
  adapter.
- `decision_confidence(subject, sources, weights?)` → the full report:
  observations, **per-construct groups**, composite (or `null` with
  `verdict = "not_comparable"`), confidence, contradictions, audit.

Each entry in `sources` is
`{"source_id": ..., "raw": <vendor payload as received>, "vendor": <optional>}`.

**The host keeps what the host should keep**: API keys, HTTP, rate limits,
caching, PII policy. The tool is a pure transform of what it is given.

---

## Why this layer should exist

**The gap is structural, not a market-size claim.** Agents increasingly call
several external risk sources. Those sources disagree in scale and, often, in
*substance*. Today an agent either trusts one vendor (silent failure when that
vendor is wrong or down) or eyeballs raw JSON through an LLM (non-repeatable
across runs). Neither leaves anything auditable afterwards.

**What already exists, and where this differs.** Cross-source disagreement is
not an unexplored idea, and pretending otherwise would be the same dishonesty
this library is built against:

| Prior work | What it does | Why it is not this |
| --- | --- | --- |
| [internet-context-mcp](https://github.com/vivekvar-dl/internet-context-mcp) | NLI-based cross-source agreement / contradiction over **web text** | Operates on natural language; its own README notes it misses hedged prose |
| [gigaxity-deep-research](https://github.com/yoloshii/gigaxity-deep-research) | PaperQA2-style disagreement surfacing over **research sources** | Flags conflicting claims in literature, not vendor scores |
| snowdrop-mcp `crowd_sourced_risk_audit` | Confidence-weighted consensus + outlier detection over assessors | Assumes every assessor is already on one 1–10 scale — normalization is skipped, and there is no notion of assessors measuring *different things* |

All three ask "do these sources agree?". This one asks the question that comes
first: **are these sources even answering the same question?** That is the
construct rule, and as far as we can find, nothing else in this space has it.
If you know of prior art that does, open an issue — it belongs in this table.

**No risk vendor will close this gap.** A vendor's product is *its own* score;
it has no incentive to ship "our competitor disagrees with us, and here is how
much to trust the combination."

**Monetization: candidate paths, none validated.**

1. Open-source core plus a hosted audit/attestation service — the audit trail
   is the part teams cannot casually self-host.
2. Per-call MCP tool for agent runtimes that need decision provenance.
3. Compliance-adjacent: decision audit trails as evidence for teams that must
   justify automated actions.

No revenue, no users, no validated willingness to pay. This is a **primitive**,
and its first job is to be correct and reusable, not to bill.

**What would prove this wrong:**

- A major risk vendor ships native cross-vendor confidence *and* construct-aware
  reporting.
- Agent frameworks absorb this as a built-in utility.
- In practice agents call exactly one risk source and never hit the problem.
- Callers routinely reach for `blended_composite_unsafe` anyway — which would
  mean the market wants one number more than it wants a correct one.

---

## Honest limitations

- **Read-only analysis, not investment advice, not a safety guarantee, not a
  compliance certification.**
- **Meta-layer dependency:** decision quality is bounded by upstream API
  availability, honesty, coverage, and latency. Correlated sources (same
  underlying data) degrade both confidence and contradiction signals — this
  library does not invent missing upstream truth.
- **The construct taxonomy is a judgment call, not a standard.** Seven labels
  drawn from what four adapters happen to measure. Where two vendors sit on the
  boundary of one construct, whoever tags the adapter decides — and that
  decision changes whether a composite exists at all.
- **Thresholds and contradiction rules are rough heuristics**, not calibrated
  against any labeled dataset. `tools/calibrate.py` is the instrument for
  fixing that; **it has never been run against real labels**, and running it on
  the bundled synthetic sample proves nothing about accuracy. This is the
  largest open weakness in the project.
- **Most constructs cannot be honestly calibrated against rug-pull labels at
  all.** Labels are assembled from outcomes that already happened; payloads are
  captured today. A dead token trivially reads "cannot be sold" and "no
  liquidity", so `tradability` and `liquidity_depth` will score near-perfectly
  and the performance is pure label leakage. `authority_control` is the
  exception — whether the deployer kept mint/pause rights is a property of the
  contract and does not change when the project dies. `tools/calibrate.py`
  grades every construct on this axis and refuses to present a leaked number
  without the caveat attached. This is a judgement about which measurements
  survive a post-mortem, not a measurement itself; argue with it in an issue.
- **Caller-supplied only** — missing inputs are marked unknown, never guessed.
  The library performs **no** network I/O.
- Token **snapshot table** is **dated and qualitative** — fast triage, not live
  truth.
- The shipped EVM adapters cover **EVM tokens only**. Solana, addresses as
  subjects, and compliance/KYT vendors go through the generic fallback and
  therefore carry no construct.
- GoPlus contributes three of the five default observations, so it carries
  extra weight *within* its constructs unless the caller passes `weights`. It is
  also the only source in two of them, so `authority_control` and
  `holder_concentration` currently have no second opinion at all.
- The MCP server is a **reference implementation**. No auth, no multi-tenant
  isolation, no HTTP inside the library — deliberately.
- Fixtures are **snapshots**. Vendors change scoring and pair lists churn; a
  failing fixture test may be a refresh signal rather than a code bug.
- A general LLM with web access may see *more current* on-chain data than a
  sandboxed caller of this library. This project's edge is **repeatable,
  comparable, construct-honest verdicts** — not data freshness.

---

## License

MIT. See [LICENSE](LICENSE).
