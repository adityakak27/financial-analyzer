from __future__ import annotations

import re
from typing import Any

from finchat.db import get_db, load_json

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_ratio",
            "description": "Get a computed financial ratio or valuation multiple for one company and fiscal year. "
                           "Use this for ANY numeric question about ratios, margins, returns, growth, liquidity, leverage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Company ticker, e.g. AAPL"},
                    "metric": {"type": "string",
                               "examples": ["roe", "net_margin", "gross_margin", "operating_margin",
                                            "current_ratio", "debt_to_equity", "revenue_growth_pct",
                                            "asset_turnover", "fcf_margin", "rd_intensity"],
                               "description": "Ratio metric name"},
                    "year": {"type": "integer", "description": "Fiscal year label, e.g. 2023"},
                },
                "required": ["ticker", "metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_metric_history",
            "description": "Get historical trend data (multi-year or multi-quarter) for a financial metric, ratio, or score. "
                           "Supports annual (10-K), quarterly (10-Q), and Trailing Twelve Months (TTM) time granularities. "
                           "Use this for ANY question asking about trends, history, quarterly progressions, or charts/graphs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Company ticker, e.g. AAPL"},
                    "metric": {"type": "string", "description": "Ratio or line item name, e.g. gross_margin, roe, revenue, altman_z"},
                    "start_year": {"type": "integer", "description": "Start fiscal year (default 2018)"},
                    "end_year": {"type": "integer", "description": "End fiscal year (default 2026)"},
                    "period_type": {
                        "type": "string",
                        "enum": ["annual", "quarterly", "ttm"],
                        "description": "Time granularity: 'annual' (default 10-K), 'quarterly' (discrete Form 10-Q quarters), or 'ttm' (Trailing Twelve Months rolling)",
                    },
                },
                "required": ["ticker", "metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_companies",
            "description": "Perform an in-depth head-to-head financial comparison (duel/scorecard) between two companies for a fiscal year. "
                           "Compares profitability margins, solvency/distress risk, accounting quality, and growth.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker_a": {"type": "string", "description": "First company ticker, e.g. AAPL"},
                    "ticker_b": {"type": "string", "description": "Second company ticker, e.g. MSFT"},
                    "year": {"type": "integer", "description": "Fiscal year to compare (optional, defaults to latest overlapping year)"},
                },
                "required": ["ticker_a", "ticker_b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_scores",
            "description": "Get Altman Z-Score, Piotroski F-Score and Beneish M-Score (with interpretations) "
                           "for one company-year. Use for distress/manipulation/quality score questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "year": {"type": "integer"},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_line_items",
            "description": "Get raw normalized financial statement line items (revenue, net income, assets, "
                           "equity, cash, debt, CFO, capex, ...) for one company-year.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "year": {"type": "integer"},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_peer_ranking",
            "description": "Get a company's rank/percentile among sector peers for a metric in a fiscal year.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "metric": {"type": "string"},
                    "year": {"type": "integer"},
                },
                "required": ["ticker", "metric"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_companies",
            "description": "List all covered companies with tickers and names.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_years",
            "description": "List the fiscal years of data available for a company.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_filings",
            "description": "Search the text of 10-K filings (MD&A and Risk Factors sections). Use ONLY for "
                           "qualitative questions about what management disclosed, risks, tone, outlook. "
                           "Never use this to find numbers - use get_ratio/get_scores/get_line_items instead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search phrase, e.g. 'supply chain constraints'"},
                    "ticker": {"type": "string", "description": "Optional ticker filter"},
                    "section": {"type": "string", "enum": ["mda", "risk"], "description": "Optional section filter"},
                    "year": {"type": "integer", "description": "Preferred fiscal year (closest matches returned)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_text_sentiment",
            "description": "Get finance-specific sentiment (Loughran-McDonald style negative/positive word shares) "
                           "and red-flag counts for one company-year's MD&A and/or Risk Factors text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "year": {"type": "integer"},
                    "section": {"type": "string", "enum": ["mda", "risk"]},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_dcf_valuation",
            "description": "Run an interactive Discounted Cash Flow (DCF) model and sensitivity analysis for a company. "
                           "Calculates projected Free Cash Flows, Gordon Growth terminal value, enterprise value, "
                           "bridge to equity value, implied intrinsic share price, and WACC vs Terminal Growth sensitivity matrix.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Company ticker, e.g. AAPL"},
                    "wacc": {"type": "number", "description": "Weighted average cost of capital / discount rate (e.g. 0.09 for 9.0%)"},
                    "terminal_growth": {"type": "number", "description": "Perpetual terminal growth rate (e.g. 0.025 for 2.5%)"},
                    "forecast_years": {"type": "integer", "description": "Discrete forecast horizon in years (default 5)"},
                    "custom_growth_rate": {"type": "number", "description": "Optional custom FCF growth rate override (e.g. 0.08 for 8.0%)"},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_equity_research",
            "description": "Trigger the collaborative 4-Agent Equity Research Panel (Valuation Specialist, Forensic Auditor, "
                           "Strategic Analyst, and Research Director) to generate an institutional-grade Initiation of Coverage Report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Company ticker, e.g. AAPL or MSFT"},
                    "year": {"type": "integer", "description": "Fiscal year to analyze (defaults to latest available)"},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_valuation_check",
            "description": "Mispricing Radar: get a company's Fundamental Quality Score (0-100, with its 4 pillars), "
                           "its EV/Sales versus the quality-implied (expected) EV/Sales, the valuation gap and verdict "
                           "(Undervalued / Fairly valued / Overvalued), whether the DCF model agrees, and the "
                           "pre-written analyst note. Use this for ANY question about whether a company looks "
                           "over/undervalued for its fundamentals, or 'cheap'/'expensive' relative to quality.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Company ticker, e.g. NVDA"},
                    "year": {"type": "integer", "description": "Fiscal year (defaults to latest available)"},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_mispriced",
            "description": "Mispricing Radar: leaderboard of companies that look most undervalued or most overvalued "
                           "for their fundamental quality in a given fiscal year, optionally filtered to one "
                           "sub-industry. Use this for questions like 'which tech companies look cheapest' or "
                           "'what looks overvalued right now'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Fiscal year (defaults to latest available)"},
                    "direction": {"type": "string", "enum": ["under", "over"],
                                  "description": "'under' for undervalued/cheapest, 'over' for overvalued/most expensive"},
                    "sub_industry": {"type": "string",
                                      "enum": ["Semiconductors", "Software & Services", "Hardware & Equipment"],
                                      "description": "Optional sub-industry filter"},
                    "limit": {"type": "integer", "description": "Max companies to return (default 10)"},
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_score_effectiveness",
            "description": "Mispricing Radar (RQ3): did companies with a high/safe/clean Piotroski F, Altman Z, or "
                           "Beneish M score actually go on to post better next-year revenue growth, net income "
                           "growth, and stock return than companies with poor scores? Returns the grouped outcomes "
                           "with sample sizes and significance tests. Use this for 'do high Piotroski scores lead "
                           "to better returns' type questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "score": {"type": "string", "enum": ["piotroski", "altman", "beneish"],
                              "description": "Which risk/forensic score to evaluate"},
                },
                "required": ["score"],
            },
        },
    },
]

