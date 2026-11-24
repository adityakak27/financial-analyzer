# Mispricing Radar: Does the Stock Market Pay for Fundamental Quality?

*57 US technology companies, FY2018-FY2024 (399 company-years), built on SEC 10-K filings.*

## Executive summary

**The market pays for fundamental quality, but only a little, and a "cheap for its quality" signal
does not predict returns.** A 0-100 Fundamental Quality Score built from SEC 10-K fundamentals
correlates with valuation at r=0.37 and explains 14.1% of the spread in
EV/Sales. Tested out of sample -- each company judged against its own sub-industry, with a fair-value
line fitted only on earlier years, and returns measured against the XLK tech ETF -- "undervalued"
companies did not beat "overvalued" ones. The classic risk scores do not predict excess returns, and
management tone describes the past rather than the future. Every number is computed by deterministic
code; the AI layer (Gemini) only narrates verified outputs, and each of its figures is checked
against the data before publication.

| Question | Hypothesis | Result | Verdict |
| --- | --- | --- | --- |
| RQ1 Quality vs valuation | Higher quality, higher multiple | r=0.37; quality explains 14.1% (p<0.001) | Supported, but weak |
| RQ2 Mispricing | "Undervalued" beats "overvalued" next year | -3.0% vs +1.1% vs XLK (p=0.642) | Not supported |
| RQ3 Risk scores | Strong scores beat weak scores | No excess-return edge; Altman flags weaker growth (p=0.006) | Mostly not supported |
| RQ4 Management tone | Upbeat tone, better results | Same year r=0.32; next year r=-0.01 | Describes the past only |
| RQ5 Sub-industries | Valuation logic differs by sector | Quality-valuation link r=0.07 to 0.50 | Supported |

![Screenshot_Radar_Chart](outputs/figures/Screenshot_Radar_Chart.png)

*The Mispricing Radar page in the FinChat app: each company's quality vs valuation, judged against its
own sub-industry's line, with leaderboards and a back-test caveat.*

## Research questions

- **RQ1.** Do higher-quality companies trade at higher valuation multiples, and how much of valuation does quality explain?
- **RQ2.** Which companies look undervalued or overvalued for their quality, does a DCF agree, and did the verdicts predict returns?
- **RQ3.** Did companies with better Piotroski F, Altman Z or Beneish M scores have better next-year growth and returns?
- **RQ4.** Does MD&A sentiment match actual performance, in the same year and the next?
- **RQ5.** Do semiconductors, software and hardware differ in quality, valuation and the link between them?

## Data and sample



- **Companies:** 57 -- the 19-ticker FinChat universe plus 38 S&P 500 Information Technology
  constituents with a full FY2018-2024 10-K history. ANSYS and Juniper Networks were dropped: both were
  acquired and no longer appear in SEC's active ticker map (a survivorship bias -- see Limitations).
- **Sources:** SEC EDGAR XBRL company facts (statements, ratios, Piotroski and Beneish scores), SEC 10-K
  MD&A text (sentiment), Yahoo Finance via yfinance (daily adjusted closes for each company and for the
  XLK Technology Select Sector ETF, cached locally).

**Sample attrition.** Every stage below loses company-years for a stated reason:

| Stage                                                              |   Company-years |
|:-------------------------------------------------------------------|----------------:|
| Company-years collected (57 x 7)                                   |             399 |
| With a Quality Score                                               |             396 |
| With EV/Sales (needs price + diluted shares)                       |             386 |
| RQ1 simple regression (Quality + EV/Sales)                         |             383 |
| RQ1 controlled regression (+ revenue growth, needs prior year)     |             330 |
| With a walk-forward verdict (FY2019+; FY2018 has no training data) |             332 |
| With a next-12m excess return                                      |             397 |
| With Piotroski F                                                   |             342 |
| With Altman Z (point-in-time)                                      |             375 |
| With Beneish M                                                     |             157 |

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
  within year *t*, and z <= -1 is "Undervalued", z >= +1 "Overvalued". FY2018 has no earlier data, so
  verdicts start in FY2019.
- **DCF:** `finchat/engine/dcf.py` with default assumptions (9% WACC, 2.5% terminal growth, 5 years),
  run as of each historical fiscal year via a backward-compatible `as_of_fy` parameter.
