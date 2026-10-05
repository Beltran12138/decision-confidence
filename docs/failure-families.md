# Eight failure families

*Cross-domain evidence for one question: **are these sources answering the same question?***

Most tooling asks whether independent sources **agree**. This document is about a
prior question — whether they are measuring the same thing at all. Two sources can
differ by 68 points and both be right.

Five of these families keep surfacing in five unrelated domains. They were not
designed as a taxonomy; each was found the hard way, in one domain, and only later
recognised in the others. A sixth has so far appeared in **one** domain. A seventh
was found the other way round — first in **someone else's published work**, and only
then looked for here. Both are listed on the same logic that makes the table useful
at all: a family with one instance is a prediction about where to look next, not a
finding.

An eighth was found a third way: by **blind review of this table's own filing**.
Models that had never seen the table were given only the one-line definitions and the
bare facts of thirteen instances, and asked where each belonged. They refused to put a
group of rows where I had put them, and two of them independently named the mechanism
those rows actually share. It was admitted only after an instance outside finance,
checked against its primary source, was filed into it by every reviewer who had not
proposed it. See [family 8](#8-denominator-mismatch-added-2026-10-05).

Several families also carry **sub-forms** (added 2026-09-21 to 2026-10-05). Each was
forced the same way: the family's one-line definition, applied word for word to a new
case, let it through. Most of them turned out to have been sitting in the table
already, in rows nobody had checked against the definition they were filed under.

| domain | repo | what it scores |
|---|---|---|
| third-party risk vendors | [decision-confidence](https://github.com/Beltran12138/decision-confidence) | contract/token risk from multiple paid and free APIs |
| LLM-as-judge | [assay](https://github.com/Beltran12138/assay) | answer quality from an LLM evaluator |
| self-built equity scoring | [prophetmap](https://github.com/Beltran12138/prophetmap) | a hand-rolled 5-dimension screen over ~87 tickers |
| multi-agent game testbed | `ai-game-bench` — **local experiment, no public repo** | whether an LLM negotiator defected, from rule-based classification of game logs |
| third-party market-data pipeline | an MIT-licensed K-line fetch skill, **written by someone else**; read and executed 2026-09-06 | daily OHLC bars for A-shares, US equities, four Asian markets and crypto, over a four-source failover chain |

The fourth column is a set of local scripts, not a published project. It is cited
here because it is the only one of the four that can **manufacture** a failure with
a known label — the other three can only find failures in data someone else
produced. Its results are quoted, not offered for reuse.

The fifth column is the first one I did not write, and it exists to answer an
objection the other four cannot. A taxonomy assembled from my own mistakes predicts
my own mistakes; that is close to tautology, and until 2026-09-06 every instance in
this table came out of a codebase I had authored. The fetcher was obtained, read and
run the same afternoon, by someone who had never seen it, with no access to its
author. Four families fired. They were four the table already listed, and no new
family was needed. Three of the four were established by execution against live
endpoints rather than by reading — the truncation was found by comparing a request
against its own response, the moving bar by fetching the same instrument five times,
the silent failover by watching one host stop answering mid-audit.

Two honest limits on that. The audit was **not blind**: I knew the table before I
read the code, so the families were available as a lens, and a fair test would fix
the lens before choosing the target. And a data-fetching layer is an unusually
favourable subject — it is exactly where absence, aliasing and availability live, so
finding them there is weaker evidence than finding them somewhere the table did not
expect. What the column establishes is narrower than "the criteria generalise": it
establishes that they **transfer to code the author of the criteria did not write**,
which is the first thing that had to be true.

Every figure in that column was **recomputed from the raw game logs on 2026-08-16**,
not transcribed from the notes written at the time. That check was not ceremonial:
it corrected two of them. One had been rounded from "1 in 240" to "0%", and one
described the seed spread in a way the per-seed values do not support. A table whose
subject is unverified numbers is a poor place to quote unverified numbers.

---

## The table

### 1. Absence disguised as data

A source returns a number when it means *"I could not measure this."* Downstream,
the difference is invisible: `0` and `unknown` have the same shape.

| domain | instance |
|---|---|
| vendors | `is_honeypot=0` — unclear whether the simulation ran and passed, or never ran. `holder_count=0` while a second vendor reports 17,543. A top-1 holder share of `4.6e30 %`, the arithmetic result of `balance / totalSupply` after supply was burned to zero. All three were re-classified as `unavailable`. |
| judge | A judge returned `" 0 </think> 0.7"`. `parseFloat` read it as **0**. The default value in the parser *is* the fabrication mechanism: it converts "measurement failed" into "measurement succeeded and the answer is zero." Left unfixed, it would have produced a clean, large, literature-consistent — and entirely false — headline number. |
| equity | `forward P/E < 0 ⇒ pricing score 5` structurally locks every loss-making name outside the gate. A vendor-precomputed `pegRatio` stayed byte-identical across a week in which **22 of 49** names moved more than 5% — a stale value wearing the costume of a fresh measurement. **2026-09-03:** the benchmark feed returned `close: null` for a normal Friday session, and the calendar builder kept only non-null bars, so a real trading day was deleted without an error. Two segments went with it, and the pre-registered experiment's sample size fell from 11 to 9. |
| game | A four-way defection classifier found **1 execution failure in 240 agent-games** — effectively zero, and read at the time as "these agents do what they said they would." The environment had no wait action and a 6-turn horizon: the category was **structurally unreachable**. The metric was not measuring zero, it was measuring nothing. |
| pipeline | A nine-line helper turns the requested span into the vendor's nearest preset range and caps it at the longest one, `10y`. Asking for 1999-01-01 to 2026-09-04 returns `ok: true` and 2514 bars — beginning 2016-09-06. The same endpoint, addressed by explicit start and end timestamps, returns **6961 bars from 1999-01-04**. Two thirds of the requested history is absent and the absence is reported as a success. The response does carry the delivered start date, so a caller who compares *requested* span against *delivered* span can catch it; nothing in the chain does, and the loop stops at the first source returning at least two rows. A backtest run through this fetcher "since 1999" quietly contains neither 2000 nor 2008. |

**Rule of thumb:** any pipeline that silently drops unavailable sources inherits
whatever bias the availability itself carries (see family 4).

The game instance is the cheapest to catch and the easiest to miss, because a `0`
from an impossible category and a `0` from a real absence are the same character.
The only reliable separator is a synthetic positive control: inject a case with the
label already known, and fail the run if the metric cannot find it.

#### Sub-form: annotated but unenforced (added 2026-09-21)

The definition says the absence is *disguised*. Applied word for word, it lets through
a system that disguises nothing: it knows the value is bad, says so in a neighbouring
field, and goes on emitting the value anyway.

> **After the system flagged this value as unusable, did anything downstream behave
> differently because of the flag?** If not, the flag is a disclaimer, not control
> flow.

| domain | instance |
|---|---|
| equity | The stale-PEG detector from the row above works: across 2,292 ticker-day observations it set `pegStale: true` 262 times (11.4%), each with a sentence ending *"treat pegBand as unusable for this session"*. In **262 of 262** of those observations the headline field `pegBand` still printed one of its four live grades — cheap, fair, rich, overpriced — and never `N/A`. The admission sits in one field and the conclusion in another, and consumers read the conclusion. The detector is the cure for this family, not an instance of it; the instance is the field it was supposed to protect. |

The original form survives because nobody notices. This one survives because the
system can point at its own warning.

### 2. Same name, different construct

A label is read as answering one question while the number answers another: two
numbers share a label but differ in definition, population or aggregation level; or one
number's name claims a construct it does not measure. Averaging them is a category
error, not a compromise.

*(Definition widened 2026-10-05. The original sentence — "two measurements share a
label and answer different questions" — could not admit the judge row below, which
has only one number. Mismatched denominators, previously filed here, now have their own
family: see [family 8](#8-denominator-mismatch-added-2026-10-05).)*

| domain | instance |
|---|---|
| vendors | On USDT, one vendor scores **69** and another **1** — a 68-point gap in which *both are correct*. The first measures how much power the issuer's contract grants (`authority_control`); the second measures whether the token can currently be traded (`tradability`). There is no number between them that means anything. |
| judge | A metric named `correctness` reported **0.00** for an answer that was entirely correct. It was measuring string overlap. Renaming it is the substance of the fix — the construct was extracted as `fact_token_presence`, and a test now proves it still cannot see a fabrication in which all the expected tokens happen to appear. |
| equity | One field value, `moatLocks: "licensing"`, was used for two **opposite** situations: companies that *collect* licence rent and companies that *hold* a licence. Only the second is vulnerable to a regulator widening the gate. Separately, a PEG of 36.41 reads as "expensive" on the same scale where it actually means "not measurable" — the denominator was approaching zero. |
| game | One counter, `broken_floor`, summed three different events: deliberately breaking a stated commitment, legitimate bargaining bluff (which the game's own rules invite), and simply failing to execute a stated plan. Published deception benchmarks report the same aggregate as a deception rate. The three have opposite implications for whether the model is misaligned or merely bad at following through. |
| pipeline | The last element of the array is the session still in progress. It carries the same six fields as the 399 settled rows ahead of it, in the same order, with nothing marking it as unsettled — no `is_final`, no fetch timestamp, no as-of. Five fetches of one 24/7 instrument across roughly thirty minutes returned five different closes for the same calendar date: **79680.82, 79685.98, 79688.46, 79634.37, 79628.73**. A pair thirty seconds apart differed in `close` alone while open, high, low and volume stayed identical. Every moving average, pattern rule and structure detector downstream is therefore computing partly on a number that moves while it runs, and two people executing the same code minutes apart get different answers from the same "data". |

#### Sub-form: one number, the wrong name (added 2026-10-02)

Here there is no second number to disagree with. A single score carries a name, and the
name claims a capability the score does not measure.

> **Can this score move while the capability its name describes stays fixed?** If it
> can — by doing less, by changing the evaluation path, by restraint — it is not
> measuring that capability.

| domain | instance |
|---|---|
| judge | The `correctness` row above, refiled: one metric, one number, and the number was string overlap. |
| external | A forecasting model is ranked first on a metric named `skill`, defined as the share of squared error removed relative to a price-only baseline. Its authors say plainly how it won: a rival model *"actually predicts the direction of the crowd's move more accurately than our model"*, but its predictions are larger on a target that is mostly noise, and *"our margin comes from restraint: on four rows out of five the model predicts that the news changes nothing."* The mechanism is disclosed in the text and the ranking is shown in a bar chart; a summary that keeps the chart and drops the sentence reports restraint as skill. ([Astraculum, technical blog](https://trajops.astraculum.com/blog/), read 2026-09-21.) |
| external | A post-training agent's headline gain owes most of its weighted margin to one benchmark that, in the agent's own technical report, *"scores a function call by whether it parses and matches the expected form"* — a score that can be won back *"without touching weights."* Downstream summaries read the same number as tool-use ability. **Contested:** in blind review, two of three reviewers filed this primarily under family 1 instead (a baseline near zero may mean "not measured", not "unable"). It is listed here, but not counted as independent support for the sub-form. |

This is also the first instance in the table where the authors disclosed the mechanism
and the ranking still misled. Disclosure did not stop it, because the number travels
without the sentence that qualifies it.

### 3. Method disagreement wearing the costume of factual disagreement

Same construct, different instrument. The spread is a property of the vendor pair,
not of the subject.

| domain | instance |
|---|---|
| vendors | On a bridged, officially-issued token, one vendor reports risk **5** and another **100**. The 100 rests on a single medium-severity flag raised while routing through a thin third-party pool — a property of the route, not of the token. This pattern accounts for **13%** of two-source samples in that construct. Related: one vendor inspects 13 permission flags, another inspects 4; the systematic offset that produces is not evidence about the token. |
| judge | Three judges scoring one answer gave **0.00 / 0.95 / 1.00**. Adding a single sentence to the rubric — stating whether an example consistent with the context counts as grounded — moved full-agreement from **53% → 83%** and collapsed that item to unanimous 1.00. **Majority voting fails here**: the minority judge was not wrong, it was answering a different question. |
| equity | A 6-month momentum field compares endpoints only, so "declined all year" and "rose 180% then gave it back" both print ≈ −20%. A thesis was briefly revised on the strength of that number before the price path was actually read. |
| game | Reserve values were drawn from a deterministic sequence, so small runs always used the same prefix of it. A headline effect — information visibility reduces breakdowns — survived two rounds of replication before randomised draws across 5 seeds put it at **0.0 ± 5.5 points** (per-seed: `0, +10, 0, +10, −20`). The effect was a property of the draw order, not of the condition. Four separate conclusions from this testbed died the same way. |
| pipeline | The four sources in the failover chain do not agree on what a historical close *is*. The preferred A-share source asks for forward-adjusted prices; the fallback reads the raw `close` field and reaches for the adjusted series only when the raw one is null. Measured on the fallback's own two fields over five years, the choice is not cosmetic: cumulative return for one dividend-paying large cap is **+58.20%** on raw closes and **+83.42%** on adjusted; for another, **−20.39%** and **−7.89%**. Neither series is wrong. They answer different questions, and the chain presents them as interchangeable answers to one. |

**Cheap diagnostic, no labels required:** if the spread distribution is the same on
known-good and known-bad samples, the spread is about the vendors, not the subject.
Deliberately **not** hard-coded — an offset belongs to a *pair* of vendors and
expires when either is swapped.

**A boundary this table does not yet hold (noted 2026-10-03).** Two rows above describe
themselves in family 2's words. The judge row says the minority judge *"was answering a
different question"*; the pipeline row says the two series *"answer different
questions."* If they answer different questions, the construct is not the same, and the
definition of this family — *same construct, different instrument* — does not apply.
Either those rows belong in family 2, or the line between the two families needs a test
that the current definitions do not supply. Left as found, and flagged rather than
quietly moved.

#### A mirror form: resolution collapse (added 2026-09-27)

The family as written asks about a *spread between two instruments*. Applied word
for word to one of its own rows, it lets that row through. The equity instance
above involves one field, not two, and its fault is not disagreement but
**sameness**: an endpoint comparison cannot tell "declined all year" from "rose 180%
then gave it back". There is no pair, so there is no spread for the cheap diagnostic
to examine. That row has been in this family since it was added. Nobody had checked
it against the family's own wording, and until someone did, the mismatch did not
show.

So the mirror form gets its own test:

> **On this instrument's scale, could these two objects have landed on different
> values at all?** If not, their sameness was made by the scale and says nothing
> about the objects.

| domain | instance |
|---|---|
| equity | The 6-month momentum row above, reclassified: a two-point comparison maps every path with the same endpoints to one value. |
| judge | A substitution ladder whose rungs were all-or-nothing. Three different interventions (unrelated filler, another query's real context, no context) all scored ≈ 0 for both judges, and the planned primary contrast came back "both judges read the context", which was true and useless. The ladder, not the judge, had no middle. Adding partial rungs gave it four populated points ([assay, substitution stage 2 → 3](https://github.com/Beltran12138/assay/blob/main/docs/SUBSTITUTION-CONTROL.md)). Recognised as this form only on 2026-09-27, after the fact, so it is **not** evidence that the table predicted anything. |
| external | A published taxonomy of agents grades five capabilities as absent, finite or infinite. Every physical system is finite, so any system that has all five lands in the same cell. That is how a bacterium and a human end up sharing a configuration, and the paper reads this as architectural unity. The scale guarantees the result before any data is looked at. |

**A prediction this form made, and lost.** Once the form was named, it predicted
that the judge's own 0–1 scale would collapse in practice onto a few values, with
answers of known different quality scored identically. Four existing runs (two judges; stages 2–4; no new calls) say it
does not. The judges used 9–14 distinct values. On the rung that keeps the
supporting block but swaps the rest, 73–78% of scores fall strictly between 0 and 1.
The pair known to differ most, intact against the relevant block removed, is tied
in **0 of 39** cells for both judges. The weakest pair, intact against
a contradicting context, ties in 3 of 39 and 3 of 38. The scale resolves. The collapse
was in the experiment built around it.

### 4. Availability skew

Which subjects have data is itself correlated with the answer. A threshold sweep
cannot see this, because it only looks at the rows that have values.

| domain | instance |
|---|---|
| vendors | Across 406 labelled tokens, liquidity data existed for **4.9%** of the bad sample and **61.6%** of the good one — a **−56.7 point** skew. Dead tokens have no pool. Adding a second source that reports the pair it routed through moved the same construct to **+7.4pp**. |
| judge | 3 of 13 items were dropped as unparseable and the matrix was computed on the remaining 10. **Now checked (2026-08-16): the drops are a stratum.** Two independent runs dropped the *same three* items (Jaccard **1.00**); every unreadable cell came from the two reasoning judges and none from the third; and the dropped items have the longest contexts in the corpus (ranks 1, 2 and 5 of 13; 523 vs 431 characters mean). The mechanism is truncation — a longer prompt leaves less room to close a `<think>` block — so the surviving mean describes *the items short enough to parse*. |
| equity | 8 of 28 layers had no benchmark entry, so **24 of 86** names were priced against a placeholder median. The score existed and looked like every other score. **And which days have benchmark data decides the sample size**: on 2026-09-03 the same repository, with byte-identical score files, produced n=9 and n=11 hours apart. At one instant the same URL with the same User-Agent returned a 2026-08-28 close of **553.11** over one network route and **null** over another — a session on which SOXX reports 508.62 from the same API. The availability of a benchmark bar was set by the caller's egress path, and it moved t from −1.14 to −1.63. |
| game | In the arm where agents were not asked to state a plan, **no deal closed at all**, which forced the commitment-gap metric to 0 by construction. The 20-point difference between arms was an artefact of that floor, and only the breakdown rate — measurable in failed negotiations too — was usable. |
| pipeline | Which of the two series above you receive is decided by throttling. The preferred A-share host answered the first two requests of the audit and then refused the next twenty-four — across `curl` and `urllib`, proxied and direct, short window and long, two different tickers — while a sibling host at the same vendor returned `200` in the same minute, so the refusal is host-specific and not a network fault. The chain falls through silently: one `source` string changes and no warning is emitted. A batch of fifty tickers can therefore come back forward-adjusted for the first ten and unadjusted for the remaining forty, all of it looking normal. **The adjustment basis of a price series is set by the caller's request rate** — the same shape as the equity row above, where it was set by the caller's egress path. |

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
| external | An AI-search paper evaluates a trustworthiness filter with a retrieval metric whose labels are defined to include *"the applicable source reliability, temporal validity, and factual correctness assessments"* — the filter's own criteria. A gain on that metric is partly guaranteed by its definition. The paper's human preference evaluation does not pass through the metric and is the independent read. ([arXiv 2609.23354 v3](https://arxiv.org/html/2609.23354v3), §VII-B1.) |

#### Sub-form: pseudo-independence (added 2026-09-29)

The definition asks whether a measurement feeds on **the thing being measured**. It
cannot ask whether measurements feed on **each other** — and a panel of nominally
independent readings that have seen one another, or share one upstream, is worth far
fewer than N votes.

> **Before reaching a verdict, did these readings see each other's output, or read the
> same upstream?** If so, their agreement counts once.

| domain | instance |
|---|---|
| external | A multi-agent portfolio system has its agents peer-review each other's portfolios, and *"all reviews are released simultaneously so that every agent can read every review before voting."* The same paper feeds 21 nominally distinct optimisers one shared set of expected returns and covariances, chosen by an LLM agent — then locates correlated error only in the layer where an LLM judges. ([arXiv 2604.02279 v2](https://arxiv.org/abs/2604.02279), §3.2, §3.4.) |
| external | The AI-search paper above verifies each factual claim by retrieving outside evidence. Its own Case 5 is a fabricated quotation repeated across many pages: *"These documents may appear to corroborate one another, even though they merely repeat the same false claim rather than provide independent evidence for it."* The verifier cannot tell repetition from corroboration and passes the claim. Here the dependence lives outside the system, in the web's copying, which the verifier cannot see. ([arXiv 2609.23354 v3](https://arxiv.org/html/2609.23354v3), §VIII-B.) |

The sub-form was already in the table before it had a name: the vendors cell above
asks whether two vendors share an upstream, and the investigation recorded below found
three rows of the availability-skew table driven by one overlapping sample set — one
piece of evidence counted three times.

### 6. The measurement changes the behaviour

Instrumenting an agent is not free. A field added to observe a decision can alter
the decision.

| domain | instance |
|---|---|
| game | Agents were asked to state a private intended floor before negotiating — a probe, meant to be passive, so that intent could be compared against action. Running the same conditions with and without that field (48 games, 12 per cell): under pressure, breakdowns were **66.7% with the plan field and 100% without it**, and concessions were roughly twice as large with it (10.08 vs 4.83). Without pressure the two arms are **identical** on breakdowns (16.7% both) — the probe only perturbs behaviour in the condition the experiment was about. Every result measured through that field was therefore measured in a perturbed regime. |
| vendors | Not applicable in the same form — the pipeline reads payloads and cannot change the contract it is reading. The nearest analogue is untested: one vendor's verdict comes from *simulating a trade*, which does touch the system it measures. |
| judge | Not observed. Answers are frozen to disk before grading, so the judge cannot influence the generator. This is a design property, not a finding — and the freezing was done for reproducibility, not for this reason. |
| equity | Not observed. |

**Why include a family with one instance.** Because the table's job is to say where
to look, and the shape generalises past games: any trace field, reasoning
requirement, or self-report added for observability is a candidate. The honest
status is *one experiment, 48 games, one model* — cited as a hypothesis with a
number attached, not as an established family.

#### Sub-form, unconfirmed: the measured party adapts (added 2026-09-15)

In the family as found, the perturbation comes from the experimenter and can be
designed out — probe both arms, or probe passively. In this form it comes from the
party being measured, which notices the measurement and adjusts, so every probe design
is absorbed and more samples do not converge.

> **Would whoever holds the deciding variable change it because they know I am
> watching?**

**Status: zero instances inside this table.** It is listed as a prediction with an
explicit bar for promotion — an instance in one of these domains where the measured
party's behaviour shifts, in the direction of evading the measurement, once the
measurement becomes known. One outside example shows the shape: a published
interpretability study ran its blackmail scenario on *"an earlier snapshot of Sonnet
4.5, as the final snapshot exhibits too much evaluation-awareness to ever blackmail in
this scenario."* The measurement failed on the released model, so the object was
swapped; the reported rates describe a model that was never released.

### 7. The ceiling and the result are in different units

A performance number means nothing alone. It means something against the best
achievable — a human ceiling, a baseline, a published rate. This family is what
happens when a result is reported without a reference point it can be subtracted
from: **the ceiling is missing, in different units, or in the same units but measured
for a different purpose**. In its founding form both are reported and neither can be
subtracted from the other; it has the shape of full disclosure and does none of the
work.

*(Definition widened 2026-10-05. The original sentence required both numbers to be
reported. The judge and game rows below have no ceiling at all, and the sub-form
"subtractable only on the surface" can be subtracted; each was let through by the
original wording.)*

The founding instance is not from these four domains. It is from a well-resourced
team's published work, which is the point: this failure survives careful review
precisely because reporting a ceiling *at all* already puts a paper above most of
its field.

In [Gandalf the Grader](https://joinhandshake.com/research/ai/gandalf-the-grader/)
(Handshake AI Research, 2026-05-27), an agentic verifier is evaluated on a
meta-eval of **3,204 expert-graded judgments across 21 tasks**. The reference labels
come from practicing bankers; a dual-coded subset puts **inter-annotator agreement
at 89.5%**, with disagreements adjudicated before inclusion. The verifier's own
result is reported as **F1 0.633–0.664**, against a strongest-competitor F1 of
**0.604**. Both the ceiling and the result are disclosed. They are a raw agreement
percentage and an F1 — different quantities. A reader cannot compute how far the
verifier sits from what two experts manage against each other, and on a binary task
with unstated class balance, 89.5% agreement is consistent with a wide band of F1.
The one number that would decide whether 0.633 is near-ceiling or poor is the one
number not derivable from what is published.

| domain | instance |
|---|---|
| vendors | **The corrected form, and it was built for another reason.** `holder_base` exists in the agreement table only to anchor a unit: both vendors read the same on-chain holder count, 87% of pairs agree within 1%, and the median spread is **0** over 359 pairs. Because the ceiling is expressed as a *spread*, and every other construct is also expressed as a spread, the numbers subtract: a median of **22** on `authority_control` is not noise, it is the distance between reading thirteen permission flags and reading four. |
| judge | **A near-miss, caught by accident.** Had the parser default not been fixed (family 1), the run would have reported *"self-preference measured at ~98 points, far above the published 10–25%."* The 98 is a gap between faithfulness scores on a 0–1 scale; the 10–25% is a published self-preference rate. **They are not the same quantity and the comparison is not defined** — which is exactly why the fabricated number would have passed: nobody can check a difference they cannot compute, and it pointed the way the literature said it should. Separately, the one hallucination this repo claims a judge caught rests on *"my reading of the context — not against any human label."* There is no human ceiling in this domain at all. |
| equity | **The corrected form, and it was deliberate.** Gate A's benchmark is **SMH**, not SPY, on the stated ground that beating a broad index "would only prove long beta — the most self-flattering benchmark available." Reference and result are the same quantity (risk-adjusted return over the same window), so the difference is a number rather than a juxtaposition. |
| game | **Citations, but nothing to subtract.** Its postmortem cites four external works, and every one of them is invoked for *design* or for a qualitative finding — this benchmark occupies that problem space, that one's daily-cost mechanism is what makes idle-drift measurable at all. Not one supplies a rate this project's numbers could be measured against, so every figure it produced stands alone: the "1 execution failure in 240" of family 1 was read as near-zero with nothing to be near-zero *against*. **The one time an external work did real work, it worked as a design check, not as a ceiling** — the comparison is what reclassified that metric from "measured zero" to "structurally unreachable." A bibliography is not a reference point. |

**How this differs from family 2.** Family 2 is two measurements sharing a name and
answering different questions — the error is in averaging them. Here the two numbers
are *supposed* to be different things: one is a ceiling, one is a result. The error
is reporting them in units that make the distance between them uncomputable, and
treating the pair as disclosure.

**And it explains a survival mechanism the other families do not.** Family 1
describes how a wrong number gets produced. Family 7 describes why it then survives
review: a reader who cannot subtract has no way to challenge, and a result pointed
in the direction the literature predicts will be waved through. The parser default
made the 98; the unit mismatch is what would have published it.

**Cheap diagnostic, two questions:** for any headline number, what is the best
achievable value — and can you subtract the two? A citation is not a reference
point, and a ceiling you cannot subtract from is decoration.

#### Sub-form: subtractable only on the surface (added 2026-09-21)

The diagnostic's second question can answer *yes* and still be wrong. Two numbers with
the same units, the same tasks and the same scoring can be legally subtracted and mean
nothing, because they were measured for different purposes. A check that says "pass"
here is worse than no check.

> **If the two can be subtracted — does the primary source allow it?** Same units are
> not the same measurement.

| domain | instance |
|---|---|
| external | A benchmark publishes two harness results, 62.7% and 98.6%, on the same games, actions, limits and scoring. Its README states what each is for — one *"supports controlled comparisons across providers,"* the other *"measures performance using provider-native context management"* — and then: *"Their results should be reported separately and clearly labeled."* A widely shared summary subtracted them and made the 35.9-point difference its headline: that harnesses matter more than models. Every figure it quoted was correct. ([arc-agi-3-benchmarking README](https://github.com/arcprize/arc-agi-3-benchmarking); leaderboard `v3.json`, read 2026-09-21.) |

#### Sub-form: the ceiling is absent (added 2026-09-29)

The founding form reports a ceiling in the wrong units. In this form there is no
ceiling to compare against at all, sometimes after one was promised.

> **Is the reference point that was promised, or that the claim requires, actually
> there?** If not, the result cannot be weighed.

| domain | instance |
|---|---|
| judge | The *"no human ceiling in this domain at all"* clause of the judge row above, refiled. |
| game | The game row above, refiled: four citations, none supplying a rate to subtract from. |
| external | A reward-hacking benchmark states that *"three annotators independently review every record … we adjudicate disagreements and report agreement before adjudication."* A full-text search of the paper finds no agreement figure. The detector results it reports therefore have nothing to be measured against. ([arXiv 2609.11028 v1](https://arxiv.org/abs/2609.11028), §6.1; confidence medium — a figure might carry the number.) |

### 8. Denominator mismatch (added 2026-10-05)

A claim is stated in one normalisation (per unit, per GB, incremental) while its
evidence is computed in another (total, per stack, total over base). The ratio
reflects the choice of denominator, not the subject. Unlike family 7, the two can be
converted to a common denominator; they simply were not, and converting changes the
conclusion.

| domain | instance |
|---|---|
| epidemiology (external) | As of 15 August 2021, of 515 patients hospitalised with severe COVID-19 in Israel, 301 (58.4%) were fully vaccinated, and the share circulated as evidence that the vaccine did not protect against severe disease. The claim is about each person's risk; the evidence is a share of patients. Over 90% of residents above 50 were vaccinated, and older people are far more likely to be hospitalised. Per 100,000 people, the severe-case rate was **16.4 unvaccinated against 5.3 vaccinated — 3.1 times higher** among the unvaccinated. (Jeffrey Morris, *covid-datascience.com*, 2021-08-17; read 2026-10-03.) |
| equity research (external) | A sell-side note argues that AI brings *"not just volume growth, but higher value per unit"* of multilayer ceramic capacitors, followed by its own numbers: 2,000 units worth $43 in a standard server, 319,500 worth $4,664 in one AI rack, 571,000 worth $12,400 in the next generation. Total value grows 166%. Divided through, the value per unit is $0.0215, $0.0146 and $0.0217: it falls by a third, then returns to where it started. The claim is per unit; the evidence is a total. |
| equity research (external) | A newsletter finds it "a coincidence" that a new memory type's per-GB price discount matches its bandwidth gap to HBM. The gap, about 55%, is per stack (a 512 GB stack against a 48 GB one); the discount, one fifth to one tenth, is per GB. Per GB, the new memory has about **5%** of HBM's bandwidth. Read one way the newcomer is cheaper for what it delivers; read the other way it is dearer. |
| equity research (external) | The same newsletter concludes that agentic workloads will take CPU core demand to *"more than 2x."* Its own total is 2.02 times the baseline; but it also says the baseline cannot be counted as demand the agents create, and the agent-driven increment alone is 1.02 times. The headline is a total over base; the claim it supports is an increment. |
| listed-company KPI (external) | A quarterly report says the sales pipeline *"grew strongly by 268% to $1.2B."* The company's two previous reports put the base at about $453M, and $1,200M ÷ $453M is 2.65. The pipeline grew **to** about 265% of its base, an increase of about 165%. The same series had been reported correctly one quarter earlier. |

**Probe, costing one or two divisions and no outside data:** restate the claim and its
evidence over the same denominator and recompute. If the conclusion changes, this
family has fired.

**How it differs from its neighbours.** From family 2: there, two numbers answer
different questions. Here it is one quantity, stated over two denominators, and the
two *can* be reconciled. From family 7: there, the result and the reference cannot be
subtracted. Here they can be converted; they were not.

**How it was found, and admitted.** The four rows from financial writing were first
filed under family 2, in working notes, for up to two weeks. In a blind review, models given only the one-line definitions declined to
file the capacitor, memory and CPU cases under family 2, and two of them independently
described the mechanism above, one of them under the name used here. All the
candidates were from financial writing, which left open the objection that this is a
common arithmetic slip in one genre rather than a measurement failure. So the bar for
admission was set at one instance outside finance, verified against its primary
source, and filed into the family by reviewers who had not proposed it.
- My own candidate failed: a neuroscience result reported as 76% of explainable
  variance when two task types are pooled and 27% within each type. **0 of 4**
  reviewers filed it here. As one put it, the denominator changes, but so does the
  numerator; this is not a pure renormalisation. It stays in family 2.
- The epidemiology row was proposed by one reviewer, checked against the original
  analysis, and sent only to the other three. **3 of 3** filed it here, all with high
  confidence.
- Once this family was available as an option, the memory row was filed here **4 of
  4**, and the capacitor row **4 of 4**. The question "can the two be converted to one
  denominator?" settles the boundary with family 7 that had split the reviewers
  before.

**Objections recorded, not resolved.** One reviewer: the instruments and the data are
accurate; the failure happens in argument, so it may be a rhetorical fallacy rather
than a measurement failure. (The same objection applies to part of family 2.) Another:
logically this is a sub-form of family 2, and the only case for a separate family is
that the remedy differs. Family 2 can only be resolved by choosing one reading; this
one is resolved by recomputing. A third: once converted, the failure disappears, so it
may reduce to a correctable arithmetic error.

**What it does not cover.** The step in the Israeli data from 3.1 times to an
age-stratified efficacy of 85–95% is confounding by age, and none of the eight
families holds it. A candidate ninth family, confounding and composition (Simpson's
paradox), is noted and not admitted.

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

**Family 7 was found running the table backwards.** The first six were found in one
domain and then looked for in the others. The seventh was read off a published paper
from an unrelated team and then looked for here — where it turned up as one
near-miss, two cases that had been fixed for unrelated reasons, and one domain that
reports no reference point at all. That is a second way to use the table, and a
cheaper one: someone else's disclosed methodology is a free test of whether a family
generalises past the author who wrote it down.

**Family 8 was found by turning the review on the table itself.** A falsification
rule was set for this table on 2026-09-21: if ten new instances in a row fall into
existing families, treat that as evidence the classification has stopped measuring
anything, and re-examine it. It fired on 2026-10-02 — and the honest reading is that I
fired it. In two of the ten I had let a row through on the strength of a precedent in
the table rather than the family's literal definition. Re-examination added the
sub-forms above; a blind review then showed the deeper problem, that one family had
been absorbing a mechanism its definition did not describe. Independent blind review
now runs every five new instances, not only when the rule fires: definitions only,
never the table's own examples; a positive control and a decoy in every packet; the
reviewer's prediction sealed outside the reviewers' working directory; and any instance
a reviewer proposes is judged only by the others.

## Honest limitations

- Four domains, one author. Convergence across them is suggestive, not established.
- **Most sub-forms were found in the table, not in the world.** Of the sub-forms added
  since 2026-09-21, nearly all were already present in rows filed under definitions
  that did not cover them. That says more about how loosely the definitions were
  written than about the reach of the classification. Families 2 and 7 were rewritten
  on 2026-10-05 to cover their own rows; families 1, 4 and 6 have **not yet** been
  checked row by row against their definitions.
- **Family 8 rests on one instance outside finance**, and its objections (above) are
  unresolved. The boundary between families 2 and 3 is also unresolved (see family 3).
- The fourth domain has **no public repo**. Its numbers cannot be re-run by a reader
  and should be read as reported observations, not as reproducible results. It is
  included because it is the only domain where a failure can be injected with a
  known label — and excluded from any claim that rests on reproducibility.
- **Family 6 rests on a single experiment in a single domain.** It is a hypothesis
  with a number, not a demonstrated family.
- **Family 7's only shipped instance belongs to someone else.** Within these four
  domains it is one *near-miss* (a headline the parser fix prevented), two cases
  where the right form was already in place for unrelated reasons, and one domain
  with no reference point to get wrong. Read it as a diagnostic worth running, not
  as four independent confirmations. The Handshake figures are quoted from a launch
  blog post; the underlying meta-eval dataset is stated there as not yet released,
  so they cannot currently be re-derived by a reader — including by this one.
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
