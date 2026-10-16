// Wallet check page: one script for every language. The page sets window.WALLET =
// {N, NV, T}: N is the trader board size, NV the number of vaults Hyperliquid lists (null if
// unknown), T the strings (built by tools/build_site.py).
(() => {
 const {N, NV, T} = window.WALLET, $ = id => document.getElementById(id), f = (x, d=2) => x == null ? '—' : Number(x).toFixed(d);
 const fill = (s, o) => s.replace(/\{(\w+)\}/g, (m, k) => k in o ? o[k] : m);
 function meter(t, bar, n) {
  // drawn at the box's own pixel width, so the labels stay readable on a phone
  const W = Math.max(320, Math.round(($('wmeter').clientWidth || 1028) - 28));
  const lo = Math.min(-1, Math.floor(t ?? 0)), hi = Math.max(Math.ceil(bar + .5), Math.ceil(t ?? 0)), H = 92, L = 14, R = 14;
  const x = v => L + (v - lo) / (hi - lo) * (W - L - R);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${T.meterAria}">`;
  s += `<rect class="zone" x="${x(bar)}" y="22" width="${W - R - x(bar)}" height="40"/>`;
  const step = W < 600 && hi - lo > 10 ? 2 : 1;
  for (let v = lo; v <= hi; v++) if ((v - lo) % step === 0 || v === 2) s += `<line class="ax" x1="${x(v)}" x2="${x(v)}" y1="22" y2="62"/><text class="lab" x="${x(v)}" y="84" text-anchor="middle">${v}</text>`;
  s += `<line class="t2" x1="${x(2)}" x2="${x(2)}" y1="8" y2="62"/><text class="t2lab" x="${x(2) - 6}" y="16" text-anchor="end">${T.meterT2}</text>`;
  s += `<line class="bar" x1="${x(bar)}" x2="${x(bar)}" y1="8" y2="62"/><text class="barlab" x="${x(bar) - 6}" y="16" text-anchor="end" dy="${W >= 600 && x(bar) - x(2) < 170 ? 14 : 0}">${W < 600 ? f(bar) : fill(T.meterBest, {N: n, bar: f(bar)})}</text>`;
  // the dot starts at t = 0 and slides to the reading (see .chart .pt.slide; skipped with reduced motion)
  if (t != null) s += `<circle class="pt best slide" cx="${x(0)}" cy="42" r="7" data-dx="${x(Math.max(lo, Math.min(hi, t))) - x(0)}"/>`;
  return s + '</svg>';
 }
 async function run(a) {
  a = a.trim().toLowerCase();
  if (!/^0x[0-9a-f]{40}$/.test(a)) { $('wout').hidden = false; $('whead').textContent = T.notAddr[0]; $('wsub').textContent = T.notAddr[1]; return; }
  history.replaceState(null, '', T.selfPath + '?a=' + a);
  if (await show(a)) {
   // one count per verdict shown: page language only, never the address
   try { fetch(T.countUrl, {method: 'POST', mode: 'no-cors', keepalive: true}); } catch (e) {}
  }
 }
 async function show(a) {
  $('wout').hidden = false; $('whead').textContent = T.reading; $('wsub').textContent = ''; $('wflags').innerHTML = '';
  $('wid').textContent = a; $('whl').href = 'https://app.hyperliquid.xyz/explorer/address/' + a; $('wvault').hidden = true;
  let pf, vd;
  try { [pf, vd] = await Promise.all([HL.fetchPortfolio(a), HL.fetchVault(a)]); } catch (e) { $('whead').textContent = T.noReach; $('wsub').textContent = String(e.message || e); return; }
  if (!Array.isArray(pf) || !pf.length) { $('whead').textContent = T.noHist; return; }
  // a vault was picked from the vault list, not the trader board
  const vault = vd && vd.name ? vd : null, NN = vault && NV ? NV : N, n = NN.toLocaleString('en'), U = vault && NV ? T.unitVault : T.unitAcct;
  if (vault) {
   $('whl').href = 'https://app.hyperliquid.xyz/vaults/' + a; $('wvault').hidden = false;
   $('wvault').textContent = fill(T.vault, {name: vault.name, lf: f(100 * (vault.leaderFraction || 0), 1), c: f(100 * (vault.leaderCommission || 0), 0)})
    + (NV ? fill(T.vaultBar, {NV: n}) : '');
  }
  const {rets, start, counted} = HL.weeklyReturns(pf), sc = HL.score(rets), v = HL.verdict(sc, NN), fl = HL.flags(pf, rets, counted);
  const [title, tag, sub] = T.say[v.key];
  $('whead').textContent = title; $('wtag').innerHTML = `<span class="tag ${tag}">${T.tag[v.key]}</span>`;
  $('wsub').textContent = fill(sub, {BAR: f(v.bar), N: n, U});
  $('wmeter').innerHTML = meter(sc.t, v.bar, n);
  const dot = $('wmeter').querySelector('.slide');
  if (dot) requestAnimationFrame(() => requestAnimationFrame(() => { dot.style.transform = `translateX(${dot.dataset.dx}px)`; }));
  $('wt').textContent = f(sc.t); $('ws').textContent = f(sc.sharpe); $('ww').textContent = sc.weeks ?? '—';
  const need = HL.monthsToClear(v.bar, sc.sharpe), have = (sc.weeks || 0) / 4.345, M = T.months;
  if (sc.sharpe == null) { $('wm').textContent = '—'; $('wml').textContent = M.noSharpe; }
  else if (need == null) { $('wm').textContent = M.never[0]; $('wml').textContent = M.never[1]; }
  else if (need <= have) { $('wm').textContent = '0'; $('wml').textContent = M.done; }
  else { const m = need - have; $('wm').textContent = m >= 1188 ? '> 99' + M.yr : m >= 24 ? (m / 12).toFixed(1) + M.yr : Math.round(m) + M.mo; $('wml').textContent = M.more; }
  $('wflags').innerHTML = fl.map(k => `<li>${T.notes[k]}</li>`).join('');
  $('wcopy').dataset.copy = location.origin + T.selfPath + '?a=' + a;
  $('wnote').textContent = start ? fill(T.wnote, {start: new Date(start).toISOString().slice(0, 10), now: new Date().toISOString().slice(0, 16).replace('T', ' ')}) : '';
  return true;
 }
 $('wform').addEventListener('submit', e => { e.preventDefault(); run($('waddr').value); });
 document.querySelectorAll('[data-ex]').forEach(b => b.addEventListener('click', () => { $('waddr').value = b.dataset.ex; run(b.dataset.ex); }));
 const q = new URLSearchParams(location.search).get('a'); if (q) { $('waddr').value = q; run(q); }
})();
