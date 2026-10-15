// Wallet check page: one script for every language. The page sets window.WALLET =
// {N, T}: N is the board size, T the strings (built by tools/build_site.py).
(() => {
 const {N, T} = window.WALLET, $ = id => document.getElementById(id), f = (x, d=2) => x == null ? '—' : Number(x).toFixed(d);
 const fill = (s, o) => s.replace(/\{(\w+)\}/g, (m, k) => k in o ? o[k] : m);
 const n = N.toLocaleString('en');
 function meter(t, bar) {
  const lo = Math.min(-1, Math.floor(t ?? 0)), hi = Math.max(Math.ceil(bar + .5), Math.ceil(t ?? 0)), W = 1000, H = 92, L = 14, R = 14;
  const x = v => L + (v - lo) / (hi - lo) * (W - L - R);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${T.meterAria}">`;
  s += `<rect class="zone" x="${x(bar)}" y="22" width="${W - R - x(bar)}" height="40"/>`;
  for (let v = lo; v <= hi; v++) s += `<line class="ax" x1="${x(v)}" x2="${x(v)}" y1="22" y2="62"/><text class="lab" x="${x(v)}" y="84" text-anchor="middle">${v}</text>`;
  s += `<line class="t2" x1="${x(2)}" x2="${x(2)}" y1="8" y2="62"/><text class="t2lab" x="${x(2) - 6}" y="16" text-anchor="end">${T.meterT2}</text>`;
  s += `<line class="bar" x1="${x(bar)}" x2="${x(bar)}" y1="8" y2="62"/><text class="barlab" x="${x(bar) - 6}" y="16" text-anchor="end" dy="${x(bar) - x(2) < 230 ? 14 : 0}">${fill(T.meterBest, {N: n, bar: f(bar)})}</text>`;
  if (t != null) s += `<circle class="pt best" cx="${x(Math.max(lo, Math.min(hi, t)))}" cy="42" r="7"/>`;
  return s + '</svg>';
 }
 async function run(a) {
  a = a.trim().toLowerCase();
  if (!/^0x[0-9a-f]{40}$/.test(a)) { $('wout').hidden = false; $('whead').textContent = T.notAddr[0]; $('wsub').textContent = T.notAddr[1]; return; }
  // count the check as a virtual page view (no address), then show the shareable URL
  history.pushState(null, '', T.checkPath); history.replaceState(null, '', T.selfPath + '?a=' + a);
  $('wout').hidden = false; $('whead').textContent = T.reading; $('wsub').textContent = ''; $('wflags').innerHTML = '';
  $('wid').textContent = a; $('whl').href = 'https://app.hyperliquid.xyz/explorer/address/' + a;
  let pf;
  try { pf = await HL.fetchPortfolio(a); } catch (e) { $('whead').textContent = T.noReach; $('wsub').textContent = String(e.message || e); return; }
  if (!Array.isArray(pf) || !pf.length) { $('whead').textContent = T.noHist; return; }
  const {rets, start, counted} = HL.weeklyReturns(pf), sc = HL.score(rets), v = HL.verdict(sc, N), fl = HL.flags(pf, rets, counted);
  const [title, tag, sub] = T.say[v.key];
  $('whead').textContent = title; $('wtag').innerHTML = `<span class="tag ${tag}">${T.tag[v.key]}</span>`;
  $('wsub').textContent = fill(sub, {BAR: f(v.bar), N: n});
  $('wmeter').innerHTML = meter(sc.t, v.bar);
  $('wt').textContent = f(sc.t); $('ws').textContent = f(sc.sharpe); $('ww').textContent = sc.weeks ?? '—';
  const need = HL.monthsToClear(v.bar, sc.sharpe), have = (sc.weeks || 0) / 4.345, M = T.months;
  if (sc.sharpe == null) { $('wm').textContent = '—'; $('wml').textContent = M.noSharpe; }
  else if (need == null) { $('wm').textContent = M.never[0]; $('wml').textContent = M.never[1]; }
  else if (need <= have) { $('wm').textContent = '0'; $('wml').textContent = M.done; }
  else { const m = need - have; $('wm').textContent = m >= 24 ? (m / 12).toFixed(1) + M.yr : Math.round(m) + M.mo; $('wml').textContent = M.more; }
  $('wflags').innerHTML = fl.map(k => `<li>${T.notes[k]}</li>`).join('');
  $('wcopy').dataset.copy = location.href;
  $('wnote').textContent = start ? fill(T.wnote, {start: new Date(start).toISOString().slice(0, 10), now: new Date().toISOString().slice(0, 16).replace('T', ' ')}) : '';
 }
 $('wform').addEventListener('submit', e => { e.preventDefault(); run($('waddr').value); });
 document.querySelectorAll('[data-ex]').forEach(b => b.addEventListener('click', () => { $('waddr').value = b.dataset.ex; run(b.dataset.ex); }));
 const q = new URLSearchParams(location.search).get('a'); if (q) { $('waddr').value = q; run(q); }
})();