PERCENT_METRICS = {"revenue_growth_pct", "net_income_growth_pct"}
FRACTION_PCT_METRICS = {"gross_margin", "operating_margin", "net_margin", "roe", "roa", "roic",
                        "fcf_margin", "rd_intensity", "sga_intensity", "working_capital_ratio",
                        "earnings_yield"}
SCORE_METRICS = {"altman_z", "piotroski_f", "beneish_m"}


METRIC_ALIASES: dict[str, str] = {}
for canonical in ["roe", "return on equity"]:
    METRIC_ALIASES[canonical] = "roe"
for k, v in {
    "roa": "roa", "return on assets": "roa",
    "roic": "roic",
    "net margin": "net_margin", "profit margin": "net_margin", "net profit margin": "net_margin",
    "gross margin": "gross_margin",
    "operating margin": "operating_margin",
    "current ratio": "current_ratio",
    "quick ratio": "quick_ratio", "acid test": "quick_ratio", "cash ratio": "cash_ratio",
    "debt to equity": "debt_to_equity", "d/e": "debt_to_equity",
    "debt to assets": "debt_to_assets",
    "asset turnover": "asset_turnover",
    "inventory turnover": "inventory_turnover",
    "receivable days": "receivable_days", "days sales outstanding": "receivable_days",
    "interest coverage": "interest_coverage",
    "free cash flow margin": "fcf_margin",
    "rd intensity": "rd_intensity", "r&d intensity": "rd_intensity", "research and development intensity": "rd_intensity",
    "revenue growth": "revenue_growth_pct", "sales growth": "revenue_growth_pct",
    "net income growth": "net_income_growth_pct", "earnings growth": "net_income_growth_pct",
    "altman z": "altman_z", "z score": "altman_z", "altman z-score": "altman_z", "zscore": "altman_z",
    "piotroski": "piotroski_f", "f score": "piotroski_f", "piotroski f-score": "piotoski_f",
    "beneish": "beneish_m", "m score": "beneish_m", "beneish m-score": "beneish_m",
}.items():
    METRIC_ALIASES[k] = v
