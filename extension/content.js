// Page panel: when the URL names a trader (a Hyperliquid address or vault, a Binance lead portfolio,
// an OKX lead trader), show the verdict in a small closable panel. It reads only the URL, not the
// page's markup, so it keeps working when the sites change their layout.
(() => {
  function target(u) {
    const url = new URL(u);
    const addr = url.pathname.match(/0x[0-9a-fA-F]{40}/);
    if (/(^|\.)hyperliquid\.xyz$|hypurrscan\.io$|hyperdash\.info$/.test(url.hostname) && addr)
      return {venue: 'hl', id: addr[0].toLowerCase(), label: 'Hyperliquid'};
    let m;
    if (url.hostname === 'www.binance.com' && (m = url.pathname.match(/copy-trading\/lead-details\/(\d+)/)))
      return {venue: 'binance', id: m[1], label: 'Binance copy trading'};
    if (url.hostname === 'www.okx.com' && (m = url.pathname.match(/copy-trading\/account\/([0-9A-F]{16})/i)))
      return {venue: 'okx', id: m[1], label: 'OKX copy trading'};
    return null;
  }

  let host = null, shown = null, closedFor = null;
  function remove() { if (host) host.remove(); host = null; shown = null; }

  function render(t) {
    remove();
    host = document.createElement('div');
    host.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647';
    const root = host.attachShadow({mode: 'closed'});
    root.innerHTML = `<style>${ED_VIEW.CSS}
.box{width:300px;background:#fff;color:#15171c;border:1px solid #ddd;border-radius:10px;box-shadow:0 8px 30px rgba(0,0,0,.18);padding:14px 16px 12px;font-family:system-ui}
.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;font:600 11px system-ui;color:#888;letter-spacing:.04em;text-transform:uppercase}
.x{background:none;border:0;font-size:18px;line-height:1;cursor:pointer;color:#888}</style>
<div class="box"><div class="top"><span>Evidence Deflator · ${t.label}</span><button class="x" title="Close">×</button></div><div class="body"><div class="ed-s">Reading the public record…</div></div></div>`;
    root.querySelector('.x').onclick = () => { closedFor = t.venue + t.id; remove(); };
    document.documentElement.appendChild(host);
    shown = t.venue + t.id;
    chrome.runtime.sendMessage({type: 'score', venue: t.venue, id: t.id}, r => {
      if (shown !== t.venue + t.id) return;
      root.querySelector('.body').innerHTML = ED_VIEW.html(r || {error: 'no response'});
    });
  }

  function check() {
    const t = target(location.href);
    if (!t) { remove(); return; }
    const key = t.venue + t.id;
    if (key !== shown && key !== closedFor) render(t);
  }
  check();
  // single-page apps change the URL without reloading
  let last = location.href;
  setInterval(() => { if (location.href !== last) { last = location.href; check(); } }, 800);
})();
