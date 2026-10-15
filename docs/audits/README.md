# Evidence audits

One page each. Every audit answers a single question: **how much of the evidence behind an AI trading claim actually counts?**

The method needs three things: the model's knowledge cutoff, the test window, and how many attempts the result was picked from. Where a project does not publish them, the audit says so; a missing input is a finding, not a verdict on the project.

Rules every audit follows:

- Sources are public and fetched on the stated date. Numbers are recomputed, not copied.
- "Cannot be ruled out as seen" is the strongest claim made about a model's training data. Never "contaminated".
- Findings state what is missing or what the numbers can and cannot support. No judgement of intent.
- Short is not the same as wrong: an underpowered result has not been shown to fail, only not shown to work.

| # | Subject | Date | Finding |
|---|---|---|---|
| [001](001-catalyst.md) | Catalyst (AI trading agents for retail) | 2026-10-12 | Cannot assess: none of the three inputs is public. The only published number is trading volume, not performance. |
| [002](002-metisai.md) | MetisAI's Liquidity Arena result | 2026-10-12 | Literally true, but the comparison set was narrowed: Sharpe 4th of 41, drawdown 2nd worst, t ≈ 1.2 against a bar of 3.26. |
| [003](003-liquidity-arena-phase-1.md) | Liquidity Arena 2026 Track A, Phase I (41 teams) | 2026-10-12 | No team reaches t = 2; the highest is 1.63. The format is closed-book; the window is too short. |
| [004](004-tradingagents-backtest.md) | TradingAgents `run_backtest` | 2026-10-12 | Data-level look-ahead is handled carefully; weight-level look-ahead is not checked. A 2024–2026 run with the default model is 88% open-book. |
| [005](005-nof1.md) | Nof1's "proto scaling law for financial intelligence" | 2026-10-12 | Cannot assess: the claim is public, the evidence is not. |
| [006](006-alpha-arena-season-1.md) | Alpha Arena Season 1 (6 LLMs, real money on Hyperliquid) | 2026-10-15 | No model is distinguishable from luck in either direction: the winner's t is 0.54, the worst loser's −0.83. 17 days needs a Sharpe of about 9.3 to reach t = 2. |
| [007](007-cex-copy-trading.md) | Copy-trading boards on OKX and Binance (profit top 100 each) | 2026-10-15 | 0 lead traders clear the bar for being picked from the board (OKX 0/97, Binance 0/83); about one in ten passes a single test. |
| [008](008-polymarket-profit-board.md) | Polymarket all-time profit board (top 50), position by position | 2026-10-15 | 0 of 38 complete records clear the bar. Reading only closed positions made 11 look like stars: unredeemed losers sit in a different list. |
| [009](009-kolscan-kol-board.md) | kolscan's Solana KOL profit board (1/7/30 days) | 2026-10-15 | Cannot assess: the longest window is 30 days and there is no capital base. 33 of the 30-day top 47 lose more trades than they win. Board frozen; recheck 2026-11-14. |

Computed with [Evidence Deflator](../../README.md). Have a backtest or a claim you want checked? Open an issue with a link to it.
