# Mispricing Radar: Does the Stock Market Pay for Fundamental Quality?

*57 US technology companies, FY2018-FY2024 (399 company-years), built on SEC 10-K filings.*

## Research questions

- **RQ1.** Do higher-quality companies trade at higher valuation multiples, and how much of valuation does quality explain?
- **RQ2.** Which companies look undervalued or overvalued for their quality, does a DCF agree, and did the verdicts predict returns?
- **RQ3.** Did companies with better Piotroski F, Altman Z or Beneish M scores have better next-year growth and returns?
- **RQ4.** Does MD&A sentiment match actual performance, in the same year and the next?
- **RQ5.** Do semiconductors, software and hardware differ in quality, valuation and the link between them?

## Data and sample

| table                     |   rows |   cols | tickers    | fy_range   |
|:--------------------------|-------:|-------:|:-----------|:-----------|
| companies                 |     57 |      4 | 57 tickers | -          |
| statements                |  12003 |      7 | 57 tickers | 2018-2024  |
| ratios                    |  11644 |      4 | 57 tickers | 2018-2024  |
| quarterly_statements      |      0 |      9 | 0 tickers  | -          |
| quarterly_ratios          |      0 |      6 | 0 tickers  | -          |
| scores                    |    399 |      9 | 57 tickers | 2018-2024  |
| peer_ranks                |   9733 |      6 | 57 tickers | 2018-2024  |
| filings                   |    397 |      8 | 57 tickers | 2018-2024  |
| chunks                    | 250554 |      6 | 57 tickers | 2018-2024  |
| textstats                 |   1189 |      8 | 57 tickers | 2018-2024  |
| prices                    | 103639 |      4 | 58 tickers | -          |
| mispricing                |    396 |     23 | 57 tickers | -          |
| mispricing_wf_fit         |     21 |     10 | -          | -          |
| mispricing_fit            |     28 |      8 | -          | -          |
| mispricing_notes          |    332 |      6 | 57 tickers | -          |
| mispricing_score_outcomes |      8 |     14 | -          | -          |

- **Companies:** 57 -- the 19-ticker FinChat universe plus 38 S&P 500 Information Technology
  constituents with a full FY2018-2024 10-K history. ANSYS and Juniper Networks were dropped: both were
  acquired and no longer appear in SEC's active ticker map (a survivorship bias -- see Limitations).
- **Sources:** SEC EDGAR XBRL company facts (statements, ratios, Piotroski and Beneish scores), SEC 10-K
  MD&A text (sentiment), Yahoo Finance via yfinance (daily adjusted closes for each company and for the
  XLK Technology Select Sector ETF, cached locally).

**Sample attrition.** Every stage below loses company-years for a stated reason:

| stage                                                              |   n |
|:-------------------------------------------------------------------|----:|
| Company-years collected (57 x 7)                                   | 399 |
| With a Quality Score                                               | 396 |
| With EV/Sales (needs price + diluted shares)                       | 386 |
| RQ1 simple regression (Quality + EV/Sales)                         | 383 |
| RQ1 controlled regression (+ revenue growth, needs prior year)     | 330 |
| With a walk-forward verdict (FY2019+; FY2018 has no training data) | 332 |
| With a next-12m excess return                                      | 397 |
| With Piotroski F                                                   | 342 |
| With Altman Z (point-in-time)                                      | 375 |
| With Beneish M                                                     | 157 |

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

| model                                                                  |   slope_on_QualityScore |     p_value |   r_squared |   n |
|:-----------------------------------------------------------------------|------------------------:|------------:|------------:|----:|
| Simple (QualityScore only)                                             |                 0.02601 | 3.18813e-14 |       0.141 | 383 |
| With controls (revenue growth, year FE, sub-industry FE; clustered SE) |                 0.02223 | 0.00323149  |       0.323 | 330 |

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

