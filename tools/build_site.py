"""Build the static site in docs/ from one template.

    python tools/build_site.py

Writes: index.html (home), leaderboard/index.html, method/index.html,
audits/index.html + one page per audits/NNN-*.md, api/index.html, 404.html.
The calculator at check/index.html is hand-maintained (it carries a JS port of
the library that tools/check_js_parity.py diffs) and is not touched here.
Needs the `markdown` package for the audit pages; nothing at runtime.
"""
import html, json, os, re

import markdown

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DOCS = os.path.join(ROOT, "docs")
SITE = "https://evidencedeflator.com"
REPO = "https://github.com/Beltran12138/evidence-deflator"
ISSUE_AUDIT = REPO + "/issues/new?title=Audit%20request%3A%20&body=Link%20to%20the%20backtest%2C%20deck%20or%20claim%3A%0A%0AModel%20(if%20known)%3A%0ATest%20window%3A%0AHow%20many%20variants%20were%20tried%3A%0A"
VERSION = "0.2.0"

MARK = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="3" width="20" height="2.2" fill="var(--accent)"/>'
        '<rect x="3.5" y="13" width="3.2" height="8" fill="currentColor"/><rect x="8.6" y="9" width="3.2" height="12" fill="currentColor"/>'
        '<rect x="13.7" y="15" width="3.2" height="6" fill="currentColor"/><rect x="18.8" y="7.5" width="3.2" height="13.5" fill="currentColor" opacity=".55"/></svg>')
GH = ('<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>')
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='4' fill='%2315171C'/%3E"
           "%3Crect x='3' y='4' width='18' height='2' fill='%23E66A4B'/%3E%3Crect x='4.5' y='13' width='3' height='7' fill='%23FAF9F6'/%3E"
           "%3Crect x='9.5' y='9.5' width='3' height='10.5' fill='%23FAF9F6'/%3E%3Crect x='14.5' y='15' width='3' height='5' fill='%23FAF9F6'/%3E%3C/svg%3E")

NAV = [("leaderboard", "Leaderboard", "/leaderboard/"), ("audits", "Audits", "/audits/"),
       ("check", "Check a backtest", "/check/"), ("method", "Method", "/method/"), ("api", "API", "/api/")]

COPY_ICON = '<span class="cp">copy</span><span class="ok">copied</span>'


def head(title, desc, path, og=f"{SITE}/leaderboard/og-2026-10.png", extra=""):
    return f"""<!DOCTYPE html>
<html lang="en">
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
<link rel="stylesheet" href="/assets/chrome.css">
<link rel="stylesheet" href="/assets/site.css">
{extra}</head>
<body>
"""


def header(active):
    cur = ' aria-current="page"'
    links = "".join(f'<a href="{u}"{cur if k == active else ""}>{t}</a>' for k, t, u in NAV)
    return f"""<header class="site-header"><div class="container">
<a class="brand" href="/">{MARK}Evidence Deflator</a>
<nav class="nav" aria-label="Main">{links}</nav>
<div class="header-cta"><a class="gh" href="{REPO}">{GH}<span>GitHub</span></a></div>
</div></header>
"""


def footer(scripts=""):
    return f"""<footer class="site-footer"><div class="container">
<div class="foot-grid">
 <div><a class="brand" href="/">{MARK}Evidence Deflator</a>
  <p style="margin-top:14px;max-width:340px">How much of an AI trading result actually counts. Open-source checks for backtests and public leaderboards.</p></div>
 <div><h4>Product</h4><ul><li><a href="/leaderboard/">Leaderboard</a></li><li><a href="/audits/">Audits</a></li><li><a href="/check/">Check a backtest</a></li><li><a href="/api/">API</a></li></ul></div>
 <div><h4>Method</h4><ul><li><a href="/method/">How it works</a></li><li><a href="/method/#principles">Principles</a></li><li><a href="/leaderboard/2026-10.json">Data (JSON)</a></li></ul></div>
 <div><h4>Project</h4><ul><li><a href="{REPO}">GitHub</a></li><li><a href="https://pypi.org/project/evidence-deflator/">PyPI</a></li><li><a href="{ISSUE_AUDIT}">Request an audit</a></li></ul></div>
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

def build_home(rows, lb):
    la, ai = lb["boards"]
    feed = [
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
    page = head("Evidence Deflator · How much of an AI trading result actually counts?",
                "Open-source checks for AI trading backtests and public leaderboards: months the model may have seen, clean months a claim needs, and the bar after selection.", "/") + header("home") + f"""
