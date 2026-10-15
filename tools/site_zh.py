"""Chinese pages: /zh-hans/ (Simplified) and /zh-hant/ (Traditional, Hong Kong usage).

Written once in Simplified Chinese. The Traditional pages are the same pages run through
OpenCC (s2t) and then HANT_WORDS, the Hong Kong word choices s2t does not make.
Called from tools/build_site.py, which passes itself in as B.
"""
import html

from opencc import OpenCC

_S2T = OpenCC("s2t")
HANT_WORDS = [("賬戶", "帳戶"), ("默認", "預設"), ("鏈接", "連結"), ("信息", "資訊"), ("打分", "評分"), ("周", "週"),
              ("纔", "才"), ("覈", "核"), ("爲", "為"), ("喫", "吃"), ("着", "著")]  # s2t emits the older forms
# Language-switch labels are fixed per language, so they must not go through s2t.
LABELS = {"⟦JIAN⟧": "简体", "⟦FAN⟧": "繁體"}
LANGS = {"zh-Hans": "/zh-hans/", "zh-Hant": "/zh-hant/"}
HTML_LANG = {"zh-Hans": "zh-Hans", "zh-Hant": "zh-Hant-HK"}
FONTS = {  # Latin in the site's faces, Chinese body in a system sans of the right script
    "zh-Hans": "'PingFang SC','Microsoft YaHei','Noto Sans SC'",
    "zh-Hant": "'PingFang HK','Microsoft JhengHei','Noto Sans TC'",
}
# Chinese headings in Source Han Serif (Noto Serif SC/TC), the CJK sibling of the site's
# Source Serif; Google Fonts serves it in slices, so a page loads only the glyphs it uses.
SERIF = {"zh-Hans": "Noto Serif SC", "zh-Hant": "Noto Serif TC"}
Q = [
    ("hyperliquid-trader-skill-or-luck", "这个 Hyperliquid 交易员是实力还是运气？", "实力还是运气？"),
    ("how-many-months-of-backtest", "回测或实盘记录要多少个月才够？", "要几个月？"),
    ("why-leaderboard-winner-is-not-evidence", "为什么排行榜第一名不算实力的证据？", "榜首不算证据"),
]
PRIVACY = "地址不会发送给我们。我们用 Cloudflare Web Analytics 统计页面访问，不使用 cookie；每完成一次检验，页面会向我们的接口记一次数，只带页面语言，不带别的。"


def hant(text):
    out = _S2T.convert(text)
    for a, b in HANT_WORDS:
        out = out.replace(a, b)
    return out


def finish(text, lang):
    if lang == "zh-Hant":
        text = hant(text)
    for k, v in LABELS.items():
        text = text.replace(k, v)
    return text


def months(t, sharpe):
    m = (t / sharpe) ** 2 * 12
    return f"{m:.0f} 个月" if m < 36 else f"{m / 12:.1f} 年"


def head(B, lang, title, desc, path, alt, extra=""):
    serif = SERIF[lang]
    style = (f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={serif.replace(" ", "+")}:wght@500;600&display=swap">\n'
             f"<style>:root{{--serif:'Source Serif 4',Georgia,'{serif}',{FONTS[lang]},serif;"
             f"--sans:Inter,{FONTS[lang]},system-ui,sans-serif}}"
             "h1,h2,h3{letter-spacing:0}h1{line-height:1.3}h2{line-height:1.35}</style>\n")
    return B.head(title, desc, path, extra=style + extra, lang=HTML_LANG[lang], alt=alt)


def header(B, P, lang, active, alt):
    cur = ' aria-current="page"'
    nav = [("wallet", "查钱包", P)] + [(slug, short, f"{P}q/{slug}/") for slug, _, short in Q] + [("method", "方法", f"{P}method/"), ("api", "API", f"{P}api/")]
    links = "".join(f'<a href="{u}"{cur if k == active else ""}>{t}</a>' for k, t, u in nav)
    switch = "".join(f'<a class="gh" href="{alt[k]}" hreflang="{k}" lang="{k}"{cur if k == lang else ""}>{t}</a>'
                     for k, t in (("zh-Hans", "⟦JIAN⟧"), ("zh-Hant", "⟦FAN⟧"), ("en", "EN")))
    return f"""<header class="site-header"><div class="container">
<a class="brand" href="{P}">{B.MARK}Evidence Deflator</a>
<nav class="nav" aria-label="主导航">{links}</nav>
<div class="header-cta">{switch}<a class="gh" href="{B.REPO}">{B.GH}<span>GitHub</span></a></div>
</div></header>
"""