- **Grouped tests (RQ3):** strong vs weak groups -- Piotroski 7-9 vs 0-3, Altman safe (>3.0) vs
  distress (<1.81), Beneish not flagged vs flagged (> -1.78) -- compared with Welch's t-test and the
  Mann-Whitney U test.

## Results

### RQ1 -- Quality vs valuation

| Model                                                                  |   Slope on Quality Score | p-value   |    R² |   N |
|:-----------------------------------------------------------------------|-------------------------:|:----------|------:|----:|
| Simple (QualityScore only)                                             |                   0.026  | <0.001    | 0.141 | 383 |
| With controls (revenue growth, year FE, sub-industry FE; clustered SE) |                   0.0222 | 0.003     | 0.323 | 330 |

Quality and valuation are positively correlated (Pearson r=0.37, p<0.001, N=383). On its
own the Quality Score explains 14.1% of the variation in log(EV/Sales). Adding
revenue growth, year and sub-industry effects raises R² to 32.3% and the sample falls
from 383 to 330 company-years (revenue growth needs a prior year); the quality
coefficient stays significant (p=0.003). Most of the added explanatory power comes from the year
and sub-industry effects -- tech multiples rose sharply into FY2023-2024 for every quality level, and
software trades richer than hardware at the same quality -- not from quality itself. The yearly
correlation rises from r=0.18 in FY2018 to
r=0.54 in FY2024.

![Figure1_Quality_vs_Valuation](outputs/figures/Figure1_Quality_vs_Valuation.png)

![Figure2_Correlation_Heatmap](outputs/figures/Figure2_Correlation_Heatmap.png)

![Figure3_Top_Quality_Scores](outputs/figures/Figure3_Top_Quality_Scores.png)

![Figure4_Top_EV_Sales](outputs/figures/Figure4_Top_EV_Sales.png)

### RQ2 -- Mispricing, and whether it predicted anything

FY2024 companies with the lowest and highest gap z-scores (each judged against its own sub-industry's
line, trained on FY2018-FY2023):

| Ticker   | Sub-industry         |   Quality | EV/Sales   | Expected EV/Sales   |   Gap z | Verdict       | DCF upside   | DCF       |
|:---------|:---------------------|----------:|:-----------|:--------------------|--------:|:--------------|:-------------|:----------|
| DXC      | Software & Services  |      31.4 | 1.1x       | 3.5x                |   -2.75 | Undervalued   | +265.6%      | agrees    |
| CTSH     | Software & Services  |      37.4 | 1.9x       | 4.0x                |   -2.01 | Undervalued   | -41.5%       | disagrees |
| CDW      | Software & Services  |      28.6 | 1.8x       | 3.3x                |   -1.72 | Undervalued   | -70.7%       | disagrees |
| DELL     | Hardware & Equipment |      38.5 | 1.2x       | 2.0x                |   -1.67 | Undervalued   | -40.7%       | disagrees |
| HPQ      | Hardware & Equipment |      33.5 | 1.1x       | 1.7x                |   -1.56 | Undervalued   | -12.7%       | disagrees |
| JBL      | Hardware & Equipment |      31.1 | 1.1x       | 1.6x                |   -1.43 | Undervalued   | +114.4%      | agrees    |
| ACN      | Software & Services  |      47.7 | 3.5x       | 5.1x                |   -1.37 | Undervalued   | -47.7%       | disagrees |
| HPE      | Hardware & Equipment |      31.5 | 1.2x       | 1.6x                |   -1.24 | Undervalued   | +58.1%       | agrees    |
| APH      | Hardware & Equipment |      45.6 | 1.9x       | 2.6x                |   -1.22 | Undervalued   | +45.0%       | agrees    |
| AKAM     | Software & Services  |      44.8 | 3.8x       | 4.8x                |   -1.13 | Undervalued   | +24.3%       | agrees    |
| EPAM     | Software & Services  |      40.7 | 3.5x       | 4.4x                |   -1.12 | Undervalued   | -10.1%       | disagrees |
| SWKS     | Semiconductors       |      58.9 | 3.1x       | 3.7x                |   -1.03 | Undervalued   | +353.5%      | agrees    |
| GDDY     | Software & Services  |      41.3 | 4.5x       | 4.4x                |   -0.74 | Fairly valued | +85.6%       | n/a       |
| CRM      | Software & Services  |      66.2 | 8.4x       | 7.7x                |   -0.61 | Fairly valued | +17.3%       | n/a       |
| GLW      | Hardware & Equipment |      34.8 | 2.0x       | 1.8x                |   -0.55 | Fairly valued | -15.2%       | n/a       |

