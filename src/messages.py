"""User-facing strings for the time axis, in English and Chinese.

The code, the docs and the tool descriptions are English; the output used to be
Chinese, which meant an English reader who followed the README hit a wall of
characters on the first run. English is now the default and Chinese is opt-in.

**Why a table rather than gettext.** This is a dependency-free standard-library
project, and the browser copy in ``docs/index.html`` has to carry the same
strings with no build step. A plain dict is the only form both can hold, and
``tools/check_js_parity.py`` diffs the two — in **both** languages, because a
second language is a second place for them to drift.

Templates use ``str.format`` field names. **A field that appears in one language
must appear in the other**; ``test_messages.py`` asserts it, since a translation
that silently drops ``{months_required}`` still renders, just without the number
that made the sentence worth printing.
"""

from __future__ import annotations

from typing import Dict

__all__ = ["LANGS", "DEFAULT_LANG", "MESSAGES", "text", "resolve_lang"]

LANGS = ("en", "zh")
DEFAULT_LANG = "en"


def resolve_lang(lang: str = None) -> str:
    """Fall back to the default rather than raising on an unknown tag.

    A wrong language is a cosmetic problem; refusing to compute the window
    because of one would be worse than answering in English.
    """
    if lang is None:
        return DEFAULT_LANG
    lang = str(lang).lower().replace("_", "-").split("-")[0]
    return lang if lang in LANGS else DEFAULT_LANG


