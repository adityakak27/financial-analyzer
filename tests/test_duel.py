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
    assert "pillar_winners" in res
    assert "Profitability" in res["pillar_winners"]
    assert "Financial Health & Solvency" in res["pillar_winners"]
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
    from unittest.mock import MagicMock, patch

    with patch("finchat.chatbot.llm.GEMINI_API_KEY", "mock-key"):
        agent = FinChatAgent()
        call_msg = MagicMock()
        tc = MagicMock()
        tc.id = "duel_call"
        tc.function.name = "compare_companies"
        tc.function.arguments = {"ticker_a": "AAPL", "ticker_b": "MSFT", "year": 2022}
        call_msg.choices = [MagicMock(message=MagicMock(content=None, tool_calls=[tc]))]

        final_msg = MagicMock()
        final_msg.choices = [MagicMock(message=MagicMock(
            content="Here is the scorecard comparison: Apple vs Microsoft for FY2022 across Profitability and Solvency.",
            tool_calls=[],
        ))]

        agent.llm.chat = MagicMock(side_effect=[call_msg, final_msg])
        resp = agent.ask("Apple vs Microsoft head-to-head scorecard in FY2022")

        assert len(resp.tool_trace) == 1
        assert resp.tool_trace[0]["name"] == "compare_companies"
        assert any(c.get("metric") == "company_duel" for c in resp.citations)
