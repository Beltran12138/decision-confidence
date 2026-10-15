"""Chinese pages: /zh-hans/ (Simplified) and /zh-hant/ (Traditional, Hong Kong usage).

Written once in Simplified Chinese. The Traditional pages are the same pages run through
OpenCC (s2t) and then HANT_WORDS, the Hong Kong word choices s2t does not make.
Called from tools/build_site.py, which passes itself in as B.
"""
import html

from opencc import OpenCC

_S2T = OpenCC("s2t")
HANT_WORDS = [("賬戶", "帳戶"), ("默認", "預設"), ("鏈接", "連結"), ("信息", "資訊"), ("打分", "評分"), ("周", "週"),
              ("纔", "才"), ("爲", "為"), ("喫", "吃"), ("着", "著")]  # s2t emits the older forms
# Language-switch labels are fixed per language, so they must not go through s2t.
LABELS = {"⟦JIAN⟧": "简体", "⟦FAN⟧": "繁體"}
LANGS = {"zh-Hans": "/zh-hans/", "zh-Hant": "/zh-hant/"}
HTML_LANG = {"zh-Hans": "zh-Hans", "zh-Hant": "zh-Hant-HK"}
FONTS = {  # Latin in the site's faces, Chinese in a system sans of the right script
    "zh-Hans": "'PingFang SC','Microsoft YaHei','Noto Sans SC'",
    "zh-Hant": "'PingFang HK','Microsoft JhengHei','Noto Sans TC'",
}
Q = [
    ("hyperliquid-trader-skill-or-luck", "这个 Hyperliquid 交易员是实力还是运气？", "实力还是运气？"),
    ("how-many-months-of-backtest", "回测或实盘记录要多少个月才够？", "要几个月？"),
    ("why-leaderboard-winner-is-not-evidence", "为什么排行榜第一名不算实力的证据？", "榜首不算证据"),
]
PRIVACY = "地址不会发送给我们；我们用 Cloudflare Web Analytics 统计页面访问和检验次数，不使用 cookie。"


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
    style = (f"<style>:root{{--serif:'Source Serif 4',Georgia,{FONTS[lang]},sans-serif;"
             f"--sans:Inter,{FONTS[lang]},system-ui,sans-serif}}</style>\n")
    return B.head(title, desc, path, extra=style + extra, lang=HTML_LANG[lang], alt=alt)


def header(B, P, lang, active, alt):
    cur = ' aria-current="page"'
    nav = [("wallet", "查钱包", P)] + [(slug, short, f"{P}q/{slug}/") for slug, _, short in Q] + [("method", "方法（英文）", "/method/")]
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
 <div><h4>产品</h4><ul><li><a href="{P}">查钱包</a></li><li><a href="/api/">API（英文）</a></li><li><a href="/">英文版首页</a></li></ul></div>
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
    T = dict(WALLET_T, checkPath=P + "check", selfPath=P)
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
 <p class="muted small">不构成投资建议。公开数据来自 <code>api.hyperliquid.xyz</code>，由你的浏览器直接读取。{PRIVACY} 方法：<a href="/method/">Method（英文）</a>、Lo (2002)、Bailey &amp; López de Prado (2014)。</p>
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
<p class="muted small">数字每天根据 <a href="/data/hl/latest.json">latest.json</a> 重建。方法：<a href="/method/">Method（英文）</a>。不构成投资建议。</p>
</article></div></main>
""" + footer(B, P)
        yield f"{P.strip('/')}/q/{slug}/index.html", finish(page, lang)


def build(B):
    import json, os
    with open(os.path.join(B.DOCS, "data", "hl", "latest.json"), encoding="utf-8") as f:
        hl = json.load(f)
    for lang, P in LANGS.items():
        B.write(f"{P.strip('/')}/index.html", wallet_page(B, hl, lang))
        for rel, page in question_pages(B, hl, lang):
            B.write(rel, page)
