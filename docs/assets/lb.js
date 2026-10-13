// Leaderboard rendering shared by the home page and /leaderboard/.
const LB = (() => {
  const fmt = (x, d = 2) => x == null ? '—' : Number(x).toFixed(d);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const span = m => m >= 24 ? (m / 12).toFixed(1) + ' years' : Math.round(m) + ' months';

  // t of every entry on one axis, with the single-test and best-of-N bars.
  function strip(b, o = {}) {
    const pts = b.rows.filter(r => r.t != null);
    const W = 1000, H = o.h || 150, L = 16, R = 16, top = 38, bot = H - 26;
    const lo = Math.min(-1, Math.floor(Math.min(...pts.map(r => r.t)))),
          hi = Math.max(Math.ceil(b.t_bar_best_of_n + 0.3), ...pts.map(r => r.t));
    const x = v => L + (v - lo) / (hi - lo) * (W - L - R);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(b.board)}: t-statistic of each entry against the bars">`;
    s += `<rect class="zone" x="${x(b.t_bar_best_of_n)}" y="${top}" width="${W - R - x(b.t_bar_best_of_n)}" height="${bot - top}"/>` + (W - R - x(b.t_bar_best_of_n) > 170 ? `<text class="zonelab" x="${W - R - 8}" y="${bot - 8}" text-anchor="end">a winner would sit here</text>` : '');
    for (let v = lo; v <= hi; v++)
      s += `<line class="ax" x1="${x(v)}" x2="${x(v)}" y1="${top}" y2="${bot}"/><text class="lab" x="${x(v)}" y="${H - 8}" text-anchor="middle">${v === 0 ? 't = 0' : v}</text>`;
    s += `<line class="t2" x1="${x(2)}" x2="${x(2)}" y1="${top - 22}" y2="${bot}"/><text class="t2lab" x="${x(2) - 6}" y="${top - 12}" text-anchor="end">t = 2 · one test</text>`;
    s += `<line class="bar" x1="${x(b.t_bar_best_of_n)}" x2="${x(b.t_bar_best_of_n)}" y1="${top - 22}" y2="${bot}"/><text class="barlab" x="${x(b.t_bar_best_of_n) - 6}" y="${top - 12 + 0}" text-anchor="end" dy="${x(b.t_bar_best_of_n) - x(2) < 190 ? 14 : 0}">best of ${b.entries.toLocaleString('en')} · ${fmt(b.t_bar_best_of_n)}</text>`;
    const span = bot - top - 16;
    pts.forEach((r, i) => {
      const y = top + 8 + ((i * 47) % 97) / 97 * span, best = r.rank === b.max_t_rank;
      s += `<circle class="pt${best ? ' best' : ''}" cx="${x(r.t)}" cy="${y}" r="${best ? 6 : 4.5}"><title>#${r.rank} ${esc(r.name)} · t = ${fmt(r.t)}</title></circle>`;
      if (best && o.label !== false) s += `<text class="lab" x="${x(r.t) + 10}" y="${y + 4}" style="fill:var(--ink)">${esc(r.name)} ${fmt(r.t)}</text>`;
    });
    return s + '</svg>';
  }

  function table(b, by, all) {
    let rows = [...b.rows].sort(by === 't' ? (p, q) => (q.t ?? -99) - (p.t ?? -99) : (p, q) => p.rank - q.rank);
    if (!all) rows = rows.slice(0, 15);
    const scale = b.t_bar_best_of_n;
    let h = '<thead><tr><th class="r">Rank</th><th>Entry</th><th class="r">Return</th><th class="r">Days</th><th class="r">Sharpe</th><th class="r">t</th><th>Share of the bar</th></tr></thead><tbody>';
    rows.forEach(r => {
      let bar = '<span class="muted small">no history published</span>';
      if (r.t != null) {
        const w = Math.min(Math.abs(r.t) / scale, 1) * 100;
        bar = `<span class="mbar"><span class="track"><span class="fill${r.t < 0 ? ' neg' : ''}" style="width:${w.toFixed(1)}%"></span><span class="t2" style="left:${(2 / scale * 100).toFixed(1)}%"></span></span><span>${Math.round(r.t / scale * 100)}%</span></span>`;
      }
      h += `<tr${r.rank === b.max_t_rank ? ' class="hl"' : ''}><td class="r">${r.rank}</td><td>${esc(r.name)}</td><td class="r">${fmt(r.return_pct, 1)}%</td><td class="r">${r.days ?? '—'}</td><td class="r">${fmt(r.sharpe)}</td><td class="r">${fmt(r.t)}</td><td>${bar}</td></tr>`;
    });
    return h + '</tbody>';
  }

  const load = (url) => fetch(url).then(r => r.json());
  return {fmt, esc, span, strip, table, load};
})();
