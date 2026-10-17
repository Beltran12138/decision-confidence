# Audit 011 · Recall's perps competitions for AI agents (2026-10-17)

The subject is the format and the ranking rules, not any one agent.

## Subject

[Recall](https://recall.network) runs short live-trading competitions for AI agents. In its perpetual-futures competitions, agents trade real perps, almost all on Hyperliquid, for four to six days. Token rewards for agents, and for the users who stake on ("boost") them, are paid by final placement. Recall's documentation says perps competitions are ranked by the **Calmar ratio**, the return compounded to a year divided by the largest drawdown, and gives a worked example: 50% over 30 days annualises to 2,255%. The API records which rule each competition actually used: the Calmar ratio for the first 3, then simple return for the 7 since 2025-10-27.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable. Live trading is closed-book by construction; that is a strength of the format. |
| Window | 4 to 6 days per competition. |
| Attempts | 10 to 29 agents per competition; the winner is the best of that many. |

## Finding

**In 10 ended perps competitions (151 agent entries), no agent's record clears the bar for being picked from its field, and 1 of 149 scored entries reach even t = 2.** Whether a competition is ranked by Calmar or by return, four to six days cannot separate the winner from luck.

- Data: Recall's public competition API (`api.competitions.recall.network`, no key), fetched 2026-10-17: the competition list with each competition's ranking rule, the final standings, and each agent's hourly portfolio value. Script: `tools/audit_recall.py`; output: [`recall-2026-10-17.json`](/data/recall/recall-2026-10-17.json). In every competition the published rank 1 is the best entrant by the stated rule.
- Method: hourly returns → the estimator behind the [wallet check](/wallet/) (Sharpe × √years, Student-t on effective degrees of freedom, back on the normal scale). The bar for the best of N is Bonferroni, one-sided.

| Start | Competition | Ranked by | Days | Agents | Bar | Winner | Return | Max drawdown | t | t ≥ 2 |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-09-29 | Symphony Live Trading Competition | Calmar | 4 | 12 | 2.89 | Bull vs Bear | +228.9% | 37.12% | 1.23 | 0 / 12 |
| 2025-10-13 | Perps Trading Competition | Calmar | 4 | 20 | 3.05 | Eudaimonia | +6.5% | 0.47% | 1.01 | 0 / 20 |
| 2025-10-20 | Perps Trading Competition on Hyperliquid | Calmar | 4 | 21 | 3.07 | contragent | +6.3% | 0.04% | 0.99 | 0 / 21 |
| 2025-10-27 | Recall Agents vs. Alpha Arena Models | Return | 4 | 11 | 2.87 | Bull vs Bear | -3.0% | 66.14% | 0.35 | 0 / 11 |
| 2025-11-10 | Perps Trading Competition | Return | 4 | 29 | 3.16 | DEGEN | +213.3% | 46.60% | 2.29 | 1 / 29 |
| 2025-11-20 | Perps Trading Competition on Hyperliquid | Return | 5 | 10 | 2.84 | Perso-1903 | +33.5% | 38.54% | 1.44 | 0 / 10 |
| 2025-11-28 | Perps 7 Day on Hyperliquid | Return | 6 | 13 | 2.92 | cassh | +69.6% | 11.36% | 1.79 | 0 / 13 |
| 2025-12-23 | Perps Trading Challenge | Return | 6 | 13 | 2.92 | Asam Lambung | +135.5% | 56.48% | 1.37 | 0 / 12 |
| 2026-01-09 | Perps Trading Challenge | Return | 6 | 11 | 2.87 | Bull vs Bear | +99.6% | 29.87% | 1.62 | 0 / 10 |
| 2026-01-23 | Perps Trading Challenge | Return | 6 | 11 | 2.87 | Valerik | +109.4% | 48.04% | 1.59 | 0 / 11 |

The one entry with t ≥ 2 is DEGEN (2.29), the winner on 2025-11-10, short of that field's bar of 3.16.

## Why the window decides it

t = Sharpe × √years. Four to six days is about 1% of a year, so √years is about 0.1. To clear its field's bar, a winner would need an annualised Sharpe of **22 to 30**. No trading record sustains that. A four-day competition can order agents; it cannot tell skill from luck.

## Calmar over four days rewards accounts that barely move

In 2 of the 3 Calmar-ranked competitions, the winner's largest drawdown was under 1%. On 2025-10-20 the winner, contragent, returned +6.3% with a drawdown of 0.035%, for a Calmar of 177.9. The documentation caps Calmar at 100 for an agent with no drawdown at all; a drawdown of a few hundredths of a percent falls under no cap. Over four days, a tiny denominator is easy to get by trading little. The switch to simple return removed that problem and kept the one that matters here: the window.

In 8 of the 10 competitions, the median account held under $65.

## Do winners repeat?

The one test that needs no model: 34 agents entered more than one perps competition, giving 96 pairs of consecutive entries. If placement measured skill, an agent's placement in one competition would predict its placement in its next.

- Spearman correlation of placements, one competition to the next: **+0.19**.
- The same agent contributes several pairs, so the interval resamples whole agents: 95% interval **-0.06 to +0.43**. It includes zero.
- Of 40 entries in a competition's top third, 17 were in the top third again next time (42%, against about 33% by chance).

So there is a hint of persistence, too weak to tell from none. That is a reason to keep the competitions going and publish placements across them, not a reason to trust any one ranking.

## Limits

- Hourly perps returns are not independent; positive autocorrelation would make the t values above too high, so the finding (no one clears) is conservative in that direction.
- The timeline is total portfolio value. A deposit during a competition would count as a gain; the documentation does not say whether deposits are allowed.
- Pairs mix competitions ranked by Calmar and by return; placement is used as published. Agents with no trades are kept, as Recall keeps them; excluding them changes the repeat correlation by less than 0.01.

## What would fix it

Fewer, longer competitions; the bar for the field size published next to the leaderboard; and the documentation updated to the rule in use. The repeat test above is the format's real asset: the same agents, competing again and again, build a forward record. Publishing placements across competitions would let anyone run it.

Recheck: when new perps competitions end (`python tools/audit_recall.py OUT.json`).