| Ticker   | Sub-industry         |   Quality | EV/Sales   | Expected EV/Sales   |   Gap z | Verdict       | DCF upside   | DCF    |
|:---------|:---------------------|----------:|:-----------|:--------------------|--------:|:--------------|:-------------|:-------|
| AVGO     | Semiconductors       |      54.8 | 17.9x      | 3.6x                |    1.84 | Overvalued    | -61.9%       | agrees |
| MPWR     | Semiconductors       |      44.4 | 15.5x      | 3.5x                |    1.66 | Overvalued    | -31.0%       | agrees |
| NVDA     | Semiconductors       |     100   | 17.9x      | 4.1x                |    1.62 | Overvalued    | -40.6%       | agrees |
| VRSN     | Software & Services  |      22.1 | 12.1x      | 2.9x                |    1.58 | Overvalued    | -21.2%       | agrees |
| ADI      | Semiconductors       |      39   | 12.1x      | 3.5x                |    1.27 | Overvalued    | -71.5%       | agrees |
| WDC      | Hardware & Equipment |      18.6 | 3.4x       | 1.0x                |    1.22 | Overvalued    | -225.6%      | agrees |
| CDNS     | Software & Services  |      52.1 | 17.1x      | 5.6x                |    1.06 | Overvalued    | -77.4%       | agrees |
| AMD      | Semiconductors       |      38.5 | 10.5x      | 3.5x                |    1.05 | Overvalued    | -88.7%       | agrees |
| KLAC     | Semiconductors       |      48.4 | 10.2x      | 3.6x                |    0.96 | Fairly valued | -59.3%       | n/a    |
| FICO     | Software & Services  |      57.7 | 17.9x      | 6.4x                |    0.92 | Fairly valued | -77.6%       | n/a    |
| KEYS     | Hardware & Equipment |      39.9 | 5.8x       | 2.1x                |    0.89 | Fairly valued | -61.8%       | n/a    |
| TXN      | Semiconductors       |      48.2 | 9.7x       | 3.6x                |    0.88 | Fairly valued | -92.4%       | n/a    |
| AAPL     | Hardware & Equipment |      53.2 | 8.9x       | 3.4x                |    0.82 | Fairly valued | -58.3%       | n/a    |
| SNPS     | Software & Services  |      45.8 | 11.9x      | 4.9x                |    0.69 | Fairly valued | -75.8%       | n/a    |
| MSI      | Hardware & Equipment |      43.2 | 5.5x       | 2.4x                |    0.6  | Fairly valued | -2.8%        | n/a    |

In FY2024, 20 companies were flagged undervalued or overvalued; the DCF agreed with
14 and disagreed with 6 (this count is for FY2024 only). 8 of 8 overvalued names also show DCF downside. 6 of 12 undervalued names (ACN, CDW, CTSH, DELL, EPAM, HPQ) show DCF downside instead: a low EV/Sales can reflect low margins rather than mispricing, which EV/Sales cannot see.

**Did the verdicts predict returns?** Out of sample, FY2019-FY2024 pooled:

| Outcome                |   n undervalued | Mean, undervalued   |   n overvalued | Mean, overvalued   | Difference   |   t-test p |   Mann-Whitney p |
|:-----------------------|----------------:|:--------------------|---------------:|:-------------------|:-------------|-----------:|-----------------:|
| Next-12m return vs XLK |              64 | -3.0%               |             44 | +1.1%              | -4.1%        |      0.642 |            0.815 |
| Next-12m raw return    |              64 | +22.1%              |             44 | +25.3%             | -3.2%        |      0.739 |            0.933 |

