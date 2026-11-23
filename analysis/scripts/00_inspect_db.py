"""Step 1: inventory data/finchat.db -- tables, coverage, missing values.

Run from the repo root: python analysis/scripts/00_inspect_db.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import DB_PATH, SUB_INDUSTRY
from analysis.utils import save_table


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    rows = []
    for t in tables:
        n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {t}", conn)["n"].iloc[0]
        cols = pd.read_sql(f"PRAGMA table_info({t})", conn)["name"].tolist()
        tickers = years = "-"
        if "ticker" in cols:
            tdf = pd.read_sql(f"SELECT DISTINCT ticker FROM {t}", conn)
            tickers = f"{tdf['ticker'].nunique()} tickers"
        if "fy" in cols:
            ydf = pd.read_sql(f"SELECT fy FROM {t}", conn)
            if not ydf.empty:
                years = f"{int(ydf.fy.min())}-{int(ydf.fy.max())}"
        rows.append({"table": t, "rows": n, "cols": len(cols), "tickers": tickers, "fy_range": years})

    inventory = pd.DataFrame(rows)
    print("\n=== Table 0: Database Inventory ===")
    print(inventory.to_string(index=False))
    save_table(inventory, "Table0_Database_Inventory")

    companies = pd.read_sql("SELECT ticker, name FROM companies ORDER BY ticker", conn)
    companies["sub_industry"] = companies["ticker"].map(SUB_INDUSTRY).fillna("Unclassified")
    print(f"\nCompanies ({len(companies)}):")
    print(companies.to_string(index=False))

    scores = pd.read_sql("SELECT * FROM scores", conn)
    print(f"\nscores table: {len(scores)} company-years, "
          f"{scores['ticker'].nunique()} tickers, "
          f"FY{int(scores.fy.min())}-{int(scores.fy.max())}")

    print("\n=== Missing-value % in key score fields ===")
    key_cols = ["altman_z", "piotroski_f", "beneish_m"]
    miss = (scores[key_cols].isna().mean() * 100).round(1)
    print(miss.to_string())

    ratios = pd.read_sql("SELECT ticker, fy, metric, value FROM ratios", conn)
    pivot = ratios.pivot_table(index=["ticker", "fy"], columns="metric", values="value", aggfunc="first")
    key_ratio_cols = [c for c in ["roe", "roic", "operating_margin", "net_margin",
                                  "revenue_growth", "net_income_growth",
                                  "current_ratio", "debt_to_equity", "interest_coverage",
                                  "fcf_margin"] if c in pivot.columns]
    print("\n=== Missing-value % in key ratio fields (of 133 company-years) ===")
    ratio_miss = (pivot[key_ratio_cols].isna().mean() * 100).round(1)
    print(ratio_miss.to_string())

    textstats = pd.read_sql("SELECT * FROM textstats", conn)
    print(f"\ntextstats table: {len(textstats)} rows "
          f"({textstats['ticker'].nunique()} tickers x sections)")

    conn.close()


if __name__ == "__main__":
    main()