METRIC_ALIASES["piotroski f-score"] = "piotroski_f"


def format_metric_value(metric: str, value: float | None) -> str:
    if value is None:
        return "not available"
    if metric in SCORE_METRICS:
        return f"{value:.2f}"
    if metric in FRACTION_PCT_METRICS:
        pct = value * 100
        return f"{pct:.2f}%" if abs(pct) < 20 else f"{pct:.1f}%"
    if metric in PERCENT_METRICS:
        return f"{value:.2f}%" if abs(value) < 20 else f"{value:.1f}%"
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    return f"{value:.2f}"


def _resolve_metric(metric: str) -> str:
    key = re.sub(r"\s+", " ", (metric or "").strip().lower().replace("-", " ").replace("_", " "))
    return METRIC_ALIASES.get(key, (metric or "").strip().lower())


def get_available_years(con, ticker: str | None = None) -> list[int]:
    q = "SELECT DISTINCT fy FROM statements"
    params: list = []
    if ticker:
        q += " WHERE ticker=?"
        params.append(ticker)
    rows = con.execute(q + " ORDER BY fy", params).fetchall()
    return sorted(int(r["fy"]) for r in rows)


def tool_get_ratio(ticker: str, metric: str, year: int | None = None) -> dict[str, Any]:
    metric = _resolve_metric(metric)
    ticker = (ticker or "").upper().strip()
    with get_db() as con:
        years = get_available_years(con, ticker)
        if not years:
            return {"error": f"No data for {ticker}", "covered_companies_hint": "call list_companies"}
        if year is None:
            year = years[-1]
        if metric.startswith("valuation_"):
            row = con.execute("SELECT value FROM ratios WHERE ticker=? AND fy=? AND metric=?",
                              (ticker, year, metric)).fetchone()
        elif metric in SCORE_METRICS:
            return tool_get_scores(ticker, year, focus=metric)
        else:
            row = con.execute("SELECT value FROM ratios WHERE ticker=? AND fy=? AND metric=?",
                              (ticker, year, metric)).fetchone()
        meta = con.execute(
            "SELECT s.tag, s.accession FROM statements s JOIN filings f ON f.ticker=s.ticker AND f.fy=s.fy "
            "WHERE s.ticker=? AND s.fy=? LIMIT 1", (ticker, year)).fetchone()
        peer = con.execute("SELECT rank, n, percentile FROM peer_ranks WHERE ticker=? AND fy=? AND metric=?",
                           (ticker, year, metric)).fetchone() if metric not in SCORE_METRICS else None
        prev_row = con.execute("SELECT value FROM ratios WHERE ticker=? AND fy=? AND metric=?",
                               (ticker, year - 1, metric)).fetchone()

    result: dict[str, Any] = {
        "ticker": ticker, "metric": metric, "year": year,
        "value": row["value"] if row else None,
        "formatted": format_metric_value(metric, row["value"] if row else None),
        "prior_year": year - 1,
        "prior_year_value": prev_row["value"] if prev_row else None,
        "prior_year_formatted": format_metric_value(metric, prev_row["value"] if prev_row else None),
        "peer_rank": dict(peer) if peer else None,
        "source": {"type": "structured_lookup",
                   "table": "ratios (computed from XBRL statements)",
                   "accession": meta["accession"] if meta else None},
    }
    if metric in FRACTION_PCT_METRICS and row and row["value"] is not None:
        result["unit_note"] = ("stored as a fraction of revenue/equity/assets; "
                               f"'formatted' shows it in percent ({row['value'] * 100:.1f}%)")
    if metric in FRACTION_PCT_METRICS and prev_row:
        result["prior_year_value_as_percent"] = prev_row["value"] * 100
    if metric in FRACTION_PCT_METRICS and row and row["value"] is not None:
        result["value_as_percent"] = row["value"] * 100
    if row is None:
        result["note"] = f"No value for {metric} FY{year}; available years: {years}"
    return result


