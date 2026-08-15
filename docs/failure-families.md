# Five failure families

*Cross-domain evidence for one question: **are these sources answering the same question?***

Most tooling asks whether independent sources **agree**. This document is about a
prior question — whether they are measuring the same thing at all. Two sources can
differ by 68 points and both be right.

The same five failure families keep surfacing in three unrelated domains. They were
not designed as a taxonomy; each was found the hard way, in one domain, and only
later recognised in the other two.

| domain | repo | what it scores |
|---|---|---|
| third-party risk vendors | [decision-confidence](https://github.com/Beltran12138/decision-confidence) | contract/token risk from multiple paid and free APIs |
| LLM-as-judge | [assay](https://github.com/Beltran12138/assay) | answer quality from an LLM evaluator |
| self-built equity scoring | [prophetmap](https://github.com/Beltran12138/prophetmap) | a hand-rolled 5-dimension screen over ~87 tickers |

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

**Rule of thumb:** any pipeline that silently drops unavailable sources inherits
whatever bias the availability itself carries (see family 4).

### 2. Same name, different construct

Two measurements share a label and answer different questions. Averaging them is a
category error, not a compromise.

| domain | instance |
|---|---|
| vendors | On USDT, one vendor scores **69** and another **1** — a 68-point gap in which *both are correct*. The first measures how much power the issuer's contract grants (`authority_control`); the second measures whether the token can currently be traded (`tradability`). There is no number between them that means anything. |
| judge | A metric named `correctness` reported **0.00** for an answer that was entirely correct. It was measuring string overlap. Renaming it is the substance of the fix — the construct was extracted as `fact_token_presence`, and a test now proves it still cannot see a fabrication in which all the expected tokens happen to appear. |
| equity | One field value, `moatLocks: "licensing"`, was used for two **opposite** situations: companies that *collect* licence rent and companies that *hold* a licence. Only the second is vulnerable to a regulator widening the gate. Separately, a PEG of 36.41 reads as "expensive" on the same scale where it actually means "not measurable" — the denominator was approaching zero. |

### 3. Method disagreement wearing the costume of factual disagreement

Same construct, different instrument. The spread is a property of the vendor pair,
not of the subject.

| domain | instance |
|---|---|
| vendors | On a bridged, officially-issued token, one vendor reports risk **5** and another **100**. The 100 rests on a single medium-severity flag raised while routing through a thin third-party pool — a property of the route, not of the token. This pattern accounts for **13%** of two-source samples in that construct. Related: one vendor inspects 13 permission flags, another inspects 4; the systematic offset that produces is not evidence about the token. |
| judge | Three judges scoring one answer gave **0.00 / 0.95 / 1.00**. Adding a single sentence to the rubric — stating whether an example consistent with the context counts as grounded — moved full-agreement from **53% → 83%** and collapsed that item to unanimous 1.00. **Majority voting fails here**: the minority judge was not wrong, it was answering a different question. |
| equity | A 6-month momentum field compares endpoints only, so "declined all year" and "rose 180% then gave it back" both print ≈ −20%. A thesis was briefly revised on the strength of that number before the price path was actually read. |

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
| judge | 3 of 13 items were dropped as unparseable, and the matrix was computed on the remaining 10. Whether the dropped items are random or systematic **has not been checked** — an open instance of this family, recorded rather than resolved. |
| equity | 8 of 28 layers had no benchmark entry, so **24 of 86** names were priced against a placeholder median. The score existed and looked like every other score. |

**A second source does three things, and "multi-source" usually names only the first:**
① cross-validation, ② answering what the first source cannot, ③ **removing availability skew**.

### 5. Self-reference

The measurement is partly derived from the thing being measured.

| domain | instance |
|---|---|
| vendors | 🕳️ **Not yet checked.** Do two nominally independent vendors share an upstream RPC or the same pair-discovery logic? If so, the "second opinion" is not independent. This cell is open. |
| judge | The default configuration used the same model as generator and judge, producing a 0.985 faithfulness score that is a self-assessment. The report emits `self_graded` as CRITICAL: every metric is near-perfect and the report refuses to call it good. |
| equity | Layer medians were computed from held names only, so a layer could never look expensive relative to itself. One layer is now recorded as **permanently** unanchorable: its external-peer count is 0, because every public comparable is either held or private. Its pricing output is a within-layer ranking and never an absolute valuation. |

---

## Why the table is worth more than the sum of its rows

It is not a retrospective taxonomy. **It predicts where the next bug is**, because a
family that has fired in two domains and not the third is usually not absent — it is
unlooked-for. Three cells above are open by that logic, and each is now a task:
vendor self-reference (family 5), whether dropped judge items are systematic
(family 4), and re-filing the stale-PEG detector under family 1 where it belongs
rather than under generic diagnostics.

## Honest limitations

- Three domains, one author. Convergence across them is suggestive, not established.
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