Undervalued companies earned -3.0% in excess of XLK over the next 12 months versus
1.1% for overvalued ones (n=64 vs 44; p=0.642, Mann-Whitney
p=0.815). Raw returns tell the same story (p=0.739). **The mispricing signal does not
predict next-year returns.** An earlier version of this study, which used one pooled line fitted on all
years and all sub-industries, reported an apparent edge; it does not survive the corrected design
(see Revisions).

![Figure12_Verdict_Outcomes](outputs/figures/Figure12_Verdict_Outcomes.png)

![Figure5_Biggest_Bargains](outputs/figures/Figure5_Biggest_Bargains.png)

![Figure6_Biggest_Premiums](outputs/figures/Figure6_Biggest_Premiums.png)

### RQ3 -- Do the risk scores predict anything?

| Score       | Group            |   N | Next-year revenue growth   | Next-12m return vs XLK   | Loss next year   |
|:------------|:-----------------|----:|:---------------------------|:-------------------------|:-----------------|
| Piotroski F | low (0-3)        |  26 | 8.0%                       | -6.1%                    | 22%              |
| Piotroski F | mid (4-6)        | 195 | 12.1%                      | -1.5%                    | 3%               |
| Piotroski F | high (7-9)       | 121 | 7.2%                       | +1.3%                    | 5%               |
| Altman Z    | distress (<1.81) |  57 | 5.7%                       | +0.6%                    | 32%              |
| Altman Z    | grey (1.81-3.0)  |  74 | 4.8%                       | -1.8%                    | 5%               |
| Altman Z    | safe (>3.0)      | 244 | 11.6%                      | +0.6%                    | 1%               |
| Beneish M   | flagged (>-1.78) |  10 | 20.0%                      | +14.4%                   | 0%               |
| Beneish M   | not flagged      | 147 | 8.3%                       | +0.6%                    | 4%               |

| Score       | Outcome                     |   n weak |   n strong | Mean, weak   | Mean, strong   |   t-test p |   Mann-Whitney p |
|:------------|:----------------------------|---------:|-----------:|:-------------|:---------------|-----------:|-----------------:|
| Piotroski F | next-12-month excess return |       26 |        120 | -6.1%        | +1.3%          |      0.324 |            0.622 |
| Piotroski F | next-year revenue growth    |       19 |        101 | 8.0%         | 7.2%           |      0.815 |            0.824 |
| Altman Z    | next-12-month excess return |       55 |        244 | +0.6%        | +0.6%          |      0.999 |            0.943 |
| Altman Z    | next-year revenue growth    |       49 |        204 | 5.7%         | 11.6%          |      0.006 |            0.02  |
| Beneish M   | next-12-month excess return |       10 |        146 | +14.4%       | +0.6%          |      0.263 |            0.168 |
| Beneish M   | next-year revenue growth    |        8 |        123 | 20.0%        | 8.3%           |      0.359 |            0.568 |

No score separates next-year **excess returns** (every p>0.05 on both tests). The clearest result is Altman Z and next-year **revenue growth**: "safe" companies grew revenue
11.6% on average versus 5.7% for "distress"
companies (p=0.006, Mann-Whitney p=0.020). It is the only result below 0.05.
Distress companies were also far more likely to report a loss the next year
(32% vs 1%). The least powerful
comparison is Beneish M on next-year revenue growth, with only 8
companies in its smaller group; Beneish M exists for only 157 of
399 company-years.

![Figure7_Piotroski_Returns](outputs/figures/Figure7_Piotroski_Returns.png)

![Figure8_Altman_Loss_Rate](outputs/figures/Figure8_Altman_Loss_Rate.png)

### RQ4 -- Management tone vs reality

| Tone measure       | Compared with                   |   N |   Pearson r | p-value   |
|:-------------------|:--------------------------------|----:|------------:|:----------|
| MD&A tone          | same-year revenue growth        | 335 |        0.32 | <0.001    |
| MD&A tone          | same-year ROE                   | 378 |        0.08 | 0.110     |
| MD&A tone          | next-year revenue growth        | 333 |        0.08 | 0.129     |
| MD&A tone          | next-12m excess return (vs XLK) | 395 |       -0.01 | 0.843     |
| YoY change in tone | revenue_growth_change           | 277 |        0.25 | <0.001    |

