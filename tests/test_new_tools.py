from __future__ import annotations

import pytest

from finchat.chatbot.tools import (
    TOOL_IMPLS,
    TOOL_SCHEMAS,
    call_tool,
    tool_get_score_effectiveness,
    tool_get_valuation_check,
    tool_list_mispriced,
)
from finchat.db import get_db


def _mispricing_built() -> bool:
    try:
        with get_db() as con:
            n = con.execute("SELECT COUNT(*) AS n FROM mispricing").fetchone()["n"]
        return n > 0
    except Exception:
        return False


requires_mispricing_data = pytest.mark.skipif(
    not _mispricing_built(),
    reason="Mispricing Radar tables are empty -- run 'python -m finchat mispricing' first.",
)


def _schema_names() -> set[str]:
    return {s["function"]["name"] for s in TOOL_SCHEMAS}


EXISTING_12 = {
    "get_ratio", "get_metric_history", "compare_companies", "get_scores", "get_line_items",
    "get_peer_ranking", "list_companies", "list_years", "search_filings", "get_text_sentiment",
    "run_dcf_valuation", "generate_equity_research",
}
NEW_3 = {"get_valuation_check", "list_mispriced", "get_score_effectiveness"}


def test_existing_12_tools_still_registered():
    names = _schema_names()
    assert EXISTING_12.issubset(names)
    for name in EXISTING_12:
        assert name in TOOL_IMPLS


def test_three_new_tools_registered_bringing_total_to_15():
    names = _schema_names()
    assert NEW_3.issubset(names)
    for name in NEW_3:
        assert name in TOOL_IMPLS
    assert len(EXISTING_12 | NEW_3) == 15
    assert names == EXISTING_12 | NEW_3


@requires_mispricing_data
@pytest.mark.parametrize("ticker", ["NVDA", "DELL", "AAPL"])
def test_get_valuation_check_shape(ticker):
    result = tool_get_valuation_check(ticker)
    assert "error" not in result, result
    assert result["ticker"] == ticker
    assert result["fiscal_year"] is not None
    assert set(result["pillars"].keys()) == {"profitability", "growth", "safety", "earnings_quality"}
    assert result["verdict"] in ("Undervalued", "Fairly valued", "Overvalued", "insufficient_data")
    assert "source" in result and result["source"]["type"] == "structured_lookup"
    assert result["disclaimer"].endswith("Not investment advice.")
    assert "walk-forward" in result["verdict_model"]["method"]
    assert result["verdict_model"]["train_years"].endswith(f"FY{result['fiscal_year'] - 1}")


@requires_mispricing_data
def test_earliest_year_has_no_verdict():
    result = tool_get_valuation_check("AAPL", 2018)
    assert result["verdict"] == "insufficient_data"
    assert result["fair_value_line_r2"] is None


@requires_mispricing_data
def test_get_valuation_check_unknown_ticker_errors_cleanly():
    result = tool_get_valuation_check("NOT_A_REAL_TICKER")
    assert "error" in result


@requires_mispricing_data
@pytest.mark.parametrize("direction", ["under", "over"])
def test_list_mispriced_shape(direction):
    result = tool_list_mispriced(direction, limit=5)
    assert "error" not in result, result
    assert result["direction"] == direction
    assert "source" in result and result["source"]["type"] == "structured_lookup"
    assert result["disclaimer"] == "Not investment advice."
    for c in result["companies"]:
        assert {"ticker", "quality_score", "ev_sales", "valuation_gap_log_points", "gap_z", "verdict"} <= c.keys()
    if direction == "under":
        assert all(c["verdict"] == "Undervalued" for c in result["companies"])
    else:
        assert all(c["verdict"] == "Overvalued" for c in result["companies"])


@requires_mispricing_data
@pytest.mark.parametrize("score", ["piotroski", "altman", "beneish"])
def test_get_score_effectiveness_shape(score):
    result = tool_get_score_effectiveness(score)
    assert "error" not in result, result
    assert result["score"] == score
    assert len(result["groups"]) >= 2
    for g in result["groups"]:
        assert "group" in g and "n" in g
        assert "avg_next_12m_excess_return_vs_xlk_pct" in g
    assert "source" in result and result["source"]["type"] == "structured_lookup"
    assert result["disclaimer"] == "Not investment advice."


def test_get_score_effectiveness_rejects_unknown_score():
    result = tool_get_score_effectiveness("not_a_score")
    assert "error" in result


@requires_mispricing_data
def test_call_tool_dispatches_the_new_tools():
    r = call_tool("get_valuation_check", {"ticker": "NVDA"})
    assert "error" not in r
    r = call_tool("list_mispriced", {"direction": "under"})
    assert "error" not in r
    r = call_tool("get_score_effectiveness", {"score": "altman"})
    assert "error" not in r
