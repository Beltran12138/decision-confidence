"""Build the static site in docs/ from one template.

    python tools/build_site.py

Writes: index.html (home), wallet/index.html (from data/hl/latest.json), leaderboard/index.html, method/index.html,
audits/index.html + one page per audits/NNN-*.md, api/index.html, 404.html.
Hand-maintained pages (HAND_PAGES: the calculator, which carries a JS port of
the library that tools/check_js_parity.py diffs, and three older pages) only get
their marked head, header and footer blocks refreshed.
Needs the `markdown` package for the audit pages; nothing at runtime.
"""
import hashlib, html, json, os, re

import markdown

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DOCS = os.path.join(ROOT, "docs")
SITE = "https://evidencedeflator.com"
REPO = "https://github.com/Beltran12138/evidence-deflator"
TG_BOT = "https://t.me/SkillOrLuckBot"
EXT_URL = REPO + "/tree/main/extension"  # switch to the Chrome Web Store page once the listing is approved
ELSEWHERE_EN = (f'<p class="muted small elsewhere">Also on <a href="{TG_BOT}" rel="noopener">Telegram, @SkillOrLuckBot</a> (send an address, get the verdict), '
                f'and as a <a href="{EXT_URL}" rel="noopener">Chrome extension</a> that shows it on Hyperliquid, Binance and OKX copy-trading pages (in Chrome Web Store review; install from GitHub for now).</p>')
ISSUE_AUDIT = REPO + "/issues/new?title=Audit%20request%3A%20&body=Link%20to%20the%20backtest%2C%20deck%20or%20claim%3A%0A%0AModel%20(if%20known)%3A%0ATest%20window%3A%0AHow%20many%20variants%20were%20tried%3A%0A"
VERSION = "0.2.0"
# Cloudflare Web Analytics site token (public, cookie-less page counts). Empty = no beacon.
CF_BEACON = "e38b718917cf4c2891f9038a6a597a88"
# Baidu Search Resource Platform site verification (public token; keep it, or the site unverifies).
BAIDU_META = '<meta name="baidu-site-verification" content="codeva-Dwaytu2snb" />\n'
PRIVACY = ("The address is never sent to us. We count page views without cookies (Cloudflare Web Analytics), and each check as one tally with the page language and nothing else."
           if CF_BEACON else "Nothing is sent to us.")
BEACON = (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
          f'data-cf-beacon=\'{{"token": "{CF_BEACON}", "spa": true}}\'></script>\n') if CF_BEACON else ""

MARK = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="3" width="20" height="2.2" fill="var(--accent)"/>'
        '<rect x="3.5" y="13" width="3.2" height="8" fill="currentColor"/><rect x="8.6" y="9" width="3.2" height="12" fill="currentColor"/>'
        '<rect x="13.7" y="15" width="3.2" height="6" fill="currentColor"/><rect x="18.8" y="7.5" width="3.2" height="13.5" fill="currentColor" opacity=".55"/></svg>')
GH = ('<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>')
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='4' fill='%2315171C'/%3E"
           "%3Crect x='3' y='4' width='18' height='2' fill='%23E66A4B'/%3E%3Crect x='4.5' y='13' width='3' height='7' fill='%23FAF9F6'/%3E"
           "%3Crect x='9.5' y='9.5' width='3' height='10.5' fill='%23FAF9F6'/%3E%3Crect x='14.5' y='15' width='3' height='5' fill='%23FAF9F6'/%3E%3C/svg%3E")

NAV = [("wallet", "Check a wallet", "/wallet/"), ("leaderboard", "Leaderboard", "/leaderboard/"), ("audits", "Audits", "/audits/"),
       ("check", "Check a backtest", "/check/"), ("method", "Method", "/method/"), ("api", "API", "/api/")]

COPY_ICON = '<span class="cp">copy</span><span class="ok">copied</span>'


