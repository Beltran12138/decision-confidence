// Polymarket wallet check: the same test as audit 008 (tools/audit_polymarket.py), run in the browser.
// Each resolved position asks whether the price paid was too low for how things turned out:
// with no skill a share bought at p pays 1 with probability p, so edge = outcome - p has mean 0, variance p(1-p).
// Positions in one event share an outcome, so the headline z sums edge by event (z_cluster).
// The page sets window.PM = {N, bar, selfPath, countUrl}.
(() => {
 const {N, bar, selfPath, countUrl} = window.PM, $ = id => document.getElementById(id);
 const API = 'https://data-api.polymarket.com/', CAP = 3000;
 const f = (x, d = 2) => x == null || !isFinite(x) ? '—' : Number(x).toFixed(d);
 const sleep = ms => new Promise(r => setTimeout(r, ms));

 async function get(url) {
  for (let i = 0; i < 4; i++) {
   const r = await fetch(url);
   if (r.ok) return r.json();
   if (r.status === 429) { await sleep(1500 * (i + 1)); continue; }
   throw new Error(`Polymarket API ${r.status}`);
  }
  throw new Error('Polymarket API is rate-limiting; try again in a minute');
 }
 async function paged(base, size, progress) {
  let out = [], off = 0;
  while (out.length < CAP) {
   const page = await get(`${base}&limit=${size}&offset=${off}`);
   if (!Array.isArray(page) || !page.length) break;
   out = out.concat(page); progress(out.length);
   if (page.length < size) break;
   off += size;
  }
  return {rows: out.slice(0, CAP), capped: out.length >= CAP};
 }
 async function resolveUser(q) {
  q = q.trim();
  const m = q.match(/0x[0-9a-fA-F]{40}/);
  if (m) return {wallet: m[0].toLowerCase()};
  const name = q.replace(/^.*polymarket\.com\/(profile\/)?@?/i, '').replace(/^@/, '').replace(/[/?#].*$/, '');
  if (!name) return null;
  // the leaderboard filters by username (prefix match) and covers every ranked wallet; profile search is fuzzy
  const lb = await get(`${API}v1/leaderboard?timePeriod=ALL&orderBy=PNL&limit=50&userName=${encodeURIComponent(name)}`);
  const exact = (Array.isArray(lb) ? lb : []).find(p => (p.userName || '').toLowerCase() === name.toLowerCase());
  if (exact) return {wallet: exact.proxyWallet.toLowerCase(), name: exact.userName};
  const r = await get(`https://gamma-api.polymarket.com/public-search?q=${encodeURIComponent(name)}&search_profiles=true&limit_per_type=10`);
  const hit = (r.profiles || []).find(p => (p.name || '').toLowerCase() === name.toLowerCase());
  return hit ? {wallet: hit.proxyWallet.toLowerCase(), name: hit.name} : {candidates: (r.profiles || []).slice(0, 5)};
 }

 function test(pos) {
  const seen = new Set(), res = [];
  for (const p of pos) {  // a partly sold position can sit in both lists: count each asset once
   const price = Number(p.avgPrice);
   if ((p.curPrice === 0 || p.curPrice === 1) && price > 0 && price < 1 && !seen.has(p.asset)) { seen.add(p.asset); res.push(p); }
  }
  if (!res.length) return null;
  const edge = res.map(p => p.curPrice - Number(p.avgPrice));
  const v = res.reduce((s, p) => s + Number(p.avgPrice) * (1 - Number(p.avgPrice)), 0);
  const ev = new Map();
  res.forEach((p, i) => { const k = p.eventSlug || p.conditionId; ev.set(k, (ev.get(k) || 0) + edge[i]); });
  const clus = [...ev.values()].reduce((s, x) => s + x * x, 0), tot = edge.reduce((a, b) => a + b, 0);
  return {resolved: res.length, events: ev.size, won: res.filter(p => p.curPrice === 1).length,
          meanPrice: res.reduce((s, p) => s + Number(p.avgPrice), 0) / res.length, meanEdge: tot / res.length,
          zNaive: v ? tot / Math.sqrt(v) : null, z: clus ? tot / Math.sqrt(clus) : null};
 }

 function meter(z) {
  const W = Math.max(320, Math.round(($('pmeter').clientWidth || 1028) - 28)), H = 92, L = 14, R = 14;
  const lo = Math.min(-1, Math.floor(z ?? 0)), hi = Math.max(Math.ceil(bar + .5), Math.ceil(z ?? 0));
  const x = v => L + (v - lo) / (hi - lo) * (W - L - R), step = W < 600 && hi - lo > 10 ? 2 : 1;
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Where this wallet's z falls against 2 and the leaderboard bar">`;
  s += `<rect class="zone" x="${x(bar)}" y="22" width="${W - R - x(bar)}" height="40"/>`;
  for (let v = lo; v <= hi; v++) if ((v - lo) % step === 0 || v === 2) s += `<line class="ax" x1="${x(v)}" x2="${x(v)}" y1="22" y2="62"/><text class="lab" x="${x(v)}" y="84" text-anchor="middle">${v}</text>`;
  s += `<line class="t2" x1="${x(2)}" x2="${x(2)}" y1="8" y2="62"/><text class="t2lab" x="${x(2) - 6}" y="16" text-anchor="end">z = 2 · one test</text>`;
  s += `<line class="bar" x1="${x(bar)}" x2="${x(bar)}" y1="8" y2="62"/><text class="barlab" x="${x(bar) - 6}" y="16" text-anchor="end" dy="${W >= 600 && x(bar) - x(2) < 170 ? 14 : 0}">${W < 600 ? f(bar) : `best of ${N.toLocaleString('en')}+ · ${f(bar)}`}</text>`;
  if (z != null) s += `<circle class="pt best slide" cx="${x(0)}" cy="42" r="7" data-dx="${x(Math.max(lo, Math.min(hi, z))) - x(0)}"/>`;
  return s + '</svg>';
 }

 const say = z => z == null ? ['Not enough resolved positions to score', 'grey', '']
  : z >= bar ? ['Clears the leaderboard bar', 'green', `z ≥ ${f(bar)}: a record like this is rare even after allowing for being picked from ${N.toLocaleString('en')}+ wallets.`]
  : z >= 2 ? ['Passes one test, not the leaderboard bar', 'amber', `z ≥ 2 would count if you had picked this wallet blind. Found on a leaderboard of ${N.toLocaleString('en')}+ wallets, it needs ${f(bar)}.`]
  : ['Cannot be told apart from luck', 'red', 'Across its events, this wallet bought at prices that turned out about as right as chance would make them.'];

 async function run(q) {
  $('pout').hidden = false; $('phead').textContent = 'Reading…'; $('psub').textContent = ''; $('pflags').innerHTML = ''; $('ptag').innerHTML = '';
  let u;
  try { u = await resolveUser(q); } catch (e) { $('phead').textContent = 'Could not reach Polymarket'; $('psub').textContent = String(e.message || e); return; }
  if (!u || u.candidates) {
   $('phead').textContent = 'That is not a Polymarket wallet or username';
   $('psub').textContent = u && u.candidates && u.candidates.length ? 'Did you mean: ' + u.candidates.map(c => c.name).join(', ') + '?' : 'Paste a 0x address, a polymarket.com profile link, or an exact username.';
   return;
  }
  const a = u.wallet;
  history.replaceState(null, '', selfPath + '?a=' + a);
  $('pid').textContent = (u.name ? u.name + ' · ' : '') + a; $('ppm').href = 'https://polymarket.com/profile/' + a;
  let closed, open;
  try {
   [closed, open] = await Promise.all([
    paged(`${API}closed-positions?user=${a}&sortBy=TIMESTAMP&sortDirection=DESC`, 50, n => { $('psub').textContent = `${n} closed positions read…`; }),
    paged(`${API}positions?user=${a}&sizeThreshold=0`, 500, () => {})]);
  } catch (e) { $('phead').textContent = 'Could not reach Polymarket'; $('psub').textContent = String(e.message || e); return; }
  // resolved but never redeemed: losing shares are worth 0 and usually stay here, not in closed-positions
  const unred = open.rows.filter(p => p.redeemable && (p.curPrice === 0 || p.curPrice === 1));
  const t = test(closed.rows.concat(unred)), tc = test(closed.rows);
  if (!t) { $('phead').textContent = 'No resolved positions with a buy price between 0 and 1'; $('psub').textContent = ''; return; }
  const [title, tag, sub] = say(t.z);
  $('phead').textContent = title; $('ptag').innerHTML = `<span class="tag tag-${tag}">${tag === 'red' ? 'Luck' : tag === 'amber' ? 'One test' : tag === 'green' ? 'Clears bar' : '—'}</span>`;
  $('psub').textContent = sub;
  $('pmeter').innerHTML = meter(t.z);
  const dot = $('pmeter').querySelector('.slide');
  if (dot) requestAnimationFrame(() => requestAnimationFrame(() => { dot.style.transform = `translateX(${dot.dataset.dx}px)`; }));
  $('pz').textContent = f(t.z); $('pev').textContent = t.events.toLocaleString('en'); $('pres').textContent = t.resolved.toLocaleString('en');
  $('pedge').textContent = (t.meanEdge >= 0 ? '+' : '') + f(100 * t.meanEdge, 1) + '¢';
  const notes = [];
  if (tc && tc.z != null && Math.abs(tc.z - t.z) >= 1) notes.push(`Counting only closed positions would give z = ${f(tc.z)}. ${unred.length} resolved positions were never redeemed (mostly losers) and sit in a separate list; they are included here.`);
  if (t.events < 30) notes.push(`Only ${t.events} events. With fewer than about 30, z rests on a handful of outcomes and is unreliable in either direction.`);
  if (closed.capped || open.capped) notes.push(`This wallet has more than ${CAP.toLocaleString('en')} positions in one list; only the most recent ${CAP.toLocaleString('en')} were read, so the result covers part of its record.`);
  if (t.zNaive != null && t.z != null && t.zNaive - t.z >= 1) notes.push(`Treating every position as independent would give z = ${f(t.zNaive)}. Positions in the same event share one outcome, so they are counted together.`);
  $('pflags').innerHTML = notes.map(n => `<li>${n}</li>`).join('');
  $('pcopy').dataset.copy = location.origin + selfPath + '?a=' + a;
  $('pnote').textContent = `${t.won} of ${t.resolved} resolved positions won, at an average price of ${f(100 * t.meanPrice, 0)}¢. Read ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC from data-api.polymarket.com.`;
  try { fetch(countUrl, {method: 'POST', mode: 'no-cors', keepalive: true}); } catch (e) {}
 }

 $('pform').addEventListener('submit', e => { e.preventDefault(); run($('paddr').value); });
 document.querySelectorAll('[data-ex]').forEach(b => b.addEventListener('click', () => { $('paddr').value = b.dataset.ex; run(b.dataset.ex); }));
 const q = new URLSearchParams(location.search).get('a');
 if (q) { $('paddr').value = q; run(q); }
})();