def tool_get_metric_history(
    ticker: str,
    metric: str,
    start_year: int = 2018,
    end_year: int = 2026,
    period_type: str = "annual",
) -> dict[str, Any]:
    metric = _resolve_metric(metric)
    ticker = (ticker or "").upper().strip()

    if (period_type or "").lower().strip() in ("quarterly", "ttm"):
        from finchat.engine.quarterly import get_quarterly_metric_series

        q_res = get_quarterly_metric_series(ticker, metric, period_type.lower().strip())
        series = q_res.get("series", [])
        if series:
            q_res["year_range"] = f"{series[0]['period']}–{series[-1]['period']}"
            q_res["source"] = {
                "type": "structured_lookup",
                "table": f"quarterly_{'ratios' if period_type.lower().strip() == 'ttm' else 'statements/ratios'} (SEC Form 10-Q)",
                "ticker": ticker,
            }
            return q_res

    with get_db() as con:
        years = get_available_years(con, ticker)
        if not years:
            return {"error": f"No data for {ticker}", "covered_companies_hint": "call list_companies"}

        source_table = "ratios"
        # 1. Look in ratios table
        rows = con.execute(
            "SELECT fy, value FROM ratios WHERE ticker=? AND metric=? AND fy BETWEEN ? AND ? ORDER BY fy ASC",
            (ticker, metric, start_year, end_year),
        ).fetchall()

        # 2. Look in statements table (e.g. revenue, net_income, cash, etc.)
        if not rows:
            source_table = "statements"
            rows = con.execute(
                "SELECT fy, value FROM statements WHERE ticker=? AND metric=? AND fy BETWEEN ? AND ? ORDER BY fy ASC",
                (ticker, metric, start_year, end_year),
            ).fetchall()

        # 3. Look in scores table (altman_z, piotroski_f, beneish_m)
        if not rows and metric in SCORE_METRICS:
            source_table = "scores"
            col_map = {"altman_z": "altman_z", "piotroski_f": "piotroski_f", "beneish_m": "beneish_m"}
            col = col_map[metric]
            rows = con.execute(
                f"SELECT fy, {col} AS value FROM scores WHERE ticker=? AND fy BETWEEN ? AND ? ORDER BY fy ASC",
                (ticker, start_year, end_year),
            ).fetchall()

        series = []
        for r in rows:
            val = r["value"]
            if val is not None:
                series.append({
                    "year": int(r["fy"]),
                    "value": float(val),
                    "formatted": format_metric_value(metric, float(val)),
                })

        is_pct = metric in FRACTION_PCT_METRICS or metric in PERCENT_METRICS
        year_span = f"FY{series[0]['year']}–FY{series[-1]['year']}" if series else f"FY{start_year}–FY{end_year}"
        return {
            "ticker": ticker,
            "metric": metric,
            "start_year": start_year,
            "end_year": end_year,
            "year_range": year_span,
            "series": series,
            "is_percentage": is_pct,
            "source": {"type": "structured_lookup", "table": f"{source_table} database", "ticker": ticker},
        }


def tool_get_scores(ticker: str, year: int | None = None, focus: str | None = None) -> dict[str, Any]:
    ticker = (ticker or "").upper().strip()
    with get_db() as con:
        years = get_available_years(con, ticker)
        if not years:
            return {"error": f"No data for {ticker}"}
        if year is None:
            year = years[-1]
        row = con.execute("SELECT * FROM scores WHERE ticker=? AND fy=?", (ticker, year)).fetchone()
        prev = con.execute("SELECT altman_z, piotroski_f, beneish_m FROM scores WHERE ticker=? AND fy=?",
                           (ticker, year - 1)).fetchone()
    if row is None:
        return {"ticker": ticker, "year": year, "error": f"No score row for FY{year}",
                "available_years": years}
    out = {
        "ticker": ticker,
        "year": int(row["fy"]),
        "altman_z": {"value": row["altman_z"], "zone": row["altman_zone"],
                     "interpretation": interpret_altman(row["altman_zone"]),
                     "prior_year_value": prev["altman_z"] if prev else None},
        "piotroski_f": {"value": row["piotroski_f"], "scale": "0-9, higher = stronger fundamentals",
                        "interpretation": interpret_piotroski(row["piotroski_f"]),
                        "prior_year_value": prev["piotroski_f"] if prev else None},
        "beneish_m": {"value": row["beneish_m"], "flag": row["beneish_flag"],
                      "interpretation": interpret_beneish(row["beneish_m"]),
                      "prior_year_value": prev["beneish_m"] if prev else None},
        "missing_inputs": load_json(row["missing_json"]),
        "source": {"type": "structured_lookup", "table": "scores",
                   "models": "Altman (1968); Piotroski (2000); Beneish (1999)"},
    }
    if focus:
        out["requested_focus"] = focus
    return out


def interpret_altman(zone: str | None) -> str:
    return {
        "safe": "Z > 3.0 historically associated with low near-term bankruptcy risk ('safe' zone).",
        "grey": "1.81 < Z < 3.0 is the 'grey zone': neither clearly safe nor distressed.",
        "distress": "Z < 1.81 historically associated with elevated distress risk ('distress' zone).",
    }.get(zone or "", "Zone unavailable (insufficient inputs).")