def ld(obj):
    """schema.org JSON-LD block for head(extra=...)."""
    data = json.dumps({"@context": "https://schema.org", **obj}, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{data}</script>\n'


APP_LD = {"@type": "SoftwareApplication", "name": "Evidence Deflator", "url": SITE + "/",
          "applicationCategory": "FinanceApplication", "operatingSystem": "Web, Python, MCP",
          "description": "Checks whether a trading record, such as a Hyperliquid wallet or a leaderboard winner, can be told apart from luck once you allow for how it was picked.",
          "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
          "license": "https://opensource.org/licenses/MIT", "codeRepository": REPO, "sameAs": [REPO]}


def hreflang(alt):
    """<link rel=alternate> for each language version; alt maps hreflang -> path."""
    if not alt:
        return ""
    links = [*alt.items(), ("x-default", alt["en"])]
    return "".join(f'<link rel="alternate" hreflang="{k}" href="{SITE}{v}">\n' for k, v in links)


def head(title, desc, path, og=f"{SITE}/leaderboard/og-2026-10.png", extra="", lang="en", alt=None):
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{SITE}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Evidence Deflator">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:image" content="{og}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{FAVICON}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap">
<link rel="stylesheet" href="{asset("chrome.css")}">
<link rel="stylesheet" href="{asset("site.css")}">
{hreflang(alt)}{extra}{BEACON}</head>
<body>
"""


def header(active, alt=None):
    cur = ' aria-current="page"'
    links = "".join(f'<a href="{u}"{cur if k == active else ""}>{t}</a>' for k, t, u in NAV)
    zh = (alt or {}).get("zh-Hans", "/zh-hans/")
    return f"""<header class="site-header"><div class="container">
<a class="brand" href="/">{MARK}Evidence Deflator</a>
<nav class="nav" aria-label="Main">{links}</nav>
<div class="header-cta"><a class="gh" href="{zh}" hreflang="zh-Hans" lang="zh-Hans">中文</a><a class="gh" href="{REPO}">{GH}<span>GitHub</span></a></div>
</div></header>
"""


def footer(scripts=""):
    return f"""<footer class="site-footer"><div class="container">
<div class="foot-grid">
 <div><a class="brand" href="/">{MARK}Evidence Deflator</a>
  <p style="margin-top:14px;max-width:340px">How much of an AI trading result actually counts. Open-source checks for backtests and public leaderboards.</p></div>
 <div><h4>Product</h4><ul><li><a href="/wallet/">Check a wallet</a></li><li><a href="/leaderboard/">Leaderboard</a></li><li><a href="/audits/">Audits</a></li><li><a href="/check/">Check a backtest</a></li><li><a href="/api/">API</a></li></ul></div>
 <div><h4>Method</h4><ul><li><a href="/method/">How it works</a></li><li><a href="/method/#principles">Principles</a></li><li><a href="/q/hyperliquid-trader-skill-or-luck/">Skill or luck?</a></li><li><a href="/q/how-many-months-of-backtest/">How many months?</a></li><li><a href="/q/why-leaderboard-winner-is-not-evidence/">Why #1 is not evidence</a></li><li><a href="/leaderboard/2026-10.json">Data (JSON)</a></li></ul></div>
 <div><h4>Project</h4><ul><li><a href="{REPO}">GitHub</a></li><li><a href="https://pypi.org/project/evidence-deflator/">PyPI</a></li><li><a href="{ISSUE_AUDIT}">Request an audit</a></li><li><a href="/privacy/">Privacy</a></li><li><a href="/terms/">Terms</a></li></ul></div>
</div>
<div class="foot-note"><span>Open source · MIT · v{VERSION}</span><span>“Cannot be ruled out as seen” is the strongest claim we make about a model’s training data.</span></div>
</div></footer>
<script src="/assets/site.js"></script>
{scripts}</body>
</html>
"""


def ic(text):
    """Escape, then render `inline code` from the markdown sources."""
    return re.sub(r"`([^`]+)`", lambda m: "<code>" + m.group(1) + "</code>", html.escape(text))


def write(rel, text):
    p = os.path.join(DOCS, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("wrote", rel, len(text))


# ---------------------------------------------------------------- audits

AUDIT_TAGS = {  # short status shown in lists; the finding text comes from audits/README.md
    "001": ("Cannot assess", "grey"), "002": ("Narrowed comparison", "amber"),
    "003": ("0 of 41 reach t = 2", "red"), "004": ("88% open-book", "red"), "005": ("Cannot assess", "grey"),
    "006": ("0 of 6 reach |t| = 2", "red"),
    "007": ("0 of 180 clear the bar", "red"),
    "008": ("0 of 38 clear the bar", "red"),
    "009": ("Cannot assess", "grey"),
    "010": ("Frozen, readings 10-23 / 10-30", "grey"),
}


def audits():
    with open(os.path.join(DOCS, "audits", "README.md"), encoding="utf-8") as f:
        readme = f.read()
    rows = []
    for m in re.finditer(r"^\| \[(\d{3})\]\(([^)]+)\.md\) \| (.+?) \| (\d{4}-\d{2}-\d{2}) \| (.+?) \|$", readme, re.M):
        num, slug, subject, date, finding = m.groups()
        rows.append(dict(num=num, slug=slug, subject=subject, date=date, finding=finding))
    return rows


def md_to_html(text):
    text = re.sub(r"\]\((\d{3}-[a-z0-9-]+)\.md\)", r"](/audits/\1.html)", text)
    text = text.replace("](../../README.md)", f"]({REPO})").replace("](../leaderboard/2026-10.md)", "](/leaderboard/)")
    return markdown.markdown(text, extensions=["tables", "fenced_code"])


def build_audits():
    rows = audits()
    for i, a in enumerate(rows):
        with open(os.path.join(DOCS, "audits", a["slug"] + ".md"), encoding="utf-8") as f:
            src = f.read()
        title_line = src.splitlines()[0].lstrip("# ").strip()
        body = md_to_html("\n".join(src.splitlines()[1:]))
        tag, colour = AUDIT_TAGS.get(a["num"], ("", "grey"))
        prev = rows[i - 1] if i > 0 else None
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        nav = ""
        if prev: nav += f'<li><a href="/audits/{prev["slug"]}.html">← {prev["num"]} · {html.escape(prev["subject"])}</a></li>'
        if nxt: nav += f'<li><a href="/audits/{nxt["slug"]}.html">{nxt["num"]} · {html.escape(nxt["subject"])} →</a></li>'
        page = head(f"Audit {a['num']} · {a['subject'].replace('`', '')} · Evidence Deflator", a["finding"].replace('`', ''), f"/audits/{a['slug']}.html") + header("audits") + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><a href="/audits/" style="text-decoration:none">Audits</a> / {a['num']}</div>
<h1 style="margin-top:16px">{ic(a['subject'])}</h1>
<div class="meta"><span class="tag tag-{colour}">{html.escape(tag)}</span><span class="mono">{a['date']}</span><span>Sources public, fetched on the stated date</span></div>
<div class="callout" style="margin-top:0"><div class="eyebrow" style="margin-bottom:10px">Finding</div>{ic(a['finding'])}</div>
{body}
</article>
<aside class="aside">
 <div class="box"><h4>Three inputs</h4><ul><li>The model’s knowledge cutoff</li><li>The test window</li><li>How many attempts the result was picked from</li></ul></div>
 <div class="box"><h4>Rules</h4><ul><li>Numbers recomputed, not copied</li><li>A missing input is a finding, not a verdict</li><li>No judgement of intent</li></ul></div>
 <div class="box"><h4>More audits</h4><ul>{nav}<li><a href="/audits/">All audits</a></li></ul></div>
 <a class="btn btn-secondary" href="{ISSUE_AUDIT}">Request an audit</a>
</aside>
</div></main>
""" + footer()
        write(f"audits/{a['slug']}.html", page)

    items = "".join(f"""<a class="row" href="/audits/{a['slug']}.html"><span class="row-date">{a['num']} · {a['date']}</span>
<span><span class="row-title">{ic(a['subject'])}</span><span class="row-sub" style="display:block">{ic(a['finding'])}</span></span>
<span class="tag tag-{AUDIT_TAGS.get(a['num'], ('', 'grey'))[1]}">{html.escape(AUDIT_TAGS.get(a['num'], ('', ''))[0])}</span></a>""" for a in rows)
    page = head("Audits · Evidence Deflator", "One-page evidence audits of public AI trading claims: how much of the evidence behind each claim actually counts.", "/audits/") + header("audits") + f"""
<main>
<div class="container page-head">
 <div class="eyebrow"><span class="dot"></span>Audits</div>
 <h1>One page per claim. How much of the evidence counts?</h1>
 <p class="lede">Each audit takes a public AI trading claim and asks for three inputs: the model’s knowledge cutoff, the test window, and how many attempts the result was picked from. Where a project does not publish them, the audit says so.</p>
 <div class="btns" style="margin-top:26px"><a class="btn btn-primary" href="{ISSUE_AUDIT}">Request an audit <span class="arr">→</span></a><span class="muted small">Free, public, usually within 48 hours.</span></div>
</div>
<div class="container" style="padding-bottom:72px">
 <div class="rows">{items}
 <a class="row" href="/case-nuclear.html"><span class="row-date">Case audit · 2026-10-06</span><span><span class="row-title">A “22% chance of a nuclear detonation” on Polymarket</span><span class="row-sub" style="display:block">Five discounts on one prediction-market price: about 16 effective wallets, and a contract that also counts tests.</span></span><span class="tag tag-amber">Wrong question</span></a>
 <a class="row" href="/audit.html"><span class="row-date">Paper audit · 2026-10-05</span><span><span class="row-title">17 published LLM trading papers</span><span class="row-sub" style="display:block">Of the 9 with a documented cutoff, none reaches 48 clean months.</span></span><span class="tag tag-red">0 of 9 reach 48 months</span></a>
 </div>
 <div class="callout" style="margin-top:40px"><h3 style="margin-bottom:8px">Rules every audit follows</h3>
 <p class="muted" style="margin:0">Sources are public and fetched on the stated date; numbers are recomputed, not copied. “Cannot be ruled out as seen” is the strongest claim made about a model’s training data, never “contaminated”. Findings state what the numbers can and cannot support, with no judgement of intent. Short is not the same as wrong: an underpowered result has not been shown to fail, only not shown to work.</p></div>
</div>
</main>
""" + footer()
    write("audits/index.html", page)
    return rows


# ---------------------------------------------------------------- home

def boards_html(hl):
    """One row per public board we have rescored: how many of its top clear the bar for being picked from it."""
    def load(*parts):
        try:
            with open(os.path.join(DOCS, "data", *parts), encoding="utf-8") as f:
                return json.load(f)
        except OSError:
            return None
    hp, hr = hl["boards"]["pnl"], hl["boards"].get("roi30") or {}
    bn, ok, pm = load("cex", "binance-2026-10-15.json"), load("cex", "okx-2026-10-15.json"), load("cex", "polymarket-2026-10-15.json")
    pt = load("papertrade", "frozen-2026-10-16.json")
    rows = [("Hyperliquid", "all-time PnL top 100", f"{hp['ranked_from']:,} accounts", hp["t_bar_best_of_n"], f"{hp['n_t_ge_bar']} / {hp['scored']}", f"{hp['n_t_ge_2']}", "/wallet/", "Check any address")]
    if hr:
        rows.append(("Hyperliquid", "30-day ROI top 100", f"{hr['ranked_from']:,} accounts", hr["t_bar_best_of_n"], f"{hr['n_t_ge_bar']} / {hr['scored']}", f"{hr['n_t_ge_2']}", "/wallet/", "Check any address"))
    if bn:
        rows.append(("Binance", "copy trading, 90-day PnL top 100", f"{bn['listed']:,} portfolios", bn["bar_best_of_n"], f"{bn['t_ge_bar']} / {bn['scored']}", f"{bn['t_ge_2']}", "/audits/007-cex-copy-trading.html", "Audit 007"))
    if ok:
        rows.append(("OKX", "copy trading, PnL top 100", f"{ok['listed']:,}+ traders", ok["bar_best_of_n"], f"{ok['daily365_t_ge_bar']} / {ok['scored']}", f"{ok['daily365_t_ge_2']}", "/audits/007-cex-copy-trading.html", "Audit 007"))
    if pm:
        pn, pb = pm.get("n_floor_revised_2026_10_16", pm["n_floor"]), pm.get("bar_best_of_n_floor_revised", pm["bar_best_of_n_floor"])
        rows.append(("Polymarket", "all-time profit top 50", f"{pn:,}+ wallets", pb, f"{pm['z_cluster_ge_bar']} / {pm['complete_and_scored']}", f"{pm['z_cluster_ge_2']}", "/polymarket/", "Check any wallet"))
    rows.append(("Alpha Arena", "season 1, 6 AI models", "6 models", 2.67, "0 / 6", "0", "/audits/006-alpha-arena-season-1.html", "Audit 006"))
    cell = lambda v, d, u: f'<td><a href="{u}"><b>{v}</b></a><span class="muted small" style="display:block">{d}</span></td>'
    body = "".join(f'<tr>{cell(v, d, u)}<td class="r hm">{n}</td><td class="r mono hm">{b:.2f}</td>'
                   f'<td class="r mono"><b class="c-accent">{c}</b></td><td class="r mono">{s1}</td></tr>'
                   for v, d, n, b, c, s1, u, lbl in rows)
    if pt:
        pt_n, pt_day = f"{pt['board_rows']:,}", pt["frozen_at"][:10]
        body += (f'<tr>{cell("Papertrade", "PnL top 100, up to 1000x", "/audits/010-papertrade-leaderboard.html")}<td class="r hm">{pt_n} accounts</td>'
                 f'<td class="r mono hm">—</td><td class="r small" colspan="2">no return series yet; frozen {pt_day}, readings 10-23 and 10-30</td></tr>')
    return f"""
<section id="boards"><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Every board we have rescored</div><h2 style="margin-top:12px">Ranked by profit. None of the top clears the bar for being picked from the board.</h2>
 <p>Each row is a public leaderboard. "Clear the bar" counts records strong enough to stand out from everyone they were picked from; "pass one test" counts those that would pass if you had picked them blind (t ≥ 2).</p></div><a class="more" href="/audits/">All audits →</a></div>
 <div class="table-wrap"><table class="data boards"><thead><tr><th>Board</th><th class="r hm">Picked from</th><th class="r hm">Bar</th><th class="r">Clear the bar</th><th class="r">Pass one test</th></tr></thead><tbody>{body}</tbody></table></div>
 <p class="muted small" style="margin-top:10px">Hyperliquid rows are rebuilt daily; the others are as of the audit date. Check one wallet yourself: <a href="/wallet/">Hyperliquid</a> (also <a href="{TG_BOT}" rel="noopener">@SkillOrLuckBot</a>), <a href="/polymarket/">Polymarket</a>; Binance and OKX traders with the <a href="{EXT_URL}" rel="noopener">Chrome extension</a>.</p>
</div></section>"""


def build_home(rows, lb):
    with open(os.path.join(DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        hl = json.load(f)
    hp, hc = hl["boards"]["pnl"], hl.get("cohort") or {}
    la, ai = lb["boards"]
    feed = [
        ("2026-10-14", "Hyperliquid leaderboard, rescored", f"Of the all-time PnL top 100, {hp['n_t_ge_bar']} of {hp['scored']} clear the bar for being picked from {hp['ranked_from']:,} accounts. 200 wallets frozen for a forward record.", "/wallet/", "Wallets"),
        ("2026-10-13", "Leaderboard No. 1", "Liquidity Arena and HKUDS AI-Trader, rescored by evidence instead of return.", "/leaderboard/", "Leaderboard"),
    ] + [(a["date"], f"Audit {a['num']} · {a['subject']}", a["finding"], f"/audits/{a['slug']}.html", "Audit") for a in reversed(rows)][:4] + [
        ("2026-10-05", "17 published LLM trading papers", "Of the 9 with a documented cutoff, none reaches 48 clean months.", "/audit.html", "Paper audit"),
    ]
    feed_html = "".join(f'<a class="row" href="{u}"><span class="row-date">{d}</span><span><span class="row-title">{ic(t)}</span><span class="row-sub" style="display:block">{ic(s)}</span></span><span class="row-tag">{k}</span></a>' for d, t, s, u, k in feed)
    py = ('<span class="k">from</span> evidence_deflator <span class="k">import</span> effective_window\n\n'
          'w = effective_window(cutoff=<span class="s">"2024-10"</span>, start=<span class="s">"2020-01"</span>,\n'
          '                     end=<span class="s">"2025-06"</span>, trials=<span class="o">41</span>)\n'
          'print(w.open_book_months, w.effective_months, w.months_required, w.verdict)\n'
          '<span class="c"># 58 8 128 underpowered</span>')
    cli = ('<span class="c"># from a clone of the repository</span>\n'
           'python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06\n'
           '<span class="c"># 66 months, 58 cannot be ruled out as seen, 8 clean; Sharpe 1 needs ~48</span>')
    mcp = ('pip install <span class="s">"evidence-deflator[mcp]"</span>\n\n'
           '<span class="c"># claude_desktop_config.json, Cursor, Claude Code …</span>\n'
           '{ <span class="s">"mcpServers"</span>: { <span class="s">"evidence-deflator"</span>: { <span class="s">"command"</span>: <span class="s">"evidence-deflator-mcp"</span> } } }')
    page = head("Evidence Deflator · Is that trading record skill, or could it be luck?",
                "Paste any Hyperliquid address and see whether its record can be told apart from luck. Open-source evidence checks for trading records, leaderboards and AI backtests.", "/",
                extra=ld(APP_LD) + BAIDU_META) + header("home") + f"""
<main>
<div class="container hero">
 <div class="eyebrow"><span class="dot"></span>Evidence for trading records</div>
 <h1 class="display">Is that trading record skill, or could it be luck?</h1>
 <p class="lede">Leaderboards rank by profit. Among {hp['ranked_from']:,} accounts, someone is always on a winning streak. Paste a Hyperliquid address and see how strong its record is once you allow for that, and how many more months it would need.</p>
 <form class="wcheck" action="/wallet/" method="get" autocomplete="off" style="margin-top:28px">
  <input name="a" placeholder="0x… Hyperliquid address" spellcheck="false" aria-label="Hyperliquid address">
  <button class="btn btn-primary" type="submit">Check <span class="arr">→</span></button>
 </form>
 {ELSEWHERE_EN}
 <div class="instrument">
  <div class="instrument-head"><span class="t"><b style="color:var(--ink);font-weight:550">Hyperliquid, all-time PnL top 100</b> · each dot is one wallet’s t-statistic · {hl['fetched'][:10]}</span><a class="small" href="/wallet/">Rescored board →</a></div>
  <div class="instrument-body chart" style="border:0;border-radius:0" id="hero-chart"></div>
  <div class="instrument-foot">
   <div><b class="c-accent">{hp['n_t_ge_bar']} / {hp['scored']}</b><span>clear the bar for the best of {hp['ranked_from']:,}</span></div>
   <div><b>{hp['t_bar_best_of_n']:.2f}</b><span>that bar; a single test needs 2</span></div>
   <div><b>{hp['n_t_ge_2']} / {hp['scored']}</b><span>would pass if you had picked them blind</span></div>
   <div><b>{hc.get('members', 0)}</b><span>wallets frozen {hc.get('frozen_at', '')[:10]}, scored from then on</span></div>
  </div>
 </div>
</div>

{boards_html(hl)}
<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">For AI backtests · where the method started</div><h2 style="margin-top:12px">Three numbers, before any performance figure</h2>
 <p>Each is plain arithmetic on inputs a project can state in one line. None needs the strategy’s code. <a href="/check/">Check a backtest →</a></p></div><a class="more" href="/method/">Read the method →</a></div>
 <div class="triad">
  <div><span class="k">01 · OPEN-BOOK MONTHS</span><h3>What the model may have seen</h3><p>Months of the test window on or before the model’s training cutoff. For those months, we cannot rule out that it already knows what happened.</p></div>
  <div><span class="k">02 · CLEAN MONTHS NEEDED</span><h3>How long the result must run</h3><p>A Sharpe of 1 needs about 48 clean months to reach t = 2; a Sharpe of 2 needs 12. The quadratic is the whole story.</p></div>
  <div><span class="k">03 · BAR AFTER SELECTION</span><h3>How many tries it beat</h3><p>The best of N attempts must clear a higher bar. Best of 41: t ≥ 3.26. Best of 23,376: t ≥ 4.76.</p></div>
 </div>
 <div class="example">
  <div><div class="eyebrow">Worked example</div><h3 style="margin:12px 0 8px">A 2020–2025 backtest, model cutoff 2024-10</h3><p class="muted small" style="margin:0">66 months in the window. 58 cannot be ruled out as seen. 8 are clean, against the 48 a Sharpe-1 claim needs. Verdict: underpowered — it rejects nothing, and it shows nothing.</p></div>
  <div><div class="meter"><i class="ob" style="width:87.9%"></i><i class="cl" style="width:12.1%"></i></div>
   <div class="legend"><span><i style="background:var(--accent)"></i>58 open-book</span><span><i style="background:var(--pos)"></i>8 clean</span><span class="mono">needs 48</span></div>
   <div class="code-wrap" style="margin-top:16px"><pre class="code" style="font-size:12.5px">python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06</pre></div></div>
 </div>
</div></section>

<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Latest</div><h2 style="margin-top:12px">Published checks</h2><p>Every number recomputed from public sources, dated, with the raw data kept.</p></div><a class="more" href="/audits/">All audits →</a></div>
 <div class="rows">{feed_html}</div>
</div></section>

<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Who it is for</div><h2 style="margin-top:12px">One check, three places it belongs</h2></div></div>
 <div class="who">
  <div><h3>Copy-trading and vault platforms</h3><p>Show an evidence score next to PnL. A score nobody can buy tells followers which records are strong enough to commit to.</p><p class="act"><a href="/wallet/">See it on Hyperliquid →</a></p></div>
  <div><h3>Allocators and reviewers</h3><p>Send a wallet, a deck, a backtest or a public claim. Get a one-page report: what is open-book, what is underpowered, what is missing.</p><p class="act"><a href="{ISSUE_AUDIT}">Request an audit →</a></p></div>
  <div><h3>Agent frameworks</h3><p>One call between “backtest” and “deploy”: flag runs whose window sits before the model’s cutoff, and charge the result for every variant tried.</p><p class="act"><a href="/api/">Python, CLI and MCP →</a></p></div>
 </div>
</div></section>

<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Use it</div><h2 style="margin-top:12px">Pure Python, no keys, no network</h2><p>The engine is the standard library. Fetching data is your job; the value is a repeatable, comparable answer.</p></div><a class="more" href="/api/">API reference →</a></div>
 <div class="code-wrap" data-tabs>
  <div class="tabs" role="tablist"><button data-tab="py" aria-selected="true">Python</button><button data-tab="cli" aria-selected="false">CLI</button><button data-tab="mcp" aria-selected="false">MCP</button></div>
  <pre class="code" data-pane="py">{py}</pre><pre class="code" data-pane="cli" hidden>{cli}</pre><pre class="code" data-pane="mcp" hidden>{mcp}</pre>
 </div>
</div></section>
</main>
""" + footer("""<script src="/assets/lb.js"></script>
<script>LB.load('/data/hl/latest.json').then(d=>{const p=d.boards.pnl,rows=p.rows.filter(r=>r.t!=null).map(r=>({t:r.t,rank:r.rank,name:r.address.slice(0,6)+'…'+r.address.slice(-4)}));
 const best=rows.reduce((a,r)=>r.t>a.t?r:a,rows[0]);
 document.getElementById('hero-chart').innerHTML=LB.strip({board:p.board,rows,entries:p.ranked_from,t_bar_best_of_n:p.t_bar_best_of_n,max_t_rank:best.rank},{h:170});});</script>
""")
    write("index.html", page)


# ---------------------------------------------------------------- leaderboard

def build_leaderboard(lb):
    la, ai = lb["boards"]
    extra = {
        la["id"]: f"""<p class="muted">Live sandbox trading, so the model could not have seen the test period: closed-book by construction. The gap is length and selection. <a href="/audits/003-liquidity-arena-phase-1.html">Audit 003</a>.</p>
<div class="stats" style="margin:22px 0 26px">
 <div><b class="c-accent">0 / {la['entries']}</b><span>teams reach t = 2</span></div>
 <div><b>{la['max_t']:.2f}</b><span>closest: {html.escape(la['max_t_name'])}, rank {la['max_t_rank']} by return. At its observed Sharpe, about {la['months_to_winner']['closest_at_observed_sharpe']} months of forward record would clear the bar.</span></div>
 <div><b>11 · 7 · 17</b><span>return ranks of the top three by evidence. The return leader is fifth by t.</span></div>
</div>""",
        ai["id"]: f"""<div class="stats" style="margin:22px 0 26px">
 <div><b class="c-accent">{ai['frozen']['moved_under_1pp_since_jul24']} / {ai['frozen']['with_any_history']}</b><span>agents with history moved under 1 point between 24 July and 12 October. A third-party report (<a href="https://github.com/HKUDS/AI-Trader/issues/311">#311</a>, unconfirmed) finds the price feed stuck at about 24 July.</span></div>
 <div><b>+271.6%</b><span>the #1 agent, with no history published. So is #2 (+145.4%): no Sharpe or drawdown can be computed.</span></div>
 <div><b>10 / 100</b><span>of the top 100 are one parameter grid (<code>OC-rot-lb126-rb30-…</code>), ranked as separate winners.</span></div>
</div>
<p class="muted small">History is July only, then one live snapshot, so annualisation is rough. {ai['frozen']['had_90pct_of_return_at_first_record']} of {ai['frozen']['with_any_history']} already had ≥ 90% of their return when the history begins. 46 of the top 100 show zero trades alongside non-zero returns; reported as published.</p>""",
    }
    boards = ""
    for b in lb["boards"]:
        boards += f"""
<section id="{b['id']}"><div class="container">
 <div class="sec-head"><div><div class="eyebrow">{b['entries']:,} entries · ranked by {html.escape(b['ranked_by'])}</div><h2 style="margin-top:12px">{html.escape(b['board'])}</h2></div>
 <span class="muted small mono">{html.escape(b['window'])}</span></div>
 {extra[b['id']]}
 <div class="chart" data-strip="{b['id']}"></div>
 <p class="muted small" style="margin-top:8px">Source: <code>{html.escape(b['source'])}</code>, fetched {lb['fetched']}.</p>
 <div class="toolbar"><div class="seg" data-b="{b['id']}"><button data-by="rank" class="on">Rank by return</button><button data-by="t">Rank by evidence</button></div>
 <button class="linkbtn" data-more="{b['id']}">Show all {len(b['rows'])} rows</button></div>
 <div class="table-wrap"><table class="data" id="t-{b['id']}"></table></div>
</div></section>"""
    summary = "".join(f"""<tr><td><a href="#{b['id']}">{html.escape(b['board'])}</a></td><td class="r">{b['entries']:,}</td><td class="wrap">{html.escape(b['window'])}</td><td class="r c-accent">{b['reaching_t2']}</td><td class="r">{b['max_t']:.2f}</td><td class="r">{b['t_bar_best_of_n']:.2f}</td><td class="wrap">{"%.0f months" % b['months_to_winner']['sharpe_5'] if b['months_to_winner']['sharpe_5'] < 24 else "%.1f years" % (b['months_to_winner']['sharpe_5']/12)} at Sharpe 5 · {"%.0f months" % b['months_to_winner']['sharpe_2'] if b['months_to_winner']['sharpe_2'] < 24 else "%.1f years" % (b['months_to_winner']['sharpe_2']/12)} at Sharpe 2</td></tr>""" for b in lb["boards"])
    page = head("Evidence-adjusted leaderboard · AI trading · October 2026",
                "Public AI trading leaderboards rank by return. We rescore them by how much each ranking can tell: 0 of 41 competition teams and 0 of 32 public agents reach even t = 2.",
                "/leaderboard/") + header("leaderboard") + f"""
<main>
<div class="container page-head">
 <div class="eyebrow"><span class="dot"></span>Evidence-adjusted leaderboard · No. 1 · October 2026</div>
 <h1>Public AI trading leaderboards rank by return. None of them can yet name a winner.</h1>
 <p class="lede">We take the equity history each board publishes and ask a different question of the same data: how much can the ranking tell you, and how long until it could show that the top entry is skilled rather than lucky?</p>
 <div class="stats" style="margin-top:36px">
  <div><b class="c-accent">0 / {la['entries']}</b><span>competition teams reach t = 2 (Liquidity Arena)</span></div>
  <div><b class="c-accent">0 / {ai['with_series']}</b><span>top public agents with history reach t = 2 (AI-Trader)</span></div>
  <div><b>~{round(la['months_to_winner']['sharpe_5'])} mo</b><span>earliest the arena could name a winner, if the best team’s true Sharpe were 5</span></div>
  <div><b>{ai['months_to_winner']['sharpe_2']/12:.1f} yr</b><span>for AI-Trader at a true Sharpe of 2, against 23,376 entries</span></div>
 </div>
 <p class="muted small" style="margin-top:14px">t = annualised Sharpe × √years. One result needs t ≥ 2; the best of N needs more. <a href="/method/#leaderboards">How this is computed</a>.</p>
</div>
<div class="container" style="padding-bottom:56px">
 <div class="table-wrap"><table class="data"><thead><tr><th>Board</th><th class="r">Entries</th><th>Window</th><th class="r">t ≥ 2</th><th class="r">Highest t</th><th class="r">Best-of-N bar</th><th>Earliest winner*</th></tr></thead><tbody>{summary}</tbody></table></div>
 <p class="muted small" style="margin-top:10px">* Months of clean, forward history the top entry would need to clear the best-of-N bar, if its true Sharpe were the value shown. Counting every entry as independent overstates the charge when entries are correlated; the true Sharpe is unknown. The two cut in opposite directions.</p>
</div>
{boards}
<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">For operators</div><h2 style="margin-top:12px">What would bring the date forward</h2></div></div>
 <div class="triad">
  <div><span class="k">LONGER WINDOWS</span><h3>Carry records across phases</h3><p>A month of live trading is too short for any realistic Sharpe. Carrying Phase I into Phase II doubles each team’s evidence at no cost.</p></div>
  <div><span class="k">PUBLISH THE HISTORY</span><h3>Rank only full equity curves</h3><p>A single snapshot supports no Sharpe, no drawdown and no test. An entry with no history should not sit at the top.</p></div>
  <div><span class="k">GROUP THE VARIANTS</span><h3>One owner, one family</h3><p>Parameter sweeps are one attempt with many tries. Show them as a family against one bar, not as separate winners.</p></div>
 </div>
</div></section>
<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Data</div><h2 style="margin-top:12px">Use the numbers</h2>
 <p>Per-entry return, days, Sharpe and t, built by <a href="{REPO}/blob/main/tools/build_leaderboard.py"><code>tools/build_leaderboard.py</code></a> from each board’s public endpoint. CC BY 4.0.</p></div></div>
 <div class="btns"><a class="btn btn-primary" href="/leaderboard/2026-10.json">Download 2026-10.json</a><a class="btn btn-secondary" href="{REPO}/issues/new?title=Leaderboard%20to%20rescore%3A%20">Suggest a board to rescore</a><a class="btn btn-secondary" href="{REPO}/blob/main/docs/leaderboard/2026-10.md">Text version</a></div>
 <p class="muted small" style="margin-top:18px">Operate one of these boards and think a number is wrong? Open an issue; corrections are published in the next edition. Next: TradeRank seasons 1–6 and Liquidity Arena Phase II.</p>
</div></section>
</main>
""" + footer("""<script src="/assets/lb.js"></script>
<script>
LB.load('/leaderboard/2026-10.json').then(d=>{
  const st={};
  d.boards.forEach(b=>{st[b.id]={by:'rank',all:false};
    document.querySelector(`[data-strip="${b.id}"]`).innerHTML=LB.strip(b);
    document.getElementById('t-'+b.id).innerHTML=LB.table(b,'rank',false);});
  const redraw=id=>{const b=d.boards.find(x=>x.id===id);document.getElementById('t-'+id).innerHTML=LB.table(b,st[id].by,st[id].all);};
  document.querySelectorAll('.seg[data-b]').forEach(g=>g.addEventListener('click',e=>{const by=e.target.dataset.by;if(!by)return;
    g.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===e.target));st[g.dataset.b].by=by;redraw(g.dataset.b);}));
  document.querySelectorAll('[data-more]').forEach(btn=>btn.addEventListener('click',()=>{const id=btn.dataset.more,b=d.boards.find(x=>x.id===id);
    st[id].all=!st[id].all;redraw(id);btn.textContent=st[id].all?'Show top 15':`Show all ${b.rows.length} rows`;}));
});
</script>
""")
    write("leaderboard/index.html", page)
    redirect = f'<!DOCTYPE html><meta charset="utf-8"><title>Moved</title><link rel="canonical" href="{SITE}/method/"><meta http-equiv="refresh" content="0; url=/method/#leaderboards"><a href="/method/#leaderboards">Method</a>\n'
    write("leaderboard/methodology.html", redirect)


# ---------------------------------------------------------------- method

METHOD_ALT = {"en": "/method/", "zh-Hans": "/zh-hans/method/", "zh-Hant": "/zh-hant/method/"}
API_ALT = {"en": "/api/", "zh-Hans": "/zh-hans/api/", "zh-Hant": "/zh-hant/api/"}


def build_method():
    page = head("Method · Evidence Deflator", "How Evidence Deflator computes open-book months, clean months needed, the bar after selection, and the earliest date a leaderboard could name a winner.", "/method/", alt=METHOD_ALT) + header("method", METHOD_ALT) + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>Method</div>
<h1 style="margin-top:16px">Plain arithmetic on inputs anyone can state</h1>
<p class="lede" style="margin-top:14px">Every number on this site can be recomputed from public data with the scripts in the repository. Nothing depends on a model of ours, and nothing needs the strategy’s code.</p>

<h2 id="open-book">1 · Open-book months</h2>
<p>Split the test window at the model’s published training cutoff. Months on or before the cutoff cannot be ruled out as seen: the model may already know what happened. Months after it are clean.</p>
<div class="eq">window 2020-01 → 2025-06, cutoff 2024-10
66 months  =  58 open-book  +  8 clean</div>
<p>Cutoffs come only from the provider’s own documentation. Where none is published, we say so and do not estimate one. An earlier cutoff always makes a result look better, so it is the input that most needs a source.</p>

<h2 id="clean-months">2 · Clean months needed</h2>
<p>A result of annualised Sharpe S reaches t = 2 after T years, where t ≈ S × √T (Lo, 2002):</p>
<div class="eq">months needed = (t / S)² × 12
Sharpe 2 → 12    Sharpe 1 → 48    Sharpe 0.5 → 192</div>
<p>If the clean segment is shorter than this, the backtest is <em>underpowered</em>: it has not been shown to fail, only not shown to work. The i.i.d. assumption makes this a floor; autocorrelated returns need longer.</p>

<h2 id="selection">3 · The bar after selection</h2>
<p>A result picked as the best of N attempts is the maximum of N draws. We raise the bar with a one-sided Bonferroni correction that keeps a single attempt at exactly t = 2:</p>
<div class="eq">α      = 1 − Φ(2)          ≈ 2.3%, one-sided
bar(N) = Φ⁻¹(1 − α / N)
N = 1 → 2.00    N = 41 → 3.26    N = 23,376 → 4.76</div>
<p>Bonferroni assumes independent attempts. Correlated variants (one owner’s parameter grid, teams on the same model) make it conservative. We say so rather than switch to a correction whose assumptions a reader cannot check; the library accepts a measured effective number of trials when one exists.</p>

<h2 id="leaderboards">4 · Leaderboards</h2>
<p>For each entry we take the published equity history, keep the last value of each day, and compute daily returns. Crypto boards annualise with 365 days, equity calendars with 252.</p>
<div class="eq">Sharpe = mean(daily return) / sd(daily return) × √(days per year)
t      = Sharpe × √(years of data)</div>
<p>“Nobody is significant” says little on its own, so each board also gets a date: how many months of clean, forward history the top entry would need to clear the best-of-N bar, if its true Sharpe were S.</p>
<div class="eq">months to a winner = (bar(N) / S)² × 12</div>
<p>We report it at S = 5 and S = 2, and at the closest entry’s observed Sharpe. These are conditional statements, not forecasts.</p>

<h2 id="principles">Principles</h2>
<ul>
 <li>Sources are public and fetched on a stated date. Numbers are recomputed, not copied.</li>
 <li>“Cannot be ruled out as seen” is the strongest claim made about a model’s training data. Never “contaminated”.</li>
 <li>A missing input is a finding, not a verdict on the project.</li>
 <li>Findings state what the numbers can and cannot support. No judgement of intent, no investment advice.</li>
 <li>The same rule for every board and every claim. No grading on a curve.</li>
 <li>Corrections are published. If you think a number is wrong, <a href="{REPO}/issues">open an issue</a>.</li>
</ul>

<h2 id="limits">What this does not do</h2>
<ul>
 <li>It does not say any strategy or model is unskilled. It says the evidence cannot yet tell skill from luck.</li>
 <li>It does not detect leakage inside a model; it bounds where leakage cannot be excluded.</li>
 <li>It uses only what a project or board publishes.</li>
</ul>

<h2 id="reading">Further reading</h2>
<p class="small">Lo, “The Statistics of Sharpe Ratios” (2002). Bailey &amp; López de Prado, “The Deflated Sharpe Ratio” (2014). Zhang &amp; Stadie, “Temporal Leakage in LLM Backtesting” (arXiv 2608.02985).</p>
</article>
<aside class="aside">
 <div class="box"><h4>On this page</h4><ul><li><a href="#open-book">Open-book months</a></li><li><a href="#clean-months">Clean months needed</a></li><li><a href="#selection">The bar after selection</a></li><li><a href="#leaderboards">Leaderboards</a></li><li><a href="#principles">Principles</a></li><li><a href="#limits">Limits</a></li></ul></div>
 <div class="box"><h4>Try it</h4><ul><li><a href="/check/">Check a backtest in the browser</a></li><li><a href="/api/">Python, CLI and MCP</a></li></ul></div>
</aside>
</div></main>
""" + footer()
    write("method/index.html", page)


# ---------------------------------------------------------------- api

def build_api():
    page = head("API · Evidence Deflator", "Use Evidence Deflator from Python, the command line, or any MCP client. Pure standard library, no keys, no network.", "/api/", alt=API_ALT) + header("api", API_ALT) + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>API</div>
<h1 style="margin-top:16px">Python, CLI and MCP</h1>
<p class="lede" style="margin-top:14px">The engine is pure Python standard library: no keys, no network, no execution. Fetching data is the caller’s job.</p>
<div class="btns" style="margin:22px 0 8px"><button class="copy" data-copy="pip install evidence-deflator">$ pip install evidence-deflator {COPY_ICON}</button><span class="muted small">Python ≥ 3.8 · MIT</span></div>

<h2 id="remote">Hosted: wallet check over HTTP and MCP</h2>
<p>For a Hyperliquid wallet there is nothing to install. The hosted endpoint fetches the public history and scores it with the same code the <a href="/wallet/">wallet page</a> runs in your browser.</p>
<pre class="code solo">curl <span class="s">"https://api.evidencedeflator.com/api/wallet?a=0xADDRESS&amp;picked_from=47153"</span></pre>
<p>Remote MCP (Streamable HTTP, no key): add <code>https://api.evidencedeflator.com/mcp</code> as a connector in Claude, ChatGPT, Cursor or any MCP client. It exposes one tool, <code>hyperliquid_wallet(address, picked_from)</code>. In Claude Code:</p>
<pre class="code solo">claude mcp add --transport http evidence-deflator https://api.evidencedeflator.com/mcp</pre>
<p>Or install the Claude Code plugin, which adds the same tool, a skill that tells the agent how to report the verdict, and a hook that counts every backtest it runs:</p>
<pre class="code solo">/plugin marketplace add Beltran12138/evidence-deflator
/plugin install evidence-deflator@evidence-deflator</pre>

<h2 id="python">Python</h2>
<pre class="code solo"><span class="k">from</span> evidence_deflator <span class="k">import</span> effective_window, selection_penalty, months_for_power

w = effective_window(cutoff=<span class="s">"2024-10"</span>, start=<span class="s">"2020-01"</span>, end=<span class="s">"2025-06"</span>, trials=<span class="o">41</span>)
w.open_book_months   <span class="c"># 58  months on or before the cutoff</span>
w.effective_months   <span class="c"># 8   clean months</span>
w.months_required    <span class="c"># 128 clean months a Sharpe-1 result needs, best of 41</span>
w.verdict            <span class="c"># 'underpowered'</span>
w.to_dict()          <span class="c"># everything, with the reasoning as plain text</span>

selection_penalty(<span class="o">41</span>).t_adjusted   <span class="c"># 3.26</span>
months_for_power(<span class="o">2.0</span>)               <span class="c"># 12</span></pre>
<p class="small muted">Pass <code>cutoff_source=</code> with the provider’s documentation URL; without one the result says the cutoff is unverified. Pass <code>effective_trials=</code> when you have measured how correlated the attempts are.</p>

<h2 id="cli">Command line</h2>
<pre class="code solo">git clone {REPO}
cd evidence-deflator
python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06
python tools/record.py --start 2026-03 --end 2026-08 --sharpe 3 --trials 4800</pre>

<h2 id="mcp">MCP server</h2>
<p>For Claude, Cursor and any other MCP client. Tools include <code>knowledge_window</code>, <code>track_record</code>, <code>counterfactual_audit</code> and <code>trace_audit</code>.</p>
<pre class="code solo">pip install <span class="s">"evidence-deflator[mcp]"</span>

{{
  <span class="s">"mcpServers"</span>: {{
    <span class="s">"evidence-deflator"</span>: {{ <span class="s">"command"</span>: <span class="s">"evidence-deflator-mcp"</span> }}
  }}
}}</pre>

<h2 id="data">Data</h2>
<p>Each leaderboard edition is published as JSON under CC BY 4.0: <a href="/leaderboard/2026-10.json"><code>/leaderboard/2026-10.json</code></a>. Fields per entry: rank, name, return_pct, days, sharpe, t.</p>

<h2 id="hosted">Hosted evidence score</h2>
<p>A hosted endpoint that returns an evidence score for a strategy, agent or leaderboard entry is planned. If you run a framework, a competition or an allocation process and would use one, <a href="{REPO}/issues/new?title=Hosted%20API%3A%20use%20case">tell us the use case</a>.</p>
</article>
<aside class="aside">
 <div class="box"><h4>On this page</h4><ul><li><a href="#python">Python</a></li><li><a href="#cli">Command line</a></li><li><a href="#mcp">MCP server</a></li><li><a href="#data">Data</a></li><li><a href="#hosted">Hosted evidence score</a></li></ul></div>
 <div class="box"><h4>Links</h4><ul><li><a href="https://pypi.org/project/evidence-deflator/">PyPI</a></li><li><a href="{REPO}">GitHub</a></li><li><a href="/method/">Method</a></li></ul></div>
</aside>
</div></main>
""" + footer()
    write("api/index.html", page)


# ---------------------------------------------------------------- wallet check

WALLET_ALT = {"en": "/wallet/", "zh-Hans": "/zh-hans/", "zh-Hant": "/zh-hant/"}

WALLET_T_EN = {
    "say": {
        "loses": ["Losing, and not by chance", "tag-red", "t is −2 or lower: over the weeks that can be measured, this wallet lost money too consistently for luck to explain."],
        "luck": ["Cannot be told apart from luck", "tag-red", "t is below 2: a record like this turns up by chance often enough that it says little about skill."],
        "clears_single": ["Passes one test, not the leaderboard bar", "tag-amber", "Strong enough if you had picked this wallet blind. If you found it on a leaderboard, it needs t ≥ {BAR}."],
        "clears_board": ["Clears the leaderboard bar", "tag-green", "The record is strong enough even allowing for having been picked from {N} {U}."],
        "too_short": ["Too short to say", "tag-grey", "Fewer than 8 weeks of history with at least $1,000 in the account."],
    },
    "tag": {"loses": "loses", "luck": "luck", "clears_single": "clears single", "clears_board": "clears board", "too_short": "too short"},
    "meterAria": "t against the two bars", "meterT2": "t = 2 · one test", "meterBest": "best of {N} · {bar}",
    "notAddr": ["That is not a Hyperliquid address", "Expected 0x followed by 40 hex characters."],
    "reading": "Reading the public record…", "noReach": "Could not reach Hyperliquid", "noHist": "No history for this address",
    "months": {"noSharpe": "needs 8 weeks of record before this can be estimated",
               "never": ["never", "at a Sharpe of zero or below, no length of record clears the bar"],
               "done": "more months needed: the record already clears the leaderboard bar",
               "more": "more record needed to clear the leaderboard bar, if the Sharpe held", "yr": " yr", "mo": " mo"},
    "notes": {"no_losing_week": "No losing week in the record. Consistent with market making, funding carry or selling tail risk; t measures consistency, not the size of a loss that has not happened yet.",
              "one_week_majority": "One week produced more than half of all the gains. The record rests mostly on that week.",
              "pnl_outside_record": "Most of the all-time PnL was booked in periods that started with under $1,000 in the account, so it cannot be turned into a return. The verdict covers only the weeks that can be measured."},
    "wnote": "History from {start}. Read {now} UTC from api.hyperliquid.xyz.",
    "unitAcct": "accounts", "unitVault": "vaults",
    "vault": "This is a vault: {name}. The leader holds {lf}% of it and takes {c}% of depositors' profits; the score is on the vault's PnL before that cut.",
    "vaultBar": " Its bar assumes it was picked from the {NV} vaults Hyperliquid lists, open and closed.",
    "selfPath": "/wallet/", "countUrl": "https://api.evidencedeflator.com/api/count?k=web&l=en",
}


def asset(name):
    """/assets/<name>?v=<content hash>: the Cloudflare edge caches assets, so a changed file needs a new URL."""
    with open(os.path.join(DOCS, "assets", name), "rb") as f:
        return f"/assets/{name}?v={hashlib.sha256(f.read()).hexdigest()[:8]}"


def wallet_scripts(n_accounts, strings, n_vaults=None):
    data = json.dumps({"N": n_accounts, "NV": n_vaults, "T": strings}, ensure_ascii=False).replace("</", "<\\/")
    return (f'<script src="/assets/site.js"></script><script src="{asset("hl.js")}"></script>\n'
            f'<script>window.WALLET = {data};</script>\n<script src="{asset("wallet.js")}"></script>\n')


def build_wallet():
    p = os.path.join(DOCS, "data", "hl", "latest.json")
    with open(p, encoding="utf-8") as f:
        hl = json.load(f)
    pnl, roi = hl["boards"]["pnl"], hl["boards"]["roi30"]
    scored = sorted((r for r in pnl["rows"] if r["t"] is not None), key=lambda r: -r["t"])
    examples = [("Highest t in the PnL top 100", scored[0]["address"]),
                ("Median of the PnL top 100", scored[len(scored) // 2]["address"]),
                ("#1 by 30-day ROI", roi["rows"][0]["address"])]
    ex = "".join(f'<button class="linkbtn" data-ex="{a}">{html.escape(t)}</button>' for t, a in examples)

    def short(a):
        return a[:6] + "…" + a[-4:]

    def money(x):
        x = float(x)
        return f"${x/1e6:,.1f}M" if abs(x) >= 1e6 else f"${x/1e3:,.0f}k"

    rows = ""
    for r in pnl["rows"][:15]:
        t = "—" if r["t"] is None else f"{r['t']:.2f}"
        w = 0 if r["t"] is None else min(abs(r["t"]) / pnl["t_bar_best_of_n"], 1) * 100
        neg = " neg" if (r["t"] or 0) < 0 else ""
        dag = "<sup>†</sup>" if "pnl_outside_record" in r["flags"] else ""
        rows += (f'<tr><td class="r">{r["rank"]}</td><td><a class="mono" href="/wallet/?a={r["address"]}">{short(r["address"])}</a>'
                 f'{" · " + html.escape(r["display"]) if r.get("display") else ""}</td><td class="r">{money(r["pnl_all_time"])}</td>'
                 f'<td class="r">{r["weeks"] if r["weeks"] else "—"}</td><td class="r">{t}{dag}</td>'
                 f'<td><span class="mbar"><span class="track"><span class="fill{neg}" style="width:{w:.1f}%"></span>'
                 f'<span class="t2" style="left:{2 / pnl["t_bar_best_of_n"] * 100:.1f}%"></span></span></span></td></tr>')

    c = hl.get("cohort")
    cohort_html = ""
    if c:
        if c["scored"]:
            reading = (f'<div><b class="c-accent">{c["n_t_ge_2"]} / {c["scored"]}</b><span>reach t = 2 on the record since the freeze</span></div>')
        else:
            reading = f'<div><b>{c["first_readings"]}</b><span>first readings: a wallet needs 8 weeks of record after the freeze before it gets a t</span></div>'
        cohort_html = f"""
<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Forward record · frozen {c['frozen_at'][:10]}</div><h2 style="margin-top:12px">The same {c['members']} wallets, scored only on what they do from now on.</h2>
 <p>A record found by looking back is a record chosen after the fact. So on {c['frozen_at'][:10]} we froze today’s two top-100 lists and publish, every day, how each wallet does after that moment. Nothing before the freeze counts, and the list cannot be edited: its hash is below and its history is in git.</p></div></div>
 <div class="stats" style="margin:8px 0 18px">
  <div><b>{c['members']}</b><span>wallets frozen at {c['frozen_at'].replace('T', ' ').replace('Z', ' UTC')}</span></div>
  {reading}
  <div><b>daily</b><span>refreshed from the public API by a scheduled job in the repository</span></div>
 </div>
 <p class="muted small mono" style="overflow-wrap:anywhere">{html.escape(c['file'])} · sha256 {c['sha256']}</p>
 <div class="btns" style="margin-top:12px"><a class="btn btn-secondary" href="/data/hl/{html.escape(c['file'])}">Frozen list</a><a class="btn btn-secondary" href="/data/hl/latest.json">Daily scores (JSON)</a></div>
</div></section>
"""

    page = head("Check a Hyperliquid wallet · Evidence Deflator",
                "Paste any Hyperliquid address. See whether its record can be told apart from luck, and how many more months it would need.",
                "/wallet/", extra=ld({**APP_LD, "@type": "WebApplication", "name": "Evidence Deflator · Hyperliquid wallet check",
                                       "url": SITE + "/wallet/", "operatingSystem": "Web"}), alt=WALLET_ALT) + header("wallet", WALLET_ALT) + f"""
<main>
<div class="container page-head">
 <div class="eyebrow"><span class="dot"></span>Hyperliquid · wallet check · public data, computed in your browser</div>
 <h1>Paste a Hyperliquid address. See how much of its record counts.</h1>
 <p class="lede">A leaderboard shows who made the most. It does not show whether that could have been luck. This reads the wallet’s public PnL history and answers one question: how strong is the evidence, and how long until it could be strong enough?</p>
 <form class="wcheck" id="wform" autocomplete="off">
  <input id="waddr" name="a" placeholder="0x… Hyperliquid address" spellcheck="false" aria-label="Hyperliquid address">
  <button class="btn btn-primary" type="submit">Check <span class="arr">→</span></button>
 </form>
 <div class="wex muted small">Try: {ex}</div>
 {ELSEWHERE_EN}
</div>

<div class="container" id="wout" hidden>
 <div class="instrument wres">
  <div class="instrument-head"><span class="t mono" id="wid"></span><span id="wtag"></span></div>
  <div class="instrument-body"><h2 id="whead" style="margin:18px 4px 6px"></h2><p id="wsub" class="muted" style="margin:0 4px 10px"></p>
   <p id="wvault" class="muted small" style="margin:0 4px 10px" hidden></p>
   <div class="chart" id="wmeter"></div></div>
  <div class="instrument-foot">
   <div><b id="wt">—</b><span>t, adjusted for record length</span></div>
   <div><b id="ws">—</b><span>annualised Sharpe, weekly</span></div>
   <div><b id="ww">—</b><span>weeks of record above $1k</span></div>
   <div><b id="wm">—</b><span id="wml">months of record to clear the leaderboard bar, at this Sharpe</span></div>
  </div>
 </div>
 <ul class="wflags" id="wflags"></ul>
 <div class="btns" style="margin:18px 0 8px"><button class="btn btn-secondary copy" id="wcopy" data-copy=""><span class="cp">Copy link to this result</span><span class="ok">Copied</span></button>
  <a class="btn btn-secondary" id="whl" href="#" rel="noopener">Open on Hyperliquid</a></div>
 <p class="muted small" id="wnote"></p>
</div>

<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Hyperliquid’s own leaderboard, rescored · {hl['fetched'][:10]}</div><h2 style="margin-top:12px">The top of the board is ranked by profit. None of it clears the bar for being picked from {pnl['ranked_from']:,}.</h2></div></div>
 <div class="stats" style="margin:8px 0 26px">
  <div><b class="c-accent">{pnl['n_t_ge_bar']} / {pnl['scored']}</b><span>of the all-time PnL top 100 clear the best-of-{pnl['ranked_from']:,} bar (t ≥ {pnl['t_bar_best_of_n']:.2f})</span></div>
  <div><b>{pnl['n_t_ge_2']} / {pnl['scored']}</b><span>would pass a single test (t ≥ 2) if you had picked them blind</span></div>
  <div><b class="c-accent">{roi['n_t_ge_bar']} / {roi['scored']}</b><span>of the 30-day ROI top 100 (account ≥ $10k) clear the bar. {roi['n_t_ge_2']} pass a single test.</span></div>
 </div>
 <div class="table-wrap"><table class="data"><thead><tr><th class="r">PnL rank</th><th>Wallet</th><th class="r">All-time PnL</th><th class="r">Weeks</th><th class="r">t</th><th>Share of the bar</th></tr></thead><tbody>{rows}</tbody></table></div>
 <p class="muted small" style="margin-top:10px">Bar: one result needs t ≥ 2. A wallet found by scanning a board of N accounts needs the best-of-N bar, {pnl['t_bar_best_of_n']:.2f} here. † Most of this wallet’s PnL was booked while the account held under $1,000, so it cannot be turned into a return; t covers only the weeks that can be measured. All {pnl['shown']} + {roi['shown']} rows: <a href="/data/hl/latest.json">latest.json</a> (built by <a href="{REPO}/blob/main/tools/build_hl_board.py"><code>tools/build_hl_board.py</code></a>).</p>
</div></section>
{cohort_html}
<section><div class="container narrow prose">
 <h2>How it reads a wallet</h2>
 <p><strong>Returns come from PnL, not account value.</strong> Account value moves when the owner deposits or withdraws; PnL does not. Each week’s return is the change in cumulative PnL divided by the account value at the start of the week. Weeks that start below $1,000 are skipped.</p>
 <p><strong>Weekly, because the history is.</strong> Hyperliquid keeps older history about a week apart and recent history minutes apart. Everything is put on one weekly grid; a week with no new data point is merged into the next one, not counted as a zero.</p>
 <p><strong>Short records are not over-read.</strong> A t computed from a handful of weeks has fat tails: with eight weeks and no skill at all, t ≥ 2 turns up about twice as often as the bar assumes. So t is taken from Student’s t with the record’s effective degrees of freedom (fewer when a few long gaps carry the record) and put back on the usual scale. For a long record it is close to Sharpe × √years; for a short one it is lower. Tested: with no skill, the share of records reaching 2 stays at the nominal 2.3% however sparsely the history was sampled.</p>
 <p><strong>Two bars.</strong> If you came to this wallet with no prior selection, t ≥ 2 is the usual bar. If you found it by sorting a leaderboard, you picked the best of many, and the bar rises with the number you picked from (Bonferroni on {pnl['ranked_from']:,} accounts: {pnl['t_bar_best_of_n']:.2f}). Most people find wallets on leaderboards. That bar counts every account as independent; accounts that trade alike are fewer independent bets, which would lower it to about 2.6 by our <a href="https://github.com/Beltran12138/evidence-deflator#a-track-record-with-no-model-behind-it">rough estimate</a> (an order of magnitude, not a measurement).</p>
 <p><strong>What t cannot see.</strong> Tail risk that has not happened yet. A strategy that sells insurance can show no losing week for a long time. Where the record has no losing week, or one week made most of the gains, the page says so.</p>
 <p class="muted small">Not investment advice. Public data from <code>api.hyperliquid.xyz</code>, fetched by your browser. {PRIVACY} Method: <a href="/method/">Method</a>, Lo (2002), Bailey &amp; López de Prado (2014).</p>
</div></section>
</main>
""" + footer(wallet_scripts(pnl["ranked_from"], WALLET_T_EN, (hl.get("vaults") or {}).get("listed")))
    write("wallet/index.html", page)


def build_polymarket():
    """Polymarket wallet check: audit 008's per-position test, run in the browser (assets/polymarket.js)."""
    with open(os.path.join(DOCS, "data", "cex", "polymarket-2026-10-15.json"), encoding="utf-8") as f:
        pm = json.load(f)
    n, bar_ = pm.get("n_floor_revised_2026_10_16", pm["n_floor"]), pm.get("bar_best_of_n_floor_revised", pm["bar_best_of_n_floor"])
    rows = {r["name"]: r for r in pm["rows"]}
    examples = [("#1 by all-time profit", rows["Theo4"]["wallet"]),
                ("Looks like a star on closed positions only", rows["DrPufferfish"]["wallet"]),
                ("Highest z in the top 50", rows["asparagus2012"]["wallet"])]
    ex = "".join(f'<button class="linkbtn" data-ex="{a}">{html.escape(t)}</button>' for t, a in examples)
    data = json.dumps({"N": n, "bar": bar_, "selfPath": "/polymarket/",
                       "countUrl": "https://api.evidencedeflator.com/api/count?k=pm&l=en"})
    page = head("Polymarket wallet check · Evidence Deflator",
                "Paste a Polymarket wallet or username and see whether its record of picks can be told apart from luck, position by position, counting the losers Polymarket lists separately.",
                "/polymarket/") + header("wallet") + f"""
<main>
<div class="container page-head">
 <div class="eyebrow"><span class="dot"></span>Polymarket · wallet check · public data, computed in your browser</div>
 <h1>Paste a Polymarket wallet. See whether its picks beat the prices it paid.</h1>
 <p class="lede">A profit board shows who made the most. It does not show whether that wallet bought at prices that were too low for how things turned out, more often than chance allows. This page reads every resolved position and answers that.</p>
 <form class="wcheck" id="pform" autocomplete="off">
  <input id="paddr" name="a" placeholder="0x… wallet, polymarket.com profile link, or username" spellcheck="false" aria-label="Polymarket wallet or username">
  <button class="btn btn-primary" type="submit">Check <span class="arr">→</span></button>
 </form>
 <div class="wex muted small">Try: {ex}</div>
 <p class="muted small elsewhere">Hyperliquid wallets: <a href="/wallet/">the wallet check</a>.</p>
</div>

<div class="container" id="pout" hidden>
 <div class="instrument wres">
  <div class="instrument-head"><span class="t mono" id="pid"></span><span id="ptag"></span></div>
  <div class="instrument-body"><h2 id="phead" style="margin:18px 4px 6px"></h2><p id="psub" class="muted" style="margin:0 4px 10px"></p>
   <div class="chart" id="pmeter"></div></div>
  <div class="instrument-foot">
   <div><b id="pz">—</b><span>z, positions in one event counted as one bet</span></div>
   <div><b id="pev">—</b><span>events</span></div>
   <div><b id="pres">—</b><span>resolved positions</span></div>
   <div><b id="pedge">—</b><span>average edge per share: outcome minus price paid</span></div>
  </div>
 </div>
 <ul class="wflags" id="pflags"></ul>
 <div class="btns" style="margin:18px 0 8px"><button class="btn btn-secondary copy" id="pcopy" data-copy=""><span class="cp">Copy link to this result</span><span class="ok">Copied</span></button>
  <a class="btn btn-secondary" id="ppm" href="#" rel="noopener">Open on Polymarket</a></div>
 <p class="muted small" id="pnote"></p>
</div>

<section><div class="container narrow prose">
 <h2>How it reads a wallet</h2>
 <p><strong>One question per position.</strong> A share bought at price p pays $1 if it wins. With no skill, it wins with probability p, so the edge, outcome minus price paid, averages zero. Someone who keeps buying at prices that turn out too low has a positive edge, and z measures how far that is from chance.</p>
 <p><strong>Bets on one event are one bet.</strong> Ten positions on the same election share one outcome. z sums the edge within each event before comparing it with chance, so a wallet cannot look strong by splitting one view into many positions.</p>
 <p><strong>The losers Polymarket lists elsewhere.</strong> A losing share is worth nothing, so many are never redeemed. They stay among open positions, not closed ones. Counting only closed positions made 11 of the profit top 50 look like stars in <a href="/audits/008-polymarket-profit-board.html">audit 008</a>; this page counts both.</p>
 <p><strong>Two bars.</strong> z ≥ 2 is the usual bar for a wallet you came to with no prior selection. A wallet found on the profit board was picked from at least {n:,} wallets, so it needs z ≥ {bar_:.2f}. That is a floor: the board reports no total, and a username search on it returns a wallet ranked {n:,}. Of the top 50 in audit 008, none came close; the highest z was 2.40.</p>
 <p><strong>What z cannot see.</strong> Position sizes (each position counts once; a few huge winning bets can make the money while the picks overall are ordinary), and whether the wallet traded on information others did not have.</p>
 <p class="muted small">Not investment advice. Public data from <code>data-api.polymarket.com</code>, fetched by your browser; the wallet is never sent to us, and each check adds one tally with no address. Method: <a href="/audits/008-polymarket-profit-board.html">audit 008</a>, <a href="{REPO}/blob/main/tools/audit_polymarket.py"><code>tools/audit_polymarket.py</code></a>.</p>
</div></section>
</main>
""" + footer(f'<script src="/assets/site.js"></script>\n<script>window.PM = {data};</script>\n<script src="{asset("polymarket.js")}"></script>\n')
    write("polymarket/index.html", page)


def build_404():
    page = head("Not found · Evidence Deflator", "Page not found.", "/404.html") + header("") + """
<main class="container page-head" style="min-height:50vh"><div class="eyebrow"><span class="dot"></span>404</div>
<h1>This page cannot be ruled out as missing.</h1><p class="lede">Try the <a href="/leaderboard/">leaderboard</a>, the <a href="/audits/">audits</a> or the <a href="/">home page</a>.</p></main>
""" + footer()
    write("404.html", page)


HAND_PAGES = [  # hand-maintained pages that only receive the shared head links, header and footer
    ("check/index.html", "check", "/check/"),
    ("audit.html", "audits", "/audit.html"),
    ("case-nuclear.html", "audits", "/case-nuclear.html"),
    ("how-many-decisions.html", "check", "/how-many-decisions.html"),
]


def inject_chrome():
    """Refresh the marked head/header/footer blocks inside the hand-maintained pages."""
    foot = "<footer" + footer().split("<footer", 1)[1].rsplit("</body>", 1)[0]
    for rel, active, path in HAND_PAGES:
        p = os.path.join(DOCS, rel)
        with open(p, encoding="utf-8") as f:
            s = f.read()
        links = "\n".join([
            f'<link rel="icon" href="{FAVICON}">',
            f'<link rel="canonical" href="{SITE}{path}">',
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap">',
            '<link rel="stylesheet" href="/assets/chrome.css">'] + ([BEACON.strip()] if BEACON else []))
        for name, body in (("site-head", links), ("site-header", header(active)), ("site-footer", foot)):
            s, n = re.subn(rf"<!-- {name} -->.*?<!-- /{name} -->",
                           lambda m, name=name, body=body: f"<!-- {name} -->\n{body}\n<!-- /{name} -->", s, count=1, flags=re.S)
            assert n == 1, (rel, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(s)
        print("refreshed", rel)


# ---------------------------------------------------------------- questions
# One page per question people actually ask, answered in the first paragraph with
# today's numbers. Answer engines cite pages whose headings match the question.

import sys as _sys
_sys.path.insert(0, os.path.join(ROOT, "src"))
from hl_wallet import bar as _bar  # noqa: E402

# Set once the Worker answers at this host (worker/README.md); empty keeps it off the pages.
API_HOST = "https://api.evidencedeflator.com"
API_LINE = (f', or <code>GET {API_HOST}/api/wallet?a=0x…</code>' if API_HOST else "")

QUESTIONS = [
    ("hyperliquid-trader-skill-or-luck", "Is this Hyperliquid trader skilled or just lucky?"),
    ("how-many-months-of-backtest", "How many months of backtest or track record are enough?"),
    ("why-leaderboard-winner-is-not-evidence", "Why isn't the #1 trader on a leaderboard evidence of skill?"),
]


def _months(t, sharpe):
    m = (t / sharpe) ** 2 * 12
    return f"{m:.0f} months" if m < 36 else f"{m / 12:.1f} years"


def build_questions():
    with open(os.path.join(DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        hl = json.load(f)
    pnl, roi = hl["boards"]["pnl"], hl["boards"]["roi30"]
    n_acc, day = pnl["ranked_from"], hl["fetched"][:10]
    b_n = _bar(n_acc)
    top10 = pnl["rows"][:10]
    outside = sum("pnl_outside_record" in r["flags"] for r in top10)
    unscored10 = sum(r["t"] is None for r in top10)
    others = "".join(f'<li><a href="/q/{slug}/">{html.escape(q)}</a></li>' for slug, q in QUESTIONS)
    form = ('<form class="wcheck" action="/wallet/" method="get" autocomplete="off" style="margin:22px 0">'
            '<input name="a" placeholder="0x… Hyperliquid address" spellcheck="false" aria-label="Hyperliquid address">'
            '<button class="btn btn-primary" type="submit">Check <span class="arr">→</span></button></form>')

    bodies = {
        "hyperliquid-trader-skill-or-luck": (
            f"Paste the address below. On {day}, of the {pnl['scored']} wallets in Hyperliquid’s all-time PnL top 100 with enough history to score, "
            f"{pnl['n_t_ge_2']} would pass the usual test (t ≥ 2) if you had picked them blind, and {pnl['n_t_ge_bar']} pass the bar that applies when "
            f"you found them by sorting a board of {n_acc:,} accounts (t ≥ {b_n:.2f}). For the 30-day ROI top 100: {roi['n_t_ge_2']} and {roi['n_t_ge_bar']} of {roi['scored']}.",
            f"""{form}
<h2>What the check does</h2>
<p>It takes the wallet’s public portfolio history from Hyperliquid, turns it into weekly returns (change in cumulative PnL over the account value at the start of the week, so deposits and withdrawals are not returns), and asks how strong that record is: t = annualised Sharpe × √years, adjusted for short and irregular records.</p>
<h2>Which bar applies</h2>
<p>If someone sent you this one wallet and you had no other candidates, t ≥ 2 is the usual bar. If you found it on a leaderboard, it is the best of {n_acc:,}, and someone is always on a streak in a crowd that size. The bar for the best of {n_acc:,} is t ≥ {b_n:.2f} (Bonferroni). Most people find wallets on leaderboards. That bar counts every account as independent; accounts that trade alike are fewer independent bets, which would lower it to about 2.6 by our <a href="https://github.com/Beltran12138/evidence-deflator#a-track-record-with-no-model-behind-it">rough estimate</a> (an order of magnitude, not a measurement).</p>
<h2>What the verdict cannot see</h2>
<p>A strategy that sells insurance can show no losing week for a long time. The page flags a record with no losing week, one where a single week made most of the gains, and one where most of the PnL was booked while the account held under $1,000 and cannot be turned into a return. In the PnL top 10 on {day}, {outside} carry that last flag and {unscored10} have too little measurable history to score at all.</p>
<p>From an agent: the MCP tool <code>hyperliquid_wallet</code>{API_LINE}, or the skill in the <a href="{REPO}">repository</a>.</p>"""),
        "how-many-months-of-backtest": (
            f"At a true annualised Sharpe of 1, about 48 months to reach t = 2 for a single result; at Sharpe 2, 12 months. "
            f"If the result is the best of many tries, it needs more: the best of 100 needs t ≥ {_bar(100):.2f}, which at Sharpe 1 is {_months(_bar(100), 1)}.",
            f"""<h2>The formula</h2>
<div class="eq">t = Sharpe × √years        months needed = (t / Sharpe)² × 12</div>
<p>This is Lo (2002) under i.i.d. returns, so it is a floor: autocorrelated returns need longer.</p>
<h2>The table</h2>
<div class="table-wrap"><table class="lb-table"><thead><tr><th>True Sharpe</th><th class="r">One result (t ≥ 2)</th><th class="r">Best of 100 (t ≥ {_bar(100):.2f})</th><th class="r">Best of {n_acc:,} (t ≥ {b_n:.2f})</th></tr></thead><tbody>
{"".join(f'<tr><td>{sh}</td><td class="r">{_months(2, sh)}</td><td class="r">{_months(_bar(100), sh)}</td><td class="r">{_months(b_n, sh)}</td></tr>' for sh in (0.5, 1, 2, 3))}
</tbody></table></div>
<h2>Which months count</h2>
<p>Only months the result was not fitted on. For a backtest run with a language model, months before the model’s training cutoff cannot be ruled out as seen; only months after it are clean. <a href="/check/">Check a backtest</a> splits the window for you. For a trader you are about to copy, only the record after the day you picked them tests the pick.</p>
<p>Count every variant tried, including ones that were dropped. An agent can try fifty in a minute; the plugin in the <a href="{REPO}">repository</a> counts them as it goes.</p>"""),
        "why-leaderboard-winner-is-not-evidence": (
            f"Because the top of a board is the maximum of many draws. Among {n_acc:,} accounts, someone is on a streak by chance alone; the best of {n_acc:,} has to clear t ≥ {b_n:.2f}, not 2. "
            f"On {day}, {pnl['n_t_ge_bar']} of the {pnl['scored']} scoreable wallets in Hyperliquid’s all-time PnL top 100 did.",
            f"""<h2>The bar rises with the number you picked from</h2>
<div class="table-wrap"><table class="lb-table"><thead><tr><th>Picked from</th><th class="r">t needed</th></tr></thead><tbody>
{"".join(f'<tr><td>{n:,}</td><td class="r">{_bar(n):.2f}</td></tr>' for n in (1, 10, 100, 1000, n_acc))}
</tbody></table></div>
<p>The bar keeps the chance that a no-skill account clears it, anywhere on the board, at the 2.3% a single test allows (Bonferroni on α = 1 − Φ(2)). Counting every account as independent overstates the charge when accounts copy each other; the true number of independent bets is unknown, so the table is an upper bound on the bar and the honest range sits below it.</p>
<h2>Profit ranks are not return ranks</h2>
<p>A PnL board ranks dollars. A large account with an ordinary return outranks a small one with an exceptional return, and PnL booked into a near-empty account cannot be turned into a return at all. In the all-time PnL top 10 on {day}, {outside} wallets had most of their PnL booked while the account held under $1,000.</p>
<h2>What would count</h2>
<p>A record found after the fact has already been picked for looking good. The clean test is forward: freeze the list, then watch. We froze 200 wallets from the top of the board on 2026-10-14 and publish how each does from then on, on the <a href="/wallet/">wallet page</a>.</p>"""),
    }
    for slug, q in QUESTIONS:
        lead, rest = bodies[slug]
        faq = ld({"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q,
                  "acceptedAnswer": {"@type": "Answer", "text": lead}}]})
        alt = {"en": f"/q/{slug}/", "zh-Hans": f"/zh-hans/q/{slug}/", "zh-Hant": f"/zh-hant/q/{slug}/"}
        page = head(f"{q} · Evidence Deflator", lead[:300], f"/q/{slug}/", extra=faq, alt=alt) + header("", alt) + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>Question · data as of {day}</div>
<h1 style="margin-top:16px">{html.escape(q)}</h1>
<p class="lede" style="margin-top:14px">{lead}</p>
{rest}
<h2>Related questions</h2><ul>{others}</ul>
<p class="muted small">Numbers rebuild daily from <a href="/data/hl/latest.json">latest.json</a>. Method: <a href="/method/">Method</a>. Not investment advice.</p>
</article></div></main>
""" + footer()
        write(f"q/{slug}/index.html", page)


# ---------------------------------------------------------------- privacy, terms

LEGAL_UPDATED = "2026-10-15"


def build_legal():
    issues = REPO + "/issues"
    pages = {
        "privacy": ("Privacy", "What Evidence Deflator collects: no accounts, no cookies, no stored wallet addresses.", f"""
<p class="lede" style="margin-top:14px">No accounts, no cookies, no stored wallet addresses. Last updated {LEGAL_UPDATED}.</p>
<h2>The website (evidencedeflator.com)</h2>
<p>Static pages hosted on GitHub Pages behind Cloudflare. We count page views with Cloudflare Web Analytics, which sets no cookies and does not identify you. When you check a wallet on the site, your browser asks Hyperliquid’s public API for that wallet’s history directly; the address is not sent to us. After a verdict is shown, the page sends our API one tally that says only “a check was done” and the page language, so we can count daily checks.</p>
<h2>The API and MCP server (api.evidencedeflator.com)</h2>
<p>When you or your AI assistant call the API or the MCP tool, the request carries a wallet address and, optionally, a number. Our server, a Cloudflare Worker, forwards the address to Hyperliquid’s public info API to fetch that wallet’s history, scores it, and returns the result. We do not store the address or the result, and we have not turned on request logging for the Worker. Each completed check adds one tally to a daily count (whether it came from the API or the MCP tool), without the address or anything about the caller. Cloudflare, which runs the Worker, processes requests (including your IP address) under its own privacy policy. Hyperliquid receives the address under its own terms.</p>
<p>A wallet address on a public blockchain is public data. Do not send anything else; the tool does not need it.</p>
<h2>The Telegram bot and the Chrome extension</h2>
<p>The Telegram bot receives the messages you send it through Telegram, which processes them under its own privacy policy. The Worker above reads the address in your message, checks it the same way, replies, and keeps nothing: not the message, not your chat or user ID. Each check adds one tally to the daily count.</p>
<p>The Chrome extension reads the address or trader ID in the URL of the page you are on and fetches that record directly from the exchange's public API (Hyperliquid, Binance or OKX). It sends nothing about the trader or you to us; it only downloads our daily board sizes. It has no analytics.</p>
<h2>The Python package, Claude Code plugin and skill</h2>
<p>They run on your machine. The plugin’s backtest counter keeps a small log of matching shell commands in your local plugin data folder; it is never sent anywhere. The package and plugin contact Hyperliquid (and our API, if you use the hosted MCP tool) only when you check a wallet.</p>
<h2>Changes and contact</h2>
<p>If this changes, this page and its date change with it, and the history is public in the <a href="{REPO}">repository</a>. Questions: <a href="{issues}">GitHub issues</a>.</p>"""),
        "terms": ("Terms", "Terms for using Evidence Deflator's website, API, MCP server and open-source code.", f"""
<p class="lede" style="margin-top:14px">Free to use, open source, no warranty, not investment advice. Last updated {LEGAL_UPDATED}.</p>
<h2>What this is</h2>
<p>Evidence Deflator computes statistical estimates from public data: how strong a trading record is once you allow for its length and for how it was picked. The estimates rest on stated assumptions (listed on the <a href="/method/">method page</a>) and can be wrong. A record that passes is not a recommendation, and a past record is not your future return after fees, latency and slippage.</p>
<h2>Not advice</h2>
<p>Nothing here is investment, financial, legal or tax advice, or an offer to buy or sell anything. Do not use it as the only basis for a decision.</p>
<h2>Use of the API and MCP server</h2>
<p>You may call the hosted API and MCP server for free. Do not use them to overload the service or Hyperliquid’s API. We may rate-limit, change or stop the hosted service at any time; the code stays available.</p>
<h2>Code and data</h2>
<p>The code is MIT-licensed; see the <a href="{REPO}">repository</a>. Wallet data comes from Hyperliquid’s public API and belongs to its sources.</p>
<h2>No warranty</h2>
<p>The website, API, MCP server and code are provided “as is”, without warranty of any kind, and to the extent the law allows we are not liable for any loss arising from their use.</p>
<h2>Contact</h2>
<p><a href="{issues}">GitHub issues</a>.</p>"""),
    }
    for slug, (title, desc, body) in pages.items():
        page = head(f"{title} · Evidence Deflator", desc, f"/{slug}/") + header("") + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>{title}</div>
<h1 style="margin-top:16px">{title}</h1>
{body}
</article></div></main>
""" + footer()
        write(f"{slug}/index.html", page)


# IndexNow (Bing, Yandex, Seznam, Naver...): the key is public by design; the
# file at /<key>.txt proves we own the host. tools/indexnow.py submits URLs.
INDEXNOW_KEY = "b756502a8abaf3fb7bf6e69716e37269"
NOT_IN_SITEMAP = {"404.html", "macau.html", "pitch.html"}  # error page and live decks


# llms.txt (llmstxt.org): a plain-text map for language models. No evidence yet that
# answer engines read it; it costs one file.
LLMS_TXT = f"""# Evidence Deflator

> Checks whether a trading record can be told apart from luck once you allow for how it was picked. Paste a Hyperliquid wallet and get a verdict; the best of a leaderboard of ~47,000 accounts has to clear t >= 4.90, not 2. Open source (MIT), no account, not investment advice.

## Use it

- [Check a Hyperliquid wallet]({SITE}/wallet/): browser tool, the address is not sent to us
- [JSON API]({API_HOST}/api/wallet?a=0x393d0b87ed38fc779fd9611144ae649ba6082109): `GET /api/wallet?a=<address>&picked_from=<N>`
- [Remote MCP server]({API_HOST}/mcp): streamable HTTP, one read-only tool `hyperliquid_wallet(address, picked_from)`
- [API, Python package and plugin install]({SITE}/api/)

## Questions

- [Is this Hyperliquid trader skilled or just lucky?]({SITE}/q/hyperliquid-trader-skill-or-luck/)
- [How many months of backtest or track record are enough?]({SITE}/q/how-many-months-of-backtest/)
- [Why isn't the #1 trader on a leaderboard evidence of skill?]({SITE}/q/why-leaderboard-winner-is-not-evidence/)

## Method and data

- [Method]({SITE}/method/): t = Sharpe x sqrt(years) with a small-sample correction; Bonferroni bar for the best of N
- [Daily Hyperliquid board data]({SITE}/data/hl/latest.json) (CC BY 4.0)
- [Frozen forward cohort, 2026-10-14]({SITE}/data/hl/cohort-2026-10-14.json): 200 wallets scored only on PnL after the freeze
- [Source code]({REPO})
"""


def build_crawl_files():
    """robots.txt, sitemap.xml and the IndexNow key file, from the pages on disk."""
    with open(os.path.join(DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        fresh = json.load(f)["fetched"][:10]
    urls = []
    for root, _, files in os.walk(DOCS):
        for name in files:
            rel = os.path.relpath(os.path.join(root, name), DOCS).replace(os.sep, "/")
            if not name.endswith(".html") or rel in NOT_IN_SITEMAP:
                continue
            urls.append("/" + (rel[: -len("index.html")] if name == "index.html" else rel))
    urls.sort(key=lambda u: (u.count("/"), u))
    daily = {"/", "/wallet/"}  # rebuilt from the daily Hyperliquid data
    body = "".join(f"  <url><loc>{SITE}{u}</loc>" + (f"<lastmod>{fresh}</lastmod>" if u in daily else "") + "</url>\n"
                   for u in urls)
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n'
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + body + "</urlset>\n")
    # Everything is public and meant to be read and cited, by search and answer engines alike.
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    write(f"{INDEXNOW_KEY}.txt", INDEXNOW_KEY)
    write("llms.txt", LLMS_TXT)
    return urls


def main():
    with open(os.path.join(DOCS, "leaderboard", "2026-10.json"), encoding="utf-8") as f:
        lb = json.load(f)
    rows = build_audits()
    build_home(rows, lb)
    build_leaderboard(lb)
    build_method()
    build_api()
    build_wallet()
    build_polymarket()
    build_404()
    build_questions()
    build_legal()
    import site_zh
    site_zh.build(_sys.modules[__name__])
    inject_chrome()
    build_crawl_files()


if __name__ == "__main__":
    main()
