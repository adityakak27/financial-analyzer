"""Point-in-time share price lookups for the Mispricing Radar.

Market prices are not in SEC filings, so this module is the one place that reaches out
to an external market-data source (yfinance). Results are cached in the `prices` SQLite
table so the running app never calls the network at request time -- only the batch
`python -m finchat prices` step does.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from finchat.db import get_db, init_db, upsert

_MAX_LOOKAHEAD_DAYS = 7  # "first trading day on or after" tolerance; never reach past this into the future


def _parse_date(d: str) -> dt.date:
    return dt.datetime.strptime(d[:10], "%Y-%m-%d").date()


def fetch_and_cache_history(ticker: str, start: str, end: str) -> int:
    """Download daily close/adj-close for [start, end] via yfinance and cache it. Returns rows cached."""
    try:
        import yfinance as yf
    except Exception:
        return 0
    try:
        hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    except Exception:
        return 0
    if hist is None or hist.empty:
        return 0
    init_db()
    n = 0
    with get_db() as con:
        for idx, row in hist.iterrows():
            date_str = idx.strftime("%Y-%m-%d")
            close = row.get("Close")
            adj_close = row.get("Adj Close", close)
            if close is None:
                continue
            upsert(con, "prices", {
                "ticker": ticker,
                "date": date_str,
                "close": float(close),
                "adj_close": float(adj_close) if adj_close is not None else float(close),
            })
            n += 1
    _ROWS_CACHE.clear()
    return n


def _cached_prices(con, ticker: str) -> list[tuple[str, float, float]]:
    rows = con.execute(
        "SELECT date, close, adj_close FROM prices WHERE ticker = ? ORDER BY date ASC",
        (ticker,),
    ).fetchall()
    return [(r["date"], r["close"], r["adj_close"]) for r in rows]


_ROWS_CACHE: dict[tuple[str, str], list[tuple[str, float, float]]] = {}


def _rows_for(ticker: str) -> list[tuple[str, float, float]]:
    import finchat.db as db_mod

    key = (str(db_mod.DB_PATH), ticker)
    if key not in _ROWS_CACHE:
        init_db()
        with get_db() as con:
            _ROWS_CACHE[key] = _cached_prices(con, ticker)
    return _ROWS_CACHE[key]


def get_price_on_or_after(ticker: str, date_str: str) -> dict[str, Any] | None:
    """First cached trading day on or after date_str (within _MAX_LOOKAHEAD_DAYS). Cache-only; no network."""
    target = _parse_date(date_str)
    rows = _rows_for(ticker)
    for d, close, adj_close in rows:
        pd = _parse_date(d)
        if pd >= target and (pd - target).days <= _MAX_LOOKAHEAD_DAYS:
            return {"date": d, "close": close, "adj_close": adj_close}
    return None


def get_return_12m(ticker: str, date_str: str) -> dict[str, Any] | None:
    """Total return (using adj_close) from date_str to ~12 months later. Cache-only; no network."""
    start = get_price_on_or_after(ticker, date_str)
    if start is None:
        return None
    target_end = _parse_date(date_str) + dt.timedelta(days=365)
    end = get_price_on_or_after(ticker, target_end.isoformat())
    if end is None or not start["adj_close"]:
        return None
    ret = (end["adj_close"] - start["adj_close"]) / start["adj_close"]
    return {"start_date": start["date"], "end_date": end["date"], "return_12m": ret}


BENCHMARK_TICKER = "XLK"  # Technology Select Sector SPDR -- the sector benchmark for excess returns


def get_excess_return_12m(ticker: str, date_str: str, benchmark: str = BENCHMARK_TICKER) -> dict[str, Any] | None:
    """Stock's 12-month total return minus the benchmark's total return over the SAME start and
    end trading days. Cache-only; no network. None if either leg is missing."""
    stock = get_return_12m(ticker, date_str)
    if stock is None:
        return None
    b_start = get_price_on_or_after(benchmark, stock["start_date"])
    b_end = get_price_on_or_after(benchmark, stock["end_date"])
    if b_start is None or b_end is None or not b_start["adj_close"]:
        return None
    bench = (b_end["adj_close"] - b_start["adj_close"]) / b_start["adj_close"]
    return {**stock, "benchmark": benchmark, "benchmark_return_12m": bench,
            "excess_return_12m": stock["return_12m"] - bench}


def build_price_cache(filings: list[dict[str, Any]]) -> dict[str, int]:
    """For each (ticker, filed) in `filings`, download+cache enough history to cover
    [filed, filed + 13 months]. One yfinance call per ticker covering its full span."""
    by_ticker: dict[str, list[str]] = {}
    for f in filings:
        by_ticker.setdefault(f["ticker"], []).append(f["filed"])

    counts: dict[str, int] = {}
    for ticker, dates in by_ticker.items():
        dates = sorted(d for d in dates if d)
        if not dates:
            counts[ticker] = 0
            continue
        start = (_parse_date(dates[0]) - dt.timedelta(days=5)).isoformat()
        end = (_parse_date(dates[-1]) + dt.timedelta(days=400)).isoformat()
        today = dt.date.today().isoformat()
        end = min(end, today)
        n = fetch_and_cache_history(ticker, start, end)
        counts[ticker] = n
        print(f"[prices] {ticker}: cached {n} trading days ({start} -> {end})")

    all_dates = sorted(f["filed"] for f in filings if f.get("filed"))
    if all_dates:
        start = (_parse_date(all_dates[0]) - dt.timedelta(days=5)).isoformat()
        end = min((_parse_date(all_dates[-1]) + dt.timedelta(days=400)).isoformat(), dt.date.today().isoformat())
        n = fetch_and_cache_history(BENCHMARK_TICKER, start, end)
        counts[BENCHMARK_TICKER] = n
        print(f"[prices] {BENCHMARK_TICKER} (benchmark): cached {n} trading days ({start} -> {end})")
    return counts
