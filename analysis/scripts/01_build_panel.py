"""Step 4 (part 1): build the company-year panel via the shared mispricing engine."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import DATA_PROCESSED_DIR, EXTRA_TICKERS
from finchat.config import UNIVERSE
from finchat.engine.mispricing import build_panel


def main():
    tickers = list(UNIVERSE.keys()) + list(EXTRA_TICKERS.keys())
    panel = build_panel(tickers=tickers)
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_PROCESSED_DIR / "panel.parquet"
    panel.to_parquet(out, index=False)
    print(f"[saved] {out} ({panel.shape[0]} rows, {panel.shape[1]} cols)")
    print(f"Tickers: {panel['ticker'].nunique()}, FY range: {int(panel.fy.min())}-{int(panel.fy.max())}")


if __name__ == "__main__":
    main()
