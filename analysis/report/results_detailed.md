# Mispricing Radar: Does the Stock Market Pay for Fundamental Quality?

*57 US technology companies, FY2018-FY2024 (399 company-years), built on SEC 10-K filings.*

## Summary

We studied 57 large US tech companies over seven years and asked four questions. Do better
businesses get higher stock prices? Can we spot companies that look too cheap or too expensive for
how good they are, and does that help pick winners? Does the tone of the annual report match what
really happened? Do chip, software and hardware companies behave differently?

All numbers come from Python code (pandas, SciPy and statsmodels). The AI part of the app only puts
these numbers into words, and a checker confirms every number it writes.

| RQ | Question | Method used | Result | Answer |
| --- | --- | --- | --- | --- |
| RQ1 | Do better-quality companies have higher valuations? | Correlation; simple linear regression; multiple regression with controls | r = 0.37. Quality explains 14.1% of valuation (p < 0.001). Still significant after controls (p = 0.003). | Yes, but the effect is small |
| RQ2 | Which companies look cheap or expensive for their quality, and did that predict returns? | Regression line per sub-industry, trained only on past years; z-scores; DCF check; t-test | "Cheap" stocks -3.0% vs "expensive" stocks +1.1% against the tech index (p = 0.642) | No |
| RQ3 | Does management's tone match real results? | Tone score from the Loughran-McDonald finance dictionary; correlation | Same year r = 0.18 (p = 0.001). Next year r = 0.07 (p = 0.205). | Only for the past year, and weakly |
| RQ4 | Do chips, software and hardware differ? | Group averages; correlation inside each group | Link between quality and valuation ranges from r = 0.07 to 0.50 | Yes |

![Screenshot_Radar_Chart](outputs/figures/Screenshot_Radar_Chart.png)

*The Mispricing Radar page in the FinChat app. Each dot is a company, placed by its quality and its
valuation and compared with the line for its own sub-industry.*

## Research questions

- **RQ1.** Do higher-quality companies trade at higher valuation multiples, and how much of valuation does quality explain?
- **RQ2.** Which companies look undervalued or overvalued for their quality, does a DCF agree, and did these labels predict next-year returns?
- **RQ3.** Does the tone of management's discussion (MD&A) match actual performance, in the same year and the next?
- **RQ4.** Do semiconductors, software and hardware differ in quality, valuation and the link between them?

## Data

We used 57 companies: the 19 companies already in the FinChat app plus 38 more from the S&P 500
technology sector that filed a 10-K for every year from 2018 to 2024. ANSYS and Juniper Networks
were left out because they were bought by other companies and no longer appear in SEC's list.

Each row of data is one company in one year, for example "NVDA, FY2024". With 57 companies and 7
years, that gives 399 rows.

The data comes from four places:

- SEC EDGAR, for the income statement, balance sheet and cash flow numbers. All ratios are worked out from these.
- The 10-K annual report text, for the Management's Discussion & Analysis (MD&A) section used in RQ3.
- The Loughran-McDonald Master Dictionary (University of Notre Dame), the finance word list used to score tone in RQ3.
- Yahoo Finance, for daily share prices of each company and of XLK, a fund that tracks the whole US tech sector. XLK is our benchmark.

Each company belongs to one sub-industry: Hardware & Equipment (18 companies), Semiconductors (17)
or Software & Services (22).

Some tests cannot use all 399 rows, because a number they need is missing:

| Stage | Company-years |
| :--- | ---: |
| All rows collected (57 x 7) | 399 |
| Has a Quality Score | 396 |
| Has EV/Sales (needs a share price and share count) | 386 |
| Used in RQ1 simple regression | 383 |
| Used in RQ1 regression with controls (revenue growth needs the year before) | 330 |
| Has an RQ2 label (starts FY2019, because FY2018 has no earlier year to learn from) | 332 |
| Has a next-12-month return against XLK | 397 |

## Main measures used in this study

Financial terms are explained in Appendix A, and statistics terms in Appendix B.

### 1. The Quality Score (0 to 100)

The Quality Score is one number that says how strong a business is, using only its accounts (no
share prices). Keeping prices out lets us compare quality with price fairly.

We build it in five steps.

**Step 1. Choose 11 measures, grouped into four areas (pillars).**

| Pillar | Measures | Better when |
| --- | --- | --- |
| Profitability | ROE, ROIC, operating margin, net margin | higher |
| Growth | revenue growth, net income growth | higher |
| Safety | current ratio, interest coverage; debt/equity | higher; debt/equity lower |
| Earnings quality | free cash flow margin; accruals = (net income - operating cash flow) / total assets | FCF higher; accruals lower |

**Step 2. Turn each measure into a z-score inside its year.** A z-score shows how far a company is
above or below the average company that year, in units of standard deviation:

