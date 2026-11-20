from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None


class ChatResetRequest(BaseModel):
    session_id: str


class DCFRequest(BaseModel):
    ticker: str
    wacc: float = 0.09
    terminal_growth: float = 0.025
    forecast_years: int = 5
    custom_growth_rate: float | None = None


class ResearchRequest(BaseModel):
    ticker: str
    year: int | None = None
