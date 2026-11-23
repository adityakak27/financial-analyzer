"""Step 7: Figures 1-11."""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import DATA_PROCESSED_DIR
from analysis.utils import save_figure, set_plot_style
from finchat.engine.mispricing import fit_fair_value_line

PILLAR_COLORS = {
    "profitability": "#2E86AB", "growth": "#4CB944",
    "safety": "#E09F3E", "earnings_quality": "#9D4EDD",
}


SECTOR_COLORS = {"Hardware & Equipment": "#8C8C8C", "Semiconductors": "#2E86AB",
                 "Software & Services": "#E09F3E"}


def fig1_scatter(panel: pd.DataFrame) -> None:
    sub = panel.dropna(subset=["QualityScore", "log_ev_sales"])
    fit = fit_fair_value_line(panel)
    fig, ax = plt.subplots(figsize=(10, 7))
    for sector, g in sub.groupby("sub_industry"):
        ax.scatter(g["QualityScore"], g["log_ev_sales"], alpha=0.45, s=30,
                   color=SECTOR_COLORS.get(sector, "#4C72B0"), label=f"{sector} (n={len(g)})")
    x = np.linspace(sub["QualityScore"].min(), sub["QualityScore"].max(), 50)
    ax.plot(x, fit["intercept"] + fit["slope"] * x, color="black", lw=2,
            label=f"Pooled descriptive fit (R²={fit['r2']:.2f})")
    ax.set_xlabel("Fundamental Quality Score (0-100)")
    ax.set_ylabel("log(EV / Sales)")
    ax.set_title(f"Figure 1: Quality vs Valuation by sub-industry (N={fit['n']} company-years, FY2018-2024)")
    ax.legend(fontsize=9, loc="lower right")
    save_figure(fig, "Figure1_Quality_vs_Valuation")
    plt.close(fig)


def fig2_heatmap(panel: pd.DataFrame) -> None:
    import seaborn as sns
    cols = ["QualityScore", "profitability_score", "growth_score", "safety_score",
            "earnings_quality_score", "ev_sales", "pe", "excess_return_next_12m",
            "altman_z", "piotroski_f", "beneish_m"]
    cols = [c for c in cols if c in panel.columns]
    corr = panel[cols].corr()
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax,
                cbar_kws={"label": "Pearson r"})
    ax.set_title(f"Figure 2: Correlation Heatmap (N={len(panel)} company-years)")
    save_figure(fig, "Figure2_Correlation_Heatmap")
    plt.close(fig)


def _hbar(df: pd.DataFrame, value_col: str, label_col: str, title: str, name: str,
          color_col: str | None = None) -> None:
    fig, ax = plt.subplots(figsize=(9, 8))
    df = df.sort_values(value_col)
    colors = "#4C72B0" if color_col is None else [PILLAR_COLORS.get(c, "#888") for c in df[color_col]]
    ax.barh(df[label_col], df[value_col], color=colors)
    ax.set_title(f"{title} (N={len(df)})")
    save_figure(fig, name)
    plt.close(fig)


def fig3_top_quality(panel: pd.DataFrame) -> None:
    latest_fy = int(panel.fy.max())
    top = panel[panel.fy == latest_fy].dropna(subset=["QualityScore"]).nlargest(15, "QualityScore")
    top = top.assign(label=top["ticker"] + " FY" + top["fy"].astype(int).astype(str))
    _hbar(top, "QualityScore", "label", f"Figure 3: Top 15 by Quality Score (FY{latest_fy})",
          "Figure3_Top_Quality_Scores")


def fig4_top_ev_sales(panel: pd.DataFrame) -> None:
    latest_fy = int(panel.fy.max())
    top = panel[panel.fy == latest_fy].dropna(subset=["ev_sales"]).nlargest(15, "ev_sales")
    top = top.assign(label=top["ticker"] + " FY" + top["fy"].astype(int).astype(str))
    _hbar(top, "ev_sales", "label", f"Figure 4: Top 15 by EV/Sales (FY{latest_fy})",
          "Figure4_Top_EV_Sales")


