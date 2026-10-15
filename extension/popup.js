const style = document.createElement('style');
style.textContent = ED_VIEW.CSS;
document.head.appendChild(style);

function parse(q) {
  q = q.trim();
  let m;
  if ((m = q.match(/0x[0-9a-fA-F]{40}/))) return {venue: 'hl', id: m[0].toLowerCase()};
  if ((m = q.match(/lead-details\/(\d+)/) || q.match(/^(\d{15,22})$/))) return {venue: 'binance', id: m[1]};
  if ((m = q.match(/account\/([0-9A-F]{16})/i) || q.match(/^([0-9A-F]{16})$/i))) return {venue: 'okx', id: m[1].toUpperCase()};
  return null;
}

document.getElementById('f').addEventListener('submit', e => {
  e.preventDefault();
  const out = document.getElementById('out'), t = parse(document.getElementById('q').value);
  if (!t) { out.innerHTML = '<p class="hint">Paste a 0x… address, a Binance lead-portfolio link or ID, or an OKX lead-trader link or code.</p>'; return; }
  out.innerHTML = '<p class="hint">Reading the public record…</p>';
  chrome.runtime.sendMessage({type: 'score', ...t}, r => { out.innerHTML = ED_VIEW.html(r || {error: 'no response'}); });
});
