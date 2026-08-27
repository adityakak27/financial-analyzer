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
}


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {"error": f"Unknown tool {name}"}
    try:
        return impl(args)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