MESSAGES: Dict[str, Dict[str, str]] = {

    # ---- verdicts -------------------------------------------------------
    "verdict.no_holdout": {
        "en": "The backtest lies entirely before the knowledge cutoff. This range "
              "does not test whether the strategy makes money; it tests whether the "
              "model remembers. Nothing concluded from it can be relied on.",
        "zh": "回测区间完全落在知识截止日之前。这段区间检验的不是策略能否盈利，"
              "而是模型记不记得。任何由它得出的结论都不可采信。",
    },
    "verdict.underpowered": {
        "en": "There is a clean segment, but it is shorter than an inference needs. "
              "The correct reading is neither \"it works\" nor \"it does not\" — it is "
              "that this backtest has no power to tell you. It rejects nothing.",
        "zh": "有干净区间，但短于可做统计推断的长度。正确结论既不是「有效」也不是「无效」，"
              "而是「这个回测没有分辨能力」——它不能拒绝任何假设。",
    },
    "verdict.sufficient": {
        "en": "The clean segment reaches the length this Sharpe requires. That "
              "removes the length constraint and nothing else; it is not evidence "
              "the strategy works.",
        "zh": "干净区间达到该 Sharpe 所需的长度。这只解除了「长度」这一条限制，"
              "不构成策略有效的证据。",
    },

    # ---- caveats that travel with every result --------------------------
    "limits": {
        "en": "The bar uses t ~ SR*sqrt(T) (Lo 2002), which assumes i.i.d. returns; "
              "monthly returns are typically positively autocorrelated, inflating the "
              "naive t — so the length required here is a floor, never generous. "
              "Screening is corrected with Bonferroni, which controls the family-wise "
              "error rate and assumes the trials are independent; correlated variants "
              "make it conservative, and that discount must come from "
              "effective_trials as a measured value.",
        "zh": "阈值用 t ≈ SR·√T（Lo 2002），假设收益 i.i.d.；月度收益通常正自相关，"
              "会抬高朴素 t 值 —— 所以这里给出的所需长度是下限，真实需求只多不少。"
              " 变体筛选用 Bonferroni 校正，它控制族错误率且假设各次试验独立；"
              "变体彼此相关时偏保守，折扣须由 effective_trials 给出且应为实测值。",
    },
    "undeclared_selection": {
        "en": "No screening count was declared; treated as a single attempt. This is "
              "not a neutral default — it asserts the strategy was specified before "
              "anyone looked at the data. Self-reported counts also run low: the "
              "variant you glanced at and abandoned does not usually get counted.",
        "zh": "⚠ 未申报变体筛选次数，按「一次成型」处理。这不是中性默认，"
              "而是断言策略在看数据之前就定好了。自报次数还系统性偏低——"
              "看一眼就放弃的那个变体，通常不会被算进去。",
    },

    # ---- selection penalty ---------------------------------------------
    "penalty.single": {
        "en": "One attempt declared. That is a **claim**, not a neutral default: it "
              "asserts the strategy was specified before anyone looked at the data.",
        "zh": "申报只试过一个变体。这是一个**主张**，不是中性默认——"
              "它断言策略在看数据之前就定好了。",
    },
    "penalty.screened": {
        "en": "{trials} variants were screened{shrunk}, so the survivor's t-statistic "
              "is the maximum of several draws. The bar rises from t>={t_base:g} to "
              "t>={t_adjusted:.2f}, and the clean sample required goes from "
              "{months_base} to {months_adjusted} months (x{ratio:.1f}).",
        "zh": "筛选了 {trials} 个变体{shrunk}，胜出者的 t 值是多次抽样的最大值。"
              "门槛由 t≥{t_base:g} 抬到 t≥{t_adjusted:.2f}，"
              "所需干净区间从 {months_base} 个月增至 {months_adjusted} 个月"
              "（×{ratio:.1f}）。",
    },
    # The enclosing "penalty.screened" already names the trial count, so this
    # fragment must not repeat it — the Chinese did, which is how the field
    # sets came apart in the first place.
    "penalty.shrunk": {
        "en": " (counted as {n_eff:g} independent trials; the discount must be "
              "measured, not asserted)",
        "zh": "（按 {n_eff:g} 次独立试验计，折扣需为实测所得，不能自行声明）",
    },

    # ---- one-line summary ----------------------------------------------
    "summary": {
        "en": "{total_months} months of backtest, {open_book_months} of them inside "
              "the model's knowledge ({open_book_share:.1%}), leaving "
              "{effective_months}; a Sharpe of {target_sharpe:g} needs "
              "{months_required} months at {bar} -> {verdict}",
        "zh": "{total_months} 个月的回测，{open_book_months} 个月在模型的知识范围内"
              "（{open_book_share:.1%}），剩下 {effective_months} 个月；"
              "Sharpe {target_sharpe:g} 要在 {bar}上成立需要 {months_required} 个月 → {verdict}",
    },
    "summary.bar_plain": {
        "en": "t>={t_threshold:g}",
        "zh": "t≥{t_threshold:g} ",
    },
    "summary.bar_adjusted": {
        "en": "t>={t_adjusted:.2f} (corrected for {trials} variants)",
        "zh": "t≥{t_adjusted:.2f}（{trials} 个变体校正后）",
    },

    # ---- remedies, dispatched on cause ----------------------------------
    "remedy.sufficient": {
        "en": "The clean segment has reached {months_required} months, so length is "
              "no longer the constraint. That is not evidence the strategy works; it "
              "means the result is now eligible to be examined.",
        "zh": "干净区间已达 {months_required} 个月，长度不再是限制。"
              "但这不是策略有效的证据，只是它现在有资格被检验。",
    },
    "remedy.mark_open_book": {
        "en": "Report the open-book span ({start} .. {open_end}) separately and keep "
              "it out of the conclusion.",
        "zh": "把开卷区间（{start} .. {open_end}）的表现单独标出，不要混进结论。",
    },
    "remedy.declare_after_pass": {
        "en": "Declare how many variants were screened: this verdict currently rests "
              "on the assumption that you got it right first time, and that is a "
              "claim, not a neutral default.",
        "zh": "申报变体筛选次数：这个判决目前建立在「一次成型」的假设上，"
              "而那是一个主张，不是中性默认。",
    },
    "remedy.clean_only": {
        "en": "Report only the clean segment: mark {start} .. {open_end} as open book "
              "and exclude it from the conclusion.",
        "zh": "只报干净段，把 {start} .. {open_end} 标为开卷，不计入结论。",
    },
    "remedy.extend": {
        "en": "{need} months short: with the same model, the backtest would have to "
              "run to {ready} to be long enough.",
        "zh": "还差 {need} 个月：同一个模型下，回测终点要推到 {ready} 才够。",
    },
    "remedy.earlier_model": {
        "en": "Or use a model with an earlier knowledge cutoff: {latest} or earlier "
              "would be enough on this range.",
        "zh": "或换知识截止更早的模型：截止 {latest} 及更早即够。",
    },
    "remedy.earlier_model_insufficient": {
        "en": "An earlier model will not close the gap — the whole range is only "
              "{total_months} months, against {months_required} required.",
        "zh": "换更早的模型不够——整段只有 {total_months} 个月，达不到 {months_required} 个月。",
    },
    "remedy.measure_overlap": {
        "en": "Measure how much those {trials} variants overlap: treat their return "
              "series as columns and compute Kish's effective sample size (the top "
              "half of docs/index.html takes a pasted table), then report it as "
              "effective_trials. Charged at the full {trials}, the penalty here is an "
              "upper bound. The discount has to be measured, not asserted.",
        "zh": "量一下那 {trials} 个变体有多重合：把它们的收益序列当成列，"
              "算 Kish 有效源数（docs/index.html 上半部分可直接贴表），"
              "用 effective_trials 报实测值。现在按全额 {trials} 次计，惩罚是上界。"
              "折扣必须是量出来的，不是声明出来的。",
    },
    "remedy.already_discounted": {
        "en": "Screening is already discounted to {n_eff:g} independent trials; going "
              "lower requires actually trying fewer things, not editing this number.",
        "zh": "筛选已按 {n_eff:g} 次独立试验折算；再降只能靠真的少试，不能靠改这个数。",
    },
    "remedy.declare_trials": {
        "en": "Declare how many variants were screened: everything above assumes you "
              "got it right first time. If you screened, the requirement only grows.",
        "zh": "申报变体筛选次数：以上都假设你一次成型。若筛选过，所需长度只会更长。",
    },
    "remedy.claim_higher_sharpe": {
        "en": "Or change the claim — {effective_months} months is only enough to "
              "demonstrate a Sharpe of {sharpe:.2f}. But that is a claim to commit to "
              "in advance, not a tier to pick after seeing the result.",
        "zh": "或改声明——{effective_months} 个月只够证明 SR {sharpe:.2f} 的策略。"
              "但那是要先兑现的主张，不是事后挑的档位。",
    },
}


