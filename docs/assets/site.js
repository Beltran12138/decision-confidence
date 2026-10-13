// Small shared behaviours: copy-to-clipboard and tab groups.
document.addEventListener('click', e => {
  const c = e.target.closest('[data-copy]');
  if (c) {
    navigator.clipboard && navigator.clipboard.writeText(c.dataset.copy).then(() => {
      c.classList.add('done'); setTimeout(() => c.classList.remove('done'), 1600);
    });
    return;
  }
  const t = e.target.closest('.tabs button');
  if (t) {
    const g = t.closest('[data-tabs]');
    g.querySelectorAll('.tabs button').forEach(b => b.setAttribute('aria-selected', b === t));
    g.querySelectorAll('[data-pane]').forEach(p => p.hidden = p.dataset.pane !== t.dataset.tab);
  }
});
