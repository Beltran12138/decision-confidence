# Audit 006 · Alpha Arena Season 1 (2026-10-15)

The subject is the whole season, not any one model.

## Subject

Nof1's Alpha Arena, Season 1: six large language models (Qwen3 Max, DeepSeek Chat V3.1, Claude Sonnet 4.5, Grok 4, Gemini 2.5 Pro, GPT-5), each given $10,000 of real money, traded crypto perpetuals on Hyperliquid from 2025-10-17 to 2025-11-03 with the same prompt and data. Qwen3 Max finished first; GPT-5 lost more than 60%. The result was widely reported as one model being better at trading than another.

## Three inputs

| Input | Value |
|---|---|
| Knowledge cutoff | Not applicable. Live trading is closed-book by construction; that is a strength of the format. |
| Window | 17 days (2025-10-17 22:00Z to the close, 2025-11-03 22:00Z). |
| Attempts | 6 (models in the season); the winner is the best of 6. |

## Finding

**None of the six results is statistically distinguishable from luck, in either direction.**

- Data: hourly `dollar_equity` per model from Nof1's own `api/account-totals`, as archived by the Wayback Machine on 2025-11-12 (the live endpoint and the arena pages returned 404 on 2026-10-12). Every model is anchored at its $10,000 start.
- Method: daily returns → the estimator behind the [wallet check](/wallet/) (Sharpe × √years, Student-t on effective degrees of freedom, put back on the normal scale). Script: `tools/audit_alpha_arena.py`.
- **Models with |t| ≥ 2: 0 of 6.** The winner's t is 0.54; the worst loser's is −0.83.
- Picking the best of 6 raises the bar from t = 2 to **t ≈ 2.67** (Bonferroni, one-sided).

| Model | Return | Sharpe (daily) | t |
|---|---|---|---|
| Qwen3 Max | +20.6% | 2.56 | 0.54 |
| DeepSeek Chat V3.1 | +4.0% | 1.95 | 0.41 |
| Claude Sonnet 4.5 | −31.9% | −2.02 | −0.43 |
| Grok 4 | −45.4% | −3.32 | −0.70 |
| Gemini 2.5 Pro | −55.2% | −2.79 | −0.59 |
| GPT-5 | −62.1% | −3.95 | −0.83 |

Returns are from the last archived hourly sample at the close and differ slightly from the figures Nof1 announced (for example +22.3% for Qwen3 Max); the finding does not depend on the difference.

## Why the window decides it

t = Sharpe × √years. Over 17 days, √years ≈ 0.22, so:

- to reach t = 2, a model needs an annualised Sharpe of about **9.3**;
- to clear the best-of-6 bar, about **12.4**.

Very few trading records sustain either. A 17-day season can rank models; it cannot tell skill from luck, and the losers have not been shown to be bad any more than the winner has been shown to be good.

## What it would take

At the season's own Sharpe, if it held:

| Model | Sharpe | Months for t = 2 | Months for best of 6 |
|---|---|---|---|
| Qwen3 Max | 2.56 | about 7 | about 13 |
| DeepSeek Chat V3.1 | 1.95 | about 13 | about 23 |

## Worth noting

Nof1's own homepage now says current models are poor at markets and improve little between releases, which is consistent with this finding. Live, closed-book trading is the right format for testing models; what it needs is a season long enough to carry the evidence, and a bar that allows for how many entrants there were.

Recheck: when a new season publishes its equity series.
