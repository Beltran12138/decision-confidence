# Papertrade leaderboard: frozen groups and a forward check (audit 010)

Written 2026-10-16, before the freeze was taken, and committed before the frozen file. Nothing below is changed after a recheck; corrections go in a dated section at the end.

## Question

Does a place near the top of Papertrade's PnL leaderboard predict the PnL that wallet makes afterwards?

Papertrade (launched 2026-10-10) offers synthetic BTC and ETH perpetuals on HyperEVM at up to 1000x, against one shared USDC pool. At 1000x a 0.1% move is the whole margin, so short-run PnL is dominated by chance. Our expectation is that the top of the board is mostly luck, and that what does persist comes from the mechanism (the launch-day price manipulation, loss farming for PAPER) rather than from reading the market.

## Data

Paperdash (paperdash.xyz), a third-party dashboard, server-renders the full board, 100 rows a page. `tools/freeze_papertrade.py freeze` stores the whole all-time board (`board-<day>.csv.gz`, sha256 of the CSV recorded) and three groups in `frozen-<day>.json`. Paperdash labels some of its own wallet data as not yet verified; its board figures will be spot-checked against on-chain events before the result is published.

## Groups (fixed by rule, before any outcome)

| Group | Rule |
|---|---|
| `top_24h` (primary) | 24-hour PnL top 100 at the freeze |
| `top_all` | All-time PnL top 100 at the freeze |
| `control` | 100 wallets drawn with seed 20261016 from all-time ranks 101 and below with at least $1M of volume |

`top_24h` is primary because Papertrade tightened position and open-interest limits on 2026-10-11. Much of the all-time top was earned under the loose launch limits, so a fall-off in `top_all` cannot separate luck from an edge that the limit change closed. The last 24 hours were traded under the current limits.

## Outcome

PnL after the freeze = the wallet's all-time PnL at the recheck minus its all-time PnL at the freeze (USDC, realised plus unrealised). PAPER rewards are not counted. Only wallets that traded after the freeze (volume increased) are scored; wallets that stopped are counted and reported separately.

## Readings

2026-10-23 (interim) and 2026-10-30 (primary). Both are reported, whatever they show.

## What would count against us

Let *share* be the fraction of scored wallets with positive PnL after the freeze.

- **H1 (primary):** `top_24h` share minus `control` share is at most 15 percentage points at the 2026-10-30 reading. If `top_24h` beats `control` by more than 15 points and its median PnL after the freeze is above zero, the leaderboard carries information, and we will say so.
- **H2:** the same comparison for `top_all`, reported, with the limit-change caveat above.
- If fewer than 30 wallets in `top_24h` trade after the freeze, the reading is "not enough data", not a result.

## Known limits

- A board of synthetic positions against a pool is not a market of traders against each other. Traders as a whole lose (the pool overflowed past its $5M cap and paid stakers), so the control is expected to lose money; the comparison is top versus control, not top versus zero.
- 100 versus 100 detects a difference of about 15 points at roughly two standard errors; a smaller real persistence would be missed.
- Papertrade may change its rules again before the readings; any change we see is noted next to the result.

## 2026-10-16, before the final freeze: data notes

Found while running the first freeze attempt (discarded; no outcome exists yet, only the board at one moment):

- Paperdash's descending board stops after the accounts with positive PnL, and its ascending board (`dir=asc`) stops after the accounts with negative PnL. The script walks both and merges them. About 5,700 of the ~20,100 accounts it counts appear in neither; every listed account has non-zero PnL, so these are taken to be accounts that never closed a trade.
- The 24-hour page reports 24-hour figures. For `top_24h` the outcome baseline is each wallet's all-time PnL taken from the all-time board at the freeze; the 24-hour figures are kept alongside.
- The control is therefore drawn from winners and losers alike (all-time ranks 101 and below, volume at least $1M), which is what the rule above says.

## 2026-10-16: secondary analysis, declared before any reading

Added after the freeze and before either reading, once Papertrade's trades turned out to be readable from HyperEVM event logs (`tools/papertrade_chain.py`; decoding checked against the launch-day wallet `0x2025…840e`, whose summed PnL matches Paperdash's to the dollar). The primary test above is unchanged.

- **Records.** For every frozen wallet, its positions from launch to the freeze (`chain-prefreeze-2026-10-16.json.gz`) and from the freeze to each reading.
- **t on independent bets.** Positions opened in the same 5-minute window ride the same price move, so they are summed into one bet. t = mean / standard deviation × √(number of bets). Fewer than 10 bets: not scored. The 30-second and 60-minute windows are reported alongside, as a sensitivity check.
- **S1.** Per group, how many wallets reach t ≥ 2 and t ≥ 4.66 (the bar for the best of 14,381) on their pre-freeze record.
- **S2.** Among wallets scored before the freeze that trade after it: the share with positive PnL after the freeze, for pre-freeze t ≥ 2 against t < 2. Descriptive, no pass mark, reported whatever it shows.
- **Board check.** Each wallet's PnL summed from the chain against Paperdash's figure at the freeze; the median absolute difference is reported and wallets more than 5% apart are listed.
