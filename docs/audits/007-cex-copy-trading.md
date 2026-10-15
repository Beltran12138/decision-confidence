# Audit 007 · Copy-trading leaderboards on OKX and Binance (2026-10-15)

The subject is each exchange's public lead-trader board, not any one trader.

## Subject

OKX and Binance let users copy a "lead trader" with one click and rank lead traders by profit. Each board shows PnL, ROI, win rate and (on Binance) a Sharpe ratio, but nothing that allows for having picked the trader from thousands.

## Three inputs

| Input | OKX | Binance |
|---|---|---|
| Knowledge cutoff | Not applicable (live trading) | Not applicable (live trading) |
| Window | Last 365 days, daily cumulative PnL ratio; last 12 weeks, weekly PnL ratio | Last 365 days, daily cumulative ROI |
| Attempts | 240 lead traders listed (the public list stops there; the true number is larger) | 9,138 public lead portfolios |

## Finding

**On both boards, no lead trader in the profit top 100 clears the bar for having been picked from the board.** About one in ten passes a single test.

| | OKX | Binance |
|---|---|---|
| Ranked by | PnL | PnL, last 90 days |
| Top 100, scoreable (8+ weeks) | 97 | 83 |
| t ≥ 2 (would pass if picked blind) | 10 | 9 |
| Bar for the best of N | 3.73 (N = 240, a floor) | 4.57 (N = 9,138) |
| Clear the bar | **0** | **0** |
| Highest t | 2.94 (rank 12) | 3.83 (rank 90, 11 weeks of record) |
| Copying now / ever (top 100) | 5,581 / 88,513 | 11,940 / not shown |

- OKX's #1 by PnL ($2.2M) has t = 0.03 over the last 365 days. Binance's #1 by 90-day PnL (+355% ROI) has t = 2.02.
- No trader in either top 100 is losing beyond chance (t ≤ −2): the boards are not full of bad traders, they are full of records that cannot be told apart from luck.

## How it was computed, and what is uncertain

- Data: OKX's documented public API (`/api/v5/copytrading/public-lead-traders`, `public-pnl`, `public-weekly-pnl`); Binance's public copy-trading web endpoints (`home-page/query-list`, `lead-portfolio/chart-data`), which are not a documented API. Fetched 2026-10-15, no key, no login. Scripts: `tools/audit_okx_copy.py`, `tools/audit_binance_copy.py`.
- Returns: neither exchange documents the base of its ratio. The cumulative daily series is compounded into weekly returns, r = (1 + R_end) / (1 + R_start) − 1, and scored with the wallet check's estimator (Student-t on effective degrees of freedom, on the normal scale).
- OKX check: its weekly endpoint and the compounded daily series disagree in some weeks. Scored on the weekly endpoint instead (12 weeks), 5 pass t ≥ 2 and 0 clear the bar; the two series agree on pass/fail at t = 2 for 82 of 97 traders. The finding holds on either.
- Survivorship: both lists show current lead traders. Traders who closed or stopped leading are not in them, which makes the boards look better than the population that started, not worse.
- The bar counts every listed trader as independent. Traders who copy each other or trade the same coins are fewer independent bets, which lowers the bar; how much is not measured here. On Hyperliquid we estimated it roughly (about 2.6); applied here, it would let 2 OKX and 4 Binance traders through, which is an order-of-magnitude statement, not a finding.

## What it would take

At the median Sharpe of the scoreable traders (Binance 1.40, OKX 0.75, annualised from weekly returns), clearing the board's bar would take about 10.6 years of record on Binance and about 25 years on OKX, if the Sharpe held. Boards rank on 7, 30 or 90 days. The fix is not a better formula; it is to say how the trader was picked and to keep a forward record from the day they were picked.

Recheck: monthly, with the frozen-cohort method if either exchange keeps its list stable.
