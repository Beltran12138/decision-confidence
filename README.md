# decision-confidence

**Agent Decision Confidence** — a small, dependency-free framework that turns
**heterogeneous risk signals from multiple external sources** into **comparable
scores**, separates **disagreement that is factual** from **disagreement that is
definitional**, and returns a **confidence** label with an **audit trail**.

> Read-only. Pure Python standard library. No network, no on-chain reads, no
> execution. Fetching is the caller's job; the value is a *repeatable,
> comparable basis* — not data freshness.

### One question, three domains

**"Are these sources answering the same question?"**

Most tooling asks whether independent sources *agree*. This one asks whether they are
measuring the same thing at all — two sources can differ by 68 points and both be right.

The same discount applies on a second axis. Across sources, several vendors
answering one question are worth fewer independent reads than the invoice says.
Across **time**, a backtest that ran mostly before a model's knowledge cutoff is
worth fewer independent months than the calendar says — and that one is pure
arithmetic, available before any performance number is computed.
See [the second axis](#the-second-axis-time), or run
`python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06`.

The same five failure families keep surfacing in four unrelated domains — and a sixth
has appeared in one of them. This repo is the **third-party-vendor** instance.

| repo | domain | the question it asks |
|---|---|---|
| **decision-confidence** ← you are here | third-party risk vendors | do these vendors answer the same question? |
| [assay](https://github.com/Beltran12138/assay) | LLM-as-judge | does this metric measure what its name claims? |
| [prophetmap](https://github.com/Beltran12138/prophetmap) | self-built equity scoring | does my own score survive my own rule? |
| `ai-game-bench` *(local, not published)* | multi-agent game testbed | can this metric detect a failure I injected on purpose? |

The argument → [`docs/same-question.md`](./docs/same-question.md) ·
evidence table → [`docs/failure-families.md`](./docs/failure-families.md) ·
the time axis, worked through → [`docs/shorter-than-you-think.md`](./docs/shorter-than-you-think.md)

---

## The thirty-second version

Three commands, no keys, no setup beyond Python ≥ 3.8:

```bash
python examples/two_kinds_of_disagreement.py          # the whole argument
python examples/live_multi_source.py --offline usdt   # three real vendors, replayed
python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06   # the time axis
```

The first prints these two blocks from the same engine:

```
CASE A — definitional disagreement (five constructs)
real vendor payloads, captured 2026-07-26
construct               risk  verdict       sources  spread
authority_control         69  high          1/2
holder_concentration      45  moderate      1/1
holder_base               20  low           2/2      0
liquidity_depth           10  low           1/2
tradability                8  low           2/2      14
composite : none  (blended_composite_unsafe=26 — a category error, exposed under a name that says so)
confidence: high

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
| Spread ≥ 40 *within* one construct | `range` contradiction — see the caveat on method below |
| Spread across *different* constructs | Nothing. They cannot contradict; the split is reported structurally |
| A fraud classifier fires while a peer reads safe | `hard_flag` — this one **does** cross constructs |
| A construct has zero usable sources | Confidence capped at `medium` — `unavailable` is not `safe` |
| The backtest behind the call has no usable holdout | Confidence floored at `low` — see [the second axis](#the-second-axis-time) |

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

## The second axis: time

> The argument at length, with all three numbers worked through →
> [**Your backtest is shorter than you think**](./docs/shorter-than-you-think.md)

Everything above discounts evidence **across sources**. The same discount
applies **across time**, and the arithmetic is simpler than anyone expects.

A model with a knowledge cutoff has read what happened before that date. A
backtest that runs mostly before the cutoff therefore does not test whether a
strategy works — it tests whether the model remembers. A 2020-01 to 2025-06
backtest against an October 2024 cutoff is **58 of 66 months open book**.

```
python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06

回测区间构成
  总长                   66 个月
  开卷（模型已见）       58 个月     87.9%
  干净（可用于检验）      8 个月     12.1%

干净区间够不够支撑一个推断
  所需长度               48 个月    （t ≈ SR·√T，SR=1 时 T=(2/1)² 年）
  实有                    8 个月       17% of requirement
```

**The share alone does not finish the argument.** "86% was open book" invites
the reply "fine, I will trust the other 14%". The other 14% is eight months,
and eight months of monthly returns cannot distinguish a Sharpe of 1.0 from
zero at any conventional bar. So a backtest fails here in two different ways,
and they call for different responses:

| verdict | meaning | the correct reading |
| --- | --- | --- |
| `no_holdout` | nothing is out of sample | the result is recall, not performance |
| `underpowered` | some is, but too little | **neither** "it works" nor "it does not" — this backtest has no power to tell you |
| `sufficient` | the clean remainder clears the bar | length is no longer the constraint; that is all it means |

Length comes from t ≈ SR·√T (Lo 2002), so T = (t/SR)² years. The quadratic is
the part nobody has internalised — **halving the Sharpe you claim to be testing
for quadruples the sample you need**:

| target Sharpe | clean months required at t ≥ 2 |
| --- | --- |
| 2.0 | 12 |
| 1.0 | 48 |
| 0.5 | 192 |

### The other way clean months get spent

A clean holdout is necessary, not sufficient. If several variants were screened
and the best one kept, the survivor's t-statistic is the **maximum of many
draws**, not one draw. The bar it has to clear is higher, so the sample needed
to clear it is larger — quadratically.

`selection_penalty` makes that a number instead of a footnote. Bonferroni, with
α derived from the caller's own `t_threshold` rather than fixed at 0.05, which
is what keeps `trials=1` an exact identity:

| variants screened | corrected bar | clean months required (SR 1.0) |
| ---: | ---: | ---: |
| 1 | t ≥ 2.00 | 48 |
| 5 | t ≥ 2.61 | 82 |
| 10 | t ≥ 2.84 | **97** |
| 20 | t ≥ 3.05 | 112 |
| 50 | t ≥ 3.32 | 133 |

**Ten variants roughly doubles the clean sample you need.** Seventeen is where
the corrected bar reaches the t > 3.0 that Harvey, Liu and Zhu argue for — a
useful check that the scale is not eccentric.

**The count is discounted the same way sources and months are.** Fifty
parameter settings of one strategy are not fifty independent tests, any more
than five vendors reading one on-chain field are five independent reads. Pass
`effective_trials` to take that discount — but it must be **measured, not
asserted**, and `tools/neff.py` is already the instrument: run it on the
variants' return series and it returns the same Kish quantity. Omit it and the
full count is charged, which over-penalises. That asymmetry is deliberate.

**And the part with no arithmetic in it.** Declaring no trials is not a neutral
default — it is the strongest claim available, that the strategy was specified
before anyone looked. So it is printed as such on every run that omits it:

```
变体筛选校正
  ⚠ 未申报变体筛选次数，按「一次成型」处理。这不是中性默认，
  而是断言策略在看数据之前就定好了。自报次数还系统性偏低——看一眼就放
  弃的那个变体，通常不会被算进去。
```

The last sentence is the one that limits the whole feature. A self-reported
count runs low, and nothing here can detect that. **This turns an unobservable
quantity into a required parameter; the default is the assertion, not the
absence of one.**

```bash
python tools/window.py --cutoff 2015-01 --start 2020-01 --end 2025-06 --trials 20
#   66 clean months, and still underpowered — the bar moved to t ≥ 3.05
```

### The third axis: the inputs

A clean window says the model had not read the answer. It does not say the agent
is reading the *question*. `counterfactual.py` asks that one: change a fact, see
whether the conclusion follows.

Published work has measured it and the number is worse than people expect —
perturbing key market inputs left the worst model's predictions unchanged
**82.13%** of the time ([Li et al., *Profit Mirage*](https://arxiv.org/abs/2510.07920)).

**But a flip rate is not a verdict**, and that is the increment here.
Perturbations come in two kinds with opposite expectations:

| kind | example | the conclusion should |
| --- | --- | --- |
| `material` | good news → bad, policy reversed, a beat → a miss | **move** |
| `cosmetic` | renamed ticker, shifted dates, rescaled magnitudes | **not move** |

Averaging those into a single "82% unchanged" discards the only part that
discriminates: an agent that flips on *everything* scores the same as one that
reads carefully. So the test is **material against the agent's own cosmetic
rate** — one-sided Fisher, exact, because these counts are single digits. Not
against 0.5 and not against an assumed rate: how often a reading agent *should*
flip is unknowable in advance, but its response to meaningless changes is
measurable and is the right baseline. Same move `carry_cost` makes on the
sources axis.

| verdict | meaning |
| --- | --- |
| `no_control` | only one kind supplied — a missing control, not a result |
| `no_power` | even a perfect split cannot clear α at this size |
| `memorised` | no cosmetic flip, and material did not do significantly better |
| `unstable` | a cosmetic change moved it at least once |
| `responsive` | material significantly above cosmetic — and that is *all* it says |

⭐ **Six perturbations is the floor.** Three material and three cosmetic, split
perfectly, give p = 0.0500 exactly; below that no result of any shape can clear
α = 0.05. Same kind of floor as `months_for_power` — it assumes the cleanest
outcome you could possibly get.

**The honest limit**: whether a conclusion "flipped", and whether a change was
material or cosmetic, are both supplied by the caller and unverifiable here.
Mislabel a material change as cosmetic and the audit passes. That is an escape
hatch of exactly the same kind as an undeclared trial count, and all the library
can do is name it on every run.

```bash
python tools/perturb.py --material 5/6 --cosmetic 0/6
#   one-sided Fisher p = 0.0076  ->  responsive
python tools/perturb.py --material 2/2 --cosmetic 0/2
#   best possible here p = 0.1667  <- already the best this size can do  ->  no_power
```

```python
from counterfactual import Perturbation, perturbation_audit, remedies

runs = [Perturbation("material", "beat -> miss", flipped=True), ...]
r = perturbation_audit(runs)
r.verdict     # 'responsive' | 'memorised' | 'unstable' | 'no_control' | 'no_power'
remedies(r)   # dispatched on what is actually missing
```

The MCP tool is `counterfactual_audit`, and its description carries the
instruction that keeps it honest: **you run the perturbations first**, both kinds
are required, and a reworded answer is not a flip.

`docs/index.html` carries this axis too, and takes the runs one at a time rather
than as two ratios. That is not a nicer form of the same input: the page is the
only surface that can put the perturbation list back on screen next to the
verdict, and the remedy every run ends with — *check that a sceptic reading your
list would classify them the same way* — is an empty instruction anywhere the
list cannot be seen.

**Where it sits, and where it deliberately does not.** It is a separate module
(`src/effective_window.py`) because the inputs share nothing: one side takes
vendor payloads, the other takes three dates. Merging them would be the exact
category error this library exists to catch. They meet only in
`DecisionReport.window`.

- It is **not** emitted as a `Contradiction`. Contradictions are disagreements
  between sources answering the same question; a knowledge window is not a
  source and disagrees with nothing. Filing it there to reuse the plumbing
  would repeat the mistake the construct rule refuses to make with scores.
- It never moves `verdict`. That is a statement about the subject's risk, and
  how a backtest was sliced says nothing about it.
- It **does** floor `confidence`, unconditionally. Ten agreeing sources do not
  make a period the model has already read informative, so there is no source
  count that repairs it.
- Omit the window and every existing caller behaves exactly as before. Absent
  is unknown, not clean.

**One convention, fixed in code because it moves the headline.** The cutoff
month counts as seen — a model whose knowledge ends in October 2024 has read
October 2024. The same configuration reads **87.9% inclusive and 86.4%
exclusive**, and a quoted share whose convention goes unstated is precisely
what this repo is about. `tests/test_effective_window.py` names both numbers.

```python
from decision_confidence import build_report, effective_window
from effective_window import remedies

w = effective_window("2024-10", "2020-01", "2025-06", target_sharpe=1.0, trials=20)
w.verdict            # 'underpowered'
w.effective_months   # 8, against months_required = 112 once screening is charged
remedies(w)          # what to do about it, dispatched on the cause

build_report("SUBJ", observations, window=w).confidence   # 'low'
```

Three entry points, one implementation: the library above, the CLI
`tools/window.py`, and the MCP tool `knowledge_window` for agents. The browser
copy in `docs/index.html` is a fourth — a deliberate reimplementation in JS so
the page needs no backend — and `tools/check_js_parity.py` diffs it against the
library on 28 numeric cases and 48 remedy texts, **verbatim**, because that copy
already drifted once. The page carries the perturbation axis on the same terms:
48 more combinations, and the p-values agree exactly rather than to a tolerance,
because both sides sum integer binomials.

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
| **Real vendor adapters** | Shipped — 4 registered, 8 observations, no API keys | `src/adapters/` |
| **MCP server** | Shipped (reference impl) | 4 tools in `src/mcp_server.py` — one per axis, plus a vendor lookup |
| **Knowledge window (time axis)** | Shipped — needs no labels and no price series | `effective_window` in `src/effective_window.py`; CLI `tools/window.py`; MCP tool `knowledge_window`; page `docs/index.html` |
| **Counterfactual audit (input axis)** | Shipped | `perturbation_audit` in `src/counterfactual.py`; CLI `tools/perturb.py`; MCP tool `counterfactual_audit`; page `docs/index.html` |
| **Calibration** | Harness shipped; **run on 406 real labels, produced no usable threshold** | `tools/calibrate.py` — see below |

Dependencies: the core library is **pure standard library**. Only the MCP
server needs an extra (`pip install -e ".[mcp]"`).

Output is **English by default**, with Chinese available (`--lang zh` on the CLI,
`lang="zh"` in the library and the MCP tool, a toggle on the page). The numbers
and the verdict are identical either way. Strings live in one table in
`src/messages.py`; the browser's copy is generated from it, and
`tools/check_js_parity.py` diffs the two entry by entry in **both** languages,
because a second language is a second place for them to drift.

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
goplus:holders              20  ok          holder_base           15,584,564 holders
honeypot_is                  1  ok          tradability           summary.riskLevel=1
honeypot_is:structure        -  unavailable authority_control     open-source, non-proxy — but cannot see
                                                                  mint/pause/freeze/blacklist rights
honeypot_is:liquidity       10  ok          liquidity_depth       routed pair Uniswap V3: WETH-USDT
                                                                  holds $85,542,448 — one pair, not the book
honeypot_is:holders         20  ok          holder_base           15,264,570 holders
dexscreener                  -  unavailable liquidity_depth       no pairs on chain 'ethereum'

construct               risk  verdict       sources  spread
authority_control         69  high          1/2   └─ honeypot_is:structure: unavailable
holder_concentration      45  moderate      1/1
holder_base               20  low           2/2      0
liquidity_depth           10  low           1/2   └─ dexscreener: unavailable
tradability                8  low           2/2      14

composite : none — these constructs measure different things.
            (blended_composite_unsafe=26 exists only for callers who insist)
confidence: high
```

Five things in that output are the whole argument:

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
   The next section is a case where they do not.
   Note also `liquidity_depth`: DexScreener returned nothing usable, and
   honeypot.is answered the construct anyway from the pair its simulation
   routed through. **A second source did not confirm the first — it replaced a
   blank.** That is why confidence reads `high` here and `medium` before the
   source was added.
4. **`holder_base` reads `2/2` with a spread of 0.** Both vendors read the same
   on-chain holder count — 15.58M and 15.26M, the same band. That is the shape
   of two sources that are not independent, and it is the baseline the other
   spreads are measured against.
5. **Confidence is about evidence, not about the verdict.** Reliable sources
   covering five constructs are *strong* evidence and *still* have no single
   composite. Conflating those two things is the mistake this layer exists to
   avoid, so `construct_mismatch` is `info` severity and does not lower
   confidence — only the blind construct does.

None of this says USDT is unsafe. It says the sources answered four different
questions, and averaging them into one number is the failure this layer exists
to prevent.

---

## And the case where one vendor is simply wrong

The USDT example shows two sources that are both right. This one shows what
only a comparison can catch.

`0x16939ef7…` on BSC is **Binance-Peg Tezos (XTZ)** — an official Binance
bridge token, labelled legitimate in the corpus.

```
goplus:tradability     5   ok   is_honeypot=0  cannot_buy=0  cannot_sell_all=0  tax 0/0
honeypot_is          100   ok   vendor verdict: HONEYPOT DETECTED;
                                basis: low_fail_rate(medium);
                                simulated through PancakeSwap V3: XTZ-ETH
```

One vendor says the token is clean. The other says **HONEYPOT DETECTED** at
`riskLevel 100`. They are answering the same question — both simulate a buy and
a sell — so this is a genuine contradiction, and the engine raises it as one.

Read the basis and the verdict comes apart. The entire case is a single
`low_fail_rate` flag whose own severity is **`medium`, index 12 out of 100**,
observed while routing through the **PancakeSwap V3 XTZ-ETH** pair — a thin
pool. Sells fail there because the pool is thin. That is a property of the
route, not of the token, and Binance is not running a honeypot.

Two things follow, and both changed the code:

- **The score is still reported as 100.** Second-guessing a vendor here would
  hide the disagreement rather than surface it; this layer reports what it was
  told. What it must also report is *why* — so the verdict, the flag with its
  severity, and the routed pair now travel in the note. A bare `100` is
  unauditable, and this is what unauditable costs.
- **Same construct does not mean same method.** Both vendors simulate, but
  through different pools, and that alone is enough to invert the conclusion.
  Construct equality makes two sources *comparable*; it does not make them
  interchangeable, and the spread between them is where the difference shows up.

This pattern — one vendor clean, the other at 100 — appears in **13% of the
subjects that have two tradability sources**. An agent trusting either vendor
alone gets a confident answer 13% of the time when the two available sources
flatly contradict each other.

---

## Vendors with a dedicated adapter

No API keys for any of them. Adapters are pure functions of `(subject, raw)` —
**the caller fetches**.

| Vendor | Construct(s) | Key needed |
| --- | --- | --- |
| [GoPlus Token Security](https://docs.gopluslabs.io/reference/api-overview) | `authority_control`, `holder_concentration`, `tradability`, `holder_base` | no |
| [honeypot.is v2](https://honeypot.is/) | `tradability`, `authority_control`*, `liquidity_depth`, `holder_base` | no |
| [DexScreener](https://docs.dexscreener.com/api/reference) | `liquidity_depth` | no |
| Perp funding (any source) | `carry_cost` — **one observation per venue** | no |

\* honeypot.is reports `authority_control` **only as a falsifier**: a structural
finding is scored, a clean structural check returns `unavailable`, because three
clean signals are not evidence about mint, pause or freeze rights it cannot see.

`examples/live_multi_source.py` is the only file in the library or its examples
that touches the network (`tools/capture_payloads.py` also does, but it is
calibration tooling, not part of the package). Real captures from 2026-07-26 are frozen in `tests/fixtures/`, so
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

Four tools — one per axis, plus a lookup:

- `decision_confidence(subject, sources, weights?)` → the full report across
  **sources**: observations, per-construct groups, composite (or `null` with
  `verdict = "not_comparable"`), confidence, contradictions, audit.
  Each entry in `sources` is
  `{"source_id": ..., "raw": <vendor payload as received>, "vendor": <optional>}`.
- `knowledge_window(cutoff, start, end, target_sharpe?, t_threshold?, trials?, effective_trials?)`
  → the same discount across **time**: months open book, months of clean
  sample, months an inference needs, `verdict`, and `remedies` — concrete
  actions dispatched on what actually caused the failure.
- `counterfactual_audit(perturbations, alpha?, lang?)` → the same discount across
  **inputs**. You run the perturbations; it scores the table. Each entry is
  `{"kind": "material"|"cosmetic", "detail": str, "flipped": bool}`.
- `list_supported_vendors()` → `{vendor_id: description}` for every registered
  adapter.

**The three axes are separate tools on purpose.** A subject, a backtest and an
agent's responsiveness are three different objects; folding the window into
`decision_confidence` would be the category error this library exists to catch,
and an agent scoring a token should not be asked for backtest dates. No answer
needs the others.

**A tool description is an interface, and one line of it is load-bearing.**
`knowledge_window` tells the model: *if you do not know how many variants were
screened, ask the user — do not omit it.* Omitting `trials` is not a neutral
default, it asserts the strategy was specified before anyone looked, and
without that instruction a model will quietly make that assertion on the user's
behalf. The description also states the two readings most likely to be
garbled — `underpowered` means "this backtest cannot tell you", **not** "the
strategy does not work"; `sufficient` means length stopped being the binding
constraint, **not** that anything was demonstrated. `tests/test_mcp_surface.py`
asserts those sentences are still present, because deleting them leaves a tool
that still works and still returns correct numbers.

**The host keeps what the host should keep**: API keys, HTTP, rate limits,
caching, PII policy. The tools are pure transforms of what they are given.

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

## What calibration actually found

`tools/calibrate.py` was run against **406 subjects from TM-RugPull**
(arXiv 2602.21529), balanced 203 scam / 203 legitimate, with GoPlus and
DexScreener payloads captured per subject. It produced **no usable threshold**,
and the reason is more useful than a number would have been.

**Nothing beat "flag everything."** With a 203/203 split, calling every subject
bad scores F1 0.684. The best any construct managed:

| construct | best F1 | at cut | leakage | availability skew |
| --- | --- | --- | --- | --- |
| liquidity_depth | 0.764 | 75 | severe | +7.4pp |
| holder_base | 0.764 | 50 | partial | +0.0pp |
| holder_concentration | 0.700 | 75 | partial | −16.0pp |
| tradability | 0.684 | **0** | severe | +7.4pp |
| authority_control | 0.684 | **0** | **clean** | +7.4pp |

A best cut of `0` is the degenerate solution. The two constructs that clear the
baseline by a real margin are both leaky — a dead token's pool *is* shallow, and
its holders *did* leave — so neither number is quotable. **The only
leakage-clean construct is still stuck at the degenerate solution.**

**And yet `authority_control` is measuring accurately.** At cut ≥ 70 it scores
**precision 1.000 with zero false positives** — no legitimate token in the
sample has authority risk that high. It just catches **3 of 200 scams**. The
instrument is sharp; it is pointed at something else.

Look at what the labels contain. HyperVerse, Fintoch, Safuu — Ponzi schemes
with open-source contracts, no honeypot flags, and over 100,000 holders each.
**The contract never misbehaved. The people did.** Meanwhile the legitimate
side is WBTC, ENS, Ampleforth — centralised by design, holding exactly the
admin rights the scanner is built to flag. On this sample `owner_change_balance`
and `is_proxy` are *more* common among the legitimate tokens.

So the finding is a construct mismatch, one level up:

> This library measures **what powers a contract grants its deployer**.
> TM-RugPull labels **whether a project eventually absconded** (its README says
> forensic evidence and *longevity criteria*). Those are two different
> constructs, and putting them in one precision/recall table is exactly the
> category error the library exists to catch — committed this time by the person
> doing the calibrating.

**The leak was not where it was predicted.** The `LEAKAGE` grades in
`calibrate.py` were written as predictions, and the run corrected the mechanism:
contamination is not in the scores, it is in **availability**.

```
construct                  bad w/ data   good w/ data      skew
liquidity_depth                  4.9%          61.6%      -56.7pp  !
holder_concentration            83.5%          99.5%      -16.0pp  ~
authority_control               98.5%          91.1%       +7.4pp
tradability                     99.5%          99.5%       +0.0pp
```

A dead token has no pool, so *whether a construct has data at all* carries the
label — and a threshold sweep cannot see it. Any pipeline that drops
unavailable sources silently inherits that 57-point skew. This is the
measurable form of "`unavailable` is not `safe`", and `calibrate.py` now
reports it directly.

**And it is fixable by adding a source.** Those numbers are from a run with one
source per construct. After honeypot.is began contributing `liquidity_depth`
from the pair its simulation routed through, the same measurement reads
**+7.4pp instead of −56.7pp**: DexScreener finds no pool for a dead token,
honeypot.is still reports the pair it traded against, and the construct stops
being blind precisely on the subjects where blindness correlated with the
label. So a second source does three separate jobs — cross-check the first,
answer what the first could not, and *drain the availability skew* — and only
the first of those is what "multiple sources" usually means.

Note the last row: `tradability` was predicted to leak severely and **did not**
(+0.0pp). GoPlus returns `is_honeypot=0` for these dead tokens rather than 1.
Whether that means "simulated fine" or "could not simulate, defaulted to 0" is
unresolved and is not assumed either way.

**What would make calibration work:** labels of *contract authority actually
abused* — mint attacks, pause-and-run, blacklist seizures — rather than
"project died". RPHunter (arXiv 2506.18398), which labels 645 incidents along
code *and* transaction dimensions, is the more likely fit. That is the next
attempt, and it may also fail.

---

## The one threshold that calibration did settle

`RANGE_SPREAD = 40` decides when two sources measuring one construct are
reported as contradicting each other. It needs no labels to calibrate: the
question is not "was this a scam" but "how far apart do two vendors asked the
same question normally land". `tools/agreement.py` measures that, and it was
run over **553 pairs across three constructs** from the same corpus.

| construct | pairs | median | p90 | 40 fires on | label gap | what a spread means here |
| --- | --- | --- | --- | --- | --- | --- |
| holder_base | 359 | **0** | 0 | 0.0% | 0.1 | the same number, twice — a baseline |
| tradability | 320 | 4 | **85** | 21.9% | **17.2** | same method, occasional inversion |
| liquidity_depth | 128 | 15 | 35 | 4.7% | 1.6 | related but different measurements |
| authority_control | 105 | 22 | 31 | 1.9% | 0.6 | same construct, unequal coverage |

Two numbers, read together, say what a spread on a construct *is*. The median
measures how far apart the **methods** sit; the label gap measures whether the
leftover variation tracks the **subject**. `holder_base` exists in this table to
anchor the first: both vendors read the same on-chain holder count, 87% of pairs
agree within 1%, and the median spread is 0. That is what zero method difference
looks like — so a median of 22 on `authority_control` is not noise, it is the
distance between reading thirteen authority flags and reading four.

**40 holds up, for four different reasons.** `tradability`'s distribution is
bimodal — 62.6% of pairs sit at 0–4, the 20–39 band is nearly empty, and 21.9%
sit above 40. The cut lands in the trough, and moving it anywhere from 20 to 40
changes the firing rate by three points. On the other two the pairs cluster
around a *systematic offset* (median 22 and 15) and 40 sits above it, firing
only on genuine outliers. Different shapes, same defensible cut. That number
started as a guess; it now has 553 observations behind it.

**But the run also weakened a claim this README was making.** "A spread inside
one construct is a factual disagreement about the subject" — measured, that is
true of **one construct out of three**.

Compare bad and good subjects. On `tradability` the spread means differ by
17.2: scams really do make the two simulators disagree more. On
`liquidity_depth` and `authority_control` they differ by 1.6 and 0.6 — the
distributions are the same for scams and for blue chips, so the spread is not
telling you about the token at all. It is telling you that GoPlus reads
thirteen authority flags while honeypot.is reads four, and that DexScreener
looks across every pool while honeypot.is looks at the one its simulation
routed through.

So there is a second question underneath the first:

> **Are these sources answering the same question?** — the construct rule.
> **Are they answering it the same way?** — the method question, which
> construct equality does not settle.

A persistent, subject-independent offset between two sources on one construct
is a method difference wearing the clothes of a disagreement. The test is
cheap and needs no labels: **if the spread distribution is the same for known-
good and known-bad subjects, the spread is about the vendors.**

This is not patched over in code, because there is no honest way to hardcode
it — the offset belongs to a *pair* of vendors, not to a construct, and it
changes the moment someone swaps a source. `tools/agreement.py` is the
instrument; run it whenever you add a vendor, and read the last block of its
output before trusting a `range` contradiction on a new construct.

---

## Case study: prophetmap

The rules in this repository have been applied to a live scoring engine —
[prophetmap](https://github.com/Beltran12138/prophetmap), a public US-equity
funnel maintained by the same author. It is the first thing this library was
pointed at, and the only case whose audit is published.

**Stated plainly: this is the author auditing his own project, not an
independent adoption.** It is evidence that the rules find something when
applied, and evidence of nothing about demand.

What the audit found, before any return was computed:

| defect | measured |
|---|---|
| membership look-ahead | all 87 roster members carry an `addedDate` *later* than the scoring start |
| forward re-scoring | **39** in-window edits to fields that decide basket membership |
| survivorship | a downgraded ticker leaves the basket rather than being carried at its loss |

None of the three makes the program fail. All three make the number look
better.

The engine has since been frozen — roster pinned, basket rule written down
before the window opens, lock running to 2027-08-17 — and the first reading
under those rules put the author's own selected basket **last of four**:
cumulative **−2.45%** against −0.95% for the whole universe, paired
**t = −1.14, n = 9, not significant**. It is published in that repository's
changelog in the same words it would have carried had the sign been positive.

### Why the two repositories stay separate

This library **measures**; prophetmap is **measured**. Folding one into the
other would not simplify anything — it would destroy the property that makes
the reading worth reading.

More concretely: prophetmap's integrity check asks git whether the frozen
roster still has exactly one commit and a clean worktree. **The anchor is that
repository's own history.** Moving the file, or retiring the repository, ends
the freeze — during a lock the author wrote and has to sit out. A
pre-registration the author can dissolve by reorganising his folders is not
one.

The division of labour follows from that:

- **Here** — diagnosis. Given the dates, the trial count and the sources,
  what is this evidence worth? Nothing is enforced; the page will tell you
  the honest answer and then let you ignore it.
- **There** — enforcement. A pre-registered rule is checked before the run,
  and a violation exits non-zero and is recorded as *a test that failed to
  run* rather than yielding a number.

Diagnosis without enforcement gets ignored. Enforcement without diagnosis has
nothing to enforce.

---

## Honest limitations

- **Read-only analysis, not investment advice, not a safety guarantee, not a
  compliance certification.**
- **Meta-layer dependency:** decision quality is bounded by upstream API
  availability, honesty, coverage, and latency. Correlated sources (same
  underlying data) degrade both confidence and contradiction signals — this
  library does not invent missing upstream truth.
- **The construct taxonomy is a judgment call, not a standard.** Eight labels
  drawn from what four adapters happen to measure. Where two vendors sit on the
  boundary of one construct, whoever tags the adapter decides — and that
  decision changes whether a composite exists at all.
- **Thresholds and contradiction rules are rough heuristics, and the first
  attempt to calibrate them failed to produce any.** See below — the failure is
  informative, and it is not the kind that a bigger sample fixes.
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
- **The length requirement on the time axis assumes i.i.d. returns.** t ≈ SR·√T
  is Lo's approximation; monthly returns are typically positively
  autocorrelated, which inflates the naive t. The months it asks for are a
  **floor** — the real requirement is longer, never shorter.
- **The screening correction turns an unobservable quantity into a required
  parameter.** `trials` is self-reported, and self-reports run low — nobody
  counts the variant they glanced at and abandoned. The library cannot detect
  an understated count; all it can do is refuse to treat silence as zero, which
  is why an undeclared run says so on every line of output.
- **Bonferroni assumes the trials are independent** and controls the
  family-wise error rate, which is stricter than controlling the false
  discovery rate. Correlated variants make it conservative — that is what
  `effective_trials` is for, and it must be measured (`tools/neff.py`) rather
  than asserted, because a caller who may set it freely has been handed an
  escape hatch rather than a correction.
- **A clean window is a necessary condition, not evidence of anything.**
  `sufficient` says only that length has stopped being the binding constraint.
  It says nothing about whether the strategy works.

---

## License

MIT. See [LICENSE](LICENSE).
