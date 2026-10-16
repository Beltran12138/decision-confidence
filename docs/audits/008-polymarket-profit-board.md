# Audit 008 · Polymarket's all-time profit leaderboard, position by position (2026-10-15)

The subject is the top 50 of the board, not any one trader.

## Subject

Polymarket ranks wallets by all-time profit. A prediction-market record has no capital series, so the wallet check's t does not apply. This audit asks of every resolved position: was the price paid too low for how things turned out?

## Method

- Under no skill, a share bought at price p pays 1 with probability p. So edge = outcome − p has mean 0 and variance p(1 − p).
- Positions on the same event (an election, a season) share an outcome, so they are one bet, not many. The headline statistic sums edge per event and uses the spread across events: z = Σ edge / √(Σ over events of (event's summed edge)²).
- Positions are equal-weighted. avgPrice is the average buy price, so a position partly sold before resolution is scored on what was bought.
- The board reaches about 10,050 wallets and reports no total, so the bar is computed for N = 10,050: **z ≥ 4.59, a floor** (the true N is larger and its bar higher). *Update 2026-10-16:* the board is far larger than that floor. Filtering it by username returns a wallet ranked 450,853, so N is at least 450,853 and the bar at least **z ≥ 5.33**. No finding changes: the highest z among the complete records is 2.40, below either bar.
- Data: `data-api.polymarket.com` (`v1/leaderboard`, `closed-positions`, `positions`), public, no key, fetched 2026-10-15. Script: `tools/audit_polymarket.py`.

## Finding

**Of the 38 top-50 wallets whose full history could be read, none clears the bar; 8 reach z ≥ 2.** Twelve of the most active wallets have more resolved positions than the script reads (3,000 per list) and are left out rather than scored on part of their record.

- Half of the 38 bet on 8 or fewer distinct events. Much of the top of the board is a few large, related bets: the #1 wallet's 22 positions are all on the 2024 US election (z = 2.05).
- With so few events, z is itself imprecise; "cannot be told apart from luck" is the safe reading, not "no skill".

## The trap this audit fell into first

Polymarket lists sold or redeemed positions under `closed-positions`. A losing share is worth nothing, so most are never redeemed: they stay under `positions`, marked `redeemable` with a final price of 0. **Scored on closed positions alone, 11 of the top 50 cleared the bar**, with z as high as 18.3. Adding the resolved, unredeemed positions:

| Wallet (rank) | Closed only: z | Resolved, never redeemed | All resolved: z |
|---|---|---|---|
| DrPufferfish (33) | 18.31 | 853 | **1.08** |
| BreakTheBank (16) | 12.95 | 568 | **−0.13** |
| 0x5966…E507 (43) | 7.86 | 67 | **2.23** |

Any wallet tracker that reads only the closed list will show the same mirage: a record of winners, because the losers were never cashed in.

## What it would take

At even odds, z = edge × √n / 0.5, so a real 5-point edge per bet needs about 2,100 independent events to reach z = 4.59. The complete record with the most events here (0x5966…E507: 168 events, 7.4 points of edge per position) reaches 2.2. The top of the profit board mostly has a handful of events.

Recheck: quarterly. A per-event calibration test (Brier against the price paid) is the natural next step; Convexly runs that kind of analysis for Polymarket.

## Update, 2026-10-16

- **Board size.** The leaderboard's username filter (`/v1/leaderboard?userName=…`) returned a wallet ranked 450,853, so the board ranks at least that many wallets, not the 10,050 that paging by offset reaches. The bar for the best of 450,853 is z ≥ 5.33. Every count above holds under either bar.
- **Check any wallet.** The same test now runs in the browser at [/polymarket/](/polymarket/), on any wallet or username. For the wallets above it reproduces this audit's figures (for example 1.08 for DrPufferfish, 18.31 on closed positions only).
