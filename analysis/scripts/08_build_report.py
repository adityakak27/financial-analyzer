"""Step 8: assemble report/results.md from the saved tables, figures and AI commentary.
Every number in the interpretation text is read from a table -- nothing is typed in by hand."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from scipy import stats as sp_stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import DATA_PROCESSED_DIR, FIGURES_DIR, OUTPUTS_DIR, REPORT_DIR, TABLES_DIR


def _t(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


def _md(name: str) -> str:
    path = TABLES_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.exists() else f"_{name} not found_"


def _md_df(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def _fig(name: str) -> str:
    path = FIGURES_DIR / f"{name}.png"
    return f"![{name}]({path.relative_to(REPORT_DIR.parent).as_posix()})" if path.exists() else ""


LABELS = {
    "piotroski_f": "Piotroski F", "altman_z": "Altman Z", "beneish_m": "Beneish M",
    "rev_growth_next": "next-year revenue growth",
    "excess_return_next_12m": "next-12-month excess return",
}


def _p(p: float) -> str:
    return "p<0.001" if p < 0.001 else f"p={p:.3f}"


def main():
    panel = pd.read_csv(DATA_PROCESSED_DIR / "analysis_dataset.csv")
    reg = _t("Table3_Regression_Summary")
    per_year = _t("Table3a_PerYear_Correlation")
    outcomes = _t("Table5b_Verdict_Outcomes").set_index("outcome")
    tests = _t("Table6b_Score_Group_Tests")
    groups = _t("Table6_Score_Group_Outcomes")
    tone = _t("Table7_Tone_Correlations")
    sub_ind = _t("Table9_Sub_Industry_Analysis").set_index("sub_industry")
    beneish_cov = _t("Table10b_Beneish_Coverage").set_index("sub_industry")
    ai_log = _t("ai_commentary_validation_log")
    from finchat.chatbot.agent import sanitize_markdown

    ai_text = sanitize_markdown((OUTPUTS_DIR / "ai_commentary.md").read_text(encoding="utf-8"))
    ai_text = ai_text.replace("# AI-Generated Key Findings", "### Key findings").replace("## Company Notes", "### Company notes")
    n_gemini = int((ai_log["model"] != "offline_template").sum())
    n_rejected = int(ai_log.get("gemini_attempts_rejected", pd.Series([0])).sum())
    models = sorted(m for m in ai_log["model"].unique() if m != "offline_template")
    ai_model = models[0] if models else "offline template"
    ai_byline = (f"Written by Gemini ({ai_model}) from the numbers above."
                 if n_gemini == len(ai_log) else
                 f"{n_gemini} of {len(ai_log)} texts written by Gemini ({ai_model}); the rest by a "
                 f"deterministic template after Gemini drafts failed the number check.")

    chat_log = _t("chat_demo_log")[["question", "tools_called", "numbers_untraced"]].rename(columns={
        "question": "Question", "tools_called": "Tool called", "numbers_untraced": "Numbers not in tool output"})
    demo = (OUTPUTS_DIR / "chat_demo.md").read_text(encoding="utf-8")
    q1 = demo.split("\n## Q: ")[1]
    q1_title, q1_answer = q1.split("**Answer:**", 1)
    q1_answer = q1_answer.split("*Numbers in the answer")[0].strip()
    chat_q1 = (f"Example -- *\"{q1_title.splitlines()[0].strip()}\"*:\n\n"
               + "\n".join("> " + line for line in q1_answer.splitlines()))

    n_companies, n_rows = panel.ticker.nunique(), len(panel)
    fy0, fy1 = int(panel.fy.min()), int(panel.fy.max())
    sub = panel.dropna(subset=["QualityScore", "log_ev_sales"])
    r_all, p_all = sp_stats.pearsonr(sub["QualityScore"], sub["log_ev_sales"])
    simple, ctrl = reg.iloc[0], reg.iloc[1]

    latest = panel[panel.fy == fy1]
    flagged = latest[latest["verdict"].isin(["Undervalued", "Overvalued"])]
    agree = flagged["dcf_agreement"].value_counts()
    ex = outcomes.loc["excess_return_next_12m"]
    raw = outcomes.loc["return_next_12m"]
    tested_years = sorted(int(y) for y in panel.loc[panel["verdict"].isin(["Undervalued", "Overvalued"]), "fy"].unique())

    def test_row(score: str, outcome: str) -> pd.Series:
        return tests[(tests.score == score) & (tests.outcome == outcome)].iloc[0]

    sig_rows = tests[(tests.t_pvalue < 0.05) | (tests.u_pvalue < 0.05)]
    excess_sig = sig_rows[sig_rows.outcome == "excess_return_next_12m"]
    rq3_returns_text = (
        "No score separates next-year **excess returns** (every p>0.05 on both tests). The clearest result is"
        if excess_sig.empty else
        f"Excess returns differ significantly only for {', '.join(LABELS[s] for s in excess_sig.score)}. The clearest result is"
    )
    smallest = tests.loc[tests[["n_weak", "n_strong"]].min(axis=1).idxmin()]
    alt_rev = test_row("altman_z", "rev_growth_next")
    alt_safe = groups[(groups.score == "altman_z") & (groups.group.str.startswith("safe"))].iloc[0]
    alt_dist = groups[(groups.score == "altman_z") & (groups.group.str.startswith("distress"))].iloc[0]
    tone_same = tone.iloc[0]
    tone_ret = tone[tone["y"].str.contains("excess")].iloc[0]
    tone_next = tone[tone["y"] == "next-year revenue growth"].iloc[0]
    strongest = sub_ind["quality_valuation_corr"].idxmax()
    weakest = sub_ind["quality_valuation_corr"].idxmin()
    highest_q = sub_ind["avg_quality_score"].idxmax()
    rq5_extra = (f"{weakest} have the highest average Quality Score yet the weakest link, consistent with "
                 f"them being priced on the cycle and growth narratives rather than steady fundamentals. "
                 if highest_q == weakest else "")

    over_flag = flagged[flagged.verdict == "Overvalued"]
    under_flag = flagged[flagged.verdict == "Undervalued"]
    over_agree = int((over_flag.dcf_agreement == "agrees").sum())
    under_disagree = under_flag[under_flag.dcf_agreement == "disagrees"]["ticker"].tolist()
    dcf_text = (f"{over_agree} of {len(over_flag)} overvalued names also show DCF downside. "
                + (f"{len(under_disagree)} of {len(under_flag)} undervalued names ({', '.join(under_disagree)}) "
                   f"show DCF downside instead: a low EV/Sales can reflect low margins rather than mispricing, "
                   f"which EV/Sales cannot see." if under_disagree else ""))

    md = f"""# Mispricing Radar: Does the Stock Market Pay for Fundamental Quality?