def interpret_piotroski(v: float | None) -> str:
    if v is None:
        return "Not computable."
    if v >= 7:
        return "Strong fundamental quality (7-9)."
    if v >= 4:
        return "Moderate fundamental quality (4-6)."
    return "Weak fundamentals per Piotroski criteria (0-3)."


def interpret_beneish(m: float | None) -> str:
    if m is None:
        return "Not computable."
    if m > -1.78:
        return "M > -1.78 falls in the range Beneish associated with higher probability of earnings manipulation."
    return "M <= -1.78 suggests the sample-level manipulation profile is less likely."


def tool_get_line_items(ticker: str, year: int | None = None) -> dict[str, Any]:
    ticker = (ticker or "").upper().strip()
    with get_db() as con:
        years = get_available_years(con, ticker)
        if not years:
            return {"error": f"No data for {ticker}"}
        if year is None:
            year = years[-1]
        rows = con.execute("SELECT metric, value, tag, accession FROM statements WHERE ticker=? AND fy=?",
                           (ticker, year)).fetchall()
    items = {r["metric"]: {"value": r["value"], "tag": r["tag"]} for r in rows}
    return {"ticker": ticker, "year": year, "items": items, "count": len(items),
            "source": {"type": "structured_lookup", "table": "statements (SEC XBRL company facts, form 10-K)"}}


def tool_get_peer_ranking(ticker: str, metric: str, year: int | None = None) -> dict[str, Any]:
    metric = _resolve_metric(metric)
    ticker = (ticker or "").upper().strip()
    with get_db() as con:
        years = get_available_years(con, ticker)
        if not years:
            return {"error": f"No data for {ticker}"}
        if year is None:
            year = years[-1]
        row = con.execute("SELECT rank, n, percentile FROM peer_ranks WHERE ticker=? AND fy=? AND metric=?",
                          (ticker, year, metric)).fetchone()
        peers = con.execute(
            "SELECT p.ticker, p.rank, p.percentile FROM peer_ranks p WHERE p.fy=? AND p.metric=? ORDER BY p.rank",
            (year, metric)).fetchall()
    return {
        "ticker": ticker, "metric": metric, "year": year,
        "rank": row["rank"] if row else None,
        "n_peers": row["n"] if row else None,
        "percentile": row["percentile"] if row else None,
        "full_ranking": [{"ticker": r["ticker"], "rank": r["rank"], "percentile": round(r["percentile"], 1)}
                         for r in peers],
        "source": {"type": "structured_lookup", "table": "peer_ranks"},
    }


def tool_list_companies() -> dict[str, Any]:
    with get_db() as con:
        rows = con.execute("SELECT ticker, name FROM companies ORDER BY ticker").fetchall()
        counts = {r["ticker"]: r["n"] for r in con.execute(
            "SELECT ticker, COUNT(DISTINCT fy) AS n FROM statements GROUP BY ticker").fetchall()}
    return {"companies": [{"ticker": r["ticker"], "name": r["name"], "years_covered": counts.get(r["ticker"], 0)}
                          for r in rows]}


def tool_list_years(ticker: str) -> dict[str, Any]:
    ticker = (ticker or "").upper().strip()
    with get_db() as con:
        years = get_available_years(con, ticker)
        fil = con.execute("SELECT fy, filed, accession FROM filings WHERE ticker=? ORDER BY fy", (ticker,)).fetchall()
    return {"ticker": ticker, "years": years,
            "filings": [{"fy": int(r["fy"]), "filed": r["filed"], "accession": r["accession"]} for r in fil]}


def tool_search_filings(query: str, ticker: str | None = None, section: str | None = None,
                        year: int | None = None, k: int = 4) -> dict[str, Any]:
    from finchat.nlp.index import get_retriever
    from finchat.config import RETRIEVAL_TOP_K

    retriever = get_retriever()
    k = k or RETRIEVAL_TOP_K
    passages = retriever.search(query, k=k, ticker=ticker, section=section, fy=year)
    if not passages and (section or year is not None):
        passages = retriever.search(query, k=k, ticker=ticker, section=None, fy=None)
    if not passages:
        passages = retriever.search(query, k=k, ticker=None, section=None, fy=None)
    out_passages = []
    for p in passages:
        url = _chunk_url(p.ticker, p.fy)
        out_passages.append({
            "ticker": p.ticker, "year": p.fy, "section": p.section, "chunk_id": p.chunk_id,
            "score": round(p.score, 4),
            "excerpt": p.text[:700],
            "citation_url": url,
        })
    return {"query": query, "results": out_passages, "n_results": len(out_passages),
            "source": {"type": "vector_search_tfidf", "corpus": "10-K MD&A / Risk Factors chunks"}}


