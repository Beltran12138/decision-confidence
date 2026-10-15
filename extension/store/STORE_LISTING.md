# Chrome Web Store listing: Evidence Deflator

Package: `python tools/build_extension.py` → `dist/evidence-deflator-extension-<version>.zip`

## Category
Productivity (alternative: Tools)

## Language
English

## Name (≤ 45)
```
Evidence Deflator: skill or luck?
```

## Short description (≤ 132)
```
See whether a trader's record could be luck, right on Hyperliquid, Hypurrscan, Binance and OKX copy-trading pages.
```

## Full description
```
Leaderboards rank traders by profit. They don't tell you whether the record behind a name could be luck. Sort thousands of accounts by profit and someone is always on a streak.

Evidence Deflator puts a verdict next to the trader you are looking at:

• Hyperliquid wallets and vaults (app.hyperliquid.xyz, hypurrscan.io, hyperdash.info pages with an address)
• Binance copy trading: lead-portfolio pages
• OKX copy trading: lead-trader pages

For each one it shows:
• t, a measure of how strong the record is once you allow for its length (Student-t, small-sample corrected)
• the bar it would need to clear given how many traders it was picked from (for example t ≥ 4.90 for the best of ~47,000 Hyperliquid accounts)
• how many more months of record it would need, and warnings for what the number cannot see (no losing week, one week carrying the record, profit booked on a near-empty account)

The toolbar popup checks any address or trader ID you paste. Right-click a selected address to open the full check.

What we found with it: on Hyperliquid, Binance and OKX, none of the top-100 traders by profit clears the bar for having been picked from the board. The audits and the method are public at evidencedeflator.com.

Privacy: records are read from each exchange's own public API. Nothing about the trader you look at, or about you, is sent to us. No analytics, no account. Open source (MIT): github.com/Beltran12138/evidence-deflator

Not investment advice. A past record is not your future return after fees, latency and slippage.
```

## Single purpose (dashboard field)
```
Show whether a trader's public record can be told apart from luck, on the pages where users choose traders to copy.
```

## Permission justifications
**contextMenus**: adds one right-click item, "Check with Evidence Deflator", for a selected address or a link, which opens the check on evidencedeflator.com.

**Host permission: api.hyperliquid.xyz**: reads the public portfolio history and vault details of the Hyperliquid address the user is viewing or pasted, to compute the verdict.

**Host permission: www.binance.com**: reads the public ROI history of the Binance lead portfolio whose page the user is on (and the content script shows the panel on those pages).

**Host permission: www.okx.com**: reads the public PnL history of the OKX lead trader whose page the user is on, through OKX's documented public API (and shows the panel on those pages).

**Host permission: evidencedeflator.com**: downloads one public file with the day's leaderboard sizes, used to compute the bar. No user or trader data is sent.

**Content scripts on app.hyperliquid.xyz, hypurrscan.io, hyperdash.info, www.binance.com, www.okx.com**: read only the page URL to find the address or trader ID, and draw the verdict panel. They do not read page content, forms or cookies.

## Remote code
No. All code is in the package.

## Data usage (dashboard checkboxes)
Does not collect: personally identifiable information, health, financial and payment information, authentication information, personal communications, location, web history, user activity, website content.
Certify: not sold to third parties; not used for unrelated purposes; not used for creditworthiness.

## Privacy policy URL
https://evidencedeflator.com/privacy/

## Homepage / support URL
https://evidencedeflator.com/ · https://github.com/Beltran12138/evidence-deflator/issues

## Images
- Icon 128: `extension/icons/128.png`
- Screenshots 1280×800: `screenshot_1_binance.png`, `screenshot_2_hypurrscan.png`, `screenshot_3_popup.png`
- Small promo tile 440×280: `promo_tile_440x280.png`
