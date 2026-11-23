from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from finchat.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies (
    ticker TEXT PRIMARY KEY,
    cik    TEXT NOT NULL,
    name   TEXT NOT NULL,
    sic    TEXT
);

CREATE TABLE IF NOT EXISTS statements (
    ticker TEXT NOT NULL,
    fy     INTEGER NOT NULL,
    metric TEXT NOT NULL,
    value  REAL,
    tag    TEXT,
    accession TEXT,
    filed  TEXT,
    PRIMARY KEY (ticker, fy, metric)
);

CREATE TABLE IF NOT EXISTS ratios (
    ticker TEXT NOT NULL,
    fy     INTEGER NOT NULL,
    metric TEXT NOT NULL,
    value  REAL,
    PRIMARY KEY (ticker, fy, metric)
);

CREATE TABLE IF NOT EXISTS quarterly_statements (
    ticker TEXT NOT NULL,
    fy     INTEGER NOT NULL,
    fq     TEXT NOT NULL,
    metric TEXT NOT NULL,
    value  REAL,
    tag    TEXT,
    accession TEXT,
    filed  TEXT,
    end_date TEXT,
    PRIMARY KEY (ticker, fy, fq, metric)
);

CREATE TABLE IF NOT EXISTS quarterly_ratios (
    ticker TEXT NOT NULL,
    fy     INTEGER NOT NULL,
    fq     TEXT NOT NULL,
    period_type TEXT NOT NULL,
    metric TEXT NOT NULL,
    value  REAL,
    PRIMARY KEY (ticker, fy, fq, period_type, metric)
);

CREATE TABLE IF NOT EXISTS scores (
    ticker TEXT NOT NULL,
    fy     INTEGER NOT NULL,
    altman_z REAL,
    altman_zone TEXT,
    piotroski_f REAL,
    beneish_m REAL,
    beneish_flag TEXT,
    components_json TEXT,
    missing_json TEXT,
    PRIMARY KEY (ticker, fy)
);

CREATE TABLE IF NOT EXISTS peer_ranks (
    ticker TEXT NOT NULL,
    fy     INTEGER NOT NULL,
    metric TEXT NOT NULL,
    rank   INTEGER,
    n      INTEGER,
    percentile REAL,
    PRIMARY KEY (ticker, fy, metric)
);

CREATE TABLE IF NOT EXISTS filings (
    ticker TEXT NOT NULL,
    fy     INTEGER NOT NULL,
    form   TEXT,
    accession TEXT,
    filed  TEXT,
    url    TEXT,
    mda_chars INTEGER,
    risk_chars INTEGER,
    PRIMARY KEY (ticker, fy)
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    fy     INTEGER NOT NULL,
    section TEXT NOT NULL,
    idx    INTEGER NOT NULL,
    text   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_ticker ON chunks(ticker);
CREATE TABLE IF NOT EXISTS textstats (
    ticker TEXT NOT NULL,
    fy     INTEGER NOT NULL,
    section TEXT NOT NULL,
    n_words INTEGER,
    neg_frac REAL,
    pos_frac REAL,
    polarity REAL,
    redflags_json TEXT,
    PRIMARY KEY (ticker, fy, section)
);

CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    close  REAL,
    adj_close REAL,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS mispricing (
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    sub_industry TEXT,
    quality_score REAL,
    profitability REAL,
    growth REAL,
    safety REAL,
    earnings_quality REAL,
    ev_sales REAL,
    expected_ev_sales REAL,
    valuation_gap REAL,
    gap_z REAL,
    verdict TEXT,
    pe REAL,
    dcf_fair_value REAL,
    price_at_filing REAL,
    dcf_upside REAL,
    dcf_agreement TEXT,
    return_next_12m REAL,
    benchmark_return_next_12m REAL,
    excess_return_next_12m REAL,
    accession TEXT,
    computed_at TEXT,
    PRIMARY KEY (ticker, fiscal_year)
);

CREATE TABLE IF NOT EXISTS mispricing_wf_fit (
    fiscal_year INTEGER NOT NULL,
    sub_industry TEXT NOT NULL,
    intercept REAL,
    slope REAL,
    train_r2 REAL,
    n INTEGER,
    train_start INTEGER,
    train_end INTEGER,
    year_gap_mean REAL,
    year_gap_std REAL,
    PRIMARY KEY (fiscal_year, sub_industry)
);

CREATE TABLE IF NOT EXISTS mispricing_fit (
    fiscal_year INTEGER NOT NULL,
    sub_industry TEXT NOT NULL,
    intercept REAL,
    slope REAL,
    r2 REAL,
    p_value REAL,
    n INTEGER,
    residual_std REAL,
    PRIMARY KEY (fiscal_year, sub_industry)
);

CREATE TABLE IF NOT EXISTS mispricing_notes (
    ticker TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    note_text TEXT,
    numbers_validated INTEGER,
    model TEXT,
    generated_at TEXT,
    PRIMARY KEY (ticker, fiscal_year)
);

CREATE TABLE IF NOT EXISTS mispricing_score_outcomes (
    score TEXT NOT NULL,
    grp TEXT NOT NULL,
    n INTEGER,
    rev_growth_next_mean REAL,
    rev_growth_next_median REAL,
    ni_growth_next_mean REAL,
    ni_growth_next_median REAL,
    return_next_12m_mean REAL,
    return_next_12m_median REAL,
    excess_return_next_12m_mean REAL,
    excess_return_next_12m_median REAL,
    loss_next_mean REAL,
    loss_next_median REAL,
    computed_at TEXT,
    PRIMARY KEY (score, grp)
);
"""


def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = DB_PATH if db_path is None else db_path
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def init_db(con: sqlite3.Connection | None = None) -> None:
    own = con is None
    con = connect() if own else con
    assert con is not None
    con.executescript(SCHEMA)
    con.commit()
    if own:
        con.close()


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def upsert(con: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
    cols = ", ".join(row.keys())
    placeholders = ", ".join("?" for _ in row)
    updates = ", ".join(f"{c}=excluded.{c}" for c in row if c not in ("ticker", "fy", "metric", "chunk_id", "section"))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO UPDATE SET {updates}"
    con.execute(sql, list(row.values()))


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def load_json(text: str | None, default: Any = None) -> Any:
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default
