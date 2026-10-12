# Audit 002 · MetisAI's Liquidity Arena result (2026-10-12)

## The claim

From QSG's launch announcement for MetisAI (2026-09-29): it took part in Liquidity Arena 2026 Track A Phase 1, "ranked third overall", and its return and Sharpe ratio were "the highest among the top three teams".

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable. This was live sandbox trading during the competition, not a historical backtest, so there is no open-book problem. |
| Window | Phase I, about 33 days (2026-07-20 to 08-21), per the organiser's site. |
| Attempts | 41 teams competed; "highest among the top three" is a selection from 41 results. |

## Finding

**The claim is literally true, but the evidence does not support "the strategy works".**

- Its Sharpe ranks **4th of 41**. "Highest among the top three" is a comparison set the announcement chose.
- Its maximum drawdown, 15.54%, is the **2nd largest of 41**.
- Phase I was a sandbox, not live capital.
- From daily closing equity, the team's single-test t-statistic is about **1.2**. Using the official Sharpe of 3.76 and assuming it is annualised, t ≈ 1.13. Neither reaches 2, and picking the best of 41 raises the bar to about **3.26**.
- Its return, 31.46%, is genuinely 1st of 41.

## Source

The organiser's public ranking endpoint, `arena.liquiditytech.com/client-web-api/official/tracka/ranking/list?phase=PHASE_I`, fetched 2026-10-11 (totalSize = 41). t-statistics as computed in [audit 003](003-liquidity-arena-phase-1.md).
