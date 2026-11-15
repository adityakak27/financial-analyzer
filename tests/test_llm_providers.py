from __future__ import annotations

from unittest.mock import MagicMock, patch

from finchat.chatbot.agent import FinChatAgent
from finchat.chatbot.llm import LLMClient


def test_offline_mode():
    client = LLMClient(force_offline=True)
    assert not client.available
    assert "Offline" in client.display_name


def test_gemini_without_key():
    with patch("finchat.chatbot.llm.GEMINI_API_KEY", ""):
        client = LLMClient()
        assert not client.available
        assert "Offline" in client.display_name


def test_gemini_with_key():
    with patch("finchat.chatbot.llm.GEMINI_API_KEY", "test-gemini-key"), \
         patch("finchat.chatbot.llm.GEMINI_MODEL", "gemini-3.5-flash"):
        client = LLMClient()
        assert client.available
        assert client.model == "gemini-3.5-flash"
        assert "Google Gemini" in client.display_name
        assert str(client._client.base_url).startswith("https://generativelanguage.googleapis.com")


def test_parse_response_with_dict_and_string_arguments():
    mock_resp = MagicMock()
    tc1 = MagicMock()
    tc1.id = "call_1"
    tc1.function.name = "get_ratio"
    tc1.function.arguments = '{"ticker": "AAPL", "metric": "roe"}'

    tc2 = MagicMock()
    tc2.id = None
    tc2.function.name = "get_scores"
    tc2.function.arguments = {"ticker": "MSFT", "year": 2023}

    mock_resp.choices = [
        MagicMock(message=MagicMock(content="Here is the data:", tool_calls=[tc1, tc2]))
    ]

    content, calls = LLMClient.parse_response(mock_resp)
    assert content == "Here is the data:"
    assert len(calls) == 2
    assert calls[0]["id"] == "call_1"
    assert calls[0]["name"] == "get_ratio"
    assert calls[0]["args"] == {"ticker": "AAPL", "metric": "roe"}

    assert calls[1]["name"] == "get_scores"
    assert calls[1]["args"] == {"ticker": "MSFT", "year": 2023}
    assert calls[1]["id"].startswith("call_1_get_scores")


def test_agent_initialization_offline(seed_db):
    agent = FinChatAgent(force_offline=True)
    assert not agent.llm.available
    assert "Offline" in agent.llm.display_name