| ticker   | sub_industry         |   QualityScore |   ev_sales |   expected_ev_sales |     gap_z | verdict       |   dcf_upside | dcf_agreement   |
|:---------|:---------------------|---------------:|-----------:|--------------------:|----------:|:--------------|-------------:|:----------------|
| DXC      | Software & Services  |           31.4 |    1.05292 |             3.53949 | -2.74746  | Undervalued   |     2.65593  | agrees          |
| CTSH     | Software & Services  |           37.4 |    1.86486 |             4.0474  | -2.01217  | Undervalued   |    -0.414909 | disagrees       |
| CDW      | Software & Services  |           28.6 |    1.82942 |             3.32479 | -1.72391  | Undervalued   |    -0.706719 | disagrees       |
| DELL     | Hardware & Equipment |           38.5 |    1.15121 |             2.02806 | -1.67332  | Undervalued   |    -0.406575 | disagrees       |
| HPQ      | Hardware & Equipment |           33.5 |    1.05292 |             1.7071  | -1.56316  | Undervalued   |    -0.127238 | disagrees       |
| JBL      | Hardware & Equipment |           31.1 |    1.05292 |             1.57161 | -1.42885  | Undervalued   |     1.14392  | agrees          |
| ACN      | Software & Services  |           47.7 |    3.47562 |             5.09504 | -1.37486  | Undervalued   |    -0.477172 | disagrees       |
| HPE      | Hardware & Equipment |           31.5 |    1.17788 |             1.59342 | -1.2444   | Undervalued   |     0.580933 | agrees          |
| APH      | Hardware & Equipment |           45.6 |    1.94449 |             2.59015 | -1.2193   | Undervalued   |     0.449549 | agrees          |
| AKAM     | Software & Services  |           44.8 |    3.78195 |             4.7753  | -1.13241  | Undervalued   |     0.24265  | agrees          |
| EPAM     | Software & Services  |           40.7 |    3.46764 |             4.35719 | -1.12451  | Undervalued   |    -0.10092  | disagrees       |
| SWKS     | Semiconductors       |           58.9 |    3.09898 |             3.67275 | -1.02952  | Undervalued   |     3.53462  | agrees          |
| GDDY     | Software & Services  |           41.3 |    4.45629 |             4.41601 | -0.73888  | Fairly valued |     0.856072 | n/a             |
| CRM      | Software & Services  |           66.2 |    8.43853 |             7.70383 | -0.605686 | Fairly valued |     0.172901 | n/a             |
| GLW      | Hardware & Equipment |           34.8 |    2.02183 |             1.7853  | -0.55156  | Fairly valued |    -0.152194 | n/a             |

| ticker   | sub_industry         |   QualityScore |   ev_sales |   expected_ev_sales |    gap_z | verdict       |   dcf_upside | dcf_agreement   |
|:---------|:---------------------|---------------:|-----------:|--------------------:|---------:|:--------------|-------------:|:----------------|
| AVGO     | Semiconductors       |           54.8 |   17.9321  |             3.62958 | 1.83644  | Overvalued    |   -0.618757  | agrees          |
| MPWR     | Semiconductors       |           44.4 |   15.5408  |             3.52234 | 1.65716  | Overvalued    |   -0.310389  | agrees          |
| NVDA     | Semiconductors       |          100   |   17.9321  |             4.13487 | 1.62475  | Overvalued    |   -0.405668  | agrees          |
| VRSN     | Software & Services  |           22.1 |   12.0881  |             2.87525 | 1.57878  | Overvalued    |   -0.211605  | agrees          |
| ADI      | Semiconductors       |           39   |   12.0832  |             3.46792 | 1.27373  | Overvalued    |   -0.71456   | agrees          |
| WDC      | Hardware & Equipment |           18.6 |    3.44415 |             1.02163 | 1.22016  | Overvalued    |   -2.25578   | agrees          |
| CDNS     | Software & Services  |           52.1 |   17.1436  |             5.62152 | 1.05733  | Overvalued    |   -0.774478  | agrees          |
| AMD      | Semiconductors       |           38.5 |   10.5138  |             3.46292 | 1.0501   | Overvalued    |   -0.886966  | agrees          |
| KLAC     | Semiconductors       |           48.4 |   10.238   |             3.56321 | 0.960567 | Fairly valued |   -0.593329  | n/a             |
| FICO     | Software & Services  |           57.7 |   17.9321  |             6.37098 | 0.922636 | Fairly valued |   -0.775912  | n/a             |
| KEYS     | Hardware & Equipment |           39.9 |    5.84384 |             2.12828 | 0.886876 | Fairly valued |   -0.618132  | n/a             |
| TXN      | Semiconductors       |           48.2 |    9.73856 |             3.56115 | 0.880275 | Fairly valued |   -0.923542  | n/a             |
| AAPL     | Hardware & Equipment |           53.2 |    8.86394 |             3.36553 | 0.819204 | Fairly valued |   -0.582638  | n/a             |
| SNPS     | Software & Services  |           45.8 |   11.8973  |             4.88322 | 0.692689 | Fairly valued |   -0.758362  | n/a             |
| MSI      | Hardware & Equipment |           43.2 |    5.47445 |             2.38458 | 0.59615  | Fairly valued |   -0.0275075 | n/a             |