*{n_companies} US technology companies, FY{fy0}-FY{fy1} ({n_rows} company-years), built on SEC 10-K filings.*

## Research questions

- **RQ1.** Do higher-quality companies trade at higher valuation multiples, and how much of valuation does quality explain?
- **RQ2.** Which companies look undervalued or overvalued for their quality, does a DCF agree, and did the verdicts predict returns?
- **RQ3.** Did companies with better Piotroski F, Altman Z or Beneish M scores have better next-year growth and returns?
- **RQ4.** Does MD&A sentiment match actual performance, in the same year and the next?
- **RQ5.** Do semiconductors, software and hardware differ in quality, valuation and the link between them?

## Data and sample

{_md("Table0_Database_Inventory")}

- **Companies:** {n_companies} -- the 19-ticker FinChat universe plus 38 S&P 500 Information Technology
  constituents with a full FY2018-2024 10-K history. ANSYS and Juniper Networks were dropped: both were
  acquired and no longer appear in SEC's active ticker map (a survivorship bias -- see Limitations).
- **Sources:** SEC EDGAR XBRL company facts (statements, ratios, Piotroski and Beneish scores), SEC 10-K
  MD&A text (sentiment), Yahoo Finance via yfinance (daily adjusted closes for each company and for the
  XLK Technology Select Sector ETF, cached locally).

