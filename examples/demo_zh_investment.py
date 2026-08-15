# -*- coding: utf-8 -*-
"""三幕演示（中文 · 投研语境）：把「共享前提」问题演给不做加密的人看。

第一幕  今天大家都在做的：五个信号归一化 → 求平均 → 得到一个看起来毫无问题的分数
第二幕  加一个问题：它们在回答同一个问题吗 → 系统拒绝出分，并报出真正的盲区
第三幕  那什么才算真分歧：同一个问题，不同的答案 → 合法求平均 + 报出矛盾

标的 SMPL 为虚构的美股半导体标的，全部数字为演示用示意值，不构成任何投资意见。

运行：
    python examples/demo_zh_investment.py
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from decision_confidence import SourceObservation, build_report  # noqa: E402

SUBJECT = "SMPL"
W = 74


def rule(ch="─"):
    print(ch * W)


def act(n, title, subtitle=""):
    print()
    rule("═")
    print(f"  第{n}幕   {title}")
    if subtitle:
        print(f"          {subtitle}")
    rule("═")


def obs(sid, score, note, construct=None):
    return SourceObservation(
        source_id=sid,
        subject=SUBJECT,
        raw={"示意值": score},
        normalized_0_100=score,
        status="ok",
        note=note,
        construct=construct,
    )


# ── 五个信号：这是绝大多数多因子打分系统手里的东西 ──────────────────
SIGNALS = [
    ("PE历史分位",        72, "估值水位", "valuation"),
    ("EV/EBITDA分位",     65, "估值水位", "valuation"),
    ("数据中心capex指引",  30, "终端需求", "demand"),
    ("卖方目标价上调比例", 25, "卖方情绪", "sentiment"),
    ("13F机构持仓变化",    18, "资金持仓", "positioning"),
]


def _w(s):
    """终端显示宽度：CJK 与全角标点占 2 列。"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(s))


def _pad(s, width):
    return str(s) + " " * max(0, width - _w(s))


def table(rows, headers):
    widths = [max(_w(r[i]) for r in ([headers] + rows)) for i in range(len(headers))]
    print("  ".join(_pad(h, widths[i]) for i, h in enumerate(headers)))
    rule()
    for r in rows:
        print("  ".join(_pad(c, widths[i]) for i, c in enumerate(r)))


def zh_contradiction(c):
    """把库里的英文提示翻成中文（仅演示展示层，不动库）。"""
    d = c.detail
    if c.kind == "construct_mismatch":
        import re
        m = re.search(r"(\d+) distinct constructs in play \(([^)]+)\)", d)
        names = {"valuation": "估值水位", "demand": "终端需求",
                 "sentiment": "卖方情绪", "positioning": "资金持仓", "supply": "供给约束"}
        if m:
            zh = "、".join(names.get(x.strip(), x.strip()) for x in m.group(2).split(","))
            return (f"  [构念不匹配/提示] 场上有 {m.group(1)} 个构念（{zh}）——"
                    f"它们测的不是一回事，\n                     综合分未定义，请分别读每个构念的分数")
    if c.kind == "range":
        d = d.replace("spread", "组内极差").replace("within", "，构念 =") \
             .replace("valuation", "估值水位").replace("demand", "终端需求") \
             .replace("sentiment", "卖方情绪").replace("positioning", "资金持仓") \
             .replace("same question, different answers", "同一个问题，不同的答案")
        return f"  [组内极差/{c.severity}] {d}"
    return f"  [{c.kind}/{c.severity}] {d}"


# ══════════════════════════ 第一幕 ══════════════════════════
act(1, "今天大家都在做的", "五个信号 → 归一化 → 求平均")

table(
    [[n, s, "—"] for n, s, _, _ in SIGNALS],
    ["信号", "分数", "它在测什么"],
)
rule()

naive = sum(s for _, s, _, _ in SIGNALS) / len(SIGNALS)
print(f"综合分   : {naive:.0f}")
print("判定     : 中性")
print("提示     : （无）")
print()
print("  ← 请注意：这个结果看起来毫无问题。没有报错，没有警告，")
print("     数字落在合理区间，你可以直接把它写进周报。")


# ══════════════════════════ 第二幕 ══════════════════════════
act(2, "只多问一个问题", "这五个信号，在回答同一个问题吗？")

table(
    [[n, s, c] for n, s, c, _ in SIGNALS] + [["先进封装CoWoS产能", "缺", "供给约束"]],
    ["信号", "分数", "它在测什么"],
)
rule()

observations = [obs(n, s, f"{c}", key) for n, s, c, key in SIGNALS]
observations.append(
    SourceObservation(
        source_id="先进封装CoWoS产能",
        subject=SUBJECT,
        raw={},
        normalized_0_100=None,
        status="unavailable",
        note="拿不到数据",
        construct="supply",
    )
)

rep = build_report(SUBJECT, observations)
print(f"综合分   : {rep.composite if rep.composite is not None else 'none  ← 拒绝出分'}")
print(f"置信度   : {rep.confidence}")
for c in rep.contradictions:
    print(zh_contradiction(c))
print()
print("  ← 「估值贵不贵」和「数据中心需求好不好」求平均，等于把两把不同的尺子相加。")
print("     第一幕那个中性分，是这么来的。")
print("     另外：供给约束这一层一个可用源都没有 —— 不是低风险，是没测。")


# ══════════════════════════ 第三幕 ══════════════════════════
act(3, "那什么才算真分歧", "同一个问题，五家投行给出不同答案")

BROKERS = [("Goldman", 22), ("MorganStanley", 38), ("JPMorgan", 47), ("BofA", 58), ("Citi", 65)]
table([[b, s, "FY2027 EPS隐含的估值水位"] for b, s in BROKERS], ["投行", "分数", "它在测什么"])
rule()

rep2 = build_report(
    SUBJECT,
    [obs(f"{b}研报", s, "FY2027 EPS隐含估值", "valuation") for b, s in BROKERS],
)
print(f"综合分   : {rep2.composite}")
print(f"置信度   : {rep2.confidence}")
for c in rep2.contradictions:
    print(zh_contradiction(c))
print()
print("  ← 这一次平均是合法的：五家在回答同一个问题。")
print("     而它们答案差 43 分这件事，被明确报成矛盾，而不是被平均抹平。")

print()
rule("═")
print("  同一个引擎，两种相反的处理。")
print("  第二幕拒绝出分 —— 因为源在回答不同的问题。")
print("  第三幕给出分数并报矛盾 —— 因为源在回答同一个问题。")
print()
print("  只会说「不可比」的工具是不可证伪的。")
print("  第三幕的存在，才让第二幕的拒绝有意义。")
rule("═")
