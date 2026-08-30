# Your backtest is shorter than you think

*Three numbers that shrink a five-and-a-half-year backtest to eight months —
and then to nothing. None of them require a price series to compute.*

---

A founder sits down with an investor and is asked to prove the business will
work. They can't. Nobody can. So they produce a TAM calculation instead — a
number with a methodology and a decimal point, which looks like evidence for
the claim being made and is in fact evidence for a different claim entirely.
Everyone in the room knows this. The ritual continues because the alternative
is admitting there is nothing to put on the slide.

We run the same ritual on ourselves, alone, with backtests.

The demand is *show me this strategy works*. The thing that cannot be supplied
is a guarantee about the future. What gets supplied instead is an equity curve:
a number with a methodology and a decimal point. And unlike the founder, we
usually forget that a substitution took place.

This is about three ways that curve is shorter than it looks. All three are
arithmetic on metadata — dates and a count. **None of them needs a price
series, which means every one of them can be computed before the first
performance figure exists.**

---

## The first number: 88%

A language model has a knowledge cutoff. Whatever happened before that date, it
has read — in prices, in filings, and above all in the enormous corpus of
after-the-fact explanation that financial writing consists of. Not *why prices
move*. Why **this** price moved, written by someone who already knew that it
had.

So when a model evaluates a period that precedes its cutoff, it is not
analysing. It is recalling. The two are indistinguishable in a backtest and
completely different in production.

Take a configuration nobody would blink at: a backtest from **2020-01 to
2025-06**, run with a model whose knowledge ends in **October 2024**. Five and
a half years, a full cycle, bear and bull. Sixty-six months.

```
total              66 months
open book          58 months   87.9%
clean                8 months   12.1%
```

Fifty-eight of those sixty-six months are on the wrong side of the cutoff.
**The curve is 88% open-book exam.** That portion is not testing whether the
strategy makes money. It is testing whether the model remembers.

This is not an estimate or a model of contamination. It is subtraction on three
dates, and you can do it before you have written a single line of strategy code.

---

## "Fine, I'll trust the other 12%"

This is the correct instinct and it is where the argument usually stops. It
shouldn't, because the other 12% is eight months, and eight months is not a
sample.