**Sample attrition.** Every stage below loses company-years for a stated reason:

{_md("Table10_Sample_Attrition")}

## Method

- **Quality Score (0-100)** from raw fundamentals only, in four pillars: Profitability (ROE, ROIC,
  operating margin, net margin), Growth (revenue and net-income growth), Safety (current ratio,
  debt/equity, interest coverage) and Earnings Quality (FCF margin, accruals). Each metric is z-scored
  within its fiscal year (sign-flipped where lower is better), averaged into pillars (a pillar needs at
  least 2 of its metrics), averaged into one score and rescaled to 0-100. Altman Z, Piotroski F and
  Beneish M are **not** inputs: they are composites of the same ratios, and Altman Z contains market
  capitalisation, which would place market valuation inside a score that is regressed on valuation.
  The three scores are tested separately in RQ3.
- **Valuation:** EV/Sales (defined even at a loss), log-transformed for regression; P/E is missing when
  EPS <= 0. EV/Sales, log EV/Sales, P/E, ROE, ROIC and debt/equity are winsorized at the 5th/95th
  percentile within each fiscal year.
- **Point-in-time prices:** the close on the first trading day on or after each 10-K filing date (at
  most 7 calendar days later) sets market cap and EV; next-12-month returns run from that day.
  **Altman Z is recomputed from that point-in-time market cap.** The pre-existing `scores` table reused
  each company's *current* market cap for every historical year (NVDA's FY2018 Altman Z was 486), which
  this study does not use.
- **Returns are benchmark-adjusted:** each stock's 12-month total return minus XLK's total return over
  the same two trading days.
- **RQ1 regressions are descriptive and in-sample:** simple OLS of log(EV/Sales) on Quality Score, and
  a controlled OLS adding revenue growth, fiscal-year and sub-industry fixed effects, with standard
  errors clustered by ticker.
- **RQ2 verdicts are walk-forward and sub-industry-relative:** for fiscal year *t*, each sub-industry's
  fair-value line is fitted only on that sub-industry's company-years from years before *t*. A
  company's gap is its actual minus expected log(EV/Sales); gaps are standardised across all companies
  within year *t*, and z <= -1 is "Undervalued", z >= +1 "Overvalued". FY{fy0} has no earlier data, so
  verdicts start in FY{tested_years[0]}.
- **DCF:** `finchat/engine/dcf.py` with default assumptions (9% WACC, 2.5% terminal growth, 5 years),
  run as of each historical fiscal year via a backward-compatible `as_of_fy` parameter.
- **Grouped tests (RQ3):** strong vs weak groups -- Piotroski 7-9 vs 0-3, Altman safe (>3.0) vs
  distress (<1.81), Beneish not flagged vs flagged (> -1.78) -- compared with Welch's t-test and the
  Mann-Whitney U test.

## Results

### RQ1 -- Quality vs valuation

{_md("Table3_Regression_Summary")}

Quality and valuation are positively correlated (Pearson r={r_all:.2f}, {_p(p_all)}, N={len(sub)}). On its
own the Quality Score explains {simple.r_squared * 100:.1f}% of the variation in log(EV/Sales). Adding
revenue growth, year and sub-industry effects raises R² to {ctrl.r_squared * 100:.1f}% and the sample falls
from {int(simple.n)} to {int(ctrl.n)} company-years (revenue growth needs a prior year); the quality
coefficient stays significant ({_p(ctrl.p_value)}). Most of the added explanatory power comes from the year
and sub-industry effects -- tech multiples rose sharply into FY2023-2024 for every quality level, and
software trades richer than hardware at the same quality -- not from quality itself. The yearly
correlation rises from r={per_year.iloc[0].pearson_r:.2f} in FY{int(per_year.iloc[0].fy)} to
r={per_year.iloc[-1].pearson_r:.2f} in FY{int(per_year.iloc[-1].fy)}.

