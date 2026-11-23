from __future__ import annotations

from unittest.mock import MagicMock, patch

from finchat.engine.mispricing import _offline_note, generate_note, validate_numbers_for_test


SOURCE_ROW = {
    "ticker": "NVDA", "fy": 2024, "quality_score": 95.1,
    "profitability": 91.1, "growth": 83.4, "safety": 99.0, "earnings_quality": 47.0,
    "ev_sales": 27.35, "expected_ev_sales": 24.2,
    "valuation_gap": 0.085, "gap_z": 0.10, "verdict": "Fairly valued",
    "dcf_upside": -0.41, "dcf_agreement": "n/a",
}


def test_offline_template_is_always_grounded():
    text = _offline_note(SOURCE_ROW)
    assert "95.1" in text
    assert "NVDA" in text
    assert text.endswith("Not investment advice.")
    ok, bad = validate_numbers_for_test(text, SOURCE_ROW)
    assert ok, bad


def test_offline_path_used_when_use_gemini_false():
    text, validated, model = generate_note(SOURCE_ROW, use_gemini=False)
    assert validated is True
    assert model == "offline_template"
    assert text.endswith("Not investment advice.")


def test_fabricated_number_is_rejected_and_falls_back_to_offline():
    """A Gemini response containing a number that isn't in the source JSON must be rejected,
    with generate_note() falling back to the (always-grounded) offline template."""
    fake_client = MagicMock()
    fake_client.model = "fake-gemini"
    # 650.3 appears nowhere in SOURCE_ROW -- a fabricated number.
    fake_client.generate.return_value = (
        "NVDA trades at an extraordinary 650.3x multiple, far beyond peers. Not investment advice."
    )
    with patch("finchat.chatbot.llm.LLMClient", return_value=fake_client):
        text, validated, model = generate_note(SOURCE_ROW, use_gemini=True)

    # The fabricated response must never be accepted as validated.
    assert "650.3" not in text
    assert model == "offline_template"
    assert validated is True  # the offline fallback IS grounded, even though Gemini's wasn't
    assert fake_client.generate.call_count == 2  # one retry before falling back


def test_truthful_gemini_response_is_accepted():
    fake_client = MagicMock()
    fake_client.model = "fake-gemini"
    # Every number here (95.1, 27.35, 24.2) is present in SOURCE_ROW.
    fake_client.generate.return_value = (
        "NVDA scores 95.1 on quality and trades at 27.35x EV/Sales versus an expected 24.2x. "
        "The data suggests this is roughly in line with its quality. Not investment advice."
    )
    with patch("finchat.chatbot.llm.LLMClient", return_value=fake_client):
        text, validated, model = generate_note(SOURCE_ROW, use_gemini=True)

    assert validated is True
    assert model == "fake-gemini"
    assert "27.35" in text
    assert fake_client.generate.call_count == 1  # accepted on the first attempt, no retry needed


def test_chat_cleanup_unwraps_latex_but_keeps_dollar_amounts():
    from finchat.chatbot.agent import sanitize_markdown

    out = sanitize_markdown("High ($n = 121$), $R^{2} = 0.29$; fair value $40.10 vs $50 now")
    assert out == "High (n = 121), R² = 0.29; fair value $40.10 vs $50 now"
