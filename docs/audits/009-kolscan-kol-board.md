# Audit 009 · kolscan's Solana KOL profit board: how short the record is (2026-10-15)

An observation, not a verdict. The data cannot support a skill test; this page says why, and freezes today's board so it can be rechecked.

## Subject

kolscan.io ranks Solana memecoin traders who are public figures ("KOLs") by profit over the last 1, 7 and 30 days, with each wallet's X account and counts of winning and losing trades. Boards like this are where many people find wallets to copy.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable (live trading) |
| Window | 1, 7 or 30 days. Nothing longer is shown. |
| Attempts | Top 50 per window, drawn from a directory of several hundred KOL wallets |

## What the board shows (fetched 2026-10-15; 142 of 150 rows parsed)

- **The longest record is 30 days.** At a Sharpe of 3, which few traders sustain, 30 days gives t ≈ 3 × √(30/365) ≈ 0.86. No trader on a 30-day board can reach t = 2 without an annualised Sharpe near 7, before any allowance for being picked from hundreds.
- **Most of the top lose more trades than they win.** On the 30-day board, 33 of 47 have more losing trades than winning ones; the median win rate is 36% (42% on the 1-day board, 44% on the 7-day). Profit comes from a few large wins, which is the shape of a lottery as much as of skill.
- **The board turns over fast.** Of today's 1-day top 10, 5 are on the 30-day top 50; of the 7-day top 10, 7 are.
- kolscan reports profit in SOL and trade counts, not a capital base, so a return series cannot be built from it; turning it into one would mean rebuilding each wallet's balances from the chain.

## Frozen for a forward check

Today's 30-day board (47 wallets) is frozen in [`/data/kolscan/frozen-2026-10-15.json`](/data/kolscan/frozen-2026-10-15.json) (SHA-256 of the file as written, LF line endings: `2210bd5e949b45ea8e5e1e80b3cd8b68af58c7271286a455391a496d37918b9f`). On **2026-11-14** this page will report how many are still on the 30-day board and what they made in the new window. No pass mark is set in advance: it is a description of turnover, not a test.

## What it would take

A board that wants its top to mean something needs a window long enough to carry evidence (months, not days), a capital base so profit becomes a return, and a statement of how many wallets the top was picked from.
