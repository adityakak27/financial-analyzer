"""Step 4 (part 3): EV/Sales, P/E, DCF fair value and DCF upside. Table 2."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import DATA_PROCESSED_DIR
from analysis.utils import save_table
from finchat.engine.mispricing import valuation


def main():
    panel = pd.read_parquet(DATA_PROCESSED_DIR / "panel.parquet")
    panel = valuation(panel, run_dcf=True)
    panel.to_parquet(DATA_PROCESSED_DIR / "panel.parquet", index=False)

    latest_fy = int(panel.fy.max())
    latest = panel[panel.fy == latest_fy].dropna(subset=["ev_sales"])
    top15 = latest.sort_values("ev_sales", ascending=False).head(15)[
        ["ticker", "fy", "ev_sales", "QualityScore"]
    ]
    print(f"\n=== Table 2: Top 15 most expensive by EV/Sales (FY{latest_fy}) ===")
    print(top15.to_string(index=False))
    save_table(top15, "Table2_Top_EV_Sales")

    print("\n=== Coverage ===")
    print(f"ev_sales:       {panel['ev_sales'].notna().sum()} / {len(panel)}")
    print(f"pe:             {panel['pe'].notna().sum()} / {len(panel)} (NaN when losses, as designed)")
    print(f"dcf_fair_value: {panel['dcf_fair_value'].notna().sum()} / {len(panel)}")
    print(f"dcf_upside:     {panel['dcf_upside'].notna().sum()} / {len(panel)}")

    missing_ev = panel[panel["ev_sales"].isna()][["ticker", "fy"]]
    if not missing_ev.empty:
        print("\nMissing ev_sales:")
        print(missing_ev.to_string(index=False))


if __name__ == "__main__":
    main()
