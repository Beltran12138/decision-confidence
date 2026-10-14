// Hyperliquid wallet check. Port of tools/build_hl_board.py (weekly_returns, score, bar);
// tools/check_hl_parity.py runs both on the same cached portfolios and diffs the output.
const HL = (() => {
  const WEEK_MS = 7 * 24 * 3600 * 1000, MIN_WEEKS = 8, MIN_AV = 1000;

  // Standard normal CDF and inverse (Acklam), enough for bars to 2 decimals.
  function cdf(x) {
    const t = 1 / (1 + 0.2316419 * Math.abs(x)),
      d = 0.3989422804014327 * Math.exp(-x * x / 2),
      p = d * t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
    return x >= 0 ? 1 - p : p;
  }
  function inv(p) {
    const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00],
      b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01],
      c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00],
      d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00];
    const lo = 0.02425;
    let q, r;
    if (p < lo) { q = Math.sqrt(-2 * Math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1); }
    if (p > 1 - lo) { q = Math.sqrt(-2 * Math.log(1 - p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1); }
    q = p - 0.5; r = q * q;
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);
  }
  const ALPHA = 0.022750131948179098;  // 1 - Phi(2)
  const bar = n => inv(1 - ALPHA / n);
  const monthsToClear = (b, s) => (s && s > 0) ? (b / s) ** 2 * 12 : null;

  // Same grid and merging rule as the Python builder.
  function weeklyReturns(pf) {
    const at = Object.fromEntries(pf), all = at.allTime;
    const av = all.accountValueHistory.map(([t, v]) => [t, +v]);
    const pnl = new Map(all.pnlHistory.map(([t, v]) => [t, +v]));
    if (av.length < 2) return {rets: [], start: null, end: null, counted: 0};
    const start = av[0][0], end = av[av.length - 1][0], grid = [];
    for (let g = end; g >= start; g -= WEEK_MS) grid.push(g);
    grid.reverse();
    const nodes = []; let i = 0;
    for (const g of grid) {
      while (i + 1 < av.length && av[i + 1][0] <= g) i++;
      if (av[i][0] <= g && (!nodes.length || nodes[nodes.length - 1] !== i)) nodes.push(i);
    }
    const rets = [];
    let counted = 0;
    for (let k = 0; k + 1 < nodes.length; k++) {
      const [ta, va] = av[nodes[k]], tb = av[nodes[k + 1]][0];
      if (va < MIN_AV || !pnl.has(ta) || !pnl.has(tb)) continue;
      rets.push([(pnl.get(tb) - pnl.get(ta)) / va, (tb - ta) / WEEK_MS]);
      counted += pnl.get(tb) - pnl.get(ta);
    }
    return {rets, start, end, counted};
  }

  function score(rets) {
    const n = rets.length;
    if (n < MIN_WEEKS) return {weeks: n, sharpe: null, t: null};
    let R = 0, W = 0;
    for (const [r, w] of rets) { R += r; W += w; }
    const mu = R / W;
    let ss = 0;
    for (const [r, w] of rets) ss += (r - mu * w) ** 2;
    if (ss === 0 || W <= 0) return {weeks: n, sharpe: null, t: null};
    const sharpe = mu / Math.sqrt(ss / W) * Math.sqrt(52);
    return {weeks: Math.round(W * 10) / 10, intervals: n, sharpe: Math.round(sharpe * 1000) / 1000, t: Math.round(R / Math.sqrt(ss) * 1000) / 1000};
  }

  // Things t cannot see, reported next to it. Same rules as flags() in the Python builder.
  function flags(pf, rets, counted) {
    const out = [];
    if (rets.length >= MIN_WEEKS) {
      if (!rets.some(([r]) => r < 0)) out.push('no_losing_week');
      const gains = rets.map(([r]) => r).filter(r => r > 0), tot = gains.reduce((s, r) => s + r, 0);
      const net = rets.reduce((a, [r]) => a + r, 0);
      if (net > 0 && gains.length && Math.max(...gains) / tot > 0.5) out.push('one_week_majority');
    }
    const ph = Object.fromEntries(pf).allTime.pnlHistory;
    const total = ph.length ? +ph[ph.length - 1][1] - +ph[0][1] : 0;
    if (total > 0 && (total - counted) / total > 0.5) out.push('pnl_outside_record');
    return out;
  }

  function verdict(sc, leaderboardN) {
    const lb = bar(leaderboardN);
    if (sc.t == null) return {key: 'too_short', bar: lb};
    if (sc.t >= lb) return {key: 'clears_board', bar: lb};
    if (sc.t >= 2) return {key: 'clears_single', bar: lb};
    if (sc.t <= -2) return {key: 'loses', bar: lb};
    return {key: 'luck', bar: lb};
  }

  async function fetchPortfolio(addr) {
    const r = await fetch('https://api.hyperliquid.xyz/info', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type: 'portfolio', user: addr})});
    if (!r.ok) throw new Error('Hyperliquid API returned ' + r.status);
    return r.json();
  }

  return {WEEK_MS, MIN_WEEKS, bar, monthsToClear, weeklyReturns, score, flags, verdict, fetchPortfolio, cdf, inv};
})();
if (typeof module !== 'undefined') module.exports = HL;
