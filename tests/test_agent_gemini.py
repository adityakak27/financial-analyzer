from __future__ import annotations

from unittest.mock import MagicMock, patch

from finchat.chatbot.agent import FinChatAgent


def _mock_llm_response(content: str | None = None, tool_calls: list[dict] | None = None):
    mock_resp = MagicMock()
    tc_objects = []
    if tool_calls:
        for i, tc in enumerate(tool_calls):
            m_tc = MagicMock()
            m_tc.id = tc.get("id", f"call_{i}")
            m_tc.function.name = tc["name"]
            m_tc.function.arguments = tc.get("args", {})
            tc_objects.append(m_tc)

    mock_msg = MagicMock(content=content, tool_calls=tc_objects)
    mock_resp.choices = [MagicMock(message=mock_msg)]
    return mock_resp


def test_agent_tool_calling_flow(seed_db):
    with patch("finchat.chatbot.llm.GEMINI_API_KEY", "mock-key"):
        agent = FinChatAgent()

        # Step 1: Model issues a tool call to get_ratio
        call_msg = _mock_llm_response(
            content=None,
            tool_calls=[{"id": "c1", "name": "get_ratio", "args": {"ticker": "AAPL", "metric": "roe", "year": 2022}}],
        )
        # Step 2: Model finishes with answer
        final_msg = _mock_llm_response(
            content="Apple's return on equity in FY2022 was 50.0%.",
            tool_calls=[],
        )

        agent.llm.chat = MagicMock(side_effect=[call_msg, final_msg])

        resp = agent.ask("What was Apple's ROE in FY2022?")
        assert resp.mode == "gemini"
        assert "50.0%" in resp.answer
        assert len(resp.tool_trace) == 1
        assert resp.tool_trace[0]["name"] == "get_ratio"
        assert len(resp.citations) >= 1
        assert resp.citations[0]["type"] == "structured_lookup"


def test_agent_dcf_tool_calling(seed_db):
    with patch("finchat.chatbot.llm.GEMINI_API_KEY", "mock-key"):
        agent = FinChatAgent()

        call_msg = _mock_llm_response(
            content=None,
            tool_calls=[{"id": "dcf_1", "name": "run_dcf_valuation", "args": {"ticker": "AAPL"}}],
        )
        final_msg = _mock_llm_response(
            content="Apple's DCF valuation indicates an implied share price of $93.03.",
            tool_calls=[],
        )

        agent.llm.chat = MagicMock(side_effect=[call_msg, final_msg])

        resp = agent.ask("Run a DCF valuation for Apple.")
        assert len(resp.tool_trace) == 1
        assert resp.tool_trace[0]["name"] == "run_dcf_valuation"
        assert "implied share price" in resp.answer.lower()
