"""Step 3: verify point-in-time price coverage for every company-year filing date.

Prices themselves are cached by `python -m finchat prices` (finchat/collect/prices.py).
This script just reports, per company-year, whether price_at_filing and the 12-month-later
price were both found -- any gaps are listed.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import DB_PATH
from analysis.utils import save_table
from finchat.collect.prices import get_price_on_or_after, get_return_12m


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    filings = pd.read_sql("SELECT ticker, fy, filed FROM filings ORDER BY ticker, fy", conn)

    rows = []
    for _, r in filings.iterrows():
        p0 = get_price_on_or_after(r.ticker, r.filed)
        ret = get_return_12m(r.ticker, r.filed)
        rows.append({
            "ticker": r.ticker, "fy": r.fy, "filed": r.filed,
            "price_at_filing": p0["close"] if p0 else None,
            "price_date_used": p0["date"] if p0 else None,
            "return_next_12m": ret["return_12m"] if ret else None,
            "return_end_date": ret["end_date"] if ret else None,
        })
    df = pd.DataFrame(rows)
    save_table(df, "Table_Price_Coverage")

    print(f"\nTotal company-years: {len(df)}")
    print(f"Missing price_at_filing: {df['price_at_filing'].isna().sum()}")
    print(f"Missing return_next_12m: {df['return_next_12m'].isna().sum()}")

    missing_ret = df[df["return_next_12m"].isna()]
    if not missing_ret.empty:
        print("\nCompany-years with no next-12m return (expected: most recent filings "
              "with <12 months of trading history since the filing date):")
        print(missing_ret[["ticker", "fy", "filed"]].to_string(index=False))

    conn.close()


if __name__ == "__main__":
    main()