In FY2024, 20 companies were flagged undervalued or overvalued; the DCF agreed with
14 and disagreed with 6 (this count is for FY2024 only). 8 of 8 overvalued names also show DCF downside. 6 of 12 undervalued names (ACN, CDW, CTSH, DELL, EPAM, HPQ) show DCF downside instead: a low EV/Sales can reflect low margins rather than mispricing, which EV/Sales cannot see.

**Did the verdicts predict returns?** Out of sample, FY2019-FY2024 pooled:

| outcome                |   n_under |   mean_under |   n_over |   mean_over |   difference |   t_stat |   t_pvalue |   u_pvalue |
|:-----------------------|----------:|-------------:|---------:|------------:|-------------:|---------:|-----------:|-----------:|
| excess_return_next_12m |        64 |      -0.0302 |       44 |      0.0108 |      -0.0409 |   -0.466 |     0.6422 |     0.8146 |
| return_next_12m        |        64 |       0.2208 |       44 |      0.2532 |      -0.0325 |   -0.335 |     0.7386 |     0.9327 |

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

| score       | group            |   n |   rev_growth_next_mean |   rev_growth_next_median |   ni_growth_next_mean |   ni_growth_next_median |   return_next_12m_mean |   return_next_12m_median |   excess_return_next_12m_mean |   excess_return_next_12m_median |   loss_next_mean |   loss_next_median |
|:------------|:-----------------|----:|-----------------------:|-------------------------:|----------------------:|------------------------:|-----------------------:|-------------------------:|------------------------------:|--------------------------------:|-----------------:|-------------------:|
| piotroski_f | low (0-3)        |  26 |                 8.0239 |                  11.8638 |              -99.445  |                -15.2413 |                 0.206  |                   0.1614 |                       -0.0609 |                         -0.0467 |           0.2222 |                  0 |
| piotroski_f | mid (4-6)        | 195 |                12.0949 |                   7.2228 |               63.7345 |                  5.7226 |                 0.2434 |                   0.1923 |                       -0.015  |                         -0.0481 |           0.0323 |                  0 |
| piotroski_f | high (7-9)       | 121 |                 7.2421 |                   8.4675 |               12.3842 |                  7.1596 |                 0.2498 |                   0.1747 |                        0.0128 |                         -0.0299 |           0.0495 |                  0 |
| altman_z    | distress (<1.81) |  57 |                 5.735  |                   3.4048 |             -198.546  |                -56.1028 |                 0.2408 |                   0.199  |                        0.0058 |                         -0.023  |           0.325  |                  0 |
| altman_z    | grey (1.81-3.0)  |  74 |                 4.7727 |                   4.3756 |               87.6925 |                  1.1869 |                 0.2103 |                   0.151  |                       -0.0181 |                         -0.0532 |           0.0462 |                  0 |
| altman_z    | safe (>3.0)      | 244 |                11.6451 |                   9.5183 |              101.728  |                 11.5287 |                 0.2447 |                   0.1958 |                        0.0059 |                         -0.0299 |           0.0149 |                  0 |
| beneish_m   | flagged (>-1.78) |  10 |                20.023  |                   1.3351 |              -41.6835 |                 -2.2009 |                 0.3078 |                   0.1523 |                        0.1443 |                          0.1497 |           0      |                  0 |
| beneish_m   | not flagged      | 147 |                 8.3497 |                   3.9345 |               42.385  |                  3.9    |                 0.2728 |                   0.19   |                        0.0061 |                         -0.0315 |           0.0407 |                  0 |

