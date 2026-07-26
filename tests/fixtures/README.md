# Fixtures — real vendor responses, frozen

Every file here is an actual response from a public API, captured on
**2026-07-26**, used so the adapter tests and `examples/live_multi_source.py
--offline` run deterministically without network.

| File | Endpoint | Subject |
| --- | --- | --- |
| `goplus_pepe.json` | `GET api.gopluslabs.io/api/v1/token_security/1?contract_addresses=…` | PEPE `0x6982…1933` |
| `goplus_usdt.json` | same | USDT `0xdAC1…1ec7` |
| `honeypot_is_pepe.json` | `GET api.honeypot.is/v2/IsHoneypot?address=…` | PEPE |
| `honeypot_is_usdt.json` | same | USDT |
| `dexscreener_pepe.json` | `GET api.dexscreener.com/latest/dex/tokens/…` | PEPE |
| `dexscreener_usdt.json` | same | USDT |

**Modifications.** The GoPlus and honeypot.is payloads are byte-faithful apart
from re-indentation. The two DexScreener payloads each returned 30 pairs; they
are trimmed to the five deepest pools to keep the repo readable. No field was
edited, renamed, or invented.

**Why these two tokens.** PEPE is the agreeing case — all three sources read
low and the report says so with high confidence. USDT is the disagreeing case,
and it is disagreeing for an interesting reason rather than because one vendor
is broken:

- GoPlus reports mint, pause, blacklist and balance-change authority → high
  **authority_control** risk. Correct.
- honeypot.is simulates a buy and a sell successfully → near-zero
  **tradability** risk. Also correct.
- DexScreener, queried by address, returns **PulseChain** pools only — the same
  address on a fork chain. The adapter refuses to score them as Ethereum
  liquidity and reports `unavailable`.

Nothing here says USDT is unsafe. It says three sources answered three
different questions, and that averaging them into one number without saying so
is the failure this layer exists to prevent.

**Staleness.** These are snapshots. Vendors change scoring, tokens change
state, and the DexScreener pair list churns constantly. Re-capture with
`examples/live_multi_source.py <address> --json` if a test starts disagreeing
with reality; that is a fixture-refresh signal, not necessarily a code bug.
