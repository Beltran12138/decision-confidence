# Six failure families

*Cross-domain evidence for one question: **are these sources answering the same question?***

Most tooling asks whether independent sources **agree**. This document is about a
prior question — whether they are measuring the same thing at all. Two sources can
differ by 68 points and both be right.

Five of these families keep surfacing in four unrelated domains. They were not
designed as a taxonomy; each was found the hard way, in one domain, and only later
recognised in the others. A sixth has so far appeared in **one** domain, and is
listed on the same logic that makes the table useful at all: a family with one
instance is a prediction about where to look next, not a finding.

| domain | repo | what it scores |
|---|---|---|
| third-party risk vendors | [decision-confidence](https://github.com/Beltran12138/decision-confidence) | contract/token risk from multiple paid and free APIs |
| LLM-as-judge | [assay](https://github.com/Beltran12138/assay) | answer quality from an LLM evaluator |
| self-built equity scoring | [prophetmap](https://github.com/Beltran12138/prophetmap) | a hand-rolled 5-dimension screen over ~87 tickers |
| multi-agent game testbed | `ai-game-bench` — **local experiment, no public repo** | whether an LLM negotiator defected, from rule-based classification of game logs |

The fourth column is a set of local scripts, not a published project. It is cited
here because it is the only one of the four that can **manufacture** a failure with
a known label — the other three can only find failures in data someone else
produced. Its results are quoted, not offered for reuse.

---

## The table

### 1. Absence disguised as data

A source returns a number when it means *"I could not measure this."* Downstream,
the difference is invisible: `0` and `unknown` have the same shape.

| domain | instance |
|---|---|
| vendors | `is_honeypot=0` — unclear whether the simulation ran and passed, or never ran. `holder_count=0` while a second vendor reports 17,543. A top-1 holder share of `4.6e30 %`, the arithmetic result of `balance / totalSupply` after supply was burned to zero. All three were re-classified as `unavailable`. |
| judge | A judge returned `" 0 </think> 0.7"`. `parseFloat` read it as **0**. The default value in the parser *is* the fabrication mechanism: it converts "measurement failed" into "measurement succeeded and the answer is zero." Left unfixed, it would have produced a clean, large, literature-consistent — and entirely false — headline number. |
| equity | `forward P/E < 0 ⇒ pricing score 5` structurally locks every loss-making name outside the gate. A vendor-precomputed `pegRatio` stayed byte-identical across a week in which **22 of 49** names moved more than 5% — a stale value wearing the costume of a fresh measurement. |
| game | A four-way defection classifier reported `plan_failure = 0%` across 120 games, which read as "these agents do what they said they would." The environment had no wait action and a 6-turn horizon: the category was **structurally unreachable**. The metric was not measuring zero, it was measuring nothing. |

**Rule of thumb:** any pipeline that silently drops unavailable sources inherits
whatever bias the availability itself carries (see family 4).

The game instance is the cheapest to catch and the easiest to miss, because a `0`
from an impossible category and a `0` from a real absence are the same character.
The only reliable separator is a synthetic positive control: inject a case with the
label already known, and fail the run if the metric cannot find it.

### 2. Same name, different construct

Two measurements share a label and answer different questions. Averaging them is a
category error, not a compromise.

| domain | instance |
|---|---|
| vendors | On USDT, one vendor scores **69** and another **1** — a 68-point gap in which *both are correct*. The first measures how much power the issuer's contract grants (`authority_control`); the second measures whether the token can currently be traded (`tradability`). There is no number between them that means anything. |
| judge | A metric named `correctness` reported **0.00** for an answer that was entirely correct. It was measuring string overlap. Renaming it is the substance of the fix — the construct was extracted as `fact_token_presence`, and a test now proves it still cannot see a fabrication in which all the expected tokens happen to appear. |
| equity | One field value, `moatLocks: "licensing"`, was used for two **opposite** situations: companies that *collect* licence rent and companies that *hold* a licence. Only the second is vulnerable to a regulator widening the gate. Separately, a PEG of 36.41 reads as "expensive" on the same scale where it actually means "not measurable" — the denominator was approaching zero. |
| game | One counter, `broken_floor`, summed three different events: deliberately breaking a stated commitment, legitimate bargaining bluff (which the game's own rules invite), and simply failing to execute a stated plan. Published deception benchmarks report the same aggregate as a deception rate. The three have opposite implications for whether the model is misaligned or merely bad at following through. |

### 3. Method disagreement wearing the costume of factual disagreement

Same construct, different instrument. The spread is a property of the vendor pair,
not of the subject.

| domain | instance |
|---|---|
| vendors | On a bridged, officially-issued token, one vendor reports risk **5** and another **100**. The 100 rests on a single medium-severity flag raised while routing through a thin third-party pool — a property of the route, not of the token. This pattern accounts for **13%** of two-source samples in that construct. Related: one vendor inspects 13 permission flags, another inspects 4; the systematic offset that produces is not evidence about the token. |
| judge | Three judges scoring one answer gave **0.00 / 0.95 / 1.00**. Adding a single sentence to the rubric — stating whether an example consistent with the context counts as grounded — moved full-agreement from **53% → 83%** and collapsed that item to unanimous 1.00. **Majority voting fails here**: the minority judge was not wrong, it was answering a different question. |
| equity | A 6-month momentum field compares endpoints only, so "declined all year" and "rose 180% then gave it back" both print ≈ −20%. A thesis was briefly revised on the strength of that number before the price path was actually read. |
| game | Reserve values were drawn from a deterministic sequence, so small runs always used the same prefix of it. A headline effect — information visibility reduces breakdowns — survived two rounds of replication before randomised draws across 5 seeds put it at **0 ± 5.5 points**, with only 1 of 5 seeds agreeing in sign. The effect was a property of the draw order, not of the condition. Four separate conclusions from this testbed died the same way. |

**Cheap diagnostic, no labels required:** if the spread distribution is the same on
known-good and known-bad samples, the spread is about the vendors, not the subject.
Deliberately **not** hard-coded — an offset belongs to a *pair* of vendors and
expires when either is swapped.

### 4. Availability skew

Which subjects have data is itself correlated with the answer. A threshold sweep
cannot see this, because it only looks at the rows that have values.

| domain | instance |
|---|---|
| vendors | Across 406 labelled tokens, liquidity data existed for **4.9%** of the bad sample and **61.6%** of the good one — a **−56.7 point** skew. Dead tokens have no pool. Adding a second source that reports the pair it routed through moved the same construct to **+7.4pp**. |
| judge | 3 of 13 items were dropped as unparseable and the matrix was computed on the remaining 10. **Now checked (2026-08-16): the drops are a stratum.** Two independent runs dropped the *same three* items (Jaccard **1.00**); every unreadable cell came from the two reasoning judges and none from the third; and the dropped items have the longest contexts in the corpus (ranks 1, 2 and 5 of 13; 523 vs 431 characters mean). The mechanism is truncation — a longer prompt leaves less room to close a `<think>` block — so the surviving mean describes *the items short enough to parse*. |
| equity | 8 of 28 layers had no benchmark entry, so **24 of 86** names were priced against a placeholder median. The score existed and looked like every other score. |
| game | In the arm where agents were not asked to state a plan, **no deal closed at all**, which forced the commitment-gap metric to 0 by construction. The 20-point difference between arms was an artefact of that floor, and only the breakdown rate — measurable in failed negotiations too — was usable. |

**A second source does three things, and "multi-source" usually names only the first:**
① cross-validation, ② answering what the first source cannot, ③ **removing availability skew**.

### 5. Self-reference

The measurement is partly derived from the thing being measured.

| domain | instance |
|---|---|
| vendors | 🕳️ **Not yet checked.** Do two nominally independent vendors share an upstream RPC or the same pair-discovery logic? If so, the "second opinion" is not independent. This cell is open. |
| judge | The default configuration used the same model as generator and judge, producing a 0.985 faithfulness score that is a self-assessment. The report emits `self_graded` as CRITICAL: every metric is near-perfect and the report refuses to call it good. |
| equity | Layer medians were computed from held names only, so a layer could never look expensive relative to itself. One layer is now recorded as **permanently** unanchorable: its external-peer count is 0, because every public comparable is either held or private. Its pricing output is a within-layer ranking and never an absolute valuation. |
| game | Both sides of every negotiation were the same model. Whatever the measurement showed about strategy, it could not distinguish a property of the model from a property of two identical copies converging on each other — structurally the same defect as a judge grading its own output. |

### 6. The measurement changes the behaviour

Instrumenting an agent is not free. A field added to observe a decision can alter
the decision.

| domain | instance |
|---|---|
| game | Agents were asked to state a private intended floor before negotiating — a probe, meant to be passive, so that intent could be compared against action. Running the same conditions with and without that field: under pressure, breakdowns were **67% with the plan field and 100% without it**, and concessions were roughly twice as large with it (10.1 vs 4.8). Writing down what you privately intend makes an agent more willing to concede. Every result measured through that field was therefore measured in a perturbed behaviour regime. |
| vendors | Not applicable in the same form — the pipeline reads payloads and cannot change the contract it is reading. The nearest analogue is untested: one vendor's verdict comes from *simulating a trade*, which does touch the system it measures. |
| judge | Not observed. Answers are frozen to disk before grading, so the judge cannot influence the generator. This is a design property, not a finding — and the freezing was done for reproducibility, not for this reason. |
| equity | Not observed. |

**Why include a family with one instance.** Because the table's job is to say where
to look, and the shape generalises past games: any trace field, reasoning
requirement, or self-report added for observability is a candidate. The honest
status is *one experiment, 48 games, one model* — cited as a hypothesis with a
number attached, not as an established family.

---

## Why the table is worth more than the sum of its rows

It is not a retrospective taxonomy. **It predicts where the next bug is**, because a
family that has fired in two domains and not the third is usually not absent — it is
unlooked-for. That has now been tested three times:

- **Family 5 × vendors** — checked, and the answer was *not* pseudo-independence
  (0 of 113 byte-identical liquidity values; 3 cases where one vendor reports 0
  holders and the other thousands). The investigation produced five other findings,
  including that three rows of the availability-skew table were driven by one
  overlapping sample set (Jaccard 0.91) — one piece of evidence counted three times.
- **Family 4 × judge** — checked 2026-08-16, and it *was* systematic. See the row
  above; the harness now fails the run rather than reporting `n = 10`.
- **Family 1 × equity** — the stale-PEG detector re-filed here from generic
  diagnostics, where being a "diagnostic field" had exempted it from scrutiny.

Adding a fourth domain did not add a fourth column of the same kind. It added the
only column where the failure can be **created on demand**, which is what makes a
positive control possible: build a case whose label you already know, and fail the
run if the metric cannot recover it. Both of the checks above came from applying
that idea to a domain that was never designed for it.

**And the control has its own construct problem.** In `assay`, three judges scored a
distilled hallucination 0.00 and the *same claims embedded in an otherwise grounded
answer* 0.80–0.90. A positive control built the obvious way — make the failure
unmistakable — would have passed, and certified a sensitivity the pipeline does not
have at realistic density.

## Honest limitations

- Four domains, one author. Convergence across them is suggestive, not established.
- The fourth domain has **no public repo**. Its numbers cannot be re-run by a reader
  and should be read as reported observations, not as reproducible results. It is
  included because it is the only domain where a failure can be injected with a
  known label — and excluded from any claim that rests on reproducibility.
- **Family 6 rests on a single experiment in a single domain.** It is a hypothesis
  with a number, not a demonstrated family.
- The equity column draws on a personal research engine; its findings are internal
  governance notes, published as evidence rather than as a product claim.
- The judge column's headline (rubric underspecification drives judge disagreement)
  is **consistent with 2026 literature and is not a first report**. What is less
  covered is the cost: sharpening the rubric raised agreement to 83% while the
  remaining disagreement concentrated on a genuine hallucination that the *stricter*
  judge caught and the more permissive rubric excused. **Agreement went up;
  correctness did not.**
- None of the numbers above are a benchmark. They are single-corpus observations
  with the corpus stated.