| score       | outcome                |   n_weak |   n_strong |   mean_weak |   mean_strong |   t_stat |   t_pvalue |   u_pvalue |
|:------------|:-----------------------|---------:|-----------:|------------:|--------------:|---------:|-----------:|-----------:|
| piotroski_f | excess_return_next_12m |       26 |        120 |     -0.0609 |        0.0128 |    0.999 |     0.3242 |     0.6216 |
| piotroski_f | rev_growth_next        |       19 |        101 |      8.0239 |        7.2421 |   -0.236 |     0.8152 |     0.8236 |
| altman_z    | excess_return_next_12m |       55 |        244 |      0.0058 |        0.0059 |    0.002 |     0.9985 |     0.9429 |
| altman_z    | rev_growth_next        |       49 |        204 |      5.735  |       11.6451 |    2.817 |     0.0057 |     0.0203 |
| beneish_m   | excess_return_next_12m |       10 |        146 |      0.1443 |        0.0061 |   -1.181 |     0.2632 |     0.1681 |
| beneish_m   | rev_growth_next        |        8 |        123 |     20.023  |        8.3497 |   -0.978 |     0.3589 |     0.5676 |

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

| x                     | y                               |   n |   pearson_r |   p_value |
|:----------------------|:--------------------------------|----:|------------:|----------:|
| mda_polarity          | same-year revenue growth        | 335 |       0.322 |    0      |
| mda_polarity          | same-year ROE                   | 378 |       0.082 |    0.1101 |
| mda_polarity          | next-year revenue growth        | 333 |       0.083 |    0.1292 |
| mda_polarity          | next-12m excess return (vs XLK) | 395 |      -0.01  |    0.8428 |
| polarity_change (YoY) | revenue_growth_change (YoY)     | 277 |       0.249 |    0      |

| ticker   |   fy |   mda_polarity |   revenue_growth_pct |   rev_growth_next |
|:---------|-----:|---------------:|---------------------:|------------------:|
| TXN      | 2023 |       0.613636 |            -12.5275  |        -10.7198   |
| INTC     | 2022 |       0.375    |            -20.2091  |        -13.9975   |
| TXN      | 2024 |       0.375    |            -10.7198  |        nan        |
| CDW      | 2023 |       0.349398 |             -9.99086 |         -1.76506  |
| TXN      | 2019 |       0.319149 |             -8.87608 |          0.542307 |
| AMD      | 2023 |       0.258824 |             -3.90238 |         13.6905   |
| TYL      | 2021 |      -0.107914 |             42.5933  |         16.1979   |
| GDDY     | 2021 |      -0.123077 |             15.0451  |          7.22279  |
| NXPI     | 2021 |      -0.138075 |             28.4603  |         19.3618   |
| KLAC     | 2020 |      -0.188811 |             27.0857  |         19.1565   |

MD&A tone tracks the year that has just happened (r=0.32 with same-year revenue
growth, p<0.001) but not the next one (r=0.08 with next-year revenue
growth, p=0.129; r=-0.01 with next-12-month excess return,
p=0.843). Tone confirms the past; it does not predict the future.

![Figure9_Tone_vs_NextYearGrowth](outputs/figures/Figure9_Tone_vs_NextYearGrowth.png)

### RQ5 -- Sub-industry differences

| sub_industry         |   n_company_years |   avg_quality_score |   avg_ev_sales |   avg_excess_return_next_12m |   quality_valuation_corr |
|:---------------------|------------------:|--------------------:|---------------:|-----------------------------:|-------------------------:|
| Hardware & Equipment |               126 |                39.1 |           2.9  |                       -0.025 |                    0.504 |
| Semiconductors       |               119 |                50.4 |           5.2  |                        0.054 |                    0.066 |
| Software & Services  |               154 |                47.4 |           7.13 |                       -0.016 |                    0.344 |

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

Example -- *"Is Nvidia overvalued for its quality?"*:

> Based on the Mispricing Radar analysis for fiscal year 2024, Nvidia (**NVDA**) has a Fundamental Quality Score of **100.0/100** (broken down as profitability 91.5, growth 100.0, safety 85.7, and earnings quality 57.3). 
> 
> Key valuation details from the tool output:
> - **EV/Sales Multiple:** 17.9x actual versus an expected 4.1x for that quality level (**actual_vs_expected_ev_sales_ratio**: 4.34x its expected multiple).
> - **Valuation Gap:** The log-point valuation gap is 1.46 (with a gap z-score of 1.62 and a gap percentile among all companies of 96.4th).
> - **Verdict:** Overvalued (judged against a walk-forward, sub-industry-relative fair-value line fitted on earlier years FY2018-FY2023, with an R² of 0.00).
> - **DCF Model:** The DCF model implies a fair value of **$40.10** (an implied upside/downside of -40.6%), which agrees with the quality-versus-valuation signal.
> 
> *A valuation verdict is a statistical comparison with sub-industry peers, not a recommendation; in back-tests the verdicts did not predict next-year returns. Not investment advice.*

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