> z = (company's value - average that year) / standard deviation that year

This puts measures with different units (percent, ratios) on the same scale. For measures where
lower is better (debt/equity and accruals), we flip the sign.

**Step 3. Average the z-scores inside each pillar.** A pillar needs at least 2 of its measures.

**Step 4. Average the four pillars** into one number.

**Step 5. Rescale to 0-100:** Score = (x - lowest) / (highest - lowest) x 100. So 100 is the best
company-year in the data and 0 is the worst.

We did not put the well-known Altman Z, Piotroski F or Beneish M scores into the Quality Score. They
are built from the same ratios, so they would count things twice. Altman Z also uses market value,
which would put the share price inside a score that we then compare with the share price.

![Figure3_Top_Quality_Scores](outputs/figures/Figure3_Top_Quality_Scores.png)

### 2. How we measure valuation: EV/Sales

- **Enterprise value (EV)** is what it would cost to buy the whole company: market value + debt - cash - short-term investments.
- **Market value** is share price x number of shares. We use the price on the first trading day on or after the 10-K was filed, so we only use prices from when the report was public.
- **EV/Sales** is EV divided by revenue. We use it instead of P/E because P/E does not work when a company makes a loss.
- **We take the log of EV/Sales** in the regressions. Most companies trade at 1x to 8x sales, but a few are at 18x or more. Taking the log pulls these big values in and makes the regression slope easy to read as a percentage change.
- **We cap extreme values** (winsorizing). In each year, any value below the 5th percentile or above the 95th is set to that limit, so a few odd companies cannot drive the results. This is done for EV/Sales, log EV/Sales, P/E, ROE, ROIC and debt/equity.

![Figure4_Top_EV_Sales](outputs/figures/Figure4_Top_EV_Sales.png)

### 3. Returns compared with the tech sector

- **Next-12-month return** is the change in share price (with dividends) from the filing date to one year later.
- **Excess return** is the stock's 12-month return minus XLK's return over the same days. This removes moves that hit all of tech at once, such as the 2022 sell-off, so we only see whether a company did better or worse than its sector.

## Results

### RQ1: Do higher-quality companies trade at higher multiples?

**The question.** If investors reward good businesses, companies with a higher Quality Score should
have a higher EV/Sales. We also want to know how much of the difference in valuation quality can explain.

**What we did.** We used three methods, each building on the last.

**Method 1: correlation.** We measured Pearson r and Spearman rho between Quality Score and
log(EV/Sales) using all 383 company-years, and then for each year on its own.

**Method 2: simple linear regression.** We fitted a straight line with Quality Score as the only input:

> log(EV/Sales) = a + b x QualityScore + error

We used `scipy.stats.linregress` on 383 company-years. The line it found is:

> **log(EV/Sales) = 0.1184 + 0.02601 x QualityScore**    (R² = 0.141, p = 3.2 x 10⁻¹⁴, N = 383)

*Reading the slope.* Because we used the log of EV/Sales, the slope works as a percentage:
e^(0.02601 x 10) = 1.30. So every 10 extra points of Quality Score goes with an EV/Sales about 30% higher.

*Example.* A company with a Quality Score of 50 gets log(EV/Sales) = 0.1184 + 0.02601 x 50 = 1.419,
so its expected EV/Sales is e^1.419 = 4.1x. A company with a score of 60 gets 0.1184 + 0.02601 x 60 =
1.679, which is 5.4x.

**Method 3: multiple regression with controls.** Quality could look important only because good
companies also tend to grow fast, or because all multiples rose over time, or because software
companies trade higher than hardware companies. To check this, we added these as extra inputs and
used `statsmodels` OLS:

> log(EV/Sales) = a + b₁·QualityScore + b₂·RevenueGrowth + (one yes/no variable per year) + (one yes/no variable per sub-industry) + error

Standard errors are clustered by company. The sample drops to 330 rows because revenue growth needs
the year before, so FY2018 falls out. FY2019 and Hardware & Equipment are the baselines that the
other years and sub-industries are compared with.

| Variable | Coefficient | Std. error | p-value | What it means |
| :--- | ---: | ---: | ---: | :--- |
| **Quality Score** | **0.0222** | 0.008 | **0.003** | 10 more points goes with about 25% higher EV/Sales (e^0.222 = 1.25), with everything else held the same |
| Revenue growth (%) | -0.0003 | 0.003 | 0.925 | no effect once quality is included |
| Year 2020 | 0.104 | 0.076 | 0.171 | no real difference from 2019 |
| Year 2021 | 0.323 | 0.102 | 0.002 | multiples about 38% higher than in 2019 |
| Year 2022 | 0.264 | 0.102 | 0.010 | about 30% higher |
| Year 2023 | 0.416 | 0.117 | <0.001 | about 52% higher |
| Year 2024 | 0.655 | 0.115 | <0.001 | about 93% higher for the same quality |
| Semiconductors | 0.420 | 0.208 | 0.044 | about 52% higher than hardware for the same quality |
| Software & Services | 0.713 | 0.237 | 0.003 | about 2x hardware for the same quality |
| Intercept | -0.354 | 0.333 | 0.288 | |

How well the model fits: R² = 0.323 (adjusted 0.304), F = 14.9 (p < 0.001), N = 330.

**The two regressions side by side:**

| Model | Slope on Quality Score | p-value | R² | N |
| :--- | ---: | :--- | ---: | ---: |
| Simple regression (Quality Score only) | 0.0260 | <0.001 | 0.141 | 383 |
| Multiple regression (plus revenue growth, year and sub-industry; clustered SE) | 0.0222 | 0.003 | 0.323 | 330 |

**Correlation in each year:**

| Fiscal year | N | Pearson r | p-value |
| ---: | ---: | ---: | ---: |
| 2018 | 51 | 0.18 | 0.217 |
| 2019 | 52 | 0.27 | 0.051 |
| 2020 | 55 | 0.42 | 0.001 |
| 2021 | 56 | 0.48 | <0.001 |
| 2022 | 56 | 0.40 | 0.003 |
| 2023 | 57 | 0.46 | <0.001 |
| 2024 | 56 | 0.54 | <0.001 |

**What we found.**

- Better-quality companies do have higher valuations: Pearson r = 0.37 (p < 0.001, N = 383). The rank-based
  Spearman rho is 0.39 (p < 0.001), so a few extreme companies are not driving the link.
- Quality on its own explains 14.1% of the differences in log(EV/Sales). The other 86% comes from other things.
- With the controls added, R² goes up to 32.3%. Most of that increase comes from the year and
  sub-industry variables. The quality slope only falls a little (from 0.026 to 0.022) and is still
  significant (p = 0.003), so growth, year and sub-industry do not explain the link away.
- The link got stronger over time, from r = 0.18 in FY2018 (not significant) to r = 0.54 in FY2024.

**What it means.** Investors do pay more for better businesses, but quality explains only a small
part of valuation. This test shows that the two move together. It cannot prove that quality causes
the higher price.

![Figure1_Quality_vs_Valuation](outputs/figures/Figure1_Quality_vs_Valuation.png)

### RQ2: Which companies look cheap or expensive for their quality, and did it matter?

**The question.** The regression line from RQ1 tells us what EV/Sales a company "should" have for its
quality. A company far below the line looks undervalued, and one far above looks overvalued. We ask
two things. Does a DCF valuation agree with these labels? And did the undervalued companies do
better than the overvalued ones over the next 12 months? Only the second tells us whether the labels
are useful to an investor.

**What we did.** We built a fair-value line for each sub-industry, trained only on past years, in eight steps.

1. **One line per sub-industry.** We fit log(EV/Sales) = a + b x QualityScore separately for each
   sub-industry, using the same regression as RQ1. Hardware usually trades at lower multiples than
   software, so a single shared line would call every hardware company "cheap".
2. **Only past data (walk-forward).** To judge a company in year t, the line is trained only on years
   before t. So FY2019 is judged with a line trained on FY2018, and FY2024 with a line trained on
   FY2018 to FY2023. The model never uses information from the same year or the future, which is how
   an investor would have had to work at the time. FY2018 has no earlier year, so labels start in FY2019.
3. **Expected multiple** = e^(a + b x QualityScore), read from the line.
4. **Gap** = actual log(EV/Sales) - expected log(EV/Sales). A positive gap means the company is more
   expensive than its quality suggests. This gap is the residual from the regression.
5. **Turn the gap into a z-score inside each year.** This removes moves that lifted all of tech in a
   year, such as the rise in multiples in 2024.
6. **Label each company.** z of -1 or lower is Undervalued; z of +1 or higher is Overvalued; anything
   in between is Fairly valued. About one in six companies falls into each of the two outer groups each year.
7. **DCF check.** A DCF (discounted cash flow) model estimates what a share is worth from its future
   cash. We start from free cash flow (operating cash flow minus capital spending), grow it for 5 years
   at the company's past 3-year growth rate (kept between -5% and +25%, slowing down over time), and
   discount it at 9% a year. After year 5 we assume 2.5% growth forever. We subtract net debt and divide
   by the number of shares to get a fair share price. The DCF agrees with an Undervalued label if it
   shows more than 10% upside, and with an Overvalued label if it shows more than 10% downside.
8. **Back-test.** We put together all labels from FY2019 to FY2024 and compared the next-12-month
   excess returns of the Undervalued group with the Overvalued group, using a Welch t-test. The test
   gives a p-value: the chance of seeing a gap this big between the two averages if the labels really
   made no difference.

**The FY2024 lines** (trained on FY2018 to FY2023):

| Sub-industry | Intercept a | Slope b | R² on training data | Rows used |
| :--- | ---: | ---: | ---: | ---: |
| Hardware & Equipment | -0.620 | 0.0345 | 0.24 | 104 |
| Semiconductors | 1.131 | 0.0029 | 0.002 | 98 |
| Software & Services | 0.562 | 0.0223 | 0.10 | 125 |

The semiconductor line is almost flat (R² = 0.002). Among chip companies, quality tells us almost
nothing about the multiple, so a chip company's label mostly compares its multiple with the chip average.

**Worked example: NVDA in FY2024.** Quality Score = 100, sub-industry Semiconductors.

- Expected log(EV/Sales) = 1.131 + 0.0029 x 100 = 1.421, so expected EV/Sales = e^1.421 = 4.1x
- Actual EV/Sales = 17.9x, and log(17.9) = 2.885
- Gap = 2.885 - 1.421 = 1.46, which means NVDA trades at about 4.3 times its expected multiple
- In FY2024 the average gap across all companies was 0.464 with a standard deviation of 0.616, so
  z = (1.46 - 0.464) / 0.616 = 1.62. Since z is above 1, the label is Overvalued.
- The DCF shows 40.6% downside, so the DCF agrees.

**FY2024: companies that look cheapest for their quality**

| Ticker | Sub-industry | Quality | EV/Sales | Expected EV/Sales | Gap z | Label | DCF upside | DCF |
| :--- | :--- | ---: | :--- | :--- | ---: | :--- | :--- | :--- |
| DXC | Software & Services | 31.4 | 1.1x | 3.5x | -2.75 | Undervalued | +265.6% | agrees |
| CTSH | Software & Services | 37.4 | 1.9x | 4.0x | -2.01 | Undervalued | -41.5% | disagrees |
| CDW | Software & Services | 28.6 | 1.8x | 3.3x | -1.72 | Undervalued | -70.7% | disagrees |
| DELL | Hardware & Equipment | 38.5 | 1.2x | 2.0x | -1.67 | Undervalued | -40.7% | disagrees |
| HPQ | Hardware & Equipment | 33.5 | 1.1x | 1.7x | -1.56 | Undervalued | -12.7% | disagrees |
| JBL | Hardware & Equipment | 31.1 | 1.1x | 1.6x | -1.43 | Undervalued | +114.4% | agrees |
| ACN | Software & Services | 47.7 | 3.5x | 5.1x | -1.37 | Undervalued | -47.7% | disagrees |
| HPE | Hardware & Equipment | 31.5 | 1.2x | 1.6x | -1.24 | Undervalued | +58.1% | agrees |
| APH | Hardware & Equipment | 45.6 | 1.9x | 2.6x | -1.22 | Undervalued | +45.0% | agrees |
| AKAM | Software & Services | 44.8 | 3.8x | 4.8x | -1.13 | Undervalued | +24.3% | agrees |
| EPAM | Software & Services | 40.7 | 3.5x | 4.4x | -1.12 | Undervalued | -10.1% | disagrees |
| SWKS | Semiconductors | 58.9 | 3.1x | 3.7x | -1.03 | Undervalued | +353.5% | agrees |

**FY2024: companies that look most expensive for their quality**

| Ticker | Sub-industry | Quality | EV/Sales | Expected EV/Sales | Gap z | Label | DCF upside | DCF |
| :--- | :--- | ---: | :--- | :--- | ---: | :--- | :--- | :--- |
| AVGO | Semiconductors | 54.8 | 17.9x | 3.6x | 1.84 | Overvalued | -61.9% | agrees |
| MPWR | Semiconductors | 44.4 | 15.5x | 3.5x | 1.66 | Overvalued | -31.0% | agrees |
| NVDA | Semiconductors | 100.0 | 17.9x | 4.1x | 1.62 | Overvalued | -40.6% | agrees |
| VRSN | Software & Services | 22.1 | 12.1x | 2.9x | 1.58 | Overvalued | -21.2% | agrees |
| ADI | Semiconductors | 39.0 | 12.1x | 3.5x | 1.27 | Overvalued | -71.5% | agrees |
| WDC | Hardware & Equipment | 18.6 | 3.4x | 1.0x | 1.22 | Overvalued | -225.6% | agrees |
| CDNS | Software & Services | 52.1 | 17.1x | 5.6x | 1.06 | Overvalued | -77.4% | agrees |
| AMD | Semiconductors | 38.5 | 10.5x | 3.5x | 1.05 | Overvalued | -88.7% | agrees |

**Does the DCF agree? (FY2024)** 20 companies got a label. The DCF agreed with 14 and disagreed with
6. All 8 overvalued companies also show downside in the DCF. But 6 of the 12 undervalued companies
(ACN, CDW, CTSH, DELL, EPAM and HPQ) show downside too. A low EV/Sales can simply mean low profit
margins, as in IT services and PC assembly, and EV/Sales cannot see margins.

**Back-test: did the labels predict returns?** All labels from FY2019 to FY2024, tested only on years the model had not seen:

| Outcome | n undervalued | Average, undervalued | n overvalued | Average, overvalued | Difference | t-test p |
| :--- | ---: | :--- | ---: | :--- | :--- | ---: |
| Next-12m return minus XLK | 64 | -3.0% | 44 | +1.1% | -4.1% | 0.642 |
| Next-12m return | 64 | +22.1% | 44 | +25.3% | -3.2% | 0.739 |

**What we found.** Over the next year, undervalued companies did 3.0% worse than XLK, while
overvalued companies did 1.1% better. The difference points the wrong way and is not significant
(t-test p = 0.642, far above 0.05). Plain returns tell the same story (p = 0.739).

**What it means.** In this data, "cheap for its quality" does not help predict next year's return.
When a company's price is far from what its quality suggests, the reason is most likely something
the score does not measure, such as expected growth, profit margins or the type of business.

![Figure12_Verdict_Outcomes](outputs/figures/Figure12_Verdict_Outcomes.png)

![Figure5_Biggest_Bargains](outputs/figures/Figure5_Biggest_Bargains.png)

![Figure6_Biggest_Premiums](outputs/figures/Figure6_Biggest_Premiums.png)

### RQ3: Does management's tone match real results?

**The question.** Every 10-K has a section called Management's Discussion & Analysis (MD&A), where
managers describe how the year went. Does a positive tone go with good results in the year being
described? And does it tell us anything about the next year, which would be more useful?

**The dictionary we used.** We measured tone with the Loughran-McDonald Master Dictionary
(1993-2025 version), published by the University of Notre Dame. Tim Loughran and Bill McDonald built
it by reading words in real 10-K filings (Journal of Finance, 2011). It is the standard word list for
finance text. General-purpose word lists do not work well here: words like *liability*, *tax* or
*cost* sound negative in everyday English but are neutral in a company report, and the
Loughran-McDonald lists leave them out.

The dictionary has 86,553 words. Each word is tagged by category. We used two categories:

- **Negative words (2,345)**, such as *loss, decline, adverse, impairment, litigation, restructuring, weak*.
- **Positive words (347)**, such as *achieve, improve, strong, gain, profitable, successful, favorable*.

The dictionary marks some words as removed in later versions, and we left those out. It also lists
every form of a word separately (for example *decline, declined, declines, declining*), so no
word-stemming is needed.

**How the tone score is calculated.**

1. We took the MD&A text out of each 10-K. These are the same filings used for the financial data,
   saved on our computer.
2. We split the text into words and changed them to lower case.
3. We counted how many words are on the negative list and how many are on the positive list. Every
   other word is ignored.
4. We calculated the tone score:

   > Tone = (positive words - negative words) / (positive words + negative words)

   The score goes from -1 (only negative words) to +1 (only positive words).

*Example.* A typical MD&A in our data has about 7,800 words. Of these, 74 are on the negative list
and 38 are on the positive list. Tone = (38 - 74) / (38 + 74) = -36 / 112 = -0.32.

Most tone scores are below zero. Company reports use far more cautious and negative wording than
positive wording, and the negative list is much longer than the positive one. This does not affect
the tests, because correlation only looks at whether a more positive report than usual goes with
better results than usual.

**How much of the text the dictionary picks up.** We checked this for all 395 MD&A sections:

| Check | Result |
| :--- | ---: |
| MD&A sections scored | 395 |
| Typical (median) length | 7,847 words |
| Typical number of negative words found | 74 |
| Typical number of positive words found | 38 |
| Share of words that are on either list (median) | 1.5% |
| Sections with no matched words | 0 |
| Average tone score | -0.31 |
| Lowest and highest tone score | -1.00 and +0.79 |

About 1.5% of words carry tone, which is normal: most words in any text (*the, revenue, quarter,
products*) are neutral. Every section had matched words, so every company-year has a usable score.

**What we tested.**

1. The Pearson correlation between tone and four outcomes: revenue growth in the same year, ROE in
   the same year, revenue growth in the next year and the next-12-month excess return.
2. Whether a change in tone from one year to the next matches a change in revenue growth.
3. A list of the biggest mismatches: the most positive reports written in years when revenue fell.

| Tone measure | Compared with | N | Pearson r | p-value |
| :--- | :--- | ---: | ---: | :--- |
| MD&A tone | revenue growth, same year | 335 | 0.18 | 0.001 |
| MD&A tone | ROE, same year | 378 | 0.00 | 0.951 |
| MD&A tone | revenue growth, next year | 333 | 0.07 | 0.205 |
| MD&A tone | next-12m return minus XLK | 395 | -0.01 | 0.813 |
| Change in tone from last year | change in revenue growth from last year | 277 | 0.15 | 0.010 |

**Most positive reports in years when revenue fell:**

| Ticker | FY | MD&A tone | Revenue growth | Revenue growth next year |
| :--- | ---: | ---: | :--- | :--- |
| TXN | 2024 | 0.58 | -10.7% | n/a |
| TXN | 2023 | 0.53 | -12.5% | -10.7% |
| INTC | 2022 | 0.23 | -20.2% | -14.0% |
| LRCX | 2024 | 0.08 | -14.5% | n/a |
| CDW | 2023 | 0.02 | -10.0% | -1.8% |
| ADI | 2024 | 0.00 | -23.4% | n/a |
| CDW | 2024 | -0.02 | -1.8% | n/a |
| HPQ | 2024 | -0.05 | -0.3% | n/a |
| IBM | 2020 | -0.17 | -4.4% | 3.9% |
| ANET | 2020 | -0.18 | -3.9% | 27.2% |

All ten are well above the average tone of -0.31, even though revenue fell in each case.

**What we found.**

- Tone matches the year that just ended, but only weakly. It has r = 0.18 with same-year revenue
  growth (p = 0.001). When tone gets more positive than the year before, revenue growth has usually
  improved too (r = 0.15, p = 0.010).
- Tone has no link with profitability (ROE): r = 0.00 (p = 0.951).
- Tone does not predict the next year. It has r = 0.07 with next-year revenue growth (p = 0.205) and
  r = -0.01 with next-year excess return (p = 0.813).

**What it means.** Tone is a weak summary of the year just reported and no help for forecasting.
TXN's reports scored +0.53 and +0.58 in FY2023 and FY2024, far above the average of -0.31, while
its revenue fell by more than 10% in both years. Tone should be read next to the actual numbers.

![Figure9_Tone_vs_NextYearGrowth](outputs/figures/Figure9_Tone_vs_NextYearGrowth.png)

### RQ4: Do sub-industries differ?

**The question.** Are chip, software and hardware companies valued in the same way, or does each
group reward quality differently?

**What we did.**

1. Split the 399 company-years into the three sub-industries.
2. Worked out each group's average Quality Score, average EV/Sales and average next-12-month excess return.
3. Measured the Pearson correlation between Quality Score and log(EV/Sales) inside each group. This
   asks the RQ1 question again, one group at a time.
4. Compared this with how well each group's RQ2 line fits (its R²).

| Sub-industry | Company-years | Avg Quality Score | Avg EV/Sales | Avg next-12m return minus XLK | Quality-valuation r | RQ2 line R² (FY2024) |
| :--- | ---: | ---: | :--- | :--- | ---: | ---: |
| Hardware & Equipment | 126 | 39.1 | 2.9x | -2.5% | 0.50 | 0.24 |
| Semiconductors | 119 | 50.4 | 5.2x | +5.4% | 0.07 | 0.002 |
| Software & Services | 154 | 47.4 | 7.1x | -1.6% | 0.34 | 0.10 |

**What we found.**

- Hardware & Equipment has the strongest link (r = 0.50). Better hardware companies reliably get
  higher multiples, although hardware multiples are low overall (2.9x on average).
- Semiconductors have the highest average quality (50.4) but almost no link (r = 0.07). Chip stocks
  seem to be priced on the industry cycle and on growth stories such as AI demand, and current
  fundamentals add little.
- Software & Services has the highest multiples (7.1x) and a medium link (r = 0.34). This group mixes
  high-multiple software firms with low-multiple IT services firms, which weakens the link.
- Average multiples differ by about 2.5 times between groups (2.9x to 7.1x). This matches the
  sub-industry results in the RQ1 multiple regression.

**What it means.** Each sub-industry values quality in its own way. This is why RQ2 uses a separate
line for each sub-industry.

![Figure10_Sub_Industry_Comparison](outputs/figures/Figure10_Sub_Industry_Comparison.png)

![Figure11_Quality_Distribution](outputs/figures/Figure11_Quality_Distribution.png)

## How the AI chat uses these results

The FinChat app has an AI chat that answers questions using the results above. All numbers
(Quality Scores, fair-value lines, labels, DCF values) are calculated in Python
(`finchat/engine/mispricing.py`) and saved in an SQLite database. The language model (Gemini) does
no maths; it only reads the results it is given.

The chat agent can call 15 tools. Two of them serve this study: `get_valuation_check` gives one
company's score, pillars, label, fair-value line and DCF, and `list_mispriced` gives the cheapest and
most expensive lists. Every tool says which table its data came from, so each answer can be traced.

Every number the AI writes must match a number in the data it was given, within 1%. If a draft
fails this check, the AI tries once more; if it fails again, a fixed template is used instead. All 21
texts published for this study passed.

The answers also follow a few rules. A label is described as a statistical comparison, never as a
buy or sell tip. Each answer gives the R² of the fair-value line, says the labels did not predict
returns in back-tests, and ends with "Not investment advice".

| Question asked in the live chat | Tool called | Numbers not found in tool output |
| :--- | :--- | ---: |
| Is Nvidia overvalued for its quality? | get_valuation_check | 0 |
| Which tech companies look cheapest right now? | list_mispriced | 0 |

![Screenshot_Chat_Answer_Crop](outputs/figures/Screenshot_Chat_Answer_Crop.png)

*The live chat answering "Is Nvidia overvalued for its quality?". The Outputs panel shows the
`get_valuation_check` tool call behind the answer.*

Example company notes written by the AI for FY2024 (every number checked):

- **DXC (Undervalued):** trades at 1.1x EV/Sales against 3.5x expected for its quality among Software
  & Services companies, using a line trained only on earlier years. Best pillar: earnings quality
  (55.2). Weakest: profitability (38.0). DCF upside is +265.6%, so the DCF supports the label.
- **DELL (Undervalued):** 1.2x EV/Sales against 2.0x expected in Hardware & Equipment. Best pillar:
  safety (77.3). Weakest: profitability (28.1). DCF upside is -40.7%, so the DCF does not support the label.
- **NVDA (Overvalued):** 17.9x EV/Sales against 4.1x expected in Semiconductors. Best pillar: growth
  (100.0). Weakest: earnings quality (57.3). DCF upside is -40.6%, so the DCF supports the label.

## Limitations

- **Small sample from one sector.** 57 companies and 399 company-years; the RQ2 back-test has 108
  labelled company-years. The results apply to large US tech companies only.
- **Survivorship bias.** We picked companies from today's index, so companies that were bought or
  delisted (such as ANSYS and Juniper) are missing.
- **Different year-ends.** Scores are compared within the same fiscal-year label, but year-ends run
  from late January (NVDA) to December. A January company can be compared with companies whose year
  ends up to eleven months later.
- **Broad sub-industries.** "Software & Services" mixes software with IT services (DXC, CTSH, ACN,
  EPAM, CDW), so some "undervalued" labels just reflect the type of business.
- **EV/Sales ignores margins.** A company with a 5% margin and one with a 40% margin can have similar
  quality scores but deserve very different sales multiples. EV/EBIT would handle this better.
- **One DCF setting for all.** Every company uses the same 9% discount rate and 2.5% long-term growth,
  and stock-based pay is not taken out of free cash flow.
- **Word counting misses context.** The dictionary method cannot see negation ("not strong" counts as positive) and counts standard legal wording like any other text.
- **Some MD&A sections are short.** For 8 of 395 filings (for example AAPL FY2024, 845 words), the automatic extraction picked up less than 1,000 words, probably only part of the MD&A. Their tone scores rest on fewer words.
- **Link, not cause.** RQ1 shows that quality and valuation move together. Both could be driven by
  expected growth.

## Conclusion

1. **RQ1:** Investors pay more for better businesses, but not much more. Ten extra Quality points go
   with an EV/Sales about 25-30% higher, and quality alone explains about 14% of the differences in
   valuation. The year and the sub-industry matter more.
2. **RQ2:** When we test "cheap for its quality" fairly (each company against its own sub-industry,
   using only past data, with returns measured against the tech sector), it does not predict next
   year's return.
3. **RQ3:** Management's tone, measured with the Loughran-McDonald dictionary, weakly reflects the year that just ended and says nothing useful about the year ahead.
4. **RQ4:** Each sub-industry values quality differently: strongly in hardware, moderately in
   software and hardly at all in chips.

A quality score built from public filings is useful for describing and screening companies. In
large US tech it does not, on its own, predict returns, so every Radar label carries the note "Not
investment advice".

## Appendix A: Financial terms

| Term | Meaning in simple words |
| --- | --- |
| **10-K** | The annual report every US-listed company must file with the SEC. It contains the financial statements and management's comments. |
| **SEC EDGAR** | The SEC's public online database of company filings. |
| **MD&A** | Management's Discussion & Analysis: the part of the 10-K where managers explain the year's results in their own words. |
| **Fiscal year (FY)** | The company's 12-month accounting year. It does not always end in December (NVDA's ends in late January). |
| **Company-year** | One company in one fiscal year, for example "NVDA, FY2024". Each is one row of data. |
| **Sub-industry** | The group a company belongs to: Hardware & Equipment, Semiconductors, or Software & Services. |
| **XLK** | An exchange-traded fund that holds the large US technology stocks. We use it as the benchmark for the tech sector. |
| **Revenue (sales)** | Money the company takes in from selling its products and services. |
| **Revenue growth** | Percentage change in revenue from the year before. |
| **Net income growth** | Percentage change in profit after all costs and taxes from the year before. |
| **ROE (return on equity)** | Net income divided by shareholders' equity: how much profit the company makes on the owners' money. |
| **ROIC (return on invested capital)** | Operating profit after tax divided by the money invested by both owners and lenders. |
| **Operating margin** | Operating profit divided by revenue: the share of each dollar of sales left after running costs. |
| **Net margin** | Net income divided by revenue: the share of each dollar of sales left as final profit. |
| **Current ratio** | Current assets divided by current liabilities: whether the company can pay bills due within a year. |
| **Interest coverage** | Operating profit divided by interest expense: how many times over the company can pay its interest. |
| **Debt/equity** | Total debt divided by shareholders' equity: how much the company relies on borrowing. |
| **Operating cash flow** | Cash the business actually brings in from its normal operations during the year. |
| **Capital spending (capex)** | Cash spent on long-term assets such as factories and equipment. |
| **Free cash flow (FCF)** | Operating cash flow minus capital spending: cash left over for owners and lenders. |
| **FCF margin** | Free cash flow divided by revenue. |
| **Accruals** | (Net income - operating cash flow) / total assets. A high value means reported profit is much bigger than the cash coming in, which is a warning sign. |
| **Market value (market capitalisation)** | Share price multiplied by the number of shares: what the stock market says the company's shares are worth. |
| **Enterprise value (EV)** | Market value + debt - cash - short-term investments: the cost of buying the whole business. |
| **Net debt** | Debt minus cash and short-term investments. |
| **EV/Sales** | Enterprise value divided by revenue: how many dollars investors pay for each dollar of sales. Higher means more expensive. |
| **Valuation multiple** | Any price measure written as a multiple, such as an EV/Sales of 4x. |
| **P/E (price-to-earnings)** | Share price divided by earnings per share. It cannot be used when a company makes a loss. |
| **DCF (discounted cash flow)** | A way to value a company by estimating its future free cash flows and converting them to today's money. |
| **Discount rate (WACC)** | The yearly rate used to convert future cash to today's money. We use 9% for every company. |
| **Terminal growth** | The growth rate assumed for every year after the forecast period ends. We use 2.5%. |
| **DCF upside** | (DCF fair price - actual share price) / actual share price. Positive means the DCF thinks the share is worth more than its price. |
| **Next-12-month return** | Percentage change in share price, including dividends, over the year after the 10-K filing date. |
| **Excess return** | A stock's return minus XLK's return over the same days: whether the stock beat or trailed the tech sector. |
| **Undervalued / Overvalued / Fairly valued** | Our RQ2 labels for a company whose EV/Sales is far below, far above, or close to what its Quality Score predicts. They are statistical comparisons, not buy or sell advice. |
| **Survivorship bias** | Error caused by studying only companies that still exist today, which leaves out companies that failed or were bought. |
| **Loughran-McDonald dictionary** | A list of positive, negative and other words built from 10-K filings, used to measure tone in finance text. |
| **Tone (polarity)** | (positive words - negative words) / (positive words + negative words), from -1 to +1. |

