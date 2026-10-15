# Retrospective freeze: results (2026-10-15)

Pre-registration: [PREREG.md](PREREG.md), committed (220254d) before anything below was computed. Script: `tools/retro_freeze.py`. Raw output: [results.json](results.json).

## Setup

Three archived copies of Hyperliquid's public leaderboard (Wayback Machine: 2025-11-10, 2026-01-26, 2026-04-03). For each, the cohort is picked with the same rule as the 2026-10-14 frozen cohort: all-time PnL top 100 plus 30-day ROI top 100 (account ≥ $10k). Each wallet's portfolio was fetched on 2026-10-15; `t_before` scores the history up to the snapshot, `t_after` the history after it, with the estimator behind the wallet check (at least 8 weeks each side).

## Result: the pre-registered rule says **win**

| Snapshot | Cohort | Scored both sides | ρ(t_before, t_after) | ρ(all-time PnL, t_after) |
|---|---|---|---|---|
| 2025-11-10 | 199 | 134 | 0.274 | 0.227 |
| 2026-01-26 | 199 | 143 | 0.190 | 0.173 |
| 2026-04-03 | 200 | 128 | 0.226 | 0.072 |
| Pooled | | 405 | **0.204** | 0.134 |

- Rule: ρ_t > ρ_pnl in at least two of three snapshots (3 of 3), and the pooled ρ_t's 95% bootstrap interval excludes 0 ([0.116, 0.296]).

## What it does and does not show

- **t read at a past date predicts the record after it.** The same wallet appears in several snapshots, so the pooled pairs are not independent; resampling by wallet (269 wallets) gives ρ_t a 95% interval of **[0.085, 0.313]**, still above 0.
- **"Better than ranking by profit" is not established.** t beat PnL in all three snapshots, but the difference has a wallet-resampled 95% interval of [−0.083, 0.220], which includes 0.
- **It orders traders; it does not find stars.** After the freeze, 1.5% to 2.1% of each cohort reached t ≥ 2, about what chance gives (2.3%). Wallets with t_before ≥ 2 had a higher median t_after (0.82 to 1.13) than the rest (0.59 to 0.80).
- **Coverage.** 405 of 598 cohort slots (68%) had 8 weeks or more on both sides; the rest were too new at the snapshot or stopped trading after it. Who drops out is not random, and the direction of that bias is unknown.
- t_after measures consistency (risk-adjusted), not the size of the return.

For comparison, the closest product (Convexly, Polymarket) reported a pre-registered forward test of its score at Spearman +0.11 against a +0.30 threshold it set, and called it failed (convexly.app/research).