### Company notes


**DXC FY2024** (Undervalued): For fiscal year 2024, DXC carries an undervalued verdict as it trades at 1.1x EV/Sales versus 3.5x expected for its quality compared to Software & Services peers on a fair-value line fitted only on earlier years. Its strongest pillar is earnings quality at 55.2, while its weakest pillar is profitability at 38.0. The DCF upside in percent is 265.6%, and the DCF supports the verdict. Not investment advice.


**CTSH FY2024** (Undervalued): For the fiscal year 2024, the data suggests CTSH carries a verdict of Undervalued as it trades at 1.9x EV/Sales versus 4.0x expected for its quality, compared with Software & Services peers on a fair-value line fitted only on earlier years. Its strongest pillar is safety at 61.3, while its weakest pillar is earnings quality at 36.0. The DCF upside is -41.5%, and the DCF does not support the verdict.

Not investment advice.


**CDW FY2024** (Undervalued): The data suggests CDW with a fiscal year 2024 verdict of Undervalued trades at 1.8x sales versus 3.3x expected. Its strongest pillar is growth at 47.1, while its weakest pillar is earnings quality at 37.2. The DCF upside is -70.7% and the DCF does not support the verdict. Not investment advice.


**DELL FY2024** (Undervalued): For fiscal year 2024, the data suggests DELL is undervalued in the Hardware & Equipment sub-industry as it trades at 1.2x sales versus 2.0x expected for its quality. Its strongest pillar score is safety at 77.3, while its weakest pillar score is profitability at 28.1. The DCF upside in percent is -40.7, and the DCF does not support the verdict. Not investment advice.


**HPQ FY2024** (Undervalued): The data suggests that HPQ for fiscal year 2024 is undervalued, as it trades at 1.1x sales versus 1.7x expected for its quality within the Hardware & Equipment sub-industry. Its strongest pillar is safety at 66.0, while its weakest pillar is profitability at 30.0. Furthermore, the DCF upside is -12.7%, and the DCF does not support the verdict. Not investment advice.


**JBL FY2024** (Undervalued): The data suggests JBL, in the Hardware & Equipment sub-industry for fiscal year 2024, has a verdict of Undervalued because it trades at an actual EV/Sales multiple of 1.1x versus an expected EV/Sales multiple of 1.6x for its quality. Its strongest pillar is profitability at 56.8, while its weakest pillar is earnings quality at 36.6. The DCF upside in percent is 114.4, and the DCF supports the verdict.

Not investment advice.


**ACN FY2024** (Undervalued): For fiscal year 2024, ACN receives an Undervalued verdict because it trades at 3.5x sales versus 5.1x expected for its quality compared with Software & Services peers. Within its pillar scores out of 100, safety is its strongest at 74.9 while earnings quality is its weakest at 46.8. Finally, the DCF upside in percent stands at -47.7%, meaning the DCF does not support the verdict. Not investment advice.


**HPE FY2024** (Undervalued): For the fiscal year 2024, HPE in the Hardware & Equipment sub-industry is deemed Undervalued as it trades at 1.2x sales versus 1.6x expected for its quality. Its strongest pillar score is growth at 49.3 out of 100, while its weakest is earnings quality at 40.2 out of 100. The data suggests a DCF upside in percent of 58.1, and the DCF supports the verdict. Not investment advice.


**APH FY2024** (Undervalued): For the fiscal year 2024, APH is deemed undervalued because it trades at an actual EV/Sales multiple of 1.9x versus an expected EV/Sales multiple of 2.6x for its quality within the Hardware & Equipment sub-industry. The data shows that its strongest pillar is profitability at 57.4, while its weakest pillar is earnings quality at 44.3. Furthermore, the DCF upside in percent is 45.0, and the DCF supports the verdict.

Not investment advice.


**AKAM FY2024** (Undervalued): For the 2024 fiscal year, AKAM trades at an actual EV/Sales multiple of 3.8x versus an expected EV/Sales multiple of 4.8x for its quality, leading to a verdict of Undervalued. Its strongest pillar is earnings quality at 70.6, while its weakest pillar is profitability at 46.4. The data suggests a DCF upside in percent of 24.3, and the DCF supports the verdict.

