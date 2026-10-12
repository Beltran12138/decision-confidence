# Audit 004 · TradingAgents `run_backtest` (2026-10-12)

The subject is an open-source framework's backtest feature, not a performance claim.

## Subject

[TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents), a multi-agent LLM trading framework (110,766 stars on 2026-10-12). Since v0.5.0 it ships `run_backtest`; the README example is `tradingagents backtest NVDA,AAPL --start 2026-06-01 --end 2026-08-01 --every 7`. Default models: GPT-6 Sol (deep tier) and GPT-6 Luna (quick tier).

## What it already does well

- v0.4.0 to v0.5.2 fixed a whole set of **data-level** look-ahead paths: FRED, sentiment, and SEC EDGAR are served as published at the time, and backtests "see only data published by each analysis date" (CHANGELOG and README).
- The README states plainly that LLM runs are non-deterministic.

## What it does not check

- **Look-ahead in the weights.** `tradingagents/backtest.py` and `graph/trading_graph.py` contain no knowledge-cutoff check. The word "cutoff" appears only for data dates and for prompts that state the current date (#836).
- **Number of attempts.** `summarize()` reports hit rate and mean alpha per rating. It does not report how many grid cells or configurations were evaluated, and runs no significance test.

The maintainers already track model-level leakage in [#805](https://github.com/TauricResearch/TradingAgents/issues/805) and note that no code change can eliminate it. This audit is about labelling it.

## Three inputs, two typical uses

Published knowledge cutoffs (OpenAI model pages, fetched 2026-10-12): GPT-6 Sol **2026-04-20**, GPT-6 Luna **2026-05-18**.

| Use | Months | Cannot rule out as seen | Clean | Needed at Sharpe 1 | Verdict |
|---|---|---|---|---|---|
| README example, 2026-06 to 2026-08 | 3 | 0 | 3 | 48 | too short (6% of what is needed) |
| A typical 2024-01 to 2026-08 run | 32 | 28 | 4 | 48 | underpowered, 88% open-book |

(`tools/window.py --cutoff 2026-04`; the cutoff month counts as seen, which is conservative.)

## Finding

**The framework is careful; the risk is in how it is used.** The README window happens to fall after the cutoff, so it is closed-book, but only three months long. Move the start back to 2024 and nearly nine in ten months may already be known to the default model, and nothing in the output says so.

## Suggestion (posted to #805)

Before the grid runs, compare each cell's date with the configured models' published cutoffs and mark cells on or before them; in `BacktestSummary`, report how many cells were evaluated. Both are small changes.