| Ticker   |   FY |   MD&A tone | Revenue growth   | Next-year revenue growth   |
|:---------|-----:|------------:|:-----------------|:---------------------------|
| TXN      | 2023 |        0.61 | -12.5%           | -10.7%                     |
| INTC     | 2022 |        0.38 | -20.2%           | -14.0%                     |
| TXN      | 2024 |        0.38 | -10.7%           | n/a                        |
| CDW      | 2023 |        0.35 | -10.0%           | -1.8%                      |
| TXN      | 2019 |        0.32 | -8.9%            | 0.5%                       |
| AMD      | 2023 |        0.26 | -3.9%            | 13.7%                      |
| TYL      | 2021 |       -0.11 | 42.6%            | 16.2%                      |
| GDDY     | 2021 |       -0.12 | 15.0%            | 7.2%                       |
| NXPI     | 2021 |       -0.14 | 28.5%            | 19.4%                      |
| KLAC     | 2020 |       -0.19 | 27.1%            | 19.2%                      |

MD&A tone tracks the year that has just happened (r=0.32 with same-year revenue
growth, p<0.001) but not the next one (r=0.08 with next-year revenue
growth, p=0.129; r=-0.01 with next-12-month excess return,
p=0.843). Tone confirms the past; it does not predict the future.

![Figure9_Tone_vs_NextYearGrowth](outputs/figures/Figure9_Tone_vs_NextYearGrowth.png)

### RQ5 -- Sub-industry differences

| Sub-industry         |   Company-years |   Avg Quality Score | Avg EV/Sales   | Avg next-12m return vs XLK   |   Quality-valuation r |
|:---------------------|----------------:|--------------------:|:---------------|:-----------------------------|----------------------:|
| Hardware & Equipment |             126 |                39.1 | 2.9x           | -2.5%                        |                  0.5  |
| Semiconductors       |             119 |                50.4 | 5.2x           | +5.4%                        |                  0.07 |
| Software & Services  |             154 |                47.4 | 7.1x           | -1.6%                        |                  0.34 |

The quality-valuation link is strongest in Hardware & Equipment (r=0.50)
and weakest in Semiconductors (r=0.07). Semiconductors have the highest average Quality Score yet the weakest link, consistent with them being priced on the cycle and growth narratives rather than steady fundamentals. Multiples differ sharply by sub-industry
(average EV/Sales 2.9x to 7.1x), which is why RQ2
judges each company against its own sub-industry.

![Figure10_Sub_Industry_Comparison](outputs/figures/Figure10_Sub_Industry_Comparison.png)

![Figure11_Quality_Distribution](outputs/figures/Figure11_Quality_Distribution.png)

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
   For this report Gemini wrote 21 of 21 texts; 1 drafts were rejected by the
   check and regenerated, and 21 of 21 published texts are verified.
4. **Guardrails in the system prompt:** a verdict is a statistical comparison, not a recommendation;
   always state the fair-value line's R²; say the verdicts did not predict returns in back-tests; never
   add causes the tools did not state; end with "Not investment advice".

**Live chat test.** The three questions below were put to the running agent (Gemini
gemini-flash-lite-latest); full answers are in `analysis/outputs/chat_demo.md`.

| Question                                         | Tool called             |   Numbers not in tool output |
|:-------------------------------------------------|:------------------------|-----------------------------:|
| Is Nvidia overvalued for its quality?            | get_valuation_check     |                            0 |
| Which tech companies look cheapest right now?    | list_mispriced          |                            0 |
| Do high Piotroski scores lead to better returns? | get_score_effectiveness |                            0 |

![Screenshot_Chat_Answer_Crop](outputs/figures/Screenshot_Chat_Answer_Crop.png)

*The live chat answering "Is Nvidia overvalued for its quality?"; the Outputs panel shows the
`get_valuation_check` tool call behind the answer.*

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

*Written by Gemini (gemini-flash-lite-latest) from the numbers above. Every number was checked against the input data before publication
(21/21 verified; 1 draft(s) rejected and regenerated). Not investment advice.*

### Key findings

