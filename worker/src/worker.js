// Evidence Deflator API: remote MCP (Streamable HTTP, stateless) and a JSON endpoint.
// Built by tools/build_worker.py, which prepends docs/assets/hl.js, so `HL` is the same
// scoring the browser runs. src/hl_wallet.py is the Python twin; tools/check_worker.py diffs them.
//
//   GET  /api/wallet?a=0x...&picked_from=47153   -> JSON verdict
//   POST /mcp                                     -> MCP JSON-RPC (initialize, tools/list, tools/call)

const SITE = 'https://evidencedeflator.com';
const SERVER = {name: 'evidence-deflator', version: '0.3.0'};
const ADDR = /^0x[0-9a-fA-F]{40}$/;

function verdict(sc, pickedFrom) {
  // Same keys and bars as verdict() in src/hl_wallet.py.
  const board = pickedFrom && pickedFrom > 1;
  const bar = board ? HL.bar(pickedFrom) : 2;
  const t = sc.t;
  let key;
  if (t == null) key = 'too_short';
  else if (board && t >= bar) key = 'clears_board';
  else if (t >= 2) key = 'clears_single';
  else if (t <= -2) key = 'loses';
  else key = 'luck';
  return {key, bar: Math.round(bar * 100) / 100};
}

const day = ms => (ms == null ? null : new Date(ms).toISOString().slice(0, 10));

function checkWallet(address, pickedFrom, pf) {
  const w = HL.weeklyReturns(pf), sc = HL.score(w.rets), v = verdict(sc, pickedFrom);
  const months = sc.sharpe ? HL.monthsToClear(v.bar, sc.sharpe) : null;
  const have = sc.t != null ? (sc.weeks || 0) / 4.345 : 0;
  return {
    address, ...sc, verdict: v.key, bar: v.bar, picked_from: pickedFrom ?? null,
    months_more_to_clear: months == null ? null : Math.round(Math.max(months - have, 0) * 10) / 10,
    flags: HL.flags(pf, w.rets, w.counted),
    history_from: day(w.start), history_to: day(w.end),
    page: `${SITE}/wallet/?a=${address}`,
  };
}

async function walletFromApi(address, pickedFrom) {
  if (!ADDR.test(address || '')) throw new RangeError('address must be 0x followed by 40 hex characters');
  const pf = await HL.fetchPortfolio(address.toLowerCase());
  if (!Array.isArray(pf) || !pf.length) throw new RangeError('no portfolio history for ' + address);
  return checkWallet(address.toLowerCase(), pickedFrom, pf);
}

const TOOL = {
  name: 'hyperliquid_wallet',
  title: 'Hyperliquid wallet: skill or luck?',
  description:
    "Is this Hyperliquid wallet's record skill, or could it be luck? Call before recommending, ranking or copying a " +
    'Hyperliquid trader, or when a PnL or leaderboard rank is cited as evidence. Scores weekly returns from public ' +
    'history (PnL-based, so deposits do not count). Ask how the user found the wallet: if from a leaderboard, pass ' +
    'its size as picked_from (Hyperliquid ranks about 47,000 accounts); omitting it drops the bar from about 4.9 to 2. ' +
    'Verdicts: too_short (say "cannot tell yet", not "no skill"), luck, clears_single, clears_board, loses. ' +
    'Always report the flags with the verdict. A past record is not the user\'s future returns.',
  inputSchema: {
    type: 'object',
    properties: {
      address: {type: 'string', description: 'Wallet address, 0x followed by 40 hex characters'},
      picked_from: {type: 'integer', minimum: 1, description: 'How many wallets it was chosen from (leaderboard size if found on one)'},
    },
    required: ['address'],
  },
  annotations: {readOnlyHint: true, openWorldHint: true},
};

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Accept, Mcp-Session-Id, Mcp-Protocol-Version',
};
const json = (body, status = 200) =>
  new Response(JSON.stringify(body, null, 2), {status, headers: {'Content-Type': 'application/json', ...CORS}});

async function rpc(msg) {
  const {id, method, params} = msg;
  const ok = result => ({jsonrpc: '2.0', id, result});
  const err = (code, message) => ({jsonrpc: '2.0', id, error: {code, message}});
  if (method === 'initialize') {
    return ok({protocolVersion: params?.protocolVersion || '2025-06-18', capabilities: {tools: {}}, serverInfo: SERVER,
               instructions: 'Evidence checks for trading records. Docs: ' + SITE + '/method/'});
  }
  if (method === 'ping') return ok({});
  if (method === 'tools/list') return ok({tools: [TOOL]});
  if (method === 'tools/call') {
    if (params?.name !== TOOL.name) return err(-32602, 'unknown tool: ' + params?.name);
    const a = params.arguments || {};
    try {
      const r = await walletFromApi(a.address, a.picked_from);
      return ok({content: [{type: 'text', text: JSON.stringify(r, null, 2)}], structuredContent: r, isError: false});
    } catch (e) {
      return ok({content: [{type: 'text', text: String(e.message || e)}], isError: true});
    }
  }
  return err(-32601, 'method not found: ' + method);
}

async function handle(request, env = {}) {
  const url = new URL(request.url);
  if (request.method === 'OPTIONS') return new Response(null, {status: 204, headers: CORS});

  // OpenAI plugin directory domain check: serve exactly the token the portal issued (a plain var, not a secret).
  if (url.pathname === '/.well-known/openai-apps-challenge') {
    return env.OPENAI_APPS_CHALLENGE ? new Response(env.OPENAI_APPS_CHALLENGE, {headers: {'Content-Type': 'text/plain'}}) : json({error: 'not found'}, 404);
  }

  if (url.pathname === '/api/wallet' && request.method === 'GET') {
    const pf = url.searchParams.get('picked_from');
    try {
      return json(await walletFromApi(url.searchParams.get('a') || url.searchParams.get('address'), pf ? parseInt(pf, 10) : null));
    } catch (e) {
      return json({error: String(e.message || e)}, e instanceof RangeError ? 400 : 502);
    }
  }

  if (url.pathname === '/mcp') {
    if (request.method !== 'POST') return new Response('Use POST (MCP Streamable HTTP, stateless).', {status: 405, headers: {Allow: 'POST', ...CORS}});
    let body;
    try { body = await request.json(); } catch { return json({jsonrpc: '2.0', id: null, error: {code: -32700, message: 'parse error'}}, 400); }
    const batch = Array.isArray(body) ? body : [body];
    const replies = [];
    for (const m of batch) if (m && m.id !== undefined && m.method) replies.push(await rpc(m));
    if (!replies.length) return new Response(null, {status: 202, headers: CORS});  // notifications only
    return json(Array.isArray(body) ? replies : replies[0]);
  }

  if (url.pathname === '/') {
    return json({service: 'Evidence Deflator API', mcp: url.origin + '/mcp', wallet: url.origin + '/api/wallet?a=0x...',
                 docs: SITE + '/api/', source: 'https://github.com/Beltran12138/evidence-deflator'});
  }
  return json({error: 'not found'}, 404);
}

export default {fetch: handle};
export {checkWallet, verdict, rpc};
