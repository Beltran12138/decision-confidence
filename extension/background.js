// Service worker: scores on request from the popup and the page panel, and adds a right-click
// "Check with Evidence Deflator" for selected text or links that contain a Hyperliquid address.
importScripts('hl.js', 'score.js');

const ADDR = /0x[0-9a-fA-F]{40}/;
const cache = new Map();  // per worker lifetime; the worker sleeps after ~30 s idle, which clears it

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.type !== 'score') return;
  const key = msg.venue + ':' + msg.id;
  if (!cache.has(key)) {
    const fn = {hl: SCORE.hyperliquid, binance: SCORE.binance, okx: SCORE.okx}[msg.venue];
    cache.set(key, fn ? fn(msg.id) : Promise.resolve({error: 'unknown venue'}));
  }
  cache.get(key).then(reply, e => { cache.delete(key); reply({error: String(e && e.message || e)}); });
  return true;  // async reply
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({id: 'ed-check', title: 'Check with Evidence Deflator', contexts: ['selection', 'link']});
});

chrome.contextMenus.onClicked.addListener(info => {
  const m = (info.selectionText || '').match(ADDR) || (info.linkUrl || '').match(ADDR);
  const url = m ? 'https://evidencedeflator.com/wallet/?a=' + m[0].toLowerCase() : 'https://evidencedeflator.com/wallet/';
  chrome.tabs.create({url});
});