def footer(B, P, scripts=""):
    qs = "".join(f'<li><a href="{P}q/{slug}/">{short}</a></li>' for slug, _, short in Q)
    return f"""<footer class="site-footer"><div class="container">
<div class="foot-grid">
 <div><a class="brand" href="{P}">{B.MARK}Evidence Deflator</a>
  <p style="margin-top:14px;max-width:340px">交易战绩是实力还是运气？开源的证据检验工具，看一份记录里有多少算数。</p></div>
 <div><h4>产品</h4><ul><li><a href="{P}">查钱包</a></li><li><a href="{P}api/">API</a></li><li><a href="{P}method/">方法</a></li><li><a href="/">英文版首页</a></li></ul></div>
 <div><h4>问题</h4><ul>{qs}</ul></div>
 <div><h4>项目</h4><ul><li><a href="{B.REPO}">GitHub</a></li><li><a href="/privacy/">隐私（英文）</a></li><li><a href="/terms/">条款（英文）</a></li></ul></div>
</div>
<div class="foot-note"><span>开源 · MIT · v{B.VERSION}</span><span>统计估计，不构成投资建议。</span></div>
</div></footer>
<script src="/assets/site.js"></script>
{scripts}</body>
</html>
"""


WALLET_T = {
    "say": {
        "loses": ["亏损，而且不是运气差", "tag-red", "t 不高于 −2：在能测量的那些周里，这个钱包亏得太稳定，运气解释不了。"],
        "luck": ["和运气分不开", "tag-red", "t 低于 2：这样的记录靠运气出现的频率太高，说明不了实力。"],
        "clears_single": ["过了单次检验，没过排行榜门槛", "tag-amber", "如果你是随手挑中这个钱包的，这个强度够了。如果你是在排行榜上找到它的，需要 t ≥ {BAR}。"],
        "clears_board": ["过了排行榜门槛", "tag-green", "即使考虑到它是从 {N} 个账户里挑出来的，这份记录也够强。"],
        "too_short": ["记录太短，还说不了", "tag-grey", "账户里至少有 $1,000 的历史不足 8 周。"],
    },
    "tag": {"loses": "亏损", "luck": "运气", "clears_single": "单次通过", "clears_board": "过门槛", "too_short": "太短"},
    "meterAria": "t 与两个门槛", "meterT2": "t = 2 · 单次检验", "meterBest": "{N} 选 1 · {bar}",
    "notAddr": ["这不是 Hyperliquid 地址", "应为 0x 加 40 位十六进制字符。"],
    "reading": "正在读取公开记录…", "noReach": "连不上 Hyperliquid", "noHist": "这个地址没有历史记录",
    "months": {"noSharpe": "至少要有 8 周记录才能估计",
               "never": ["永远", "夏普为零或负数时，多长的记录都过不了门槛"],
               "done": "个月：记录已经过了排行榜门槛",
               "more": "如果夏普保持不变，过排行榜门槛还需要的记录", "yr": " 年", "mo": " 个月"},
    "notes": {"no_losing_week": "记录里没有一个亏损周。这和做市、吃资金费率或卖尾部风险的策略一致；t 衡量的是稳定性，不是一笔还没发生的亏损有多大。",
              "one_week_majority": "单独一周贡献了一半以上的收益，这份记录主要靠那一周撑着。",
              "pnl_outside_record": "全期盈亏的大部分记在账户不足 $1,000 的时段，无法换算成收益率。结论只覆盖能测量的那些周。"},
    "wnote": "历史起于 {start}。{now} UTC 读取自 api.hyperliquid.xyz。",
}


def money(x):
    x = float(x)
    return f"${x/1e6:,.1f}M" if abs(x) >= 1e6 else f"${x/1e3:,.0f}k"


