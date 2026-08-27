from __future__ import annotations

from finchat.chatbot.agent import FinChatAgent
from finchat.evaluation.checks import (
    extract_stance,
    guardrail_respected,
    matches_ground_truth,
)


def _offline_agent(seed_db) -> FinChatAgent:
    return FinChatAgent(force_offline=True)


def test_factual_answer_contains_exact_value(seed_db):
    agent = _offline_agent(seed_db)
    resp = agent.ask("What was Test Apple Inc's return on equity in FY2022?")
    assert resp.mode == "offline"
    assert "50.0%" in resp.answer
    assert resp.citations and resp.citations[0]["type"] == "structured_lookup"


def test_followup_uses_conversation_state(seed_db):
    agent = _offline_agent(seed_db)
    agent.ask("What was Test Apple Inc's gross margin in FY2022?")
    resp = agent.ask("And the year before?")
    trace_args = [t["args"] for t in resp.tool_trace]
    assert any(a.get("year") == 2021 for a in trace_args if isinstance(a, dict))
    ok, _ = matches_ground_truth(resp.answer, 330 / 900, 1.0, True)
    assert ok


def test_comparative_question(seed_db):
    agent = _offline_agent(seed_db)
    resp = agent.ask("Compare Microsoft and Apple on ROE in FY2022")
    assert "Test Microsoft" in resp.answer and "Test Apple" in resp.answer
    names = {t["name"] for t in resp.tool_trace}
    assert {"get_ratio"} <= names


def test_analytical_cites_scores(seed_db):
    agent = _offline_agent(seed_db)
    resp = agent.ask("Does Test Microsoft Corp look like a distress risk in FY2022?")
    low = resp.answer.lower()
    assert "distress" in low
    assert "altman" in low and "piotroski" in low
    scores = [c for c in resp.citations if c.get("table") == "scores"]
    assert scores


def test_advice_guardrail(seed_db):
    agent = _offline_agent(seed_db)
    resp = agent.ask("Should I buy NVDA stock right now?")
    assert guardrail_respected(resp.answer)


def test_unknown_company_prompts_clarify(seed_db):
    agent = _offline_agent(seed_db)
    resp = agent.ask("What was the net margin of SomeRandom Corp?")
    assert "couldn't tell which company" in resp.answer.lower()


def test_stance_extractor():
    assert extract_stance("The company looks financially strong with low risk.") == "strong"
    assert extract_stance("Elevated risk and weak fundamentals dominate.") == "weak"
    assert extract_stance("The profile is mixed overall.") == "mixed"
