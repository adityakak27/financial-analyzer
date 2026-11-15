from __future__ import annotations

import pytest

from finchat.chatbot.agent import FinChatAgent
from finchat.engine.duel import compare_companies


def test_compare_companies_basic(seed_db):
    res = compare_companies("AAPL", "MSFT", 2022)
    assert "error" not in res
    assert res["ticker_a"] == "AAPL"
    assert res["ticker_b"] == "MSFT"
    assert res["year"] == 2022
    assert "pillars" in res
    assert "Profitability" in res["pillars"]
    assert "Financial Health & Solvency" in res["pillars"]
    assert "Accounting Quality" in res["pillars"]
    assert "Growth" in res["pillars"]
    assert res["wins_a"] + res["wins_b"] + res["ties"] > 0
    assert res["overall_winner"] in ("AAPL", "MSFT", "TIE")
    assert res["verdict"]


def test_compare_companies_direction_and_scoring(seed_db):
    res = compare_companies("AAPL", "MSFT", 2022)
    pillars = res["pillars"]

    # Check profitability metric gross margin (direction: higher)
    prof_metrics = {m["metric_id"]: m for m in pillars["Profitability"]}
    gm = prof_metrics.get("gross_margin")
    assert gm is not None
    assert gm["direction"] == "higher"
    if gm["val_a"] is not None and gm["val_b"] is not None:
        expected_winner = "AAPL" if gm["val_a"] > gm["val_b"] else "MSFT"
        assert gm["winner"] == expected_winner

    # Check solvency metric debt to equity (direction: lower)
    solv_metrics = {m["metric_id"]: m for m in pillars["Financial Health & Solvency"]}
    dte = solv_metrics.get("debt_to_equity")
    assert dte is not None
    assert dte["direction"] == "lower"
    if dte["val_a"] is not None and dte["val_b"] is not None:
        expected_winner = "AAPL" if dte["val_a"] < dte["val_b"] else "MSFT"
        assert dte["winner"] == expected_winner


def test_compare_companies_unknown_ticker(seed_db):
    res = compare_companies("UNKNOWN", "AAPL", 2022)
    assert "error" in res
    assert "No financial data available for UNKNOWN" in res["error"]


def test_agent_duel_query(seed_db):
    agent = FinChatAgent(force_offline=True)
    resp = agent.ask("Apple vs Microsoft head-to-head scorecard in FY2022")
    assert resp.intent == "comparative_duel"
    assert "⚔️ Company Duel" in resp.answer
    assert "Scorecard Summary" in resp.answer
    assert "Profitability" in resp.answer
    assert any(c.get("metric") == "scorecard" for c in resp.citations)