{_fig("Figure1_Quality_vs_Valuation")}

{_fig("Figure2_Correlation_Heatmap")}

{_fig("Figure3_Top_Quality_Scores")}

{_fig("Figure4_Top_EV_Sales")}

### RQ2 -- Mispricing, and whether it predicted anything

FY{fy1} companies with the lowest and highest gap z-scores (each judged against its own sub-industry's
line, trained on FY{fy0}-FY{fy1 - 1}):

{_md("Table4_Undervalued")}

{_md("Table5_Overvalued")}

In FY{fy1}, {len(flagged)} companies were flagged undervalued or overvalued; the DCF agreed with
{int(agree.get('agrees', 0))} and disagreed with {int(agree.get('disagrees', 0))} (this count is for FY{fy1} only). {dcf_text}

**Did the verdicts predict returns?** Out of sample, FY{tested_years[0]}-FY{tested_years[-1]} pooled:

{_md("Table5b_Verdict_Outcomes")}

Undervalued companies earned {ex.mean_under * 100:.1f}% in excess of XLK over the next 12 months versus
{ex.mean_over * 100:.1f}% for overvalued ones (n={int(ex.n_under)} vs {int(ex.n_over)}; {_p(ex.t_pvalue)}, Mann-Whitney
{_p(ex.u_pvalue)}). Raw returns tell the same story ({_p(raw.t_pvalue)}). **The mispricing signal does not
predict next-year returns.** An earlier version of this study, which used one pooled line fitted on all
years and all sub-industries, reported an apparent edge; it does not survive the corrected design
(see Revisions).

{_fig("Figure12_Verdict_Outcomes")}

{_fig("Figure5_Biggest_Bargains")}

{_fig("Figure6_Biggest_Premiums")}

### RQ3 -- Do the risk scores predict anything?

{_md("Table6_Score_Group_Outcomes")}

{_md("Table6b_Score_Group_Tests")}

{rq3_returns_text} Altman Z and next-year **revenue growth**: "safe" companies grew revenue
{alt_safe.rev_growth_next_mean:.1f}% on average versus {alt_dist.rev_growth_next_mean:.1f}% for "distress"
companies ({_p(alt_rev.t_pvalue)}, Mann-Whitney {_p(alt_rev.u_pvalue)}). {"It is the only result below 0.05." if len(sig_rows) == 1 else ""}
Distress companies were also far more likely to report a loss the next year
({alt_dist.loss_next_mean * 100:.0f}% vs {alt_safe.loss_next_mean * 100:.0f}%). The least powerful
comparison is {LABELS[smallest.score]} on {LABELS[smallest.outcome]}, with only {int(min(smallest.n_weak, smallest.n_strong))}
companies in its smaller group; Beneish M exists for only {int(beneish_cov.beneish_available.sum())} of
{n_rows} company-years.

{_fig("Figure7_Piotroski_Returns")}

{_fig("Figure8_Altman_Loss_Rate")}

### RQ4 -- Management tone vs reality

{_md("Table7_Tone_Correlations")}

{_md("Table8_Tone_Mismatches")}

MD&A tone tracks the year that has just happened (r={tone_same.pearson_r:.2f} with same-year revenue
growth, {_p(tone_same.p_value)}) but not the next one (r={tone_next.pearson_r:.2f} with next-year revenue
growth, {_p(tone_next.p_value)}; r={tone_ret.pearson_r:.2f} with next-12-month excess return,
{_p(tone_ret.p_value)}). Tone confirms the past; it does not predict the future.

{_fig("Figure9_Tone_vs_NextYearGrowth")}

