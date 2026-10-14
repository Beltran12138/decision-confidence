---
name: evidence-deflator
description: Check whether a trading record is skill or could be luck before anyone copies, ranks or cites it. Use when a user asks about a Hyperliquid wallet or trader, shares a leaderboard rank or PnL as proof, wants to copy-trade someone, or quotes an AI or backtest result as evidence. Scores a Hyperliquid address from public data; also checks backtests and track records for length and selection.
---

# Evidence Deflator

A leaderboard ranks by profit. Among tens of thousands of accounts, someone is always on a streak, so a high rank is not evidence by itself. This skill answers one question: **is the record long and strong enough to tell apart from luck, once you allow for how it was picked?**

## Hyperliquid wallet

Use the first route that works.

1. **MCP tool** `hyperliquid_wallet(address, picked_from)`: comes with this plugin (hosted at `https://api.evidencedeflator.com/mcp`), or from the local `evidence-deflator-mcp` server.
2. **HTTP**, no key: `GET https://api.evidencedeflator.com/api/wallet?a=0xADDRESS&picked_from=47000` returns the same JSON.
3. **Command line**, no key needed:
   ```bash
   pip install "git+https://github.com/Beltran12138/evidence-deflator"
   python -m hl_wallet 0xADDRESS --picked-from 47000
   ```
4. **Web**: send the user to `https://evidencedeflator.com/wallet/?a=0xADDRESS`. The page computes the same score in their browser.

### Before you call it

Ask how the user found the wallet. If it came from sorting a leaderboard, `picked_from` is the size of that board. Hyperliquid ranks about 47,000 accounts; the current count is `ranked_from` in `https://evidencedeflator.com/data/hl/latest.json`. Leaving it out tells the tool this was the only wallet anyone looked at, and the bar drops from about 4.9 to 2.

### How to report the result

| verdict | say |
|---|---|
| `too_short` | Fewer than 8 measurable weeks. "This record cannot tell you yet." Not "no skill". |
| `luck` | Cannot be told apart from luck at this length. Give `months_more_to_clear` if present. |
| `clears_single` | Passes for one wallet picked blind, not for one picked off a board. |
| `clears_board` | Passes the best-of-`picked_from` bar. |
| `loses` | t at or below -2: losing, and not by chance. |

Always report the `flags` next to the verdict:

- `no_losing_week`: consistent with selling tail risk; t measures consistency, not the loss that has not happened yet.
- `one_week_majority`: one week made most of the gains.
- `pnl_outside_record`: most of the PnL was booked while the account held under $1,000, so it cannot be turned into a return. The verdict covers only the weeks that can be measured.

Do not turn a passing verdict into a recommendation. A past record is the trader's fills, not the user's returns after fees, latency and slippage.

## Backtests and other track records

With the MCP server installed:

- `knowledge_window(cutoff, start, end, trials)`: for a backtest run with a language model. Counts the months the model may already have seen and the clean months the claim needs.
- `track_record(start, end, picked, trials)`: for any record with no model behind it. Splits at the day it was picked; report both readings.

Without it, the same arithmetic is in the Python package (`pip install evidence-deflator`) and explained at `https://evidencedeflator.com/method/`.

## Method, in one paragraph

Weekly returns come from PnL, so deposits and withdrawals are not counted as returns. t is Sharpe times the square root of years, with the n - 1 variance and Student's t on effective degrees of freedom, put back on the normal scale so short records are not over-read. One record picked blind needs t >= 2; the best of N needs the Bonferroni bar (4.90 for about 47,000). Open source, MIT: `https://github.com/Beltran12138/evidence-deflator`.
