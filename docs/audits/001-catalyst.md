# Audit 001 · Catalyst (2026-10-12)

## Subject

Catalyst (catalyst.app): users describe a market view in plain language; agents analyse signals, backtest, and deploy strategies, with user confirmation for steps that move money. Raised a $30M seed led by Sequoia (announced 2026-10-08). In research preview, free, non-custodial.

Sources, fetched 2026-10-12: Sequoia's partnership post, Fortune's report, catalyst.app (homepage and FAQ).

## The published evidence

| What | Source |
|---|---|
| A pilot that "generated hundreds of millions in trading volume over a couple of weeks", focused on power traders | Fortune: "the company says …" |
| Agents "help you backtest and deploy strategies" | Sequoia |
| "Every action is verifiable end-to-end" | catalyst.app FAQ |

## Three inputs

| Input | Published? |
|---|---|
| Knowledge cutoff of the model that generates or scores strategies | No. No model is named in any of the three sources. |
| Backtest window | No. No backtest is published. |
| Number of attempts | No. |

## Finding

**Cannot assess: none of the three inputs is public.** This is a gap in the evidence, not a negative finding about Catalyst.

## What can be said without the inputs

1. **The only published number is volume, not performance.** Volume shows usage. It says nothing about whether strategies work. No user count, revenue, or returns are given.
2. **The product makes attempts nearly free.** Rewording a thesis produces a new strategy and a new backtest. The version a user deploys is picked from however many they tried; the platform can count that, the user does not see it. For a Sharpe-1 strategy, one attempt needs about 48 clean months; twenty attempts need about 112.
3. **The example trigger on the site is "bullish confidence above 85%".** Who produces that score, and whether it is calibrated, is not stated.
4. **"Verifiable end-to-end" refers to execution** (what the agent did), not to evidence (whether the backtest that justified it can be trusted). These are different properties.

## What would allow a verdict

The model name and its published cutoff; the window of the backtest a user sees before deploying; how many strategy versions that user generated first (the platform logs this).