An analysis of 57 companies across 383 company-years spanning FY2018-FY2024 reveals that fundamental quality shares a real but modest relationship with market valuation. The correlation between fundamental quality and valuation yields an r of 0.37, with an R² of 0.141, indicating that fundamental quality explains 14.1% of the variation in valuation. Furthermore, quality remains significant even when applying controls, yielding a p of 0.003. When testing out-of-sample verdicts for FY2019-FY2024, the data identified 12 companies categorized as undervalued in the latest year and 8 companies categorized as overvalued in the latest year. However, these verdicts did not successfully predict subsequent performance, as the undervalued group registered an average excess return versus XLK of -3.0%, while the overvalued group recorded an average excess return versus XLK of 1.1%, with a difference yielding a p of 0.64.

Additional fundamental tests produced varied outcomes across the sample. The Piotroski strong versus weak excess return test yielded a p of 0.32, and the Beneish clean versus flagged excess return test resulted in a p of 0.26. The Altman safe versus distress excess return test showed a p of 1.0. However, the Altman test highlighted distinct operational differences, with safe companies achieving a next-year revenue growth of 11.6% compared to 5.7% for distressed companies, a statistically significant difference with a p of 0.006. 

Finally, textual analysis of management tone demonstrated divergent relationships with growth and performance metrics. Management tone showed a correlation with same-year revenue growth of r = 0.32, but exhibited virtually no correlation with next 12-month excess returns, recording an r of -0.01. The data suggests that fundamental metrics relate to operational results and baseline valuations, but do not reliably track subsequent excess returns in this sample. Not investment advice.

### Example company notes (FY2024)

- **DXC (Undervalued):** For fiscal year 2024, DXC carries an undervalued verdict as it trades at 1.1x EV/Sales versus 3.5x expected for its quality compared to Software & Services peers on a fair-value line fitted only on earlier years. Its strongest pillar is earnings quality at 55.2, while its weakest pillar is profitability at 38.0. The DCF upside in percent is 265.6%, and the DCF supports the verdict.
- **DELL (Undervalued):** For fiscal year 2024, the data suggests DELL is undervalued in the Hardware & Equipment sub-industry as it trades at 1.2x sales versus 2.0x expected for its quality. Its strongest pillar score is safety at 77.3, while its weakest pillar score is profitability at 28.1. The DCF upside in percent is -40.7, and the DCF does not support the verdict.
- **NVDA (Overvalued):** For fiscal year 2024, the verdict on NVDA in Semiconductors is Overvalued because it trades at an actual EV/Sales multiple of 17.9x versus an expected EV/Sales multiple of 4.1x for its quality. Its strongest pillar is growth at 100.0, while its weakest pillar is earnings quality at 57.3. The DCF upside is -40.6%, and the DCF supports the verdict, as the data suggests.

*All 20 notes are in `analysis/outputs/ai_commentary.md`.*

## Limitations

- **Small, single-sector sample.** 57 companies and 399 company-years; RQ2's out-of-sample test
  has 108 flagged company-years. Findings describe large US tech only.
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
  14% in Software & Services versus
  67% in Semiconductors; Beneish results say little about software.
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
| "Undervalued beat overvalued" | 29.9% vs 17.3% raw return, p=0.11 | -3.0% vs 1.1% excess return, p=0.642 |
| Quality explains valuation (R²) | 14.8% | 14.1% |
| AI commentary | Deterministic template (no API key) | Written by Gemini, every number verified |
| Figure 12 sample-size label | Error bar struck through "n=224" (read as "n=-24") | n shown in the axis labels |

The first version's RQ3 text also said every p-value exceeded 0.10, contradicting a Mann-Whitney
p=0.02 in its own table; that result was an artefact of the Altman Z bug and is gone after the fix.

## Conclusion

Fundamental quality and valuation are positively related in this tech sample, but modestly: quality
alone explains about 14% of the spread in EV/Sales, and sector and timing explain
more. When the "cheap for its quality" signal is tested properly -- each company against its own
sub-industry, with a fair-value line that never sees the future, and returns measured against the tech
sector -- it does **not** predict next-year returns. The classic risk scores do not predict excess
returns either, although Altman Z does flag weaker next-year revenue growth and more losses, and
management tone describes the past rather than the future. The honest conclusion is that a quality score
built from public filings is a useful way to *describe* and *screen* companies, but in large-cap tech it
is not, on its own, a source of returns -- which is why every Radar verdict is labelled "Not investment
advice".
