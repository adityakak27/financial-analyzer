"""Step 5: RQ1-RQ5 -- correlations, regressions, walk-forward mispricing, score-group outcomes,
tone correlations, sub-industry analysis, sample attrition. Tables 3-10 + analysis_dataset.csv.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats as sp_stats

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
warnings.filterwarnings("ignore", category=FutureWarning)

from analysis.config import DATA_PROCESSED_DIR, TABLES_DIR
from analysis.utils import save_table
from finchat.engine.mispricing import (dcf_agreement, fit_fair_value_line, score_group_outcomes,
                                        walk_forward_mispricing, winsorize_panel)


def _two_group_test(a: pd.Series, b: pd.Series) -> dict:
    a, b = a.dropna(), b.dropna()
    if len(a) < 2 or len(b) < 2:
        return {"t_stat": None, "t_pvalue": None, "u_pvalue": None}
    t, p_t = sp_stats.ttest_ind(a, b, equal_var=False)
    _, p_u = sp_stats.mannwhitneyu(a, b, alternative="two-sided")
    return {"t_stat": round(float(t), 3), "t_pvalue": round(float(p_t), 4), "u_pvalue": round(float(p_u), 4)}


def rq1_quality_vs_valuation(panel: pd.DataFrame) -> dict:
    print("\n" + "=" * 70)
    print("RQ1: Does quality explain valuation? (descriptive, in-sample)")
    print("=" * 70)

    sub = panel.dropna(subset=["QualityScore", "log_ev_sales"])
    pear_r, pear_p = sp_stats.pearsonr(sub["QualityScore"], sub["log_ev_sales"])
    spear_r, spear_p = sp_stats.spearmanr(sub["QualityScore"], sub["log_ev_sales"])
    print(f"N = {len(sub)} company-years")
    print(f"Pearson r  = {pear_r:.3f} (p={pear_p:.2g})   Spearman rho = {spear_r:.3f} (p={spear_p:.2g})")

    per_year = []
    for fy, g in sub.groupby("fy"):
        if len(g) >= 5:
            r, p = sp_stats.pearsonr(g["QualityScore"], g["log_ev_sales"])
            per_year.append({"fy": int(fy), "n": len(g), "pearson_r": round(r, 3), "p_value": round(p, 4)})
    print(pd.DataFrame(per_year).to_string(index=False))
    save_table(pd.DataFrame(per_year), "Table3a_PerYear_Correlation")

    fit1 = fit_fair_value_line(panel)
    print(f"\nRegression 1: log(EV/Sales) = {fit1['intercept']:.4f} + {fit1['slope']:.5f}*Q  "
          f"R^2={fit1['r2']:.4f} p={fit1['p_value']:.2g} N={fit1['n']}")

    reg_df = sub.dropna(subset=["revenue_growth_pct"]).copy()
    reg_df["fy_cat"] = reg_df["fy"].astype(int).astype(str)
    model2 = smf.ols(
        "log_ev_sales ~ QualityScore + revenue_growth_pct + C(fy_cat) + C(sub_industry)", data=reg_df,
    ).fit(cov_type="cluster", cov_kwds={"groups": reg_df["ticker"]})
    print(f"Regression 2 (controls, clustered SE), N={int(model2.nobs)}, R^2={model2.rsquared:.4f}")
    print(model2.summary().tables[1])

    (TABLES_DIR / "regression_results.txt").write_text(
        f"Regression 1 (simple OLS, pooled FY2018-2024, descriptive)\n"
        f"log(EV/Sales) = {fit1['intercept']:.4f} + {fit1['slope']:.5f} * QualityScore\n"
        f"R^2 = {fit1['r2']:.4f}, p = {fit1['p_value']:.3g}, N = {fit1['n']}\n\n"
        f"Regression 2 (+ revenue growth, fiscal-year and sub-industry fixed effects; SE clustered "
        f"by ticker). N falls from {fit1['n']} to {int(model2.nobs)} because revenue growth needs a "
        f"prior year.\n" + str(model2.summary()),
        encoding="utf-8",
    )
    table3 = pd.DataFrame({
        "model": ["Simple (QualityScore only)",
                  "With controls (revenue growth, year FE, sub-industry FE; clustered SE)"],
        "slope_on_QualityScore": [round(fit1["slope"], 5), round(model2.params["QualityScore"], 5)],
        "p_value": [fit1["p_value"], model2.pvalues["QualityScore"]],
        "r_squared": [round(fit1["r2"], 3), round(model2.rsquared, 3)],
        "n": [fit1["n"], int(model2.nobs)],
    })
    save_table(table3, "Table3_Regression_Summary")
    return {"fit1": fit1, "model2": model2, "pearson_r": pear_r, "spearman_r": spear_r}


def rq2_mispricing(panel: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("RQ2: Walk-forward, sub-industry-relative mispricing")
    print("=" * 70)

    panel, wf_fits = walk_forward_mispricing(panel)
    panel["dcf_agreement"] = panel.apply(dcf_agreement, axis=1)
    panel["expected_ev_sales"] = np.exp(panel["expected_log_ev_sales"])
    save_table(wf_fits.round(4), "Table3b_WalkForward_Fits")

    latest_fy = int(panel.fy.max())
    latest = panel[panel.fy == latest_fy].dropna(subset=["gap_z"])
    cols = ["ticker", "sub_industry", "QualityScore", "ev_sales", "expected_ev_sales",
            "gap_z", "verdict", "dcf_upside", "dcf_agreement"]
    under = latest.sort_values("gap_z").head(15)[cols]
    over = latest.sort_values("gap_z", ascending=False).head(15)[cols]
    print(f"\nTable 4: 15 lowest gap z-scores (FY{latest_fy}):\n{under.to_string(index=False)}")
    print(f"\nTable 5: 15 highest gap z-scores (FY{latest_fy}):\n{over.to_string(index=False)}")
    save_table(under, "Table4_Undervalued")
    save_table(over, "Table5_Overvalued")

    flagged = latest[latest["verdict"].isin(["Undervalued", "Overvalued"])]
    agree = flagged["dcf_agreement"].value_counts().to_dict()
    print(f"\nDCF agreement among FY{latest_fy} flagged companies (n={len(flagged)}): {agree}")

    tested = panel[panel["verdict"].isin(["Undervalued", "Overvalued"])]
    rows = []
    for outcome in ("excess_return_next_12m", "return_next_12m"):
        u = tested[tested.verdict == "Undervalued"][outcome].dropna()
        o = tested[tested.verdict == "Overvalued"][outcome].dropna()
        rows.append({"outcome": outcome, "n_under": len(u), "mean_under": round(u.mean(), 4),
                     "n_over": len(o), "mean_over": round(o.mean(), 4),
                     "difference": round(u.mean() - o.mean(), 4), **_two_group_test(u, o)})
    test_years = sorted(int(y) for y in tested["fy"].unique())
    did_it_work = pd.DataFrame(rows)
    print(f"\nDid it work out? Out-of-sample verdicts, FY{test_years[0]}-FY{test_years[-1]} pooled:")
    print(did_it_work.to_string(index=False))
    save_table(did_it_work, "Table5b_Verdict_Outcomes")
    return panel


def rq3_score_effectiveness(panel: pd.DataFrame) -> None:
    print("\n" + "=" * 70)
    print("RQ3: Do Piotroski/Altman/Beneish predict next-year outcomes?")
    print("=" * 70)

    table6 = score_group_outcomes(panel)
    print(table6.round(3).to_string(index=False))
    save_table(table6.round(4), "Table6_Score_Group_Outcomes")

    def groups(score_col: str, outcome: str) -> tuple[pd.Series, pd.Series]:
        sub = panel.dropna(subset=[score_col, outcome])
        if score_col == "piotroski_f":
            return sub[sub[score_col] <= 3][outcome], sub[sub[score_col] >= 7][outcome]
        if score_col == "altman_z":
            return sub[sub[score_col] < 1.81][outcome], sub[sub[score_col] > 3.0][outcome]
        return sub[sub[score_col] > -1.78][outcome], sub[sub[score_col] <= -1.78][outcome]

    tests = []
    for score_col in ("piotroski_f", "altman_z", "beneish_m"):
        for outcome in ("excess_return_next_12m", "rev_growth_next"):
            weak, strong = groups(score_col, outcome)
            tests.append({"score": score_col, "outcome": outcome, "n_weak": len(weak), "n_strong": len(strong),
                          "mean_weak": round(weak.mean(), 4), "mean_strong": round(strong.mean(), 4),
                          **_two_group_test(strong, weak)})
    tests_df = pd.DataFrame(tests)
    print("\nStrong vs weak group tests (Welch t + Mann-Whitney U):")
    print(tests_df.to_string(index=False))
    save_table(tests_df, "Table6b_Score_Group_Tests")


def rq4_tone_vs_reality(panel: pd.DataFrame) -> None:
    print("\n" + "=" * 70)
    print("RQ4: Does management tone (MD&A polarity) match reality?")
    print("=" * 70)
    rows = []
    for x, y, label in [
        ("mda_polarity", "revenue_growth_pct", "same-year revenue growth"),
        ("mda_polarity", "roe", "same-year ROE"),
        ("mda_polarity", "rev_growth_next", "next-year revenue growth"),
        ("mda_polarity", "excess_return_next_12m", "next-12m excess return (vs XLK)"),
    ]:
        sub = panel.dropna(subset=[x, y])
        r, p = sp_stats.pearsonr(sub[x], sub[y])
        rows.append({"x": x, "y": label, "n": len(sub), "pearson_r": round(r, 3), "p_value": round(p, 4)})
    ps = panel.sort_values(["ticker", "fy"]).copy()
    ps["polarity_change"] = ps.groupby("ticker")["mda_polarity"].diff()
    ps["rev_growth_change"] = ps.groupby("ticker")["revenue_growth_pct"].diff()
    sub = ps.dropna(subset=["polarity_change", "rev_growth_change"])
    r, p = sp_stats.pearsonr(sub["polarity_change"], sub["rev_growth_change"])
    rows.append({"x": "polarity_change (YoY)", "y": "revenue_growth_change (YoY)",
                 "n": len(sub), "pearson_r": round(r, 3), "p_value": round(p, 4)})
    table7 = pd.DataFrame(rows)
    print(table7.to_string(index=False))
    save_table(table7, "Table7_Tone_Correlations")

    tone = panel.dropna(subset=["mda_polarity", "revenue_growth_pct"]).copy()
    tone["q"] = pd.qcut(tone["mda_polarity"], 4, labels=False, duplicates="drop")
    mism = pd.concat([
        tone[(tone.q == tone.q.max()) & (tone.revenue_growth_pct < 0)],
        tone[(tone.q == tone.q.min()) & (tone.revenue_growth_pct > 15)],
    ])
    table8 = mism.sort_values("mda_polarity", ascending=False)[
        ["ticker", "fy", "mda_polarity", "revenue_growth_pct", "rev_growth_next"]].head(10)
    save_table(table8, "Table8_Tone_Mismatches")


def rq5_sub_industry(panel: pd.DataFrame) -> None:
    print("\n" + "=" * 70)
    print("RQ5: Sub-industry differences")
    print("=" * 70)
    rows = []
    for ind, g in panel.groupby("sub_industry"):
        s = g.dropna(subset=["QualityScore", "log_ev_sales"])
        r = sp_stats.pearsonr(s["QualityScore"], s["log_ev_sales"])[0] if len(s) >= 5 else None
        rows.append({"sub_industry": ind, "n_company_years": len(g),
                     "avg_quality_score": round(g["QualityScore"].mean(), 1),
                     "avg_ev_sales": round(g["ev_sales"].mean(), 2),
                     "avg_excess_return_next_12m": round(g["excess_return_next_12m"].mean(), 3),
                     "quality_valuation_corr": round(r, 3) if r is not None else None})
    table9 = pd.DataFrame(rows)
    print(table9.to_string(index=False))
    save_table(table9, "Table9_Sub_Industry_Analysis")


def sample_attrition(raw: pd.DataFrame, panel: pd.DataFrame, res1: dict) -> None:
    print("\n" + "=" * 70)
    print("Sample attrition and missingness")
    print("=" * 70)
    verdict_rows = panel[panel["verdict"] != "insufficient_data"]
    steps = pd.DataFrame([
        {"stage": "Company-years collected (57 x 7)", "n": len(raw)},
        {"stage": "With a Quality Score", "n": int(panel["QualityScore"].notna().sum())},
        {"stage": "With EV/Sales (needs price + diluted shares)", "n": int(panel["ev_sales"].notna().sum())},
        {"stage": "RQ1 simple regression (Quality + EV/Sales)", "n": res1["fit1"]["n"]},
        {"stage": "RQ1 controlled regression (+ revenue growth, needs prior year)", "n": int(res1["model2"].nobs)},
        {"stage": "With a walk-forward verdict (FY2019+; FY2018 has no training data)", "n": len(verdict_rows)},
        {"stage": "With a next-12m excess return", "n": int(panel["excess_return_next_12m"].notna().sum())},
        {"stage": "With Piotroski F", "n": int(panel["piotroski_f"].notna().sum())},
        {"stage": "With Altman Z (point-in-time)", "n": int(panel["altman_z"].notna().sum())},
        {"stage": "With Beneish M", "n": int(panel["beneish_m"].notna().sum())},
    ])
    print(steps.to_string(index=False))
    save_table(steps, "Table10_Sample_Attrition")

    by_sector = panel.groupby("sub_industry").agg(
        company_years=("ticker", "size"),
        beneish_available=("beneish_m", lambda s: int(s.notna().sum())),
        sga_reported=("sga", lambda s: int(s.notna().sum())),
        ppe_reported=("ppe_net", lambda s: int(s.notna().sum())),
    ).reset_index()
    by_sector["beneish_coverage_pct"] = (100 * by_sector["beneish_available"] / by_sector["company_years"]).round(1)
    print("\nBeneish M coverage by sub-industry (needs SG&A, PP&E and a prior year):")
    print(by_sector.to_string(index=False))
    save_table(by_sector, "Table10b_Beneish_Coverage")


def main():
    raw = pd.read_parquet(DATA_PROCESSED_DIR / "panel.parquet")
    panel = winsorize_panel(raw)

    res1 = rq1_quality_vs_valuation(panel)
    panel = rq2_mispricing(panel)
    rq3_score_effectiveness(panel)
    rq4_tone_vs_reality(panel)
    rq5_sub_industry(panel)
    sample_attrition(raw, panel, res1)

    panel.to_csv(DATA_PROCESSED_DIR / "analysis_dataset.csv", index=False)
    print(f"\n[saved] analysis_dataset.csv ({len(panel)} rows, {panel.shape[1]} cols)")


if __name__ == "__main__":
    main()
