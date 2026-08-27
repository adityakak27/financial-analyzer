from __future__ import annotations

import math

import numpy as np
import pandas as pd


def peer_percentiles(ratios_df: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    rows = []
    for (fy, metric), grp in ratios_df.groupby(["fy", "metric"]):
        vals = grp["value"].astype(float)
        valid = vals.dropna()
        if len(valid) < 3:
            continue
        for _, row in grp.iterrows():
            v = row["value"]
            if v is None or (isinstance(v, float) and math.isnan(v)):
                pct = np.nan
                rank = None
            else:
                rank = int((valid > v).sum()) + 1
                pct = float((valid <= v).mean() * 100)
            rows.append({"ticker": row["ticker"], "fy": fy, "metric": metric,
                         "rank": rank, "n": len(valid), "percentile": pct})
    return pd.DataFrame(rows)


def higher_is_better(metric: str) -> bool:
    lower_better = {"debt_to_equity", "debt_to_assets", "liabilities_to_assets",
                    "receivable_days", "sga_intensity", "beneish_m"}
    if metric in lower_better:
        return False
    return True
