from __future__ import annotations

import pytest

from finchat.chatbot.agent import FinChatAgent
from finchat.chatbot.tools import tool_get_metric_history
from finchat.db import get_db
from finchat.engine.quarterly import get_quarterly_metric_series


def test_quarterly_db_records_exist():
    with get_db() as con:
        count_stmts = con.execute("SELECT COUNT(*) AS c FROM quarterly_statements").fetchone()["c"]
        count_ratios = con.execute("SELECT COUNT(*) AS c FROM quarterly_ratios").fetchone()["c"]
    assert count_stmts > 0
    assert count_ratios > 0


def test_quarterly_metric_series_discrete():
    res = get_quarterly_metric_series("AAPL", "revenue", "quarterly")
    assert res["ticker"] == "AAPL"
    assert res["metric"] == "revenue"
    assert res["period_type"] == "quarterly"
    series = res["series"]
    assert len(series) >= 20
    # Every period has period label and positive revenue
    for s in series:
        assert "FY" in s["period"]
        assert s["value"] > 0


def test_ttm_metric_series():
    res = get_quarterly_metric_series("MSFT", "gross_margin", "ttm")
    assert res["ticker"] == "MSFT"
    assert res["metric"] == "gross_margin"
    assert res["period_type"] == "ttm"
    assert res["is_percentage"] is True
    series = res["series"]
    assert len(series) >= 15
    # Microsoft TTM gross margin is between 50% and 85%
    for s in series:
        assert 0.50 <= s["value"] <= 0.85


def test_tool_get_metric_history_period_type():
    res_q = tool_get_metric_history("NVDA", "gross_margin", period_type="quarterly")
    assert "series" in res_q
    assert len(res_q["series"]) > 10
    assert "Q" in res_q["series"][-1]["period"]

    res_ttm = tool_get_metric_history("NVDA", "gross_margin", period_type="ttm")
    assert "series" in res_ttm
    assert len(res_ttm["series"]) > 10


def test_agent_quarterly_trend_query():
    agent = FinChatAgent(force_offline=True)
    resp = agent.ask("Show Apple quarterly gross margin trend")
    assert resp.intent == "trend"
    assert "trend" in resp.answer.lower()
    assert "Q" in resp.answer
