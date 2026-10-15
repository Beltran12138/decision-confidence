# Evidence Deflator for Chrome

Shows whether a trader's record can be told apart from luck, on the pages where you pick traders:

- Hyperliquid wallets and vaults: any `app.hyperliquid.xyz`, `hypurrscan.io` or `hyperdash.info` page whose URL contains a `0x…` address
- Binance copy trading: lead-portfolio pages (`/copy-trading/lead-details/<id>`)
- OKX copy trading: lead-trader pages (`/copy-trading/account/<code>`)

A small panel shows the verdict, t, the bar for having been picked from the board, and how much more record it would need. The toolbar popup checks any address or ID you paste, and right-clicking a selected address or a link opens the full check.

## Privacy

Records are read from each exchange's own public API. Nothing about the trader you look at is sent to evidencedeflator.com; the extension fetches only the daily board sizes (`/data/hl/latest.json`). No analytics, no account.

## Method

The same estimator as the [wallet check](https://evidencedeflator.com/wallet/) (`hl.js` is copied in from `docs/assets/` by `tools/build_extension.py`). Binance and OKX publish a cumulative return series without documenting its base; it is compounded into weekly returns, as in [audit 007](https://evidencedeflator.com/audits/007-cex-copy-trading.html).

## Build and install (until it is on the Chrome Web Store)

```
python tools/build_extension.py      # copies hl.js, draws the icons, writes dist/evidence-deflator-extension-<version>.zip
```

Then open `chrome://extensions`, turn on Developer mode, choose **Load unpacked** and select this folder.