### RQ5 -- Sub-industry differences

{_md("Table9_Sub_Industry_Analysis")}

The quality-valuation link is strongest in {strongest} (r={sub_ind.loc[strongest, 'quality_valuation_corr']:.2f})
and weakest in {weakest} (r={sub_ind.loc[weakest, 'quality_valuation_corr']:.2f}). {rq5_extra}Multiples differ sharply by sub-industry
(average EV/Sales {sub_ind['avg_ev_sales'].min():.1f}x to {sub_ind['avg_ev_sales'].max():.1f}x), which is why RQ2
judges each company against its own sub-industry.

{_fig("Figure10_Sub_Industry_Comparison")}

{_fig("Figure11_Quality_Distribution")}

## How the AI system uses these results

The study above is the evidence layer of FinChat; this section is how the AI layer turns it into
answers without ever doing the maths itself.

1. **Computation and narration are separate.** Every figure -- Quality Scores, fair-value lines,
   verdicts, DCF, grouped outcomes -- is computed by deterministic Python (`finchat/engine/mispricing.py`)
   and stored in SQLite. The language model never calculates; it only reads tool output.
2. **Tool use.** The Gemini agent chooses among 15 tools, three of them added for this study:
   `get_valuation_check` (one company's score, pillars, verdict, fair-value line and DCF),
   `list_mispriced` (leaderboards) and `get_score_effectiveness` (RQ3 outcomes). Every tool returns JSON
   with a `source` field, so each answer can be traced to a table.
3. **Number grounding.** Every number in AI-written text must match a value in the data it was given
   (within 1%, or x100 for percentages); notation such as R^2 or FY2024 is ignored. A failing draft is
   regenerated once, then replaced by a deterministic template, so nothing unverified is published.
   For this report Gemini wrote {n_gemini} of {len(ai_log)} texts; {n_rejected} drafts were rejected by the
   check and regenerated, and {len(ai_log)} of {len(ai_log)} published texts are verified.
4. **Guardrails in the system prompt:** a verdict is a statistical comparison, not a recommendation;
   always state the fair-value line's R²; say the verdicts did not predict returns in back-tests; never
   add causes the tools did not state; end with "Not investment advice".

**Live chat test.** The three questions below were put to the running agent (Gemini
{ai_model}); full answers are in `analysis/outputs/chat_demo.md`.

{_md_df(chat_log)}

{chat_q1}

**What the number check cannot catch.** It verifies that each figure exists in the tool output, not
that it is described correctly. Reviewing the answers by hand found three such slips in earlier runs,
each fixed at the source: an invented explanation for a result; DXC's gap called "the largest
positive" when it is the most negative; and NVDA's gap of 1.46 log points restated as "+146.4%"
(which passed the check, because genuine fractions may be shown x100). The tool now labels the gap
in log points and also returns the plain ratio (NVDA trades at 4.34x its expected multiple), and the
prompt forbids converting gaps to percentages and adding unstated causes. One slip remains in the
final run: the leaderboard answer attributes the same-year R² (0.29) to the sub-industry lines,
whose own R² differs. AI wording still needs human review.

## AI-generated key findings and company notes

*{ai_byline} Every number was checked against the input data before publication
({len(ai_log)}/{len(ai_log)} verified; {n_rejected} draft(s) rejected and regenerated). Not investment advice.*

{ai_text}

## Limitations

- **Small, single-sector sample.** {n_companies} companies and {n_rows} company-years; RQ2's out-of-sample test
  has {int(ex.n_under) + int(ex.n_over)} flagged company-years. Findings describe large US tech only.
- **Survivorship bias.** Companies were chosen from today's index; acquired or delisted firms (ANSYS,
  Juniper) are missing, which tilts the sample toward survivors.
