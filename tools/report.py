#!/usr/bin/env python3
"""The deliverable: one self-contained HTML audit of a score table.

Everything the other tools print to a terminal, arranged as the single page a
buyer can put in front of someone else. Nothing here computes anything new —
it calls the same ``within_label_rho`` / ``neff`` / bootstrap path the CLI
tools use, so the page and the terminal cannot disagree.

Three things it refuses to do, because they are the failure modes the whole
package exists to name:

* **No number without its interval.** The headline n_eff is printed with its
  bootstrap 95% interval, always. A single point estimate is the shape of claim
  this tool was written to argue against.
* **No silent caveats.** Whether the correlations were controlled on an outcome
  label, and how incomplete rows were handled, are printed in the body, not a
  footnote — they change the answer.
* **No recommendation.** The page reports how many independent sources a table
  is worth. What to do about it belongs to whoever owns the decision.

Self-contained: no external CSS, fonts, scripts or images, so it survives being
emailed, and a page that phones home is not an audit artefact.

    python tools/report.py .data/equity-roster.jsonl -o out/audit.html \\
        --title "AI 产业链选股模型" --draws 1000
"""

from __future__ import annotations

import argparse
import html
import os
import sys
from itertools import combinations

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from redundancy import collect, load_rows  # noqa: E402
from neff import greedy_order, key, neff, within_label_rho  # noqa: E402
from neff_ci import neff_of  # noqa: E402

CSS = """
*{box-sizing:border-box}
body{margin:0;padding:0;background:#F4F6F9;color:#1A1A1A;
 font-family:"Microsoft YaHei","PingFang SC","Hiragino Sans GB","Segoe UI",sans-serif;
 -webkit-font-smoothing:antialiased;line-height:1.6}
.sheet{max-width:940px;margin:26px auto;background:#fff;padding:44px 52px 34px;
 box-shadow:0 2px 14px rgba(0,0,0,.10)}
h1{font-family:"FangSong","STFangsong",serif;font-size:29px;color:#1F3864;margin:0 0 6px;
 font-weight:700;line-height:1.25}
.sub{color:#595959;font-size:14px;margin:0 0 18px}
.rule{border:0;border-top:2.5px solid #1F3864;margin:0 0 22px}
h2{font-size:17px;color:#1F3864;margin:30px 0 10px;font-weight:700;
 border-bottom:1px solid #D6DCE4;padding-bottom:7px}
.mn{font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;font-variant-numeric:tabular-nums}
.head{display:flex;align-items:baseline;gap:18px;flex-wrap:wrap;
 background:#EFF4FB;border-left:4px solid #4472C4;padding:18px 22px;margin:4px 0 6px}
.head .big{font-family:ui-monospace,Consolas,monospace;font-size:54px;font-weight:700;
 color:#1F3864;line-height:1}
.head .of{font-size:20px;color:#595959}
.head .ci{font-size:15px;color:#1A1A1A}
.verdict{font-size:15px;padding:12px 16px;margin:10px 0 0;border-left:4px solid #C00000;
 background:#FBEAEA}
.verdict.ok{border-left-color:#2E7D32;background:#E8F3E9}
table{width:100%;border-collapse:collapse;font-size:13.5px;margin:8px 0}
th{text-align:left;color:#1F3864;font-weight:700;border-bottom:1.5px solid #1F3864;
 padding:7px 9px;font-size:12.5px;letter-spacing:.02em}
td{padding:7px 9px;border-bottom:1px solid #E8EDF3}
td.n{text-align:right;font-family:ui-monospace,Consolas,monospace;font-variant-numeric:tabular-nums}
tr.hot td{background:#FBEAEA}
tr.hot td.n{color:#C00000;font-weight:700}
.bar{display:inline-block;height:9px;background:#4472C4;vertical-align:middle;margin-right:7px}
.bar.neg{background:#2E7D32}
.note{font-size:12.5px;color:#595959;line-height:1.55;margin:9px 0 0}
.limits li{font-size:13.5px;margin-bottom:7px}
.ft{margin-top:30px;padding-top:12px;border-top:1px solid #D6DCE4;
 font-size:11.5px;color:#8C8C8C;display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap}
.ft .mn{letter-spacing:.01em}
@media print{body{background:#fff}.sheet{box-shadow:none;margin:0;max-width:none}}
"""


def esc(x):
    return html.escape(str(x))