<main>
<div class="container hero">
 <div class="eyebrow"><span class="dot"></span>Evidence checks for AI trading</div>
 <h1 class="display">How much of an AI trading result actually counts?</h1>
 <p class="lede">AI agents now write, backtest and rank strategies in minutes. Two things almost nobody reports: what the model may already have seen, and how many attempts the winner was picked from. Evidence Deflator turns both into numbers.</p>
 <div class="btns">
  <a class="btn btn-primary" href="/leaderboard/">See the October leaderboard <span class="arr">→</span></a>
  <a class="btn btn-secondary" href="/check/">Check a backtest</a>
  <button class="copy" data-copy="pip install evidence-deflator">$ pip install evidence-deflator {COPY_ICON}</button>
 </div>
 <div class="instrument">
  <div class="instrument-head"><span class="t"><b style="color:var(--ink);font-weight:550">{html.escape(la['board'])}</b> · each dot is one team’s t-statistic</span><a class="small" href="/leaderboard/#{la['id']}">Full board →</a></div>
  <div class="instrument-body chart" style="border:0;border-radius:0" id="hero-chart"></div>
  <div class="instrument-foot">
   <div><b class="c-accent">0 / {la['entries']}</b><span>teams reach even t = 2</span></div>
   <div><b>{la['t_bar_best_of_n']:.2f}</b><span>bar for the best of {la['entries']}</span></div>
   <div><b>{la['max_t']:.2f}</b><span>closest: {html.escape(la['max_t_name'])}, rank {la['max_t_rank']} by return</span></div>
   <div><b>~{round(la['months_to_winner']['sharpe_5'])} mo</b><span>before a winner could be named, at a true Sharpe of 5</span></div>
  </div>
 </div>
</div>

<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">The method</div><h2 style="margin-top:12px">Three numbers, before any performance figure</h2>
 <p>Each is plain arithmetic on inputs a project can state in one line. None needs the strategy’s code.</p></div><a class="more" href="/method/">Read the method →</a></div>
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
  <div><h3>Agent frameworks</h3><p>One call between “backtest” and “deploy”: flag runs whose window sits before the model’s cutoff, and charge the result for every variant tried.</p><p class="act"><a href="/api/">Python, CLI and MCP →</a></p></div>
  <div><h3>Competition operators</h3><p>Show a t-statistic next to return, and the date a winner could first be named. Carry records across phases so evidence accumulates.</p><p class="act"><a href="/leaderboard/">See the leaderboard →</a></p></div>
  <div><h3>Allocators and reviewers</h3><p>Send a deck, a backtest or a public claim. Get a one-page report: what is open-book, what is underpowered, what is missing.</p><p class="act"><a href="{ISSUE_AUDIT}">Request an audit →</a></p></div>
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
<script>LB.load('/leaderboard/2026-10.json').then(d=>{document.getElementById('hero-chart').innerHTML=LB.strip(d.boards[0],{h:170})});</script>
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

def build_method():
    page = head("Method · Evidence Deflator", "How Evidence Deflator computes open-book months, clean months needed, the bar after selection, and the earliest date a leaderboard could name a winner.", "/method/") + header("method") + f"""
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
    page = head("API · Evidence Deflator", "Use Evidence Deflator from Python, the command line, or any MCP client. Pure standard library, no keys, no network.", "/api/") + header("api") + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>API</div>
<h1 style="margin-top:16px">Python, CLI and MCP</h1>
<p class="lede" style="margin-top:14px">The engine is pure Python standard library: no keys, no network, no execution. Fetching data is the caller’s job.</p>
<div class="btns" style="margin:22px 0 8px"><button class="copy" data-copy="pip install evidence-deflator">$ pip install evidence-deflator {COPY_ICON}</button><span class="muted small">Python ≥ 3.8 · MIT</span></div>

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


def build_404():
    page = head("Not found · Evidence Deflator", "Page not found.", "/404.html") + header("") + """
<main class="container page-head" style="min-height:50vh"><div class="eyebrow"><span class="dot"></span>404</div>
<h1>This page cannot be ruled out as missing.</h1><p class="lede">Try the <a href="/leaderboard/">leaderboard</a>, the <a href="/audits/">audits</a> or the <a href="/">home page</a>.</p></main>
""" + footer()
    write("404.html", page)


def build_check():
    """Refresh the shared head links, header and footer inside the hand-maintained calculator."""
    p = os.path.join(DOCS, "check", "index.html")
    with open(p, encoding="utf-8") as f:
        s = f.read()
    links = "\n".join([
        f'<link rel="icon" href="{FAVICON}">',
        f'<link rel="canonical" href="{SITE}/check/">',
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap">',
        '<link rel="stylesheet" href="/assets/chrome.css">'])
    foot = "<footer" + footer().split("<footer", 1)[1].rsplit("</body>", 1)[0]
    for name, body in (("site-head", links), ("site-header", header("check")), ("site-footer", foot)):
        s = re.sub(rf"<!-- {name} -->.*?<!-- /{name} -->",
                   lambda m, name=name, body=body: f"<!-- {name} -->\n{body}\n<!-- /{name} -->", s, count=1, flags=re.S)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)
    print("refreshed check/index.html")


def main():
    with open(os.path.join(DOCS, "leaderboard", "2026-10.json"), encoding="utf-8") as f:
        lb = json.load(f)
    rows = build_audits()
    build_home(rows, lb)
    build_leaderboard(lb)
    build_method()
    build_api()
    build_404()
    build_check()


if __name__ == "__main__":
    main()
