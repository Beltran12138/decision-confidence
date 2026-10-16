# Audit 010 · Papertrade's PnL leaderboard: frozen for a forward check (2026-10-16)

An observation now, a test later. The board has no return series, so no record on it can be scored today. This page records what the board ranks, and freezes it so we can check, before the end of October, whether the top keeps winning.

## Subject

Papertrade launched on 2026-10-10: synthetic BTC and ETH perpetuals on HyperEVM at up to 1000x, with no order book. Every trade is filled against one shared USDC pool at the midpoint of Hyperliquid's best bid and offer. Losing trades mint the PAPER token. Paperdash (paperdash.xyz), a third-party dashboard, ranks every account by PnL.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable (live trading) |
| Window | Six days since launch (all-time), or the last 24 hours |
| Attempts | 14,381 accounts with non-zero PnL (Paperdash counts 20,140 accounts in all) |

## What the board ranks (fetched 2026-10-16 03:01 UTC)

- **The #1 account by all-time PnL ($1,278,867) is the wallet The Block identified** (`0x2025…840e`) buying and selling ETH on Hyperliquid in size while it held 660x positions on Papertrade, which priced off that same Hyperliquid quote. Its 305 trades won 97% of the time, with a typical hold of 98 seconds (on-chain monitoring reported by BlockBeats). Paperdash shows it last active on 2026-10-11 at 02:35 UTC. On a PnL board it is the best trader on the platform.
- **The third-worst account is one of the most profitable.** `0x35b2…95a7` is ranked 14,379 of 14,381 with −$979,132 on $10.1 billion of volume. Losing trades mint PAPER, and staked PAPER earns a share of the pool. Paperdash records 252 million PAPER and $1,675,142 of USDC staking rewards for the same wallet. Lookonchain reported on 2026-10-12 that it was already ahead overall. Ranked by PnL, it is near last.
- **Most accounts lose, and the winnings are concentrated.** 2,766 of 14,381 accounts are in profit (19%). Traders as a whole are down $54.4 million. The top 100 hold 76% of all profit made by winners; the #1 account alone holds 13.6%.
- **The top of the 24-hour board is not the top of the all-time board.** 30 of the 24-hour top 100 are down since launch.
- **What the bar would be.** An account picked from 14,381 needs t ≥ 4.66 before its record says anything (one result alone needs 2). At 1000x a 0.1% move is the whole margin, so six days of PnL is mostly chance. The board shows no return series; the chain does, and the next section scores the #1 account from it.

A PnL board cannot tell skill, luck and exploitation of the mechanism apart. On this one the top account made its money by moving the price Papertrade copies, and one of the biggest winners shows up as a loser.

## Counting trades or counting bets: the #1 account, scored from the chain

Papertrade's Exchange contract logs every open, close and liquidation on HyperEVM. Decoded with `tools/papertrade_chain.py`, the #1 account's record matches what was published about it: 307 closed positions, 296 of them winners, a median hold of 98 seconds, and 30 shorts opened at $2,507.35 and 660x ($297.0 million notional) liquidated for a $450,000 loss. Its realised PnL sums to $1,278,867, the same as Paperdash shows.

| Counted as | Bets | Won | t |
|---|---|---|---|
| Each position a bet | 337 | 296 of 307 closed, 30 liquidated | 8.35 |
| Positions opened in the same 30 seconds as one bet | 58 | 52 | 2.29 |
| … in the same 5 minutes | 21 | 18 | 1.77 |
| … in the same hour | 5 | 4 | 0.99 |

Counted position by position, the record looks overwhelming. But the positions were opened in bursts, each burst riding one push of the Hyperliquid price, so a burst is one bet. Counted that way, 18 of 21 bets won and t is 1.77: below even a single test, because the one burst that failed lost $450,000. However the bursts are drawn, from 30 seconds to an hour, t stays far from the 4.66 bar.

Two lessons for any record built from many small trades: t computed per trade overstates the evidence when trades share one bet, and an edge that wins 97% of the time can still lose in one move what it made in the rest.

## Frozen for a forward check

Three groups of 100, fixed by rule before any outcome: the 24-hour PnL top 100 (primary), the all-time PnL top 100, and a control of 100 drawn with a fixed seed from the rest of the board (volume at least $1M). The whole board and the groups are in [`docs/data/papertrade/`](https://github.com/Beltran12138/evidence-deflator/tree/main/docs/data/papertrade) (`frozen-2026-10-16.json`, SHA-256 of the file as written, LF line endings: `d2218edb6118d23e6dd043ee6fd86af45acc41eca71f8a223fe1e1694ead1722`). The rule and the readings were written down before the freeze: [`PREREG.md`](https://github.com/Beltran12138/evidence-deflator/blob/main/docs/data/papertrade/PREREG.md).

On **2026-10-23** (interim) and **2026-10-30** (primary) this page will report the PnL each group made after the freeze. If the 24-hour top beats the control by more than 15 percentage points in the share of wallets making money, and its median is positive, the board carries information and we will say so.

## How it was computed, and what is uncertain

- Data: Paperdash's server-rendered leaderboard, walked from both ends (`tools/freeze_papertrade.py`). Paperdash marks part of its wallet data as not yet verified; board figures, including the staking rewards above, will be checked against on-chain events before the forward result is published.
- The account behind `0x2025…840e` is identified by The Block's analysis of 2026-10-11 (as reported by FinanceFeeds, CoinDesk and others); this page does not make its own finding about intent.
- Papertrade tightened position and open-interest limits on 2026-10-11, so much of the all-time top was earned under looser rules than the ones in force now. That is why the 24-hour group is the primary one.
- PAPER rewards are not counted as PnL, here or in the forward check. They are what makes the board's sign wrong for wallets like `0x35b2…95a7`.

## What it would take

A board that wants its top to mean something needs returns rather than dollars, a window long enough to carry evidence, the number of accounts the top was picked from, and every source of a wallet's profit in one figure.
