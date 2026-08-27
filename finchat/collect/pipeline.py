from __future__ import annotations

import sys

from finchat.collect.edgar import Edgar
from finchat.collect.facts import collect_ticker
from finchat.config import UNIVERSE, FY_START, FY_END
from finchat.db import get_db, init_db, upsert


def collect_all(tickers: list[str] | None = None) -> dict[str, int]:
    init_db()
    tickers = tickers or list(UNIVERSE.keys())
    counts: dict[str, int] = {}
    with get_db() as con:
        for ticker in tickers:
            print(f"[collect] {ticker} ...", flush=True)
            try:
                cik, name, data = collect_ticker(ticker, None, None, FY_START, FY_END)
            except Exception as exc:
                print(f"  FAILED: {exc}", file=sys.stderr)
                counts[ticker] = 0
                continue
            upsert(con, "companies", {"ticker": ticker, "cik": cik, "name": name, "sic": ""})
            n = 0
            for fy, metrics in sorted(data.items()):
                for metric, meta in metrics.items():
                    if metric.startswith("_"):
                        continue
                    upsert(con, "statements", {
                        "ticker": ticker, "fy": fy, "metric": metric,
                        "value": meta["value"], "tag": meta["tag"],
                        "accession": meta.get("accession") or "", "filed": meta.get("filed", ""),
                    })
                    n += 1
            counts[ticker] = len(data)
            print(f"  {n} line items across {len(data)} fiscal years")
    return counts


if __name__ == "__main__":
    args = sys.argv[1:]
    collect_all(args or None)
