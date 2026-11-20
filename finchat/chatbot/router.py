from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from finchat.chatbot.llm import LLMClient


class IntentClassificationResult(BaseModel):
    intent: Literal[
        "valuation",
        "research_report",
        "comparison",
        "trend",
        "credit_and_forensic",
        "factual_ratio",
        "qualitative_risks",
        "advice_probe",
        "general_chat",
    ] = Field(description="Primary intent category of the financial question")
    primary_ticker: Optional[str] = Field(default=None, description="Company ticker identified, if any (e.g. AAPL)")
    fiscal_year: Optional[int] = Field(default=None, description="Fiscal year referenced, if any (e.g. 2023)")
    metric_name: Optional[str] = Field(default=None, description="Specific ratio or metric requested, if any")
    reasoning: str = Field(description="Brief 1-sentence reasoning for classification")


def classify_intent_with_ai(question: str, client: LLMClient | None = None) -> IntentClassificationResult:
    """Classify user intent using Google Gemini with strict Pydantic Structured Output."""
    llm = client or LLMClient()
    messages = [
        {
            "role": "user",
            "content": f"Analyze this user query for an institutional equity research platform:\n\"{question}\"",
        }
    ]
    return llm.parse_structured(messages, response_model=IntentClassificationResult, temperature=0.0)


def route(question: str, resolved: dict[str, Any]) -> dict[str, Any]:
    try:
        classification = classify_intent_with_ai(question)
        return {
            "intent": classification.intent,
            "structured_classification": classification.model_dump(),
            **resolved,
        }
    except Exception:
        return {
            "intent": "conversational",
            **resolved,
        }