def text(key: str, lang: str = None, **kwargs) -> str:
    """Look up a message and format it.

    Raises ``KeyError`` on an unknown key — an unknown key is a bug in the
    caller, not a runtime condition, and returning the key as a placeholder
    would ship the bug to the reader.
    """
    entry = MESSAGES[key]
    template = entry[resolve_lang(lang)]
    return template.format(**kwargs) if kwargs else template


# ---------------------------------------------------------------------------
# Command-line labels. Separate block because they are layout, not argument:
# the sentences above carry the reasoning, these carry the table.
# ---------------------------------------------------------------------------

MESSAGES.update({
    "cli.header_dates": {
        "en": "Knowledge cutoff  {cutoff}        Backtest  {start} .. {end}",
        "zh": "模型知识截止  {cutoff}        回测区间  {start} .. {end}",
    },
    "cli.header_target": {
        "en": "Target Sharpe     {target_sharpe:g}        Bar  t >= {t_threshold:g}",
        "zh": "目标 Sharpe   {target_sharpe:g}           要求 t ≥ {t_threshold:g}",
    },
    "cli.section_split": {"en": "How the backtest range splits", "zh": "回测区间构成"},
    "cli.row_total": {"en": "total", "zh": "总长"},
    "cli.row_open": {"en": "open book (model has read)", "zh": "开卷（模型已见）"},
    "cli.row_clean": {"en": "clean (usable for testing)", "zh": "干净（可用于检验）"},
    "cli.unit_months": {"en": "months", "zh": "个月"},

    "cli.section_power": {
        "en": "Is that long enough to support an inference",
        "zh": "干净区间够不够支撑一个推断",
    },
    "cli.row_required": {"en": "required", "zh": "所需长度"},
    "cli.row_have": {"en": "available", "zh": "实有"},
    "cli.formula": {
        "en": "(t ~ SR*sqrt(T); at SR={target_sharpe:g}, T=({t_eff:.2f}/{target_sharpe:g})^2 years)",
        "zh": "（t ≈ SR·√T，SR={target_sharpe:g} 时 T=({t_eff:.2f}/{target_sharpe:g})² 年）",
    },
    "cli.of_requirement": {"en": "of requirement", "zh": "of requirement"},

    "cli.section_selection": {"en": "Screening correction", "zh": "变体筛选校正"},
    "cli.sel_declared": {"en": "variants declared", "zh": "申报变体数"},
    "cli.sel_counted": {"en": "counted as independent", "zh": "计入独立试验"},
    "cli.sel_discounted": {"en": "measured discount", "zh": "实测折扣"},
    "cli.sel_full": {
        "en": "undiscounted (upper bound)",
        "zh": "未折扣，按全额计（惩罚是上界）",
    },
    "cli.sel_bar": {"en": "t bar", "zh": "t 门槛"},
    "cli.sel_bonferroni": {
        "en": "(Bonferroni: alpha {alpha_base:.2e} -> {alpha_adjusted:.2e})",
        "zh": "（Bonferroni：α {alpha_base:.2e} → {alpha_adjusted:.2e}）",
    },
    "cli.sel_undeclared_tail": {
        "en": "Charged as one attempt, the requirement stays at {months_required} "
              "months. Declare with --trials N.",
        "zh": "按一次成型计，所需长度维持 {months_required} 个月。申报请加 --trials N。",
    },

    "cli.headline": {
        "en": "  >  {total_months} months of backtest, {effective_months} usable for "
              "testing, and you need {months_required}",
        "zh": "  ▶  {total_months} 个月的回测，能用来检验的是 {effective_months} 个月，"
              "而你需要 {months_required} 个月",
    },
    "cli.headline_no_holdout": {
        "en": "  >  {total_months} months of backtest, not one of them unseen by the model",
        "zh": "  ▶  {total_months} 个月的回测，没有一个月是模型没见过的",
    },

    "cli.section_verdict": {"en": "Verdict", "zh": "判决"},
    "cli.section_remedies": {"en": "What to do about it", "zh": "那要怎么办"},

    "cli.section_sweep": {"en": "Same range, different target Sharpe", "zh": "同一段区间，只换目标 Sharpe"},
    "cli.sweep_corrected": {
        "en": " (bar corrected for screening: t >= {t_eff:.2f})",
        "zh": "（门槛用筛选校正后的 t≥{t_eff:.2f}）",
    },
    "cli.sweep_row": {
        "en": "  SR {sr:<5g} needs {need:>4} months   have {have:>3}   {verdict}",
        "zh": "  SR {sr:<5g} 需要 {need:>4} 个月   实有 {have:>3} 个月   {verdict}",
    },
    "cli.sweep_note": {
        "en": "  (Required length grows with the inverse square of Sharpe: halve the "
              "target, quadruple the sample.)",
        "zh": "  （所需长度随 Sharpe 平方反比增长：目标减半，样本要四倍。）",
    },

    "cli.bad_input": {"en": "Invalid input: {err}", "zh": "输入无效：{err}"},
    "cli.arrow": {"en": "->", "zh": "→"},
})


# ---------------------------------------------------------------------------
# Browser-only strings. They live here rather than in the page so that the
# page's copy has a single source to be diffed against, the same as everything
# else the two implementations share.
# ---------------------------------------------------------------------------

MESSAGES.update({
    "web.err_trials": {
        "en": "Variants screened must be a whole number >= 1, or blank for undeclared.",
        "zh": "变体数要是 ≥1 的整数，或留空表示未申报。",
    },
    "web.err_eff_without_trials": {
        "en": "\"Independent trials\" given without \"variants screened\" — there is "
              "nothing to discount.",
        "zh": "填了「独立几次」却没填「筛选过几个变体」——没有可折扣的对象。",
    },
    "web.err_eff_range": {
        "en": "\"Independent trials\" must fall between 1 and the number of variants: "
              "attempts cannot be more independent than they are numerous.",
        "zh": "「独立几次」要在 1 和变体数之间：试验不可能比它的次数更独立。",
    },
    "web.err_dates": {
        "en": "Dates must be written YYYY-MM, with the month between 01 and 12.",
        "zh": "日期要写成 YYYY-MM，月份 01–12。",
    },
    "web.err_range_inverted": {
        "en": "The backtest end precedes its start.",
        "zh": "回测止早于回测起。",
    },
})
