from __future__ import annotations

from finchat.chatbot import tools as T
from finchat.chatbot.state import ConversationState, find_tickers, resolve_question


def test_get_ratio_exact(seed_db):
    out = T.tool_get_ratio("AAPL", "roe", 2022)
    assert out["value"] == 0.5
    assert out["formatted"] == "50.0%"
    assert out["source"]["type"] == "structured_lookup"


def test_metric_alias_resolution():
    assert T._resolve_metric("Return on Equity") == "roe"
    assert T._resolve_metric("debt-to-equity") == "debt_to_equity"
    assert T._resolve_metric("net_margin") == "net_margin"
    assert T._resolve_metric("gross margin") == "gross_margin"


def test_default_year_is_latest(seed_db):
    out = T.tool_get_ratio("AAPL", "gross margin")
    assert out["year"] == 2022
    assert abs(out["value"] - 0.4) < 1e-9


def test_scores_lookup_with_interpretation(seed_db):
    out = T.tool_get_scores("MSFT", 2022)
    assert out["altman_z"]["zone"] == "distress"
    assert out["piotroski_f"]["value"] is not None
    assert out["beneish_m"]["value"] is not None
    assert "DISTRESS" in out["altman_z"]["interpretation"].upper()


def test_peer_ranking_shape(seed_db):
    out = T.tool_get_peer_ranking("AAPL", "roe", 2022)
    assert out["metric"] == "roe"
    assert out["full_ranking"] in ([], None) or isinstance(out["full_ranking"], list)


def test_search_filings_finds_chunk(seed_db):
    out = T.tool_search_filings("supply chain constraints", ticker="AAPL", year=2022)
    assert out["n_results"] >= 1
    assert "supply chain" in out["results"][0]["excerpt"].lower()
    assert out["results"][0]["section"] == "risk"


def test_find_tickers_capitalization_rules(seed_db):
    assert find_tickers("Compare Microsoft and Apple ROE") == ["MSFT", "AAPL"]
    assert find_tickers("what can you show me now") == []
    assert find_tickers("AAPL vs MSFT margins") == ["AAPL", "MSFT"]


def test_resolve_prior_year_followup(seed_db):
    state = ConversationState(current_ticker="AAPL", current_fy=2022, last_metric="roe")
    r = resolve_question("What about the year before?", state)
    assert r["fy"] == 2021
    r2 = resolve_question("And two years earlier?", state)
    assert r2["fy"] == 2020


def test_list_companies(seed_db):
    out = T.tool_list_companies()
    tickers = {c["ticker"] for c in out["companies"]}
    assert {"AAPL", "MSFT"} <= tickers