def fmt(x, n=2):
    return f"{x:.{n}f}"


def build(corpus, title, draws, seed, stamp):
    rows = load_rows(corpus)
    per_subject, missing = collect(rows)
    names = sorted({c for scores, _v, _l in per_subject for c in scores})
    if len(names) < 2:
        raise SystemExit("需要至少两个构念才谈得上冗余")

    labels = sorted({lab for _s, _v, lab in per_subject})
    n_sub = len(per_subject)

    rho, pair_n = {}, {}
    for a, b in combinations(names, 2):
        r, n = within_label_rho(per_subject, a, b)
        rho[key(a, b)] = 0.0 if r is None else r
        pair_n[key(a, b)] = n

    point = neff(names, rho)

    # Bootstrap over subjects — same path tools/neff_ci.py takes.
    import random
    rng = random.Random(seed)
    draws_out = []
    for _ in range(draws):
        sample = [per_subject[rng.randrange(n_sub)] for _ in range(n_sub)]
        try:
            draws_out.append(neff_of(sample, names))
        except ZeroDivisionError:
            continue
    draws_out.sort()

    def pct(p):
        i = min(len(draws_out) - 1, max(0, int(round(p * (len(draws_out) - 1)))))
        return draws_out[i]

    lo, hi = pct(0.025), pct(0.975)

    order = greedy_order(names, rho)
    steps, prev = [], 0.0
    for i in range(1, len(order) + 1):
        v = neff(order[:i], rho)
        steps.append((order[i - 1], v, v - prev))
        prev = v

    pairs = sorted(rho.items(), key=lambda kv: -abs(kv[1]))
    N = len(names)

    # ---- page ----
    p = []
    A = p.append
    A(f'<meta charset="utf-8"><title>有效源数审计 · {esc(title)}</title>')
    A(f"<style>{CSS}</style>")
    A('<div class="sheet">')
    A(f"<h1>有效源数审计：{esc(title)}</h1>")
    A(f'<p class="sub">{N} 个打分维度 · {n_sub} 个标的 · 语料 '
      f'<span class="mn">{esc(os.path.basename(corpus))}</span> · 生成于 {esc(stamp)}</p>')
    A('<hr class="rule">')

    A("<h2>结论</h2>")
    A('<div class="head">')
    A(f'<div><span class="big">{fmt(point)}</span> <span class="of">／ {N}</span></div>')
    A(f'<div class="ci">这 {N} 个维度实际相当于 <b>{fmt(point)}</b> 个互不相干的源，'
      f'效率 <b>{round(point / N * 100)}%</b><br>'
      f'<span class="mn">bootstrap 95% 区间 [{fmt(lo)}, {fmt(hi)}]</span>'
      f'（{len(draws_out)} 次重抽，对标的重抽）</div>')
    A("</div>")

    if hi < N:
        A(f'<p class="verdict">区间上界 <b class="mn">{fmt(hi)}</b> 仍小于 {N}——'
          f'即使按测量误差最乐观的一端读，<b>「这 {N} 个维度等于 {N} 份独立证据」'
          f'在 95% 水平上被排除。</b></p>')
    else:
        A(f'<p class="verdict ok">区间上界触到 {N}——本语料<b>不足以排除</b>'
          f'「这些维度确实互不相干」。结论是数据不够，不是维度冗余。</p>')

    A("<h2>哪两个在重复</h2>")
    A("<table><tr><th>维度对</th><th style='width:34%'>残余相关</th>"
      "<th style='text-align:right'>ρ</th><th style='text-align:right'>样本</th></tr>")
    for k, v in pairs:
        a, b = k
        hot = " class='hot'" if abs(v) >= 0.30 else ""
        w = min(100, abs(v) * 100)
        neg = " neg" if v < 0 else ""
        A(f"<tr{hot}><td>{esc(a)} ~ {esc(b)}</td>"
          f"<td><span class='bar{neg}' style='width:{w:.0f}px'></span></td>"
          f"<td class='n'>{'+' if v >= 0 else ''}{fmt(v)}</td>"
          f"<td class='n'>{pair_n.get(k, 0)}</td></tr>")
    A("</table>")
    A('<p class="note">相关是在每个标签分层<b>内部</b>算完再合并的（Fisher-z 加权）。'
      '两个指标只是因为都答对了而长得像，不该算重复；控制住结局才分得开这两件事。'
      '负相关会把有效源数抬到维度数之上——算术上正确，但也是小样本波动伤害最大的地方。</p>')

    A("<h2>逐个买入，第几个开始不划算</h2>")
    A("<table><tr><th>顺序</th><th>加入的维度</th>"
      "<th style='text-align:right'>累计有效源数</th>"
      "<th style='text-align:right'>本次增量</th></tr>")
    for i, (nm, v, d) in enumerate(steps, 1):
        hot = " class='hot'" if i > 1 and d < 0.30 else ""
        A(f"<tr{hot}><td class='n'>{i}</td><td>{esc(nm)}</td>"
          f"<td class='n'>{fmt(v)}</td><td class='n'>+{fmt(d)}</td></tr>")
    A("</table>")
    A('<p class="note">这是<b>买方的最好情形</b>：假设每一步都恰好选中了下一个最不重复的维度。'
      '真实采购不会这么走，所以实际增量只会更低。</p>')

    if N >= 3:
        best = worst = None
        for k in (3,) if N > 3 else ():
            for combo in combinations(names, k):
                v = neff(list(combo), rho)
                if best is None or v > best[0]:
                    best = (v, combo)
                if worst is None or v < worst[0]:
                    worst = (v, combo)
        if best and worst:
            A("<h2>同样买三个，选法决定一切</h2>")
            A("<table><tr><th>选法</th><th>组合</th>"
              "<th style='text-align:right'>有效源数</th></tr>")
            A(f"<tr><td>选对的三个</td><td>{esc(' + '.join(best[1]))}</td>"
              f"<td class='n'>{fmt(best[0])}</td></tr>")
            A(f"<tr class='hot'><td>选错的三个</td><td>{esc(' + '.join(worst[1]))}</td>"
              f"<td class='n'>{fmt(worst[0])}</td></tr>")
            A("</table>")
            A(f'<p class="note">差 <b>{fmt(best[0] / worst[0], 2)} 倍</b>——'
              f'而两份账单上都会写着「3 个数据源」。</p>')

    A("<h2>这份报告的边界</h2><ul class='limits'>")
    if len(labels) <= 1:
        A("<li><b>未控制结局。</b>该语料只有一个标签分层，所以上面的相关是"
          "<b>未条件化</b>的原始秩相关——这是相关性的<b>上界读法</b>，"
          "不是「控制结局后」的读法。有了可测的结局，这些数会变。</li>")
    else:
        A(f"<li><b>已控制结局。</b>相关在 {len(labels)} 个标签分层内部分别计算后合并。</li>")
    A("<li><b>重抽的是标的，不是格子。</b>标的才是从世界里抽出来的单位，"
      "同一个标的上的各维度是联动的。对格子重抽会切断这层联动，"
      "得到偏窄的区间——那是往好看的方向偏。</li>")
    A("<li><b>缺失行的处理会改变答案。</b>本次的口径见语料生成步骤；"
      "逐行剔除与逐对取样在同一份数据上会给出不同的数。"
      "这个差值本身不是误差，是口径选择。</li>")
    if missing:
        worst_missing = sorted(missing.items(), key=lambda kv: -len(kv[1]))[:3]
        txt = "、".join(f"{esc(c)}（{len(s)} 个标的无可用值）" for c, s in worst_missing)
        A(f"<li><b>覆盖不齐。</b>{txt}。覆盖率差异会让某些维度只在容易的标的上发言。</li>")
    A("<li><b>本报告不给出任何买卖建议。</b>它只回答一件事："
      "这张分数表实际值几份独立证据。怎么办，属于对这个决策负责的人。</li>")
    A("</ul>")

    A('<div class="ft">')
    A('<span>decision-confidence · MIT · '
      '<span class="mn">github.com/Beltran12138/decision-confidence</span></span>')
    A(f'<span class="mn">Kish n_eff · within-label Spearman · Fisher-z · '
      f'bootstrap seed {seed}</span>')
    A("</div></div>")
    return "\n".join(p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--title", default="未命名分数表")
    ap.add_argument("--draws", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260823)
    ap.add_argument("--stamp", default="", help="生成日期；留空则不标日期而非编一个")
    args = ap.parse_args()

    page = build(args.corpus, args.title, args.draws, args.seed,
                 args.stamp or "（未标注日期）")
    d = os.path.dirname(os.path.abspath(args.out))
    if d:
        os.makedirs(d, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"已写入 {args.out}  ({len(page)} 字符，无外部资源)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
