// Scoring for the extension's background worker. Hyperliquid uses HL (hl.js, the wallet check's
// own code, copied in by tools/build_extension.py). Binance and OKX publish a cumulative return
// series, which is compounded into weekly returns and scored with the same HL.score, as in
// tools/audit_binance_copy.py and tools/audit_okx_copy.py. Nothing is sent to evidencedeflator.com
// except a request for the daily board sizes.
const SCORE = (() => {
  const DAY = 86400000, WEEK = 7 * DAY;
  const FALLBACK = {hl: 47039, vaults: 9477, binance: 9138, okx: 240};
  let sizes = null;

  async function boardSizes() {
    if (sizes) return sizes;
    sizes = {...FALLBACK};
    try {
      const d = await (await fetch('https://evidencedeflator.com/data/hl/latest.json')).json();
      sizes.hl = d.boards.pnl.ranked_from || sizes.hl;
      if (d.vaults && d.vaults.listed) sizes.vaults = d.vaults.listed;
    } catch (e) {}
    return sizes;
  }

  // Weekly compounded returns from a cumulative series [[ms, R]] (R as a fraction), each node the
  // last sample at or before it, anchored at the last sample; leading zeros before the start dropped.
  function weeklyFromCumulative(pts) {
    pts = pts.filter(p => Number.isFinite(p[1])).sort((a, b) => a[0] - b[0]);
    const first = pts.findIndex(p => p[1] !== 0);
    if (first < 0) return [];
    pts = pts.slice(Math.max(first - 1, 0));
    const nodes = [];
    let i = 0;
    const span = pts[pts.length - 1][0] - pts[0][0];
    for (let g = pts[0][0] + span % WEEK; g <= pts[pts.length - 1][0]; g += WEEK) {
      while (i + 1 < pts.length && pts[i + 1][0] <= g) i++;
      if (pts[i][0] <= g && (!nodes.length || nodes[nodes.length - 1] !== i)) nodes.push(i);
    }
    const out = [];
    for (let k = 0; k + 1 < nodes.length; k++) {
      const [ta, ra] = pts[nodes[k]], [tb, rb] = pts[nodes[k + 1]];
      if (1 + ra > 0) out.push([(1 + rb) / (1 + ra) - 1, (tb - ta) / WEEK]);
    }
    return out;
  }

  function result(venue, id, sc, n, unit, extra = {}) {
    const v = HL.verdict(sc, n);
    return {venue, id, ...sc, verdict: v.key, bar: Math.round(v.bar * 100) / 100, n, unit,
            months: HL.monthsToClear(v.bar, sc.sharpe), ...extra};
  }

  async function hyperliquid(addr) {
    const s = await boardSizes();
    const [pf, vd] = await Promise.all([HL.fetchPortfolio(addr), HL.fetchVault(addr)]);
    if (!Array.isArray(pf) || !pf.length) return {venue: 'hl', id: addr, error: 'no_history'};
    const {rets, counted} = HL.weeklyReturns(pf), sc = HL.score(rets);
    const vault = vd && vd.name ? vd : null;
    return result('hl', addr, sc, vault ? s.vaults : s.hl, vault ? 'vaults' : 'accounts',
                  {name: vault ? vault.name : null, flags: HL.flags(pf, rets, counted),
                   link: 'https://evidencedeflator.com/wallet/?a=' + addr});
  }

  async function binance(id) {
    const s = await boardSizes();
    const r = await fetch(`https://www.binance.com/bapi/futures/v1/public/future/copy-trade/lead-portfolio/chart-data?dataType=ROI&portfolioId=${id}&timeRange=365D`);
    const d = (await r.json()).data || [];
    const sc = HL.score(weeklyFromCumulative(d.map(x => [+x.dateTime, +x.value / 100])));
    return result('binance', id, sc, s.binance, 'lead portfolios', {note: 'Binance does not document how its ROI is computed.',
                  link: 'https://evidencedeflator.com/audits/007-cex-copy-trading.html'});
  }

  async function okx(code) {
    const s = await boardSizes();
    const r = await fetch(`https://www.okx.com/api/v5/copytrading/public-pnl?instType=SWAP&uniqueCode=${code}&lastDays=4`);
    const d = (await r.json()).data || [];
    const sc = HL.score(weeklyFromCumulative(d.map(x => [+x.beginTs, +x.pnlRatio])));
    return result('okx', code, sc, s.okx, 'listed lead traders (a floor)', {note: 'OKX does not document the base of its PnL ratio.',
                  link: 'https://evidencedeflator.com/audits/007-cex-copy-trading.html'});
  }

  return {hyperliquid, binance, okx, weeklyFromCumulative};
})();
if (typeof module !== 'undefined') module.exports = SCORE;