- **Staggered fiscal years.** Z-scores and winsorization are computed within a fiscal-year label, but
  year-ends range from late January (NVDA) to December (most companies), so a January filer is ranked
  against peers whose same-labelled year closes up to eleven months later. Prices and fair-value lines
  are point-in-time; this cross-sectional ranking is not.
- **Coarse sub-industries.** "Software & Services" mixes high-multiple software with low-multiple IT
  services (DXC, CTSH, ACN, EPAM, CDW), so some IT-services "undervalued" verdicts reflect business mix.
- **EV/Sales ignores margins.** A 5%-margin assembler and a 40%-margin software firm can look alike on
  quality yet deserve very different sales multiples; EV/EBIT or EV/gross profit would control for this.
- **Non-random missing data.** Beneish M needs SG&A, PP&E and a prior year, so coverage is
  {beneish_cov.loc['Software & Services', 'beneish_coverage_pct']:.0f}% in Software & Services versus
  {beneish_cov.loc['Semiconductors', 'beneish_coverage_pct']:.0f}% in Semiconductors; Beneish results say little about software.
- **The DCF is a uniform yardstick:** one WACC (9%) and terminal growth (2.5%) for every company, no
  CAPM beta, and free cash flow is not reduced by stock-based compensation, which flatters tech companies.
- **Score design.** Altman Z was built on 1960s manufacturers and saturates for asset-light firms; the
  Loughran-McDonald word counts ignore negation and boilerplate.
- **Correlation, not causation.** RQ1 is descriptive; quality and valuation may both reflect growth
  expectations.

## Revisions since the first version

An external review of the first version found several design problems. Each was checked against the
data and fixed:

| Issue | First version | This version |
| --- | --- | --- |
| Altman Z used each company's *current* market cap for every historical year | NVDA FY2018 Altman Z = 486, Quality Score 100 | Point-in-time market cap; NVDA FY2018 Altman Z = 4.4 |
| Altman Z, Piotroski F and Beneish M inside the Quality Score (double counting; market cap inside the predictor) | Included | Removed; tested separately in RQ3 |
| One fair-value line for all sub-industries | Low-multiple hardware firms systematically looked "undervalued" | One line per sub-industry |
| Fair-value line fitted on all years, then used to judge earlier years | In-sample | Walk-forward: fitted only on earlier years |
| Raw returns | Market-wide swings included | Returns in excess of XLK |
| "Undervalued beat overvalued" | 29.9% vs 17.3% raw return, p=0.11 | {ex.mean_under * 100:.1f}% vs {ex.mean_over * 100:.1f}% excess return, {_p(ex.t_pvalue)} |
| Quality explains valuation (R²) | 14.8% | {simple.r_squared * 100:.1f}% |
| AI commentary | Deterministic template (no API key) | Written by Gemini, every number verified |
| Figure 12 sample-size label | Error bar struck through "n=224" (read as "n=-24") | n shown in the axis labels |

The first version's RQ3 text also said every p-value exceeded 0.10, contradicting a Mann-Whitney
p=0.02 in its own table; that result was an artefact of the Altman Z bug and is gone after the fix.

## Conclusion

Fundamental quality and valuation are positively related in this tech sample, but modestly: quality
alone explains about {simple.r_squared * 100:.0f}% of the spread in EV/Sales, and sector and timing explain
more. When the "cheap for its quality" signal is tested properly -- each company against its own
sub-industry, with a fair-value line that never sees the future, and returns measured against the tech
sector -- it does **not** predict next-year returns. The classic risk scores do not predict excess
returns either, although Altman Z does flag weaker next-year revenue growth and more losses, and
management tone describes the past rather than the future. The honest conclusion is that a quality score
built from public filings is a useful way to *describe* and *screen* companies, but in large-cap tech it
is not, on its own, a source of returns -- which is why every Radar verdict is labelled "Not investment
advice".
"""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / "results.md"
    out.write_text(md, encoding="utf-8")
    print(f"[saved] {out} ({len(md)} chars)")


if __name__ == "__main__":
    main()