def fig5_bargains(panel: pd.DataFrame) -> None:
    latest_fy = int(panel.fy.max())
    sub = panel[(panel.fy == latest_fy)].dropna(subset=["gap_z"])
    bottom = sub.nsmallest(15, "gap_z").assign(label=lambda d: d["ticker"] + " (" + d["sub_industry"].str.split().str[0] + ")")
    _hbar(bottom, "gap_z", "label",
          f"Figure 5: Lowest gap z-scores, FY{latest_fy} (vs own sub-industry, walk-forward)",
          "Figure5_Biggest_Bargains")


def fig6_premiums(panel: pd.DataFrame) -> None:
    latest_fy = int(panel.fy.max())
    sub = panel[(panel.fy == latest_fy)].dropna(subset=["gap_z"])
    top = sub.nlargest(15, "gap_z").assign(label=lambda d: d["ticker"] + " (" + d["sub_industry"].str.split().str[0] + ")")
    _hbar(top, "gap_z", "label",
          f"Figure 6: Highest gap z-scores, FY{latest_fy} (vs own sub-industry, walk-forward)",
          "Figure6_Biggest_Premiums")


def fig7_piotroski_returns(panel: pd.DataFrame) -> None:
    sub = panel.dropna(subset=["piotroski_f", "excess_return_next_12m"]).copy()
    sub["grp"] = pd.cut(sub["piotroski_f"], bins=[-1, 3, 6, 9], labels=["low (0-3)", "mid (4-6)", "high (7-9)"])
    g = sub.groupby("grp", observed=True)["excess_return_next_12m"].agg(["mean", "sem", "count"])
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(g.index.astype(str), g["mean"] * 100, yerr=g["sem"] * 100, capsize=5, color="#4C72B0")
    ax.axhline(0, color="black", lw=1)
    ax.set_ylabel("Mean next-12m return in excess of XLK (%)")
    ax.set_title(f"Figure 7: Next-Year Excess Return by Piotroski F Group (N={int(g['count'].sum())})")
    save_figure(fig, "Figure7_Piotroski_Returns")
    plt.close(fig)


def fig12_verdict_outcomes(panel: pd.DataFrame) -> None:
    sub = panel[panel["verdict"] != "insufficient_data"].dropna(subset=["excess_return_next_12m"])
    order = ["Undervalued", "Fairly valued", "Overvalued"]
    g = sub.groupby("verdict")["excess_return_next_12m"].agg(["mean", "sem", "count"]).reindex(order)
    years = sorted(int(y) for y in sub["fy"].unique())
    fig, ax = plt.subplots(figsize=(8, 6))
    labels = [f"{v}\n(n={int(g.loc[v, 'count'])})" for v in order]
    ax.bar(labels, g["mean"] * 100, yerr=g["sem"] * 100, capsize=5,
           color=["#4CB944", "#8C8C8C", "#E09F3E"])
    ax.axhline(0, color="black", lw=1)
    for i, v in enumerate(order):
        m = g.loc[v, "mean"] * 100
        ax.annotate(f"{m:+.1f}%", (i + 0.43, m), ha="left", va="center", fontsize=11, fontweight="bold")
    ax.set_xlim(-0.6, len(order) - 0.15)
    ax.set_ylabel("Mean next-12m return in excess of XLK (%)")
    ax.set_title(f"Figure 12: Out-of-sample excess return by verdict (FY{years[0]}-FY{years[-1]})")
    save_figure(fig, "Figure12_Verdict_Outcomes")
    plt.close(fig)


