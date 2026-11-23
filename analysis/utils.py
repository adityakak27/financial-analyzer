"""Shared helpers for the Mispricing Radar analysis scripts."""
from __future__ import annotations

import pandas as pd

from analysis.config import FIGURES_DIR, TABLES_DIR


def winsorize(series: pd.Series, low: float = 0.05, high: float = 0.95) -> pd.Series:
    """Clip a series to its [low, high] quantiles. NaNs pass through untouched."""
    if series.dropna().empty:
        return series
    lo, hi = series.quantile(low), series.quantile(high)
    return series.clip(lower=lo, upper=hi)


def winsorize_by_year(df: pd.DataFrame, col: str, year_col: str = "fy",
                       low: float = 0.05, high: float = 0.95) -> pd.Series:
    """Winsorize a column within each fiscal year separately (small-sample safe)."""
    return df.groupby(year_col)[col].transform(lambda s: winsorize(s, low, high))


def zscore(series: pd.Series) -> pd.Series:
    mu, sd = series.mean(), series.std(ddof=0)
    if not sd or pd.isna(sd) or sd == 0:
        return series * 0.0
    return (series - mu) / sd


def zscore_by_year(df: pd.DataFrame, col: str, year_col: str = "fy") -> pd.Series:
    return df.groupby(year_col)[col].transform(zscore)


def set_plot_style() -> None:
    import matplotlib.pyplot as plt
    import seaborn as sns

    sns.set_theme(style="whitegrid", context="talk")
    plt.rcParams.update({
        "figure.dpi": 100,
        "savefig.dpi": 200,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })


def save_table(df: pd.DataFrame, name: str, index: bool = False) -> None:
    """Save a table as both CSV and Markdown under outputs/tables/."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = TABLES_DIR / f"{name}.csv"
    md_path = TABLES_DIR / f"{name}.md"
    df.to_csv(csv_path, index=index)
    try:
        md_path.write_text(df.to_markdown(index=index), encoding="utf-8")
    except Exception:
        md_path.write_text(df.to_string(index=index), encoding="utf-8")
    print(f"[saved] {csv_path.name} ({len(df)} rows)")


def save_figure(fig, name: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"{name}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight")
    print(f"[saved] {path.name}")