def _chunk_url(ticker: str, fy: int) -> str | None:
    with get_db() as con:
        row = con.execute("SELECT url FROM filings WHERE ticker=? AND fy=?", (ticker, fy)).fetchone()
    return row["url"] if row else None


def tool_get_text_sentiment(ticker: str, year: int | None = None, section: str | None = None) -> dict[str, Any]:
    ticker = (ticker or "").upper().strip()
    with get_db() as con:
        years = get_available_years(con, ticker)
        if not years:
            return {"error": f"No data for {ticker}"}
        if year is None:
            year = years[-1]
        q = "SELECT * FROM textstats WHERE ticker=? AND fy=?"
        params: list = [ticker, year]
        if section:
            q += " AND section=?"
            params.append(section)
        rows = con.execute(q, params).fetchall()
    out = []
    for r in rows:
        out.append({
            "section": r["section"], "n_words": r["n_words"],
            "negative_word_share_pct": round((r["neg_frac"] or 0) * 100, 2),
            "positive_word_share_pct": round((r["pos_frac"] or 0) * 100, 2),
            "polarity": r["polarity"],
            "red_flags": load_json(r["redflags_json"], {}),
        })
    return {"ticker": ticker, "year": year, "sections": out,
            "lexicon_note": "Loughran-McDonald-style lexicon (full lexicon if provided, compact fallback otherwise)",
            "source": {"type": "structured_lookup", "table": "textstats"}}


def tool_compare_companies(ticker_a: str, ticker_b: str, year: int | None = None) -> dict[str, Any]:
    from finchat.engine.duel import compare_companies

    return compare_companies(ticker_a, ticker_b, year)


def tool_run_dcf_valuation(
    ticker: str,
    wacc: float = 0.09,
    terminal_growth: float = 0.025,
    forecast_years: int = 5,
    custom_growth_rate: float | None = None,
) -> dict[str, Any]:
    from finchat.engine.dcf import calculate_dcf

    res = calculate_dcf(
        ticker,
        wacc=wacc,
        terminal_growth=terminal_growth,
        forecast_years=forecast_years,
        custom_growth_rate=custom_growth_rate,
    )
    res["source"] = {"type": "structured_lookup", "table": "dcf_valuation_engine"}
    return res


def tool_generate_equity_research(ticker: str, year: int | None = None) -> dict[str, Any]:
    from finchat.engine.research_agents import ResearchDirector

    rd = ResearchDirector()
    res = rd.generate_initiation_report(ticker, year=year)
    res["source"] = {"type": "structured_lookup", "table": "equity_research_panel"}
    return res


def tool_get_valuation_check(ticker: str, year: int | None = None) -> dict[str, Any]:
    from finchat.engine.mispricing import (latest_mispricing_year, load_fit, load_mispricing_rows,
                                            load_note, load_wf_fit)

    ticker = (ticker or "").upper().strip()
    if year is None:
        year = latest_mispricing_year()
    rows = load_mispricing_rows(year=year)
    row = next((r for r in rows if r["ticker"] == ticker), None)
    if row is None:
        return {"error": f"No Mispricing Radar data for {ticker} in FY{year}. "
                          f"Run 'python -m finchat mispricing' if the Radar hasn't been built yet."}

    peers_in_year = [r for r in rows if r.get("gap_z") is not None]
    peers_sorted = sorted(peers_in_year, key=lambda r: r["gap_z"])
    percentile = None
    if row.get("gap_z") is not None and peers_sorted:
        rank = sum(1 for r in peers_sorted if r["gap_z"] <= row["gap_z"])
        percentile = round(100 * rank / len(peers_sorted), 1)

    same_year = load_fit(year, sub_industry="ALL")
    wf = load_wf_fit(year, row.get("sub_industry") or "")
    note = load_note(ticker, year)
    has_model = bool(wf and wf.get("slope") is not None)

    return {
        "ticker": ticker, "fiscal_year": year, "sub_industry": row.get("sub_industry"),
        "quality_score": row.get("quality_score"),
        "pillars": {
            "profitability": row.get("profitability"), "growth": row.get("growth"),
            "safety": row.get("safety"), "earnings_quality": row.get("earnings_quality"),
        },
        "ev_sales": row.get("ev_sales"), "expected_ev_sales": row.get("expected_ev_sales"),
        "actual_vs_expected_ev_sales_ratio": (round(row["ev_sales"] / row["expected_ev_sales"], 2)
                                               if row.get("ev_sales") and row.get("expected_ev_sales") else None),
        "valuation_gap_log_points": row.get("valuation_gap"), "gap_z": row.get("gap_z"),
        "verdict": row.get("verdict"),
        "gap_percentile_among_all_companies_this_year": percentile,
        "verdict_model": {
            "method": "walk-forward, sub-industry-relative fair-value line",
            "sub_industry": row.get("sub_industry"),
            "train_years": f"FY{wf['train_start']}-FY{wf['train_end']}" if has_model else None,
            "train_n": wf.get("n") if has_model else None,
        } if has_model else {"method": "none: no earlier fiscal years to train on"},
        "fair_value_line_r2": wf.get("train_r2") if has_model else None,
        "same_year_quality_valuation_r2": same_year.get("r2") if same_year else None,
        "dcf_fair_value": row.get("dcf_fair_value"), "dcf_upside": row.get("dcf_upside"),
        "dcf_agreement": row.get("dcf_agreement"),
        "next_12m_excess_return_vs_xlk": row.get("excess_return_next_12m"),
        "analyst_note": note.get("note_text") if note else None,
        "note_numbers_validated": bool(note.get("numbers_validated")) if note else None,
        "disclaimer": ("A valuation verdict is a statistical comparison with sub-industry peers, not a "
                       "recommendation; in back-tests the verdicts did not predict next-year returns. "
                       "Not investment advice."),
        "source": {"type": "structured_lookup", "table": "mispricing"},
    }


