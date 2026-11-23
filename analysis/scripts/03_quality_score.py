"""Step 4 (part 2): Fundamental Quality Score (0-100) + 4 pillars. Table 1."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import DATA_PROCESSED_DIR
from analysis.utils import save_table
from finchat.engine.mispricing import attach_prices, quality_score, recompute_point_in_time_altman_z


def main():
    panel = pd.read_parquet(DATA_PROCESSED_DIR / "panel.parquet")
    # attach_prices (and the point-in-time Altman Z recompute that depends on its market_cap)
    # must run BEFORE quality_score: otherwise the Safety pillar uses the `scores` table's
    # altman_z, which is computed from each ticker's CURRENT market cap reused across every
    # historical fiscal year -- e.g. NVDA FY2018 would score ~486 using NVDA's 2026 market cap.
    panel = attach_prices(panel)
    panel = recompute_point_in_time_altman_z(panel)
    panel = quality_score(panel)
    panel.to_parquet(DATA_PROCESSED_DIR / "panel.parquet", index=False)

    latest_fy = int(panel.fy.max())
    latest = panel[panel.fy == latest_fy].dropna(subset=["QualityScore"])
    top15 = latest.sort_values("QualityScore", ascending=False).head(15)[
        ["ticker", "fy", "QualityScore", "profitability_score", "growth_score",
         "safety_score", "earnings_quality_score"]
    ]
    print(f"\n=== Table 1: Top 15 by Quality Score (FY{latest_fy}) ===")
    print(top15.to_string(index=False))
    save_table(top15, "Table1_Top_Quality_Scores")

    print("\n=== Top 20 company-years overall ===")
    top20 = panel.dropna(subset=["QualityScore"]).sort_values("QualityScore", ascending=False).head(20)[
        ["ticker", "fy", "QualityScore"]
    ]
    print(top20.to_string(index=False))

    print(f"\nQualityScore missing for {panel['QualityScore'].isna().sum()} / {len(panel)} company-years")
    print(panel[panel["QualityScore"].isna()][["ticker", "fy"]].to_string(index=False))


if __name__ == "__main__":
    main()