A Sharpe ratio's t-statistic grows with the square root of the sample: t ≈
SR·√T, with T in years ([Lo 2002](https://doi.org/10.2469/faj.v58.n4.2453), *Financial Analysts Journal* 58(4)). Turn
it around and you get the length required to clear a bar:

> **T = (t / SR)² years**

The quadratic is the part almost nobody has internalised:

| Sharpe you claim to be testing for | Clean months needed at t ≥ 2 |
| --- | ---: |
| 2.0 | 12 |
| 1.0 | **48** |
| 0.5 | 192 |

**Halving the Sharpe quadruples the sample.** A spectacular strategy is cheap
to demonstrate; a merely good one is expensive; a modest one is, for practical
purposes, undemonstrable within a career.

## The second number: 17%

Against a 48-month requirement, eight clean months is **17% of what an
inference needs**.

Which means the honest reading of that backtest is not "it works" and not "it
doesn't work". It is:

> **This backtest has no power to tell you anything. It cannot reject a
> hypothesis in either direction.**

That is an uncomfortable output because it feels like a non-answer. It is
actually the most useful thing on this page, because it is the reading people
reliably skip. A curve that is 88% recall and 12% underpowered gets reported as
a curve.

The two failures are genuinely different and take different actions:

| verdict | what happened | what it means |
| --- | --- | --- |
| `no_holdout` | nothing is out of sample | the result is recall — do not quote it |
| `underpowered` | some is, but too little | **neither** "works" nor "doesn't" — no power |
| `sufficient` | the clean part clears the bar | length has stopped being the constraint. That is *all* it means |

`sufficient` is not a pass. It says one specific obstacle is no longer binding.

---

## The third number: 2.3×

There is a second way the clean months get spent, and it leaves no trace on a
calendar.

If you tried several variants and kept the best one, the survivor's
t-statistic is not one draw. It is the **maximum of many draws**. The bar it has
to clear is higher, and by the quadratic above, the sample needed to clear that
bar grows faster still.

Bonferroni gives the corrected bar by dividing the error rate you already
accepted. Deriving α from your own `t` rather than fixing it at 0.05 is what
keeps "I tried one thing" an exact identity — declaring a single attempt must
not move the requirement by even a month:

```
α_base = 1 − Φ(t_base)
α_adj  = α_base / n
t_adj  = Φ⁻¹(1 − α_adj)
```

At SR 1.0, starting from t ≥ 2:

| variants screened | corrected bar | clean months needed |
| ---: | ---: | ---: |
| 1 | t ≥ 2.00 | 48 |
| 5 | t ≥ 2.61 | 82 |
| **10** | t ≥ 2.84 | **97** |
| 20 | t ≥ 3.05 | **112** &nbsp;(**2.3×**) |
| 50 | t ≥ 3.32 | 133 |

**Ten variants roughly doubles the sample you need.** Seventeen is where the
corrected bar reaches t > 3.0, the threshold [Harvey, Liu and
Zhu](https://doi.org/10.1093/rfs/hhv059) argue for on published factors
(*Review of Financial Studies* 29(1)) — a useful check that this scale is not eccentric.

And the effect composes with the first number in a way that is worth seeing
directly. Take a backtest with **no contamination at all** — sixty-six months
entirely after the cutoff, spotless:

```
clean 66 months, requirement 48   →  sufficient
```

Now declare that you screened twenty variants before keeping this one. Nothing
about the data changed:

```
clean 66 months, requirement 112  →  underpowered
```

**A perfectly clean backtest, disqualified by something that happened in your
editor.**

---

## The count gets discounted too

Fifty parameter settings of one strategy are not fifty independent tests, any
more than five vendors reading one on-chain field are five independent reads.
Charging the full count over-penalises, sometimes badly:

```
50 variants, charged in full        t ≥ 3.32   133 months
50 variants, measured as 5 effective  t ≥ 2.61    82 months
```

So the correction takes an `effective_trials` discount — with one condition
that is the whole point: **it has to be measured, not asserted.** A discount the
user may set freely is not a correction, it is an escape hatch.

The instrument ships with the repo, and it is the *other half* of the same page:
paste the variants' return series in as columns and it returns Kish's effective
sample size — the same quantity, applied to your search instead of to your
vendors. (`tools/neff.py` computes it too, but takes this repo's own JSONL
corpus rather than arbitrary series; the tooling points at the one that can
actually accept your data.)

## The part with no arithmetic in it

Here is the uncomfortable bit.

`trials` is self-reported. And **not reporting it is not a neutral default —
it is the strongest claim available**: that the strategy was specified before
anyone looked. Silence is an assertion, so every run that omits it says so.
This is what the tool actually prints when you leave it out:

```
Screening correction
  No screening count was declared; treated as a single attempt. This
  is not a neutral default — it asserts the strategy was specified
  before anyone looked at the data. Self-reported counts also run
  low: the variant you glanced at and abandoned does not usually get
  counted.
  Charged as one attempt, the requirement stays at 48 months. Declare
  with --trials N.
```

Worse: self-reported counts run low, and nothing here can detect that. **Nobody
counts the variant they glanced at and abandoned.** This correction turns an
unobservable quantity into a required parameter; all the tool can do is refuse
to treat silence as zero.

That is a real limitation, not a caveat I'm adding for form. If you want a
number that cannot be gamed by the person entering it, this isn't one.

---

## One month of ambiguity, worth naming

Earlier I wrote 87.9%. You may have seen this configuration quoted as **86.4%**.
Both are defensible: the difference is whether the cutoff month itself counts as
seen.

|  | open-book months | share |
| --- | ---: | ---: |
| cutoff month counts as read | 58 | **87.9%** |
| cutoff month excluded | 57 | **86.4%** |

"Knowledge cutoff: October 2024" most naturally means October 2024 was in the
training data, so this library counts it. But that is a convention, and **a
quoted share whose convention goes unstated is exactly the failure this project
exists to catch.** So it is fixed in code and a test names both numbers, which
is the only way a figure stops drifting between tellings.

One and a half points changes no conclusion here. It is in this article because
the reflex to leave it out is the thing worth resisting.

---

## Try it

Nothing below performs network I/O or reads a price series.

**In the browser** — no backend, no build, works offline, nothing leaves the
page: **[the knowledge-window calculator](https://beltran12138.github.io/decision-confidence/)**
(second half of the page; the first half is the source-side version of the same
discount).

**Command line** (`--lang zh` for Chinese output; the numbers are identical
either way):

```bash
python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06 --trials 20
```

**Library:**

```python
from effective_window import effective_window, remedies

w = effective_window("2024-10", "2020-01", "2025-06", target_sharpe=1.0, trials=20)
w.verdict           # 'underpowered'
w.months_required   # 112
remedies(w)         # what to do, dispatched on what actually caused the failure
```

**MCP**, for agents that run backtests on someone's behalf: the
`knowledge_window` tool. Its description carries one instruction that does more
work than the code — *if you do not know how many variants were screened, ask
the user; do not omit it* — because a model that omits the parameter has quietly
made that assertion on the user's behalf.

The browser copy is a deliberate reimplementation in JavaScript, which is a
drift risk. `tools/check_js_parity.py` diffs it against the library across 28
numeric cases and 24 remedy texts, **verbatim**, because that copy already
drifted once.

---

## What this does not do

- **It does not tell you a strategy works.** `sufficient` means length stopped
  being the binding constraint. Nothing more.
- **The length requirement is a floor.** t ≈ SR·√T assumes i.i.d. returns;
  monthly returns are typically positively autocorrelated, which inflates the
  naive t. The real requirement is longer, never shorter.
- **Bonferroni assumes independent trials** and controls the family-wise error
  rate, which is stricter than controlling false discovery. Correlated variants
  make it conservative — hence the measured discount above.
- **It cannot detect an understated trial count.** See above.
- **It says nothing about whether your data is any good**, whether your
  execution assumptions are realistic, or whether the strategy makes sense. It
  answers one question — *could this backtest have told anyone anything?* — and
  a "yes" on that question is the beginning of the analysis, not the end.

Which is the honest version of the thing the founder can't say in the meeting:
not *here is proof*, but *here is precisely which claims this evidence is
incapable of supporting*. That is a smaller statement. It has the advantage of
being true.

---

*Part of [decision-confidence](https://github.com/Beltran12138/decision-confidence)
— one discount on two axes. Across sources: are these vendors answering the same
question? Across time: how much of this had the model already read? MIT, pure
standard library, no network.*