def tool_list_mispriced(direction: str, year: int | None = None, sub_industry: str | None = None,
                        limit: int = 10) -> dict[str, Any]:
    from finchat.engine.mispricing import latest_mispricing_year, load_fit, load_mispricing_rows

    if year is None:
        year = latest_mispricing_year()
    rows = load_mispricing_rows(year=year, sub_industry=sub_industry, direction=direction, limit=limit)
    fit = load_fit(year, sub_industry=sub_industry or "ALL")
    return {
        "fiscal_year": year, "direction": direction, "sub_industry": sub_industry,
        "verdict_method": ("each company vs its own sub-industry's fair-value line, fitted only on "
                           "earlier fiscal years (walk-forward)"),
        "same_year_quality_valuation_r2": fit.get("r2") if fit else None,
        "n_companies": len(rows),
        "companies": [
            {"ticker": r["ticker"], "name": r.get("company_name"), "quality_score": r.get("quality_score"),
             "ev_sales": r.get("ev_sales"), "valuation_gap_log_points": r.get("valuation_gap"),
             "gap_z": r.get("gap_z"),
             "verdict": r.get("verdict"), "dcf_upside": r.get("dcf_upside"),
             "dcf_agreement": r.get("dcf_agreement")}
            for r in rows
        ],
        "disclaimer": "Not investment advice.",
        "source": {"type": "structured_lookup", "table": "mispricing"},
    }


def tool_get_score_effectiveness(score: str) -> dict[str, Any]:
    from finchat.engine.mispricing import load_score_outcomes

    score = (score or "").strip().lower()
    if score not in ("piotroski", "altman", "beneish"):
        return {"error": f"Unknown score '{score}'. Use 'piotroski', 'altman' or 'beneish'."}

    rows = load_score_outcomes(score)
    if not rows:
        return {"error": f"No grouped outcomes available for {score}. "
                          f"Run 'python -m finchat mispricing' if the Radar hasn't been built yet."}

    return {
        "score": score,
        "groups": [
            {"group": r["grp"], "n": r["n"],
             "avg_next_year_revenue_growth_pct": round(r["rev_growth_next_mean"], 2) if r["rev_growth_next_mean"] is not None else None,
             "avg_next_year_net_income_growth_pct": round(r["ni_growth_next_mean"], 2) if r["ni_growth_next_mean"] is not None else None,
             "avg_next_12m_stock_return_pct": round(r["return_next_12m_mean"] * 100, 2) if r["return_next_12m_mean"] is not None else None,
             "avg_next_12m_excess_return_vs_xlk_pct": round(r["excess_return_next_12m_mean"] * 100, 2) if r["excess_return_next_12m_mean"] is not None else None,
             "loss_rate_next_year_pct": round(r["loss_next_mean"] * 100, 1) if r["loss_next_mean"] is not None else None}
            for r in rows
        ],
        "interpretation": ("Grouped comparison of next-year outcomes by score tier, not a trained predictive model. "
                           "Excess return = the stock's 12-month return minus the XLK tech ETF's over the same days. "
                           "See the Mispricing Radar study (analysis/report/results.md) for significance tests."),
        "disclaimer": "Not investment advice.",
        "source": {"type": "structured_lookup", "table": "mispricing_score_outcomes"},
    }


