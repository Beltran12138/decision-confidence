// Shared rendering for the popup and the page panel: one result object in, HTML out.
const ED_VIEW = (() => {
  const SAY = {
    loses: ['Losing, and not by chance', 'red', 't is −2 or lower: it lost too consistently for luck to explain.'],
    luck: ['Cannot be told apart from luck', 'red', 't is below 2: a record like this turns up by chance often enough that it says little about skill.'],
    clears_single: ['Passes one test, not the board bar', 'amber', 'Strong enough if picked blind. Found on a leaderboard, it needs t ≥ {BAR}.'],
    clears_board: ['Clears the board bar', 'green', 'Strong enough even allowing for having been picked from {N} {U}.'],
    too_short: ['Too short to say', 'grey', 'Fewer than 8 weeks of record that can be measured.'],
  };
  const FLAGS = {no_losing_week: 'No losing week: consistent with market making or selling tail risk.',
                 one_week_majority: 'One week produced more than half the gains.',
                 pnl_outside_record: 'Most PnL was booked on a near-empty account; t covers only the measurable weeks.'};
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const f = (x, d = 2) => x == null ? '—' : Number(x).toFixed(d);

  function html(r) {
    if (r.error) return `<div class="ed-h">Could not check</div><div class="ed-s">${esc(r.error)}</div>`;
    const [title, tone, sub] = SAY[r.verdict];
    const n = Number(r.n).toLocaleString('en');
    let months = '—';
    if (r.sharpe != null && r.months != null) {
      const more = Math.max(r.months - (r.weeks || 0) / 4.345, 0);
      months = more === 0 ? '0' : more >= 1188 ? '> 99 yr' : more >= 24 ? (more / 12).toFixed(1) + ' yr' : Math.round(more) + ' mo';
    } else if (r.sharpe != null) months = 'never';
    return `<div class="ed-tag ed-${tone}">${esc(r.verdict.replace('_', ' '))}</div>
<div class="ed-h">${esc(title)}</div>
${r.name ? `<div class="ed-s">Vault: ${esc(r.name)}</div>` : ''}
<div class="ed-s">${esc(sub.replace('{BAR}', f(r.bar)).replace('{N}', n).replace('{U}', r.unit))}</div>
<div class="ed-grid"><div><b>${f(r.t)}</b><span>t</span></div><div><b>${f(r.bar)}</b><span>bar, best of ${esc(n)}</span></div>
<div><b>${r.weeks ?? '—'}</b><span>weeks</span></div><div><b>${months}</b><span>more to clear</span></div></div>
${(r.flags || []).map(k => `<div class="ed-flag">${esc(FLAGS[k] || k)}</div>`).join('')}
${r.note ? `<div class="ed-flag">${esc(r.note)}</div>` : ''}
<a class="ed-link" href="${esc(r.link)}" target="_blank" rel="noopener">How this is computed →</a>`;
  }

  const CSS = `.ed-tag{display:inline-block;font:600 11px/1 system-ui;text-transform:uppercase;letter-spacing:.04em;padding:4px 7px;border-radius:4px;margin-bottom:8px}
.ed-red{background:#fbe4df;color:#a5321a}.ed-amber{background:#fbf0d6;color:#8a5a00}.ed-green{background:#dff3e4;color:#1d6b35}.ed-grey{background:#eceae5;color:#555}
.ed-h{font:600 16px/1.3 Georgia,serif;margin:0 0 6px}.ed-s{font:13px/1.45 system-ui;color:#555;margin:0 0 8px}
.ed-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0}.ed-grid div{background:#f4f2ee;border-radius:6px;padding:8px}
.ed-grid b{display:block;font:600 18px/1.1 ui-monospace,Consolas,monospace}.ed-grid span{font:11px system-ui;color:#666}
.ed-flag{font:12px/1.4 system-ui;color:#444;border-left:3px solid #e66a4b;padding-left:8px;margin:6px 0}
.ed-link{display:inline-block;margin-top:6px;font:13px system-ui;color:#15171c}`;
  return {html, CSS};
})();