def wallet_page(B, hl, lang):
    P = LANGS[lang]
    pnl, roi, c = hl["boards"]["pnl"], hl["boards"]["roi30"], hl.get("cohort")
    N, bar, day = pnl["ranked_from"], pnl["t_bar_best_of_n"], hl["fetched"][:10]
    scored = sorted((r for r in pnl["rows"] if r["t"] is not None), key=lambda r: -r["t"])
    examples = [("PnL 榜前 100 里 t 最高的", scored[0]["address"]),
                ("PnL 榜前 100 的中位数", scored[len(scored) // 2]["address"]),
                ("30 日 ROI 榜第 1", roi["rows"][0]["address"])]
    ex = "".join(f'<button class="linkbtn" data-ex="{a}">{t}</button>' for t, a in examples)

    rows = ""
    for r in pnl["rows"][:15]:
        t = "—" if r["t"] is None else f"{r['t']:.2f}"
        w = 0 if r["t"] is None else min(abs(r["t"]) / bar, 1) * 100
        neg = " neg" if (r["t"] or 0) < 0 else ""
        dag = "<sup>†</sup>" if "pnl_outside_record" in r["flags"] else ""
        a = r["address"]
        rows += (f'<tr><td class="r">{r["rank"]}</td><td><a class="mono" href="{P}?a={a}">{a[:6]}…{a[-4:]}</a>'
                 f'{" · " + html.escape(r["display"]) if r.get("display") else ""}</td><td class="r">{money(r["pnl_all_time"])}</td>'
                 f'<td class="r">{r["weeks"] if r["weeks"] else "—"}</td><td class="r">{t}{dag}</td>'
                 f'<td><span class="mbar"><span class="track"><span class="fill{neg}" style="width:{w:.1f}%"></span>'
                 f'<span class="t2" style="left:{2 / bar * 100:.1f}%"></span></span></span></td></tr>')

    k = pnl["n_t_ge_bar"]
    verdict_h2 = (f"榜单按利润排名。前 100 名里，没有一个过得了「从 {N:,} 个账户里挑出来」的门槛。" if k == 0 else
                  f"榜单按利润排名。前 100 名里，只有 {k} 个过得了「从 {N:,} 个账户里挑出来」的门槛。")

    cohort_html = ""
    if c:
        frozen = c["frozen_at"][:10]
        reading = (f'<div><b class="c-accent">{c["n_t_ge_2"]} / {c["scored"]}</b><span>冻结以来的记录达到 t = 2</span></div>' if c["scored"] else
                   f'<div><b>{c["first_readings"]}</b><span>首次读数：钱包要在冻结后累积 8 周记录才有 t 值</span></div>')
        cohort_html = f"""
<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">前向记录 · {frozen} 冻结</div><h2 style="margin-top:12px">同样这 {c['members']} 个钱包，只按从冻结那一刻起的表现打分。</h2>
 <p>回头翻出来的战绩，都是事后挑过的。所以我们在 {frozen} 把当天两个前 100 名单冻结下来，每天公开每个钱包在那一刻之后的表现。冻结之前的一概不算，名单也改不了：它的哈希值在下面，修改历史在 git 里。</p></div></div>
 <div class="stats" style="margin:8px 0 18px">
  <div><b>{c['members']}</b><span>个钱包，冻结于 {c['frozen_at'].replace('T', ' ').replace('Z', ' UTC')}</span></div>
  {reading}
  <div><b>每天</b><span>由仓库里的定时任务从公开 API 刷新</span></div>
 </div>
 <p class="muted small mono" style="overflow-wrap:anywhere">{html.escape(c['file'])} · sha256 {c['sha256']}</p>
 <div class="btns" style="margin-top:12px"><a class="btn btn-secondary" href="/data/hl/{html.escape(c['file'])}">冻结名单</a><a class="btn btn-secondary" href="/data/hl/latest.json">每日分数（JSON）</a></div>
</div></section>
"""

    alt = {"en": "/wallet/", **LANGS}
    T = dict(WALLET_T, selfPath=P, countUrl=f"https://api.evidencedeflator.com/api/count?k=web&l={lang.lower()}")
    page = head(B, lang, "查 Hyperliquid 钱包：实力还是运气 · Evidence Deflator",
                "贴入任意 Hyperliquid 地址，看它的战绩能不能和运气分开，还差几个月才够。", P, alt,
                extra=B.ld({**B.APP_LD, "@type": "WebApplication", "name": "Evidence Deflator · 查 Hyperliquid 钱包",
                            "url": B.SITE + P, "operatingSystem": "Web", "inLanguage": HTML_LANG[lang]})) + header(B, P, lang, "wallet", alt) + f"""
<main>
<div class="container page-head">
 <div class="eyebrow"><span class="dot"></span>Hyperliquid · 钱包检验 · 公开数据，在你的浏览器里计算</div>
 <h1>贴一个 Hyperliquid 地址，看它的战绩有多少算数。</h1>
 <p class="lede">排行榜只告诉你谁赚得最多，不告诉你那会不会只是运气。这个页面读取钱包公开的盈亏历史，只回答一个问题：证据有多强，还要多久才可能够强？</p>
 <form class="wcheck" id="wform" autocomplete="off">
  <input id="waddr" name="a" placeholder="0x… Hyperliquid 地址" spellcheck="false" aria-label="Hyperliquid 地址">
  <button class="btn btn-primary" type="submit">检验 <span class="arr">→</span></button>
 </form>
 <div class="wex muted small">试试：{ex}</div>
</div>

<div class="container" id="wout" hidden>
 <div class="instrument wres">
  <div class="instrument-head"><span class="t mono" id="wid"></span><span id="wtag"></span></div>
  <div class="instrument-body"><h2 id="whead" style="margin:18px 4px 6px"></h2><p id="wsub" class="muted" style="margin:0 4px 10px"></p>
   <div class="chart" id="wmeter"></div></div>
  <div class="instrument-foot">
   <div><b id="wt">—</b><span>t 值，已按记录长度校正</span></div>
   <div><b id="ws">—</b><span>年化夏普比率（按周）</span></div>
   <div><b id="ww">—</b><span>账户高于 $1k 的周数</span></div>
   <div><b id="wm">—</b><span id="wml">按当前夏普，过排行榜门槛需要的记录月数</span></div>
  </div>
 </div>
 <ul class="wflags" id="wflags"></ul>
 <div class="btns" style="margin:18px 0 8px"><button class="btn btn-secondary copy" id="wcopy" data-copy=""><span class="cp">复制这个结果的链接</span><span class="ok">已复制</span></button>
  <a class="btn btn-secondary" id="whl" href="#" rel="noopener">在 Hyperliquid 上查看</a></div>
 <p class="muted small" id="wnote"></p>
</div>

<section><div class="container">
 <div class="sec-head"><div><div class="eyebrow">Hyperliquid 官方排行榜，重新打分 · {day}</div><h2 style="margin-top:12px">{verdict_h2}</h2></div></div>
 <div class="stats" style="margin:8px 0 26px">
  <div><b class="c-accent">{k} / {pnl['scored']}</b><span>全期 PnL 前 100 中，过「{N:,} 选 1」门槛（t ≥ {bar:.2f}）的数量</span></div>
  <div><b>{pnl['n_t_ge_2']} / {pnl['scored']}</b><span>假如是随手挑中、没经过筛选，能过单次检验（t ≥ 2）的数量</span></div>
  <div><b class="c-accent">{roi['n_t_ge_bar']} / {roi['scored']}</b><span>30 日 ROI 前 100（账户 ≥ $10k）中过门槛的数量；{roi['n_t_ge_2']} 个能过单次检验。</span></div>
 </div>
 <div class="table-wrap"><table class="data"><thead><tr><th class="r">PnL 排名</th><th>钱包</th><th class="r">全期 PnL</th><th class="r">周数</th><th class="r">t</th><th>占门槛的比例</th></tr></thead><tbody>{rows}</tbody></table></div>
 <p class="muted small" style="margin-top:10px">门槛：单个结果需要 t ≥ 2；从 N 个账户的榜单里扫出来的钱包，要过「N 选 1」的门槛，这里是 {bar:.2f}。† 这个钱包的大部分盈亏是在账户不足 $1,000 时记下的，无法换算成收益率；t 只覆盖能测量的那些周。全部 {pnl['shown']} + {roi['shown']} 行见 <a href="/data/hl/latest.json">latest.json</a>（由 <a href="{B.REPO}/blob/main/tools/build_hl_board.py"><code>tools/build_hl_board.py</code></a> 生成）。</p>
</div></section>
{cohort_html}
<section><div class="container narrow prose">
 <h2>怎么读一个钱包</h2>
 <p><strong>收益率来自盈亏，不来自账户余额。</strong>账户余额会随充值和提现变化，盈亏不会。每周收益率 = 累计盈亏在这一周的变化 ÷ 周初的账户价值。周初账户低于 $1,000 的周跳过。</p>
 <p><strong>按周算，因为历史数据就是这样存的。</strong>Hyperliquid 较早的历史大约一周一个点，最近的几分钟一个点。所有数据放到同一个周网格上；没有新数据点的周并入下一周，不记为零。</p>
 <p><strong>短记录不会被高估。</strong>只有几周数据算出来的 t 尾部很厚：8 周记录、完全没有实力，t ≥ 2 出现的频率大约是门槛假设的两倍。所以 t 取自按记录有效自由度计算的 Student t 分布（靠少数几段长间隔撑起来的记录，自由度更低），再换回常用的尺度。记录长时，它接近 夏普 × √年数；记录短时会更低。已检验：没有实力时，无论历史采样多稀疏，达到 2 的比例都保持在名义上的 2.3%。</p>
 <p><strong>两个门槛。</strong>如果你没有经过任何筛选就来看这个钱包，t ≥ 2 是常用门槛。如果你是在排行榜上排序找到它的，你就是从很多个里挑了最好的那个，门槛会随候选数量上升（对 {N:,} 个账户做 Bonferroni 校正：{bar:.2f}）。大多数人都是在排行榜上找到钱包的。</p>
 <p><strong>t 看不到什么。</strong>还没发生的尾部风险。卖保险式的策略可以很长时间没有一个亏损周。记录里没有亏损周、或者某一周贡献了大部分收益时，页面会标出来。</p>
 <p class="muted small">不构成投资建议。公开数据来自 <code>api.hyperliquid.xyz</code>，由你的浏览器直接读取。{PRIVACY} 方法：<a href="{P}method/">方法</a>、Lo (2002)、Bailey &amp; López de Prado (2014)。</p>
</div></section>
</main>
""" + footer(B, P, B.wallet_scripts(N, T))
    return finish(page, lang)


def question_pages(B, hl, lang):
    P = LANGS[lang]
    pnl, roi = hl["boards"]["pnl"], hl["boards"]["roi30"]
    N, day = pnl["ranked_from"], hl["fetched"][:10]
    bn, b100 = B._bar(N), B._bar(100)
    top10 = pnl["rows"][:10]
    outside = sum("pnl_outside_record" in r["flags"] for r in top10)
    unscored10 = sum(r["t"] is None for r in top10)
    api = f"，或者 <code>GET {B.API_HOST}/api/wallet?a=0x…</code>" if B.API_HOST else ""
    form = (f'<form class="wcheck" action="{P}" method="get" autocomplete="off" style="margin:22px 0">'
            '<input name="a" placeholder="0x… Hyperliquid 地址" spellcheck="false" aria-label="Hyperliquid 地址">'
            '<button class="btn btn-primary" type="submit">检验 <span class="arr">→</span></button></form>')
    r_ = ' class="r"'
    th = lambda *cols: "".join(f'<th{r_ if i else ""}>{c}</th>' for i, c in enumerate(cols))

    bodies = {
        "hyperliquid-trader-skill-or-luck": (
            f"把地址贴到下面。{day}，Hyperliquid 全期 PnL 前 100 里有 {pnl['scored']} 个钱包历史够长、可以打分。假如你是随手挑中它们的，"
            f"其中 {pnl['n_t_ge_2']} 个能过常用检验（t ≥ 2）；如果你是从 {N:,} 个账户的榜单里排序找到的，门槛是 t ≥ {bn:.2f}，"
            f"过了的有 {pnl['n_t_ge_bar']} 个。30 日 ROI 前 100 可打分的 {roi['scored']} 个里，分别是 {roi['n_t_ge_2']} 个和 {roi['n_t_ge_bar']} 个。",
            f"""{form}
<h2>这个检验做什么</h2>
<p>它读取钱包在 Hyperliquid 上的公开历史，换算成周收益率（累计盈亏在这一周的变化 ÷ 周初账户价值，所以充值和提现不算收益），再问这份记录有多强：t = 年化夏普 × √年数，并针对短记录和不规则记录做了校正。</p>
<h2>该用哪个门槛</h2>
<p>如果有人只发给你这一个钱包、你没有别的候选，t ≥ 2 是常用门槛。如果你是在排行榜上找到它的，它就是 {N:,} 个里最好的那个，人这么多，总有人正好走运。{N:,} 选 1 的门槛是 t ≥ {bn:.2f}（Bonferroni 校正）。大多数人都是在排行榜上找到钱包的。</p>
<h2>结论看不到什么</h2>
<p>卖保险式的策略可以很长时间没有亏损周。页面会标出三种情况：没有亏损周；某一周贡献了大部分收益；大部分盈亏是在账户不足 $1,000 时记下的、无法换算成收益率。{day} 的 PnL 前 10 里，有 {outside} 个带最后这个标记，{unscored10} 个可测量的历史太短，根本打不了分。</p>
<p>在 AI 助手里用：MCP 工具 <code>hyperliquid_wallet</code>{api}，或者<a href="{B.REPO}">仓库</a>里的 skill。</p>"""),
        "how-many-months-of-backtest": (
            f"如果真实年化夏普是 1，单个结果要约 48 个月才能达到 t = 2；夏普 2 要 12 个月。如果这个结果是试了很多次里最好的那个，需要更久："
            f"100 选 1 要 t ≥ {b100:.2f}，夏普 1 时是 {months(b100, 1)}。",
            f"""<h2>公式</h2>
<div class="eq">t = 夏普 × √年数        所需月数 = (t / 夏普)² × 12</div>
<p>这是 Lo (2002) 在收益独立同分布假设下的结果，所以是下限：收益有自相关时需要更久。</p>
<h2>对照表</h2>
<div class="table-wrap"><table class="lb-table"><thead><tr>{th("真实夏普", "单个结果（t ≥ 2）", f"100 选 1（t ≥ {b100:.2f}）", f"{N:,} 选 1（t ≥ {bn:.2f}）")}</tr></thead><tbody>
{"".join(f'<tr><td>{sh}</td><td class="r">{months(2, sh)}</td><td class="r">{months(b100, sh)}</td><td class="r">{months(bn, sh)}</td></tr>' for sh in (0.5, 1, 2, 3))}
</tbody></table></div>
<h2>哪些月份算数</h2>
<p>只有没被拿来拟合的月份才算。用大语言模型跑的回测，模型训练截止日之前的月份无法排除被模型见过，只有截止日之后的月份是干净的。<a href="/check/">Check a backtest（英文）</a>会帮你切分时间窗。对于你准备跟单的交易员，只有你选中他之后的记录，才检验得了你这次选择。</p>
<p>每一个试过的变体都要算上，包括被丢掉的。AI agent 一分钟就能试五十个；<a href="{B.REPO}">仓库</a>里的插件会边跑边计数。</p>"""),
        "why-leaderboard-winner-is-not-evidence": (
            f"因为榜首是很多次抽签里的最大值。{N:,} 个账户里，光靠运气就总会有人走运；{N:,} 选 1 要过 t ≥ {bn:.2f}，而不是 2。"
            f"{day}，Hyperliquid 全期 PnL 前 100 里可打分的 {pnl['scored']} 个钱包中，过了的有 {pnl['n_t_ge_bar']} 个。",
            f"""<h2>门槛随候选数量上升</h2>
<div class="table-wrap"><table class="lb-table"><thead><tr>{th("候选数量", "需要的 t")}</tr></thead><tbody>
{"".join(f'<tr><td>{n:,}</td><td class="r">{B._bar(n):.2f}</td></tr>' for n in (1, 10, 100, 1000, N))}
</tbody></table></div>
<p>这个门槛保证：一个没有实力的账户在整个榜单任何位置过线的概率，仍然是单次检验允许的 2.3%（对 α = 1 − Φ(2) 做 Bonferroni 校正）。把每个账户都当成独立的，在账户互相跟单时会高估这个惩罚；真正独立的下注数量未知，所以这张表给的是门槛的上限，合理的范围在它下面。</p>
<h2>利润排名不是收益率排名</h2>
<p>PnL 榜按美元排。收益率普通的大账户，会排在收益率惊人的小账户前面；记在几乎空账户里的盈亏，根本换算不成收益率。{day} 的全期 PnL 前 10 里，有 {outside} 个钱包的大部分盈亏是在账户不足 $1,000 时记下的。</p>
<h2>什么才算数</h2>
<p>事后找出来的记录，本来就是因为看起来好才被挑中的。干净的检验是前向的：先冻结名单，再看。我们在 2026-10-14 冻结了榜单前列的 200 个钱包，在<a href="{P}">钱包页面</a>公开每个钱包此后的表现。</p>"""),
    }
    others = "".join(f'<li><a href="{P}q/{slug}/">{q}</a></li>' for slug, q, _ in Q)
    for slug, q, _ in Q:
        lead, rest = bodies[slug]
        alt = {"en": f"/q/{slug}/", **{k: f"{v}q/{slug}/" for k, v in LANGS.items()}}
        faq = B.ld({"@type": "FAQPage", "inLanguage": HTML_LANG[lang], "mainEntity": [{"@type": "Question", "name": q,
                    "acceptedAnswer": {"@type": "Answer", "text": lead}}]})
        page = head(B, lang, f"{q} · Evidence Deflator", lead[:160], f"{P}q/{slug}/", alt, extra=faq) + header(B, P, lang, slug, alt) + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>问题 · 数据截至 {day}</div>
<h1 style="margin-top:16px">{q}</h1>
<p class="lede" style="margin-top:14px">{lead}</p>
{rest}
<h2>相关问题</h2><ul>{others}</ul>
<p class="muted small">数字每天根据 <a href="/data/hl/latest.json">latest.json</a> 重建。方法：<a href="{P}method/">方法</a>。不构成投资建议。</p>
</article></div></main>
""" + footer(B, P)
        yield f"{P.strip('/')}/q/{slug}/index.html", finish(page, lang)


def method_page(B, lang):
    P = LANGS[lang]
    alt = {"en": "/method/", **{k: f"{v}method/" for k, v in LANGS.items()}}
    page = head(B, lang, "方法 · Evidence Deflator", "Evidence Deflator 怎么算：开卷月数、需要多少干净月份、挑选之后的门槛，以及一个排行榜最早哪天能分出赢家。",
                f"{P}method/", alt) + header(B, P, lang, "method", alt) + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>方法</div>
<h1 style="margin-top:16px">用任何人都说得清的输入，做最朴素的算术</h1>
<p class="lede" style="margin-top:14px">本站每一个数字，都能用仓库里的脚本从公开数据重新算出来。不依赖我们自己的模型，也不需要策略的代码。</p>

<h2 id="wallet">0 · Hyperliquid 钱包</h2>
<p>钱包检验的算法写在<a href="{P}">钱包页面</a>底部「怎么读一个钱包」：周收益率来自盈亏（充值提现不算收益），t 按记录的有效自由度做小样本校正，门槛按挑选范围用下面第 3 节的 Bonferroni 公式抬高。</p>

<h2 id="open-book">1 · 开卷月数</h2>
<p>在模型官方公布的训练截止日把回测窗口切开。截止日当月及之前的月份，无法排除被模型见过：模型可能已经知道当时发生了什么。截止日之后的月份才是干净的。</p>
<div class="eq">窗口 2020-01 → 2025-06，截止日 2024-10
66 个月  =  58 个开卷  +  8 个干净</div>
<p>截止日只采用模型提供方自己的文档。没有公布的，我们直说没有，不替它估。截止日越早，结果看起来越好，所以它是最需要出处的那个输入。</p>

<h2 id="clean-months">2 · 需要多少干净月份</h2>
<p>年化夏普为 S 的结果，经过 T 年达到 t = 2，其中 t ≈ S × √T（Lo, 2002）：</p>
<div class="eq">所需月数 = (t / S)² × 12
夏普 2 → 12    夏普 1 → 48    夏普 0.5 → 192</div>
<p>如果干净的那段比这个短，这次回测就是<em>检验力不足</em>：它没有被证明失败，只是没有被证明有效。独立同分布假设让这个数成为下限；收益有自相关时需要更久。</p>

<h2 id="selection">3 · 挑选之后的门槛</h2>
<p>从 N 次尝试里挑出最好的那个结果，就是 N 次抽签的最大值。我们用单侧 Bonferroni 校正抬高门槛，并让只试一次时的门槛正好保持在 t = 2：</p>
<div class="eq">α      = 1 − Φ(2)          ≈ 2.3%，单侧
bar(N) = Φ⁻¹(1 − α / N)
N = 1 → 2.00    N = 41 → 3.26    N = 23,376 → 4.76</div>
<p>Bonferroni 假设各次尝试相互独立。相关的变体（同一个人调的参数网格、用同一个模型的不同队伍）会让它偏保守。我们把这一点写明，而不是换成一个读者无法核对假设的校正；如果测得了有效尝试次数，程序库也接受直接传入。</p>

<h2 id="leaderboards">4 · 排行榜</h2>
<p>每个参赛者取其公开的净值历史，每天保留最后一个值，算日收益率。加密货币榜按一年 365 天年化，股票日历按 252 天。</p>
<div class="eq">夏普 = 日收益率均值 / 日收益率标准差 × √(每年天数)
t    = 夏普 × √(数据年数)</div>
<p>单说「没有人显著」意义不大，所以每个榜单还会给一个日期：如果榜首的真实夏普是 S，它需要多少个月干净的前向记录才能过「N 选 1」的门槛。</p>
<div class="eq">分出赢家所需月数 = (bar(N) / S)² × 12</div>
<p>我们给出 S = 5、S = 2 以及最接近门槛那个参赛者实测夏普下的结果。这些是条件陈述，不是预测。</p>

<h2 id="principles">原则</h2>
<ul>
 <li>来源公开，并注明抓取日期。数字重新计算，不照抄。</li>
 <li>对模型训练数据，我们最强的说法是「无法排除被见过」，从不说「被污染」。</li>
 <li>缺少某个输入本身就是发现，不是对项目的判决。</li>
 <li>结论写明数字能支持什么、不能支持什么。不判断动机，不给投资建议。</li>
 <li>每个榜单、每个说法用同一条规则，不按曲线打分。</li>
 <li>更正会公开。你觉得哪个数字错了，请<a href="{B.REPO}/issues">提 issue</a>。</li>
</ul>

<h2 id="limits">这套方法不做什么</h2>
<ul>
 <li>它不说任何策略或模型没有实力，只说现有证据还分不清实力和运气。</li>
 <li>它不检测模型内部的泄漏，只划出无法排除泄漏的范围。</li>
 <li>它只用项目或榜单自己公开的东西。</li>
</ul>

<h2 id="reading">延伸阅读</h2>
<p class="small">Lo, “The Statistics of Sharpe Ratios” (2002). Bailey &amp; López de Prado, “The Deflated Sharpe Ratio” (2014). Zhang &amp; Stadie, “Temporal Leakage in LLM Backtesting” (arXiv 2608.02985).</p>
</article>
<aside class="aside">
 <div class="box"><h4>本页</h4><ul><li><a href="#wallet">Hyperliquid 钱包</a></li><li><a href="#open-book">开卷月数</a></li><li><a href="#clean-months">干净月份</a></li><li><a href="#selection">挑选之后的门槛</a></li><li><a href="#leaderboards">排行榜</a></li><li><a href="#principles">原则</a></li><li><a href="#limits">局限</a></li></ul></div>
 <div class="box"><h4>试一试</h4><ul><li><a href="{P}">查一个钱包</a></li><li><a href="/check/">在浏览器里检验回测（英文）</a></li><li><a href="{P}api/">API、MCP 与 Python</a></li></ul></div>
</aside>
</div></main>
""" + footer(B, P)
    return finish(page, lang)


def api_page(B, lang):
    P = LANGS[lang]
    alt = {"en": "/api/", **{k: f"{v}api/" for k, v in LANGS.items()}}
    page = head(B, lang, "API · Evidence Deflator", "在 Python、命令行或任何 MCP 客户端里使用 Evidence Deflator。托管的钱包检验接口免密钥。",
                f"{P}api/", alt) + header(B, P, lang, "api", alt) + f"""
<main class="container article"><div class="split">
<article class="prose">
<div class="eyebrow"><span class="dot"></span>API</div>
<h1 style="margin-top:16px">托管接口、MCP 与 Python</h1>
<p class="lede" style="margin-top:14px">查 Hyperliquid 钱包不用安装任何东西；检验回测的引擎是纯 Python 标准库，不要密钥、不联网、不执行代码。</p>

<h2 id="remote">托管：通过 HTTP 和 MCP 检验钱包</h2>
<p>托管接口读取钱包的公开历史并打分，用的是和<a href="{P}">钱包页面</a>在你浏览器里跑的同一套代码。</p>
<pre class="code solo">curl <span class="s">"https://api.evidencedeflator.com/api/wallet?a=0xADDRESS&amp;picked_from=47153"</span></pre>
<p><code>picked_from</code> 是你从多大的榜单里挑出这个钱包；不传就按「没经过筛选」处理，门槛是 2。</p>
<p>远程 MCP（Streamable HTTP，免密钥）：在 Claude、ChatGPT、Cursor 或任何 MCP 客户端里，把 <code>https://api.evidencedeflator.com/mcp</code> 添加为连接器。它只有一个只读工具 <code>hyperliquid_wallet(address, picked_from)</code>。在 Claude Code 里：</p>
<pre class="code solo">claude mcp add --transport http evidence-deflator https://api.evidencedeflator.com/mcp</pre>
<p>或者安装 Claude Code 插件。它带同一个工具、一个告诉 agent 如何汇报结论的 skill，以及一个给每次回测计数的 hook：</p>
<pre class="code solo">/plugin marketplace add Beltran12138/evidence-deflator
/plugin install evidence-deflator@evidence-deflator</pre>

<h2 id="python">Python</h2>
<div class="btns" style="margin:10px 0 14px"><button class="copy" data-copy="pip install evidence-deflator">$ pip install evidence-deflator <span class="cp">复制</span><span class="ok">已复制</span></button><span class="muted small">Python ≥ 3.8 · MIT</span></div>
<pre class="code solo"><span class="k">from</span> evidence_deflator <span class="k">import</span> effective_window, selection_penalty, months_for_power

w = effective_window(cutoff=<span class="s">"2024-10"</span>, start=<span class="s">"2020-01"</span>, end=<span class="s">"2025-06"</span>, trials=<span class="o">41</span>)
w.open_book_months   <span class="c"># 58  截止日当月及之前的月份</span>
w.effective_months   <span class="c"># 8   干净月份</span>
w.months_required    <span class="c"># 128 夏普 1、41 选 1 时需要的干净月份</span>
w.verdict            <span class="c"># 'underpowered'（检验力不足）</span>
w.to_dict()          <span class="c"># 全部结果，附文字推理</span>

selection_penalty(<span class="o">41</span>).t_adjusted   <span class="c"># 3.26</span>
months_for_power(<span class="o">2.0</span>)               <span class="c"># 12</span></pre>
<p class="small muted">用 <code>cutoff_source=</code> 传入模型提供方的文档链接；不传的话，结果会注明截止日未经核实。测得了尝试之间的相关程度时，传 <code>effective_trials=</code>。</p>

<h2 id="cli">命令行</h2>
<pre class="code solo">git clone {B.REPO}
cd evidence-deflator
python tools/window.py --cutoff 2024-10 --start 2020-01 --end 2025-06
python tools/record.py --start 2026-03 --end 2026-08 --sharpe 3 --trials 4800</pre>

<h2 id="mcp">本地 MCP 服务器</h2>
<p>适用于 Claude、Cursor 等 MCP 客户端，工具包括 <code>knowledge_window</code>、<code>track_record</code>、<code>counterfactual_audit</code>、<code>trace_audit</code> 和 <code>hyperliquid_wallet</code>。</p>
<pre class="code solo">pip install <span class="s">"evidence-deflator[mcp]"</span>

{{
  <span class="s">"mcpServers"</span>: {{
    <span class="s">"evidence-deflator"</span>: {{ <span class="s">"command"</span>: <span class="s">"evidence-deflator-mcp"</span> }}
  }}
}}</pre>

<h2 id="data">数据</h2>
<p>Hyperliquid 每日分数：<a href="/data/hl/latest.json"><code>/data/hl/latest.json</code></a>；冻结名单：<a href="/data/hl/cohort-2026-10-14.json"><code>/data/hl/cohort-2026-10-14.json</code></a>。AI 交易排行榜每期以 JSON 发布，CC BY 4.0：<a href="/leaderboard/2026-10.json"><code>/leaderboard/2026-10.json</code></a>。</p>
</article>
<aside class="aside">
 <div class="box"><h4>本页</h4><ul><li><a href="#remote">托管接口与 MCP</a></li><li><a href="#python">Python</a></li><li><a href="#cli">命令行</a></li><li><a href="#mcp">本地 MCP</a></li><li><a href="#data">数据</a></li></ul></div>
 <div class="box"><h4>链接</h4><ul><li><a href="https://pypi.org/project/evidence-deflator/">PyPI</a></li><li><a href="{B.REPO}">GitHub</a></li><li><a href="{P}method/">方法</a></li></ul></div>
</aside>
</div></main>
""" + footer(B, P)
    return finish(page, lang)


def build(B):
    import json, os
    with open(os.path.join(B.DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        hl = json.load(f)
    for lang, P in LANGS.items():
        B.write(f"{P.strip('/')}/index.html", wallet_page(B, hl, lang))
        B.write(f"{P.strip('/')}/method/index.html", method_page(B, lang))
        B.write(f"{P.strip('/')}/api/index.html", api_page(B, lang))
        for rel, page in question_pages(B, hl, lang):
            B.write(rel, page)
