"""User-facing strings for the time axis, in English and Chinese.

The code, the docs and the tool descriptions are English; the output used to be
Chinese, which meant an English reader who followed the README hit a wall of
characters on the first run. English is now the default and Chinese is opt-in.

**Why a table rather than gettext.** This is a dependency-free standard-library
project, and the browser copy in ``docs/index.html`` has to carry the same
strings with no build step. A plain dict is the only form both can hold, and
``tools/check_js_parity.py`` diffs the two — in **both** languages, because a
second language is a second place for them to drift. The page's copy is written
by ``tools/gen_js_messages.py``; run it after changing anything here, or let
``--check`` tell you it is stale.

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
    "cli.of_requirement": {"en": "of requirement", "zh": "达到所需长度"},

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

MESSAGES.update({
    "web.ph_paste": {
        "en": "subject\tgrowth\tvaluation\tquality\tsentiment\nNVDA\t4\t2\t5\t4\nAMD\t3\t3\t3\t3\n...",
        "zh": "标的\t增长\t估值\t质量\t情绪\nNVDA\t4\t2\t5\t4\nAMD\t3\t3\t3\t3\n...",
    },
    "web.ph_trials": {"en": "blank = undeclared", "zh": "留空＝未申报"},
    "web.ph_eff_trials": {"en": "blank = charge in full", "zh": "留空＝按全额"},
    "web.lang_note": {
        "en": "Numbers are identical in both languages; only the wording changes.",
        "zh": "两种语言的数字完全相同，只有措辞不同。",
    },
})

MESSAGES.update({
    "web.share_line": {
        "en": "Open book (model has read) {open_book_months} months, {open_book_share:.1%}",
        "zh": "开卷（模型已读）{open_book_months} 个月，占 {open_book_share:.1%}",
    },
    "web.row_have_clean": {"en": "clean months available", "zh": "实有干净区间"},
    "web.row_open_book": {"en": "open book", "zh": "开卷区间"},
    "web.none": {"en": "(none)", "zh": "（无）"},
    "web.quad_note": {
        "en": "Required length grows with the inverse square of Sharpe: halve the "
              "target, quadruple the sample. At t >= {t_eff:.2f} — SR 2.0 needs "
              "{m2} months, SR 1.0 needs {m1} months, SR 0.5 needs {m05} months.",
        "zh": "所需长度随 Sharpe 平方反比增长：目标减半，样本要四倍。"
              "t ≥ {t_eff:.2f} 下 — SR 2.0 需 {m2} 个月，SR 1.0 需 {m1} 个月，"
              "SR 0.5 需 {m05} 个月。",
    },
    "web.bar_corrected": {
        "en": " (the bar is already corrected for screening)",
        "zh": "（门槛已按筛选校正）",
    },
    "web.undeclared_title": {"en": "Not declared", "zh": "未申报"},
    "web.undeclared_body": {
        "en": "Charged as a single attempt, so the requirement stays at "
              "{months_required} months. This page cannot detect an understated "
              "count; it can only decline to read silence as zero.",
        "zh": "按「一次成型」处理，所需长度维持 {months_required} 个月。"
              "本页无法检测被低报的次数，只能拒绝把沉默当成零。",
    },
    "web.sel_declared_note": {
        "en": "the pool this one was picked out of",
        "zh": "从这么多候选里挑出了当前这一个",
    },
    "web.sel_full_note": {
        "en": "undiscounted, charged in full (the penalty is an upper bound)",
        "zh": "未折扣，按全额计（惩罚是上界）",
    },
    "web.sel_discounted_note": {"en": "measured discount applied", "zh": "已按实测折扣"},
    "web.sel_hint_full": {
        "en": "If those {trials} variants are highly correlated, charging the full "
              "count is too heavy. Paste their return series into the top half of "
              "this page; the effective-source count it returns is what belongs in "
              "\"of those, independent\". The discount has to be measured, not asserted.",
        "zh": "这 {trials} 个变体若彼此高度相关，全额计入就过重了。"
              "把它们的收益序列贴进本页上半部分，算出的有效源数就是「独立几次」该填的值。"
              "折扣必须是量出来的，不是声明出来的。",
    },
    "web.sel_hint_discounted": {
        "en": "Discounted to {n_eff:g} independent trials. Going lower requires "
              "actually trying fewer things, not editing this number.",
        "zh": "已按 {n_eff:g} 次独立试验折算。再往下降只能靠真的少试，不能靠改这个数。",
    },
})

# ---------------------------------------------------------------------------
# The third axis: counterfactual perturbation. Same discount, applied to the
# inputs — N judgements from one agent are worth fewer independent judgements
# than N suggests, if the agent is not actually reading the inputs.
# ---------------------------------------------------------------------------

MESSAGES.update({
    "cf.verdict.no_control": {
        "en": "Only one kind of perturbation was supplied, so nothing here is "
              "interpretable. Material changes alone cannot separate \"ignores its "
              "inputs\" from \"reacts to everything\"; cosmetic ones alone cannot "
              "show whether real changes register at all. Both are needed, for the "
              "same reason a control group is.",
        "zh": "只提供了一类扰动，结果无法解读。只有实质扰动，分不开「不看输入」和"
              "「对什么都反应」；只有表面扰动，看不出真实变化到底能不能触发它。"
              "两类都要，理由和需要对照组是同一个。",
    },
    "cf.verdict.no_power": {
        "en": "Even a perfect split — every material change flipping the conclusion "
              "and every cosmetic one leaving it alone — would not reach the "
              "significance bar with this many perturbations. The correct reading is "
              "not that the agent passed or failed, but that this audit cannot tell.",
        "zh": "即便结果完美分离——每次实质扰动都翻转、每次表面扰动都不翻——"
              "以现在的扰动次数也达不到显著性门槛。正确结论不是「通过」或「没通过」，"
              "而是这次审计分辨不了。",
    },
    "cf.verdict.memorised": {
        "en": "Cosmetic changes never moved the conclusion, and material ones did not "
              "move it significantly more. The agent is reciting rather than reading: "
              "an input it should have reacted to went past without effect.",
        "zh": "表面扰动一次都没有改变结论，而实质扰动也没有显著更能改变它。"
              "这个 agent 在复述而不是在读输入——本该引起反应的改动，过去了却没有反应。",
    },
    "cf.verdict.unstable": {
        "en": "A cosmetic change moved the conclusion at least once, and material ones "
              "did not do significantly better. Whatever drives this output, it is not "
              "the part of the input that matters — a conclusion that flips on a "
              "renamed ticker is not evidence either.",
        "zh": "至少有一次表面扰动改变了结论，而实质扰动并没有显著做得更好。"
              "驱动输出的不是输入里要紧的那部分——换个代码名就翻转的结论，同样不构成证据。",
    },
    "cf.verdict.responsive": {
        "en": "Material changes move the conclusion significantly more than cosmetic "
              "ones. That is the shape a reading agent should have — and it is all "
              "this says. It is not evidence the conclusion is correct.",
        "zh": "实质扰动对结论的影响显著大于表面扰动。这是一个真在读输入的 agent 该有的"
              "形状——也仅止于此，它不构成结论正确的证据。",
    },
    "cf.limits": {
        "en": "Whether a conclusion \"flipped\", and whether a change was material or "
              "cosmetic, are both supplied by the caller and cannot be checked here. "
              "Mislabel a material change as cosmetic and the audit passes; this is an "
              "escape hatch of the same kind as an undeclared trial count. The test is "
              "one-sided Fisher against the agent's own cosmetic flip rate rather than "
              "against an assumed rate, because how often a reading agent should flip "
              "is not knowable in advance.",
        "zh": "「结论是否翻转」与「这次改动算实质还是表面」都由调用方给出，本层无法核验。"
              "把实质扰动标成表面就能通过——这和不申报筛选次数是同一类逃生舱。"
              "检验用单边 Fisher，比的是这个 agent 自己的表面扰动翻转率，"
              "而不是某个假定的比率，因为「真在推理的 agent 该翻多少次」事先无从得知。",
    },
    "cf.summary": {
        "en": "{n_material} material perturbations flipped {material_flips} times "
              "({material_rate:.0%}); {n_cosmetic} cosmetic ones flipped "
              "{cosmetic_flips} times ({cosmetic_rate:.0%}); one-sided p={p_value:.4f} "
              "against alpha={alpha:g} -> {verdict}",
        "zh": "{n_material} 次实质扰动翻转了 {material_flips} 次（{material_rate:.0%}）；"
              "{n_cosmetic} 次表面扰动翻转了 {cosmetic_flips} 次（{cosmetic_rate:.0%}）；"
              "单边 p={p_value:.4f}，对照 alpha={alpha:g} → {verdict}",
    },

    "cf.remedy.add_cosmetic": {
        "en": "Add cosmetic perturbations — rename the ticker, shift the dates, change "
              "the magnitudes, reword the narration. Without them a low flip rate "
              "cannot be told apart from an agent that never flips.",
        "zh": "补上表面扰动——换标的代码、平移日期、改数量级、改写叙述措辞。"
              "没有它们，低翻转率和「这个 agent 从不翻转」区分不开。",
    },
    "cf.remedy.add_material": {
        "en": "Add material perturbations — flip good news to bad, reverse the policy "
              "direction, turn a beat into a miss. Cosmetic ones alone only show the "
              "agent is stable, not that it is reading anything.",
        "zh": "补上实质扰动——利好改利空、政策方向翻转、超预期改不及预期。"
              "只有表面扰动，最多说明它稳定，说明不了它在读什么。",
    },
    "cf.remedy.need_more": {
        "en": "{shortfall} more perturbations are needed: at this split, even a perfect "
              "result would only reach p={best_p:.4f}. A balanced {min_material}+"
              "{min_cosmetic} is the smallest set that can clear alpha={alpha:g} at all.",
        "zh": "还需要 {shortfall} 次扰动：按当前配比，即使结果完美也只能到 p={best_p:.4f}。"
              "能够达到 alpha={alpha:g} 的最小组合是 {min_material}+{min_cosmetic} 的均衡配置。",
    },
    "cf.remedy.inspect_unflipped": {
        "en": "List the {unflipped} material perturbations that did not flip the "
              "conclusion and read them one by one. Either the change was not material "
              "after all — in which case relabel it — or the agent did not read it.",
        "zh": "把那 {unflipped} 次没能翻转结论的实质扰动列出来逐条看。"
              "要么那次改动其实不算实质（那就改标注），要么 agent 根本没读它。",
    },
    "cf.remedy.inspect_flipped_cosmetic": {
        "en": "List the {flipped} cosmetic perturbations that did flip the conclusion. "
              "A conclusion that moves when only the ticker name changed is being "
              "driven by something other than the evidence.",
        "zh": "把那 {flipped} 次翻转了结论的表面扰动列出来看。"
              "只改了代码名就变的结论，驱动它的不是证据。",
    },
    "cf.remedy.not_a_pass": {
        "en": "This says the agent responds to material changes. It does not say the "
              "conclusion is right, and it says nothing about the other two axes — "
              "run the sources and the window separately.",
        "zh": "这只说明 agent 会对实质改动作出反应。它不说明结论正确，"
              "也不涉及另外两条轴——源和窗口要各自单独跑。",
    },
    "cf.remedy.labels_are_yours": {
        "en": "The material/cosmetic labels and the flip judgements are yours. Before "
              "quoting this verdict, check that a sceptic reading your perturbation "
              "list would classify them the same way.",
        "zh": "实质/表面的标注和「是否翻转」的判断都出自你自己。"
              "引用这个判决之前，先确认一个持怀疑态度的人看你的扰动清单，会给出同样的分类。",
    },

    # ---- the same axis in the browser -----------------------------------
    # The CLI takes two ratios; the page takes the runs one by one, because the
    # page is where the labels can be shown back. ``labels_are_yours`` asks the
    # reader to check that a sceptic would classify them the same way, and that
    # request is empty unless the list is on screen next to the verdict.
    "web.cf_kind_material": {"en": "material", "zh": "实质扰动"},
    "web.cf_kind_cosmetic": {"en": "cosmetic", "zh": "表面扰动"},
    "web.cf_expect_move": {
        "en": "the conclusion should move",
        "zh": "结论本该改变",
    },
    "web.cf_expect_hold": {
        "en": "the conclusion should not move",
        "zh": "结论本不该改变",
    },
    "web.cf_detail_ph": {"en": "what you changed", "zh": "你改了什么"},
    "web.cf_flipped_label": {"en": "flipped", "zh": "翻转了"},
    "web.cf_unchanged": {"en": "unchanged", "zh": "未翻转"},
    "web.cf_no_detail": {"en": "(not described)", "zh": "（未填写）"},
    "web.cf_col_flipped": {"en": "FLIPPED", "zh": "翻转"},
    "web.cf_col_runs": {"en": "RUNS", "zh": "次数"},
    "web.cf_col_rate": {"en": "RATE", "zh": "翻转率"},
    "web.cf_err_empty": {
        "en": "Record at least one perturbation. This page scores runs you have "
              "already made; it cannot make them for you.",
        "zh": "至少记录一次扰动。本页给你已经跑过的结果打分，不能替你跑。",
    },
    "web.cf_p_line": {
        "en": "one-sided Fisher, p = {p_value:.4f} against alpha = {alpha:g}",
        "zh": "单边 Fisher，p = {p_value:.4f}，对照 alpha = {alpha:g}",
    },
    "web.cf_p_none": {
        "en": "No p-value: one kind of perturbation is missing, so there is nothing "
              "to compare against.",
        "zh": "没有 p 值：缺一类扰动，没有可比的对照。",
    },
    "web.cf_best_line": {
        "en": "The best {n_total} perturbations split this way could reach is "
              "p = {best_p:.4f}.",
        "zh": "{n_total} 次扰动按当前配比，最好也只能到 p = {best_p:.4f}。",
    },
    "web.cf_best_is_floor": {
        "en": " That is already the best case, so no arrangement of these runs "
              "could clear the bar.",
        "zh": "这已经是最好情况——这些次数怎么排都过不了门槛。",
    },
    "web.cf_floor_line": {
        "en": "Floor at alpha = {alpha:g}: {total} perturbations, {material} "
              "material and {cosmetic} cosmetic, split perfectly.",
        "zh": "alpha = {alpha:g} 下的下限：{total} 次扰动（{material} 实质 + "
              "{cosmetic} 表面），且结果完美分离。",
    },
})