## Appendix B: Statistics terms

| Term | Meaning in simple words |
| --- | --- |
| **Average (mean)** | The total of all values divided by how many values there are. |
| **Median** | The middle value when all values are put in order. Unlike the average, a few extreme values do not pull it around. |
| **Percentile** | The value below which a given share of the data falls. The 95th percentile is higher than 95% of values. |
| **Standard deviation** | How spread out values are around the average. A small standard deviation means most values are close to the average. |
| **z-score** | (value - average) / standard deviation: how many standard deviations a value is above or below the average. |
| **Winsorizing** | Capping extreme values at a chosen percentile (here the 5th and 95th) so a few outliers cannot drive the results. |
| **Log (natural logarithm)** | A transformation that shrinks large numbers more than small ones. In a regression on log values, the slope can be read as a percentage change. e^x turns a log value back into a normal number. |
| **Pearson r (correlation)** | How closely two things move together in a straight line. Goes from -1 to +1. 0 means no link, 0.3 is a weak to medium link, 0.5 is a medium to strong link. |
| **Spearman rho** | The same idea, but using ranks (1st, 2nd, 3rd...) so a few extreme values do not distort it. |
| **Linear regression (OLS)** | Draws the best straight line y = a + b·x through the data. "Best" means the line with the smallest total of squared distances between the points and the line. OLS stands for ordinary least squares. |
| **Intercept (a)** | The value the line predicts when x is 0. |
| **Slope / coefficient (b)** | How much y changes when x goes up by 1, keeping the other inputs the same. |
| **Multiple regression** | A regression with more than one input, so the effect of each input is measured while the others are held fixed. |
| **Control variable** | An extra input added to a regression so that its effect is taken out of the result we care about. |
| **Fixed effect (dummy variable)** | A yes/no (1/0) input for each year or each group. A year fixed effect soaks up anything that affected all companies in that year. |
| **Baseline category** | The year or group that the fixed effects are compared with (here FY2019 and Hardware & Equipment). |
| **Residual** | Actual value minus the value the line predicts. |
| **R²** | How much of the ups and downs in y the model explains, from 0 to 1. R² = 0.14 means 14%. |
| **Adjusted R²** | R² lowered slightly to account for the number of inputs, so adding useless inputs does not make a model look better. |
| **Standard error** | How uncertain a coefficient is. A coefficient much bigger than its standard error is unlikely to be zero. |
| **Clustered standard errors** | Standard errors corrected for the fact that the 7 rows of the same company are related. Without the correction, p-values would look better than they really are. |
| **F-statistic** | A test of whether the model as a whole explains anything at all. |
| **p-value** | The chance of seeing a result this strong if there were really no link or no difference. |
| **Statistically significant** | A result with a p-value below 0.05: unlikely to be due to luck alone. |
| **N** | The number of observations (company-years) used in a test. |
| **Welch t-test** | Checks whether the averages of two groups are really different, or whether the gap could just be luck. The Welch version does not assume both groups are equally spread out. |
| **In-sample** | Measured on the same data the model was fitted on. |
| **Out-of-sample / walk-forward** | The model is fitted only on earlier years and then tested on a later year it has never seen, as an investor would have had to do at the time. |
| **Back-test** | Checking how a rule would have performed on past data. |
