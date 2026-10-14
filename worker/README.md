# api.evidencedeflator.com

Cloudflare Worker: remote MCP (Streamable HTTP, stateless) and a JSON endpoint for the
Hyperliquid wallet check. No state, no keys, no logging beyond Cloudflare's defaults.

```
python tools/build_worker.py                     # docs/assets/hl.js + worker/src/worker.js -> worker/dist/worker.js
python tools/check_worker.py --cache DIR --live  # diff against src/hl_wallet.py, smoke-test routes
cd worker && npx wrangler@4 deploy
```

Routes: `GET /api/wallet?a=0x..&picked_from=N`, `POST /mcp`, `GET /` (index).