def fig8_altman_loss_rate(panel: pd.DataFrame) -> None:
    sub = panel.dropna(subset=["altman_z", "loss_next"]).copy()
    sub["grp"] = pd.cut(sub["altman_z"], bins=[-np.inf, 1.81, 3.0, np.inf],
                         labels=["distress (<1.81)", "grey (1.81-3.0)", "safe (>3.0)"])
    g = sub.groupby("grp", observed=True)["loss_next"].agg(["mean", "count"])
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.bar(g.index.astype(str), g["mean"] * 100, color="#E09F3E")
    ax.set_ylabel("% of companies with a loss next year")
    ax.set_title(f"Figure 8: Next-Year Loss Rate by Altman Zone (N={int(g['count'].sum())})")
    save_figure(fig, "Figure8_Altman_Loss_Rate")
    plt.close(fig)


def fig9_tone_scatter(panel: pd.DataFrame) -> None:
    sub = panel.dropna(subset=["mda_polarity", "rev_growth_next"])
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(sub["mda_polarity"], sub["rev_growth_next"], alpha=0.4, s=35, color="#4C72B0")
    if len(sub) >= 5:
        z = np.polyfit(sub["mda_polarity"], sub["rev_growth_next"], 1)
        x = np.linspace(sub["mda_polarity"].min(), sub["mda_polarity"].max(), 50)
        ax.plot(x, np.polyval(z, x), color="black", lw=2)
    ax.set_xlabel("MD&A polarity (same-year filing)")
    ax.set_ylabel("Next-year revenue growth (%)")
    ax.set_title(f"Figure 9: MD&A Tone vs Next-Year Revenue Growth (N={len(sub)})")
    save_figure(fig, "Figure9_Tone_vs_NextYearGrowth")
    plt.close(fig)


def fig10_sub_industry(panel: pd.DataFrame) -> None:
    g = panel.groupby("sub_industry").agg(
        avg_quality_score=("QualityScore", "mean"), avg_ev_sales=("ev_sales", "mean"),
        n=("ticker", "count"),
    ).reset_index()
    fig, ax1 = plt.subplots(figsize=(9, 6))
    ax2 = ax1.twinx()
    x = np.arange(len(g))
    ax1.bar(x - 0.18, g["avg_quality_score"], width=0.36, color="#4C72B0", label="Avg Quality Score")
    ax2.bar(x + 0.18, g["avg_ev_sales"], width=0.36, color="#E09F3E", label="Avg EV/Sales")
    ax1.set_xticks(x)
    ax1.set_xticklabels(g["sub_industry"], rotation=15)
    ax1.set_ylabel("Avg Quality Score (0-100)")
    ax2.set_ylabel("Avg EV/Sales (x)")
    ax1.set_title(f"Figure 10: Sub-Industry Comparison (N={int(g['n'].sum())})")
    fig.legend(loc="upper right")
    save_figure(fig, "Figure10_Sub_Industry_Comparison")
    plt.close(fig)


def fig11_quality_distribution(panel: pd.DataFrame) -> None:
    import seaborn as sns
    sub = panel.dropna(subset=["QualityScore"])
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.histplot(sub["QualityScore"], bins=20, kde=True, ax=ax, color="#4C72B0")
    ax.set_xlabel("Fundamental Quality Score (0-100)")
    ax.set_title(f"Figure 11: Distribution of the Quality Score (N={len(sub)})")
    save_figure(fig, "Figure11_Quality_Distribution")
    plt.close(fig)


def main():
    set_plot_style()
    panel = pd.read_csv(DATA_PROCESSED_DIR / "analysis_dataset.csv")

    fig1_scatter(panel)
    fig2_heatmap(panel)
    fig3_top_quality(panel)
    fig4_top_ev_sales(panel)
    fig5_bargains(panel)
    fig6_premiums(panel)
    fig7_piotroski_returns(panel)
    fig8_altman_loss_rate(panel)
    fig9_tone_scatter(panel)
    fig10_sub_industry(panel)
    fig11_quality_distribution(panel)
    fig12_verdict_outcomes(panel)
    print("\nAll 12 figures saved.")


if __name__ == "__main__":
    main()
