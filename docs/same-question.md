# Are these sources answering the same question?

Two risk vendors scored the same token. One returned **69**. The other returned **1**.

The token was USDT. Neither vendor was wrong. The first was measuring how much power
the issuer's contract grants — mint, pause, blacklist. The second was measuring
whether the token can currently be traded. Both answers are correct, and the 68-point
gap between them is not a disagreement about USDT. It is two different questions
printed on the same scale.

There is no number between 69 and 1 that means anything. An average of 35 would be a
statement about nothing.

I have spent a few months building three unrelated things — a risk-normalisation
library, an LLM-judge harness, and an equity screen — and the same failure keeps
arriving in all three. This is what I have found, including the four times the rule
caught the tool that implements it.

---

## The question almost nobody asks

Every multi-source tool I have looked at asks the same thing: **do these sources
agree?** Cross-validation, consensus scoring, credibility weighting, ensembling,
majority vote. All of it operates on a prior assumption — that the sources are
already on one scale, so that agreement and disagreement are meaningful.

That assumption is doing enormous unexamined work.

Before you can ask whether two numbers agree, you have to establish that they are
answers to one question. In measurement theory this is *construct validity*, and it
has an established literature: Cronbach and Meehl set it out in 1955, and a
2026 systematic review of 445 LLM benchmarks — 42 authors, 29 expert reviewers — found
construct-validity weaknesses in nearly all of them.[^1] That work is about **benchmark design** — is
this test measuring the thing its name claims?

What I could not find anyone doing is the runtime version: an agent, in production,
holding five numbers from five sources, deciding what to do. Searching for formal
reconciliation of conflicting runtime signals returns nothing. The closest thing —
a 2026 framework that weights sources by credibility[^2] — is exactly the move that
assumes the problem away. Weighting presumes comparability. If two sources are
measuring different things, a credibility weight tells you which one to believe about
a question only one of them was asked.

So: group by construct, average only within a group, and refuse to produce a composite
across groups.

## The obvious objection, and why it is right

A tool that can only ever say "not comparable" is unfalsifiable. Refusal dressed as
judgement. It would be trivially correct in every case and useless in all of them.

This is the strongest argument against the whole idea and it needs an answer that is
not rhetoric. The answer is a control case. Perpetual-futures funding rates: five
venues, one question — *what does it cost to hold this position?* — and five different
numbers. Same construct, genuine disagreement. The library averages them, reports the
spread as a contradiction, and returns a score.

Two commands sit in the repo, side by side, and produce opposite behaviour on the same
engine. Without the second one, the first is a tool that has never been observed to
be wrong.

---

## Five families

Once the rule existed, the same failures kept surfacing in domains that share no code,
no vendors, and no data. Full evidence per cell is in
[`failure-families.md`](./failure-families.md); the short version:

**1. Absence disguised as data.** A source returns a number when it means *I could not
measure this*. A vendor reports `holder_count = 0` while another reports 17,543 for
the same token. A top-1 holder share arrives as `4.6e30 %` — the arithmetic result of
dividing by a supply that has been burned to zero. In the judge harness, an evaluator
returned `" 0 </think> 0.7"` and `parseFloat` read it as **0**. That default value is
the fabrication mechanism: it converts *measurement failed* into *measurement
succeeded, and the answer is zero*. Left in place it would have produced a large,
clean, literature-consistent and entirely false headline number.

**2. Same name, different construct.** The 68-point gap above. A metric named
`correctness` reporting 0.00 for an answer that was completely correct, because it was
measuring string overlap. A field value used simultaneously for companies that *collect*
licence rent and companies that *hold* a licence — opposite exposures, one label.

**3. Method disagreement wearing the costume of factual disagreement.** Two vendors,
the same construct, different instruments. On 113 subjects where both point at the
*same liquidity pool*, their reported USD liquidity differs by a median of 3.8% and a
**p90 of 62.2%**. Same pool, same moment, 62% apart. And in 43.9% of cases they are
not even looking at the same pool: one routes through whichever pair its simulation
used, which can be a thin third-party pool, and reports the resulting failure as a
property of the token rather than of the route.

The judge harness gave the cleanest instance. Three judges scored one answer
**0.00 / 0.95 / 1.00**. Adding one sentence to the rubric — stating whether an example
consistent with the source counts as grounded — moved full agreement from **53% to
83%** and collapsed that item to unanimous 1.00. The judges did not have personalities.
They had an underspecified question. **Majority voting fails here**: the minority judge
was not wrong, it was answering something else.

That finding is consistent with 2026 work on rubric-based judges and is not a first
report.[^3] What I have not seen stated is the cost. In the remaining 13% of
disagreement, one model scored 0.00 on an answer that had invented a UI path and three
network names that appear nowhere in the source. It was right. The permissive rubric I
had just written was what excused the hallucination. **Agreement went up. Correctness
did not.**

**4. Availability skew.** Whether a subject *has* data is itself correlated with the
answer. Across 406 labelled tokens, liquidity data existed for **4.9%** of the bad
sample and **61.6%** of the good one. A dead token has no pool. A threshold sweep
cannot see this, because it only looks at rows that have values.