Not investment advice.


**AVGO FY2024** (Overvalued): The data suggests the company is overvalued, trading at an actual EV/Sales multiple of 17.9x versus an expected EV/Sales multiple of 3.6x for its quality. Its strongest pillar is earnings quality at 74.8, while its weakest pillar is safety at 47.4. Furthermore, the DCF upside in percent is -61.9%, and the DCF supports the verdict. Not investment advice.


**MPWR FY2024** (Overvalued): For fiscal year 2024, MPWR in the Semiconductors sub-industry receives a verdict of Overvalued as it trades at 15.5x actual EV/Sales versus 3.5x expected EV/Sales for its quality. Its strongest pillar score out of 100 is profitability at 88.1, while its weakest pillar score out of 100 is earnings quality at 5.2. The DCF upside is -31.0%, and the DCF supports the verdict. Not investment advice.


**NVDA FY2024** (Overvalued): For fiscal year 2024, the verdict on NVDA in Semiconductors is Overvalued because it trades at an actual EV/Sales multiple of 17.9x versus an expected EV/Sales multiple of 4.1x for its quality. Its strongest pillar is growth at 100.0, while its weakest pillar is earnings quality at 57.3. The DCF upside is -40.6%, and the DCF supports the verdict, as the data suggests. Not investment advice.


**VRSN FY2024** (Overvalued): For fiscal year 2024, the data suggests VRSN is overvalued as it trades at 12.1x sales versus 2.9x expected for its quality compared to Software & Services peers. Within its pillar scores out of 100, safety stands out at 39.1, while profitability, growth, and earnings quality have no data available. Furthermore, the DCF upside in percent is -21.2, and the DCF supports the verdict. Not investment advice.


**ADI FY2024** (Overvalued): For the fiscal year 2024, ADI is assessed as Overvalued because it trades at an actual EV/Sales multiple of 12.1x versus an expected EV/Sales multiple of 3.5x for its quality. Within its pillar scores out of 100, its strongest pillar is earnings quality at 63.6 and its weakest pillar is growth at 39.2. Furthermore, the DCF upside in percent is -71.5%, and the DCF supports the verdict.

Not investment advice.


**WDC FY2024** (Overvalued): WDC receives a verdict of Overvalued, trading at an Actual EV/Sales multiple of 3.4 compared to an Expected EV/Sales multiple for its quality of 1.0. Among its pillar scores out of 100, its growth score is the strongest at 46.9 while its profitability score is the weakest at 25.0. The DCF upside in percent is -225.6, and the DCF does support the verdict.

Not investment advice.


**CDNS FY2024** (Overvalued): CDNS has a verdict of Overvalued, trading at an actual EV/Sales multiple of 17.1x versus an expected EV/Sales multiple of 5.6x for its quality. Within its pillar scores out of 100, the strongest pillar is profitability at 65.9 and the weakest pillar is growth at 52.0. The DCF upside in percent is -77.4, and the DCF supports the verdict with a "yes".

Not investment advice.


**AMD FY2024** (Overvalued): The data suggests that AMD, classified under Semiconductors, is overvalued because it trades at an actual EV/Sales multiple of 10.5x versus an expected EV/Sales multiple of 3.5x for its quality. Its strongest pillar score is safety at 58.5, while its weakest pillar score is profitability at 39.2. Furthermore, the DCF upside is -88.7%, and the DCF does support the verdict. Not investment advice.


**KLAC FY2024** (Fairly valued): For fiscal year 2024, KLAC carries a verdict of Fairly valued because it trades at 10.2x sales versus 3.6x expected for its quality. Its strongest pillar is profitability at 70.6, while its weakest pillar is growth at 45.2. The DCF upside in percent is -59.3%, and the DCF does the DCF support the verdict with no clear signal. Not investment advice.


**FICO FY2024** (Fairly valued): The data suggests FICO trades at 17.9x sales versus 6.4x expected, resulting in a verdict of Fairly valued compared with Software & Services peers on a fair-value line fitted only on earlier years. Its strongest pillar is earnings quality at 70.8, while its weakest pillar is growth at 52.4. Furthermore, the DCF upside is -77.6% and does the DCF support the verdict indicates no clear signal. Not investment advice.


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