def tool_get_mispricing_overview(year: int | None = None, sub_industry: str | None = None) -> dict[str, Any]:
    """Backend-only bulk view for the Mispricing Radar page's scatter chart and stats strip.
    Not a chatbot tool (not in TOOL_SCHEMAS) -- reads only, never computes or calls an LLM."""
    from finchat.engine.mispricing import (latest_mispricing_year, list_sub_industries, load_fit,
                                            load_mispricing_rows, load_wf_fit)
    from finchat.db import get_db

    if year is None:
        year = latest_mispricing_year()
    with get_db() as con:
        years = sorted({int(r["fiscal_year"]) for r in con.execute("SELECT DISTINCT fiscal_year FROM mispricing").fetchall()})
    rows = load_mispricing_rows(year=year, sub_industry=sub_industry)
    fit = load_fit(year, sub_industry=sub_industry or "ALL")

    # The verdict lines: one per sub-industry, shifted by the year's mean gap so that a point lying
    # exactly on its sub-industry's line has gap z = 0 ("Fairly valued" at its centre).
    lines = []
    for sub in ([sub_industry] if sub_industry else list_sub_industries()):
        wf = load_wf_fit(year, sub)
        if wf and wf.get("slope") is not None and wf.get("year_gap_mean") is not None:
            lines.append({"sub_industry": sub, "intercept": wf["intercept"] + wf["year_gap_mean"],
                          "slope": wf["slope"], "train_start": wf["train_start"],
                          "train_end": wf["train_end"], "train_r2": wf["train_r2"]})

    return {
        "fiscal_year": year, "available_years": years, "sub_industry": sub_industry,
        "sub_industries": list_sub_industries(),
        "fit": fit,
        "verdict_lines": lines,
        "n_companies": len(rows),
        "n_with_verdict": sum(1 for r in rows if r.get("verdict") not in (None, "insufficient_data")),
        "points": [
            {"ticker": r["ticker"], "name": r.get("company_name"), "sub_industry": r.get("sub_industry"),
             "quality_score": r.get("quality_score"), "ev_sales": r.get("ev_sales"),
             "expected_ev_sales": r.get("expected_ev_sales"), "valuation_gap": r.get("valuation_gap"),
             "gap_z": r.get("gap_z"), "verdict": r.get("verdict")}
            for r in rows if r.get("quality_score") is not None and r.get("ev_sales") is not None
        ],
        "source": {"type": "structured_lookup", "table": "mispricing + mispricing_fit"},
    }


TOOL_IMPLS = {
    "get_ratio": lambda args: tool_get_ratio(args.get("ticker"), args.get("metric", ""), args.get("year")),
    "get_scores": lambda args: tool_get_scores(args.get("ticker"), args.get("year")),
    "get_line_items": lambda args: tool_get_line_items(args.get("ticker"), args.get("year")),
    "get_peer_ranking": lambda args: tool_get_peer_ranking(args.get("ticker"), args.get("metric", ""),
                                                           args.get("year")),
    "list_companies": lambda args: tool_list_companies(),
    "list_years": lambda args: tool_list_years(args.get("ticker", "")),
    "search_filings": lambda args: tool_search_filings(args.get("query", ""), args.get("ticker"),
                                                       args.get("section"), args.get("year"),
                                                       args.get("k", 4)),
    "get_text_sentiment": lambda args: tool_get_text_sentiment(args.get("ticker"), args.get("year"),
                                                               args.get("section")),
    "get_metric_history": lambda args: tool_get_metric_history(
        args.get("ticker", ""),
        args.get("metric", ""),
        args.get("start_year", 2018),
        args.get("end_year", 2026),
        args.get("period_type", "annual"),
    ),
    "compare_companies": lambda args: tool_compare_companies(
        args.get("ticker_a", ""),
        args.get("ticker_b", ""),
        args.get("year"),
    ),
    "run_dcf_valuation": lambda args: tool_run_dcf_valuation(
        args.get("ticker", ""),
        float(args.get("wacc", 0.09) or 0.09),
        float(args.get("terminal_growth", 0.025) or 0.025),
        int(args.get("forecast_years", 5) or 5),
        float(args.get("custom_growth_rate")) if args.get("custom_growth_rate") is not None else None,
    ),
    "generate_equity_research": lambda args: tool_generate_equity_research(
        args.get("ticker", ""),
        int(args["year"]) if args.get("year") else None,
    ),
    "get_valuation_check": lambda args: tool_get_valuation_check(
        args.get("ticker", ""),
        int(args["year"]) if args.get("year") else None,
    ),
    "list_mispriced": lambda args: tool_list_mispriced(
        args.get("direction", "under"),
        int(args["year"]) if args.get("year") else None,
        args.get("sub_industry"),
        int(args.get("limit", 10) or 10),
    ),
    "get_score_effectiveness": lambda args: tool_get_score_effectiveness(args.get("score", "")),
}


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {"error": f"Unknown tool {name}"}
    try:
        return impl(args)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
