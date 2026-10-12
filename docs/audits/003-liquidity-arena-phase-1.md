# Audit 003 · Liquidity Arena 2026 Track A, Phase I (2026-10-12)

The subject is the whole leaderboard, not any one team.

## Subject

Phase I of LTP's AI quant trading competition: a sandbox elimination round, 2026-07-20 to 08-21, 41 teams, official rankings and equity curves.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable. Live, forward-looking trading is closed-book by construction; that is a strength of the format. |
| Window | 25 to 31 return days per team (median 30). |
| Attempts | 41 (teams in the round); the winner is the best of 41. |

## Finding

**None of the 41 results is statistically distinguishable from luck.**

- Method: daily closing equity from each team's `equityCurve` → daily returns → annualised Sharpe (× √365) → t = Sharpe × √(days / 365).
- **Teams with t ≥ 2: 0 of 41.** The highest t is 1.63 (rank 11). The top three are about 1.42, 1.40 and 1.20.
- Picking the best of 41 raises the bar from t = 2 to **t ≈ 3.26** (Bonferroni, one-sided; `selection_penalty(41)`).

| Rank | Team | Sharpe (daily equity) | Official Sharpe | Days | t |
|---|---|---|---|---|---|
| 1 | Little J | 4.87 | 3.28 | 31 | 1.42 |
| 2 | X-Explore | 5.23 | 3.20 | 26 | 1.40 |
| 3 | Quantech Services Group | 4.13 | 3.76 | 31 | 1.20 |
| 11 | Kinance (highest t) | 5.58 | 2.50 | 31 | 1.63 |

The official Sharpe's method is not stated, so it differs from ours. The finding holds under either: plugging the official values into 33 days gives a highest t of about 1.46.

## What it would take

| True Sharpe | Evidence needed, one attempt | Evidence needed, best of 41 |
|---|---|---|
| 5 | about 2 months | about 5 months |
| 2 | about 12 months | about 32 months |

## What this does and does not say

- It says a one-month ranking mostly reflects luck and risk appetite.
- It does not say any team's strategy fails. The window is too short to show either.

## Source

Official ranking endpoint (fetched 2026-10-11; snapshot at the end of Phase I). A suggestion to show t-statistics on the leaderboard was sent to the organiser on 2026-10-12.
