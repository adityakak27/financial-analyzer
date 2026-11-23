from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Make the sibling `finchat` package (lives at repo root, one level above backend/)
# importable without requiring the user to install it as a package.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from finchat.chatbot.tools import (
    tool_compare_companies,
    tool_get_line_items,
    tool_get_metric_history,
    tool_get_mispricing_overview,
    tool_get_peer_ranking,
    tool_get_ratio,
    tool_get_score_effectiveness,
    tool_get_scores,
    tool_get_text_sentiment,
    tool_get_valuation_check,
    tool_list_companies,
    tool_list_mispriced,
    tool_list_years,
    tool_run_dcf_valuation,
    tool_search_filings,
    tool_generate_equity_research,
)
from finchat.config import GEMINI_MODEL, UNIVERSE, llm_available

from app.schemas import ChatRequest, ChatResetRequest, DCFRequest, ResearchRequest
from app.sessions import store

app = FastAPI(title="FinChat Equity Research API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "llm_available": llm_available(),
        "model": GEMINI_MODEL,
        "universe_size": len(UNIVERSE),
    }


@app.get("/api/companies")
def companies() -> dict:
    return tool_list_companies()


@app.get("/api/companies/{ticker}/years")
def years(ticker: str) -> dict:
    return tool_list_years(ticker)


@app.get("/api/ratio")
def ratio(ticker: str, metric: str, year: int | None = None) -> dict:
    return tool_get_ratio(ticker, metric, year)


@app.get("/api/metric-history")
def metric_history(
    ticker: str,
    metric: str,
    start_year: int = 2018,
    end_year: int = 2026,
    period_type: str = "annual",
) -> dict:
    return tool_get_metric_history(ticker, metric, start_year, end_year, period_type)


@app.get("/api/scores")
def scores(ticker: str, year: int | None = None) -> dict:
    return tool_get_scores(ticker, year)


@app.get("/api/line-items")
def line_items(ticker: str, year: int | None = None) -> dict:
    return tool_get_line_items(ticker, year)


@app.get("/api/peer-ranking")
def peer_ranking(ticker: str, metric: str, year: int | None = None) -> dict:
    return tool_get_peer_ranking(ticker, metric, year)


@app.get("/api/compare")
def compare(ticker_a: str, ticker_b: str, year: int | None = None) -> dict:
    return tool_compare_companies(ticker_a, ticker_b, year)


@app.get("/api/search-filings")
def search_filings(query: str, ticker: str | None = None, section: str | None = None, year: int | None = None) -> dict:
    return tool_search_filings(query, ticker, section, year)


@app.get("/api/text-sentiment")
def text_sentiment(ticker: str, year: int | None = None, section: str | None = None) -> dict:
    return tool_get_text_sentiment(ticker, year, section)


@app.post("/api/dcf")
async def dcf(req: DCFRequest) -> dict:
    result = await asyncio.to_thread(
        tool_run_dcf_valuation,
        req.ticker,
        req.wacc,
        req.terminal_growth,
        req.forecast_years,
        req.custom_growth_rate,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/research")
async def research(req: ResearchRequest) -> dict:
    result = await asyncio.to_thread(tool_generate_equity_research, req.ticker, req.year)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/mispricing/overview")
def mispricing_overview(year: int | None = None, sub_industry: str | None = None) -> dict:
    return tool_get_mispricing_overview(year, sub_industry)


@app.get("/api/mispricing/leaderboard")
def mispricing_leaderboard(
    direction: str, year: int | None = None, sub_industry: str | None = None, limit: int = 10,
) -> dict:
    return tool_list_mispriced(direction, year, sub_industry, limit)


@app.get("/api/mispricing/company")
def mispricing_company(ticker: str, year: int | None = None) -> dict:
    result = tool_get_valuation_check(ticker, year)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/mispricing/score-effectiveness")
def mispricing_score_effectiveness(score: str) -> dict:
    result = tool_get_score_effectiveness(score)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    if not llm_available():
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not set on the server. Add it to .env and restart the backend.",
        )
    session_id, agent = store.get_or_create(req.session_id)
    resp = await asyncio.to_thread(agent.ask, req.question)
    out = resp.to_dict()
    out["session_id"] = session_id
    return out


@app.post("/api/chat/reset")
def chat_reset(req: ChatResetRequest) -> dict:
    store.reset(req.session_id)
    return {"session_id": req.session_id, "reset": True}