**5. Self-reference.** A judge scoring its own output at 0.985. Layer medians computed
only from held positions, so no layer could ever look expensive relative to itself.

---

## The part I got wrong

Adding a second liquidity source moved that **−56.7pp** skew to **+7.4pp**, and I wrote
it up as the highest-value by-product of the whole exercise: *multi-source eliminates
the availability leak.*

Then I checked. On the 223 subjects that only the second source covers:

| | n | median pool | under $100 |
|---|---:|---:|---:|
| **scam** | 181 | **$0.64** | **76%** |
| legitimate | 42 | $884.17 | 38% |

The first source said *no data*. The second said *yes: sixty-four cents*. **Those two
statements carry the same information.** The skew number moved. The leak did not. It
migrated out of availability and into the values, which is why that construct still
posts the highest F1 in the whole sweep and still carries a `severe` leakage grade.

So the honest version of the claim is weaker in one way and much more useful in another:

> **A second source does not remove the bias. It moves the bias from somewhere you
> cannot see it to somewhere you can.**

That is still a win — an availability leak is invisible to every threshold sweep you
will ever run, and a value leak sits right there in the distribution. But *eliminated*
was the wrong verb, and the wrong verb is how a real finding turns into a slogan.

---

## Turning the rule on the tool

Four times now, applying the construct rule to my own code has found something. The
fourth was this week and it is the one I would least like to have written.

The calibration harness prints, per construct, a leakage grade and a short reason. Two
of those reasons carried skew figures with the word **"measured"** attached. They *were*
measured — in August, before the second source existed. After it was wired in the skew
moved, and the static text kept reporting the pre-fix number **in the same run whose own
skew table disagreed with it**.

Two of the four entries were still correct. That is the dangerous shape. All four wrong
gets caught immediately; a reader who spot-checks one and finds it right believes the
other three.

A stale value wearing the costume of a fresh measurement — family 1, committed by the
tool that exists to catch family 1.

The fix could not be to update the numbers, because that guarantees the same drift
again. The dictionary now holds only a grade and the reasoning behind it — the parts
that are judgement and do not move when the corpus does. One function computes every
figure, and everything that prints one reads from it.

Then, immediately, two more:

**Three skew rows were one finding.** Three constructs printed an identical skew.
They were not independent: two of them are blind on **21 of the same 23 subjects**.
Availability skew is driven entirely by which subjects lack data, and the skew table
computes each row alone, so it structurally could not show this. One gap, counted
three times, in a diagnostic table whose entire job is to catch that kind of thing. The
harness now prints pairwise overlap for every construct pair and marks anything above
0.80 as *treat as one*.

**The corpus had never been inspected as an instrument.** It was described as 203 scam
/ 203 legitimate, perfectly balanced, for as long as nobody counted distinct addresses
rather than lines: **406 rows, 396 subjects**, and by subject the balance is 199/197.
One address carries **both labels** — it is a true positive and a false positive at the
same threshold, so every precision figure in the run is internally inconsistent by that
much.

Nothing was de-duplicated. Collapsing those rows would silently move every number the
harness has ever printed, which is the exact re-rating this library argues against
everywhere else. It reports what the denominators contain and leaves the decision
upstream.

---

## What this does not establish

Three domains, one author. Convergence across them is suggestive, not established —
I chose all three problems, so I may simply be a person who makes one kind of mistake.

None of the numbers here are a benchmark. They are single-corpus observations, and
I have stated the corpus, including its defects.

The calibration exercise never produced a usable threshold. No construct beat the
degenerate "flag everything" baseline of F1 0.684, and the one construct that measured
something real — contract permissions, `precision 1.000` with zero false positives at
its cut — caught **2 of 200** scams. The failure was more informative than a threshold
would have been: the labels record *whether a project eventually collapsed*, and the
library measures *what powers a contract grants*. Those are two constructs. Putting
them in one precision-recall table is the category error the whole library exists to
name, and that time I was the one making it.

The claim I will defend is narrow: **before you reconcile two numbers, check that they
are answers to one question — and when a fix makes a bias number improve, check where
the bias went.**

---

*Code, evidence table and the runs behind every figure:*
[decision-confidence](https://github.com/Beltran12138/decision-confidence) ·
[assay](https://github.com/Beltran12138/assay) ·
[prophetmap](https://github.com/Beltran12138/prophetmap)

[^1]: Bean et al., *Measuring what Matters: Construct Validity in Large Language Model Benchmarks*, arXiv [2511.04703](https://arxiv.org/abs/2511.04703).
[^2]: *AgentPulse: A Continuous Multi-Signal Framework for Evaluating AI Agents in Deployment*, arXiv [2604.24038](https://arxiv.org/pdf/2604.24038).
[^3]: *Agreement Measurement for Rubric-based LLM Judges*, arXiv [2606.00093](https://arxiv.org/html/2606.00093).
