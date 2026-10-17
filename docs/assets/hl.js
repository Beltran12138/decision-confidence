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

  // Student's t tail via the regularized incomplete beta, as in the Python builder.
  function lgamma(x) {  // Lanczos, g = 7
    const g = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059,
      12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
    if (x < 0.5) return Math.log(Math.PI / Math.abs(Math.sin(Math.PI * x))) - lgamma(1 - x);
    x -= 1;
    let a = g[0];
    const t = x + 7.5;
    for (let i = 1; i < 9; i++) a += g[i] / (x + i);
    return 0.5 * Math.log(2 * Math.PI) + (x + 0.5) * Math.log(t) - t + Math.log(a);
  }
  function betacf(a, b, x) {
    const tiny = 1e-300, qab = a + b, qap = a + 1, qam = a - 1;
    let c = 1, d = 1 - qab * x / qap;
    d = 1 / (Math.abs(d) > tiny ? d : tiny);
    let h = d;
    for (let m = 1; m < 300; m++) {
      const m2 = 2 * m;
      for (const aa of [m * (b - m) * x / ((qam + m2) * (a + m2)), -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))]) {
        d = 1 + aa * d; d = 1 / (Math.abs(d) > tiny ? d : tiny);
        c = 1 + aa / c; c = Math.abs(c) > tiny ? c : tiny;
        h *= d * c;
      }
      if (Math.abs(d * c - 1) < 1e-15) break;
    }
    return h;
  }
  function betai(a, b, x) {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    const bt = Math.exp(lgamma(a + b) - lgamma(a) - lgamma(b) + a * Math.log(x) + b * Math.log(1 - x));
    return x < (a + 1) / (a + b + 2) ? bt * betacf(a, b, x) / a : 1 - bt * betacf(b, a, 1 - x) / b;
  }
  // Normal score with the same tail probability as Student's t with `dof` degrees of freedom.
  function tToZ(t, dof) {
    if (t === 0) return 0;
    const p = 0.5 * betai(dof / 2, 0.5, dof / (dof + t * t));
    return Math.sign(t) * -inv(Math.max(p, 1e-300));
  }

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
    let ss = 0, s2 = 0, s3 = 0;
    for (const [r, w] of rets) { ss += (r - mu * w) ** 2; s2 += w * w; s3 += w ** 3; }
    const eff = W - s2 / W;  // n - 1 correction for unequal intervals
    if (ss === 0 || W <= 0 || eff <= 0) return {weeks: n, sharpe: null, t: null};
    const sigma = Math.sqrt(ss / eff), sharpe = mu / sigma * Math.sqrt(52), tStudent = R / (sigma * Math.sqrt(W));
    const dof = eff ** 2 / (s2 - 2 * s3 / W + s2 * s2 / W ** 2);  // Satterthwaite
    const r3 = x => Math.round(x * 1000) / 1000;
    return {weeks: Math.round(W * 10) / 10, intervals: n, sharpe: r3(sharpe), t_student: r3(tStudent),
            dof: Math.round(dof * 10) / 10, t: r3(tToZ(tStudent, dof))};
  }

  // Where the record stands against its own peak, and how ordinary that is if its edge is real.
  // The path adds up the scored weekly returns (the same arithmetic returns t is built from; most
  // accounts add and withdraw money, so compounding would describe a portfolio nobody held). For a
  // path drifting at m per week with variance s2 per week, the distance below the running peak
  // settles to an exponential with rate 2m/s2, so
  // the share of time spent at least d below the peak is exp(-2 m d / s2). Measured weekly, the
  // walk overshoots the peak between samples; Siegmund's correction (d + 0.5826 s) keeps the share
  // within about 2% of simulation up to Sharpe 3, where the plain formula is 1.6x too high.
  // m and s2 are measured on the same record (same estimator as score). Same as drawdown() in
  // src/hl_wallet.py.
  const SIEGMUND = 0.5826;  // -zeta(1/2) / sqrt(2 pi)
  function drawdown(rets) {
    const n = rets.length;
    if (n < MIN_WEEKS) return null;
    let w = 0, peak = 0, maxDd = 0, since = 0, R = 0, W = 0;
    for (const [r, dt] of rets) {
      w += r; R += r; W += dt;
      if (w >= peak) { peak = w; since = 0; } else since += dt;
      maxDd = Math.max(maxDd, peak - w);
    }
    const mu = R / W;
    let ss = 0, s2 = 0;
    for (const [r, dt] of rets) { ss += (r - mu * dt) ** 2; s2 += dt * dt; }
    const eff = W - s2 / W, v = eff > 0 ? ss / eff : 0, m = mu, d = peak - w;
    const r4 = x => Math.round(x * 1e4) / 1e4;
    return {now: r4(d), weeks_below: Math.round(since * 10) / 10, deepest: r4(maxDd),
            share_if_real: !(m > 0 && v > 0) ? null : d === 0 ? 1 : r4(Math.exp(-2 * m * (d + SIEGMUND * Math.sqrt(v)) / v))};
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

  // Vault details, or null when the address is not a vault (the API answers null). The portfolio
  // endpoint already returns a vault's own PnL history, so scoring is unchanged; this only says
  // what the address is and which board it was picked from.
  async function fetchVault(addr) {
    try {
      const r = await fetch('https://api.hyperliquid.xyz/info', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({type: 'vaultDetails', vaultAddress: addr})});
      return r.ok ? await r.json() : null;
    } catch (e) { return null; }
  }

  return {WEEK_MS, MIN_WEEKS, bar, monthsToClear, weeklyReturns, score, drawdown, flags, verdict, fetchPortfolio, fetchVault, cdf, inv, tToZ};
})();
if (typeof module !== 'undefined') module.exports = HL;
