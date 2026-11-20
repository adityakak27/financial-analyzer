from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from finchat.chatbot.llm import LLMClient


class RiskAuditResult(BaseModel):
    overall_risk_severity: Literal["Low", "Moderate", "High", "Critical"] = Field(
        description="Overall assessed severity of corporate risk"
    )
    primary_concerns: list[str] = Field(
        default_factory=list, description="Primary business and operational concerns disclosed"
    )
    red_flags: list[str] = Field(
        default_factory=list, description="Specific accounting, regulatory, debt covenant, or litigation alerts"
    )
    accounting_and_internal_controls: list[str] = Field(
        default_factory=list, description="Any internal control weaknesses, restatements, or audit flags"
    )
    summary: str = Field(description="2-sentence executive summary of the risk audit")


def audit_disclosures_with_ai(text: str, client: LLMClient | None = None) -> RiskAuditResult:
    """Audit corporate SEC 10-K disclosures using Google Gemini with strict Pydantic Structured Output."""
    if not text or not text.strip():
        return RiskAuditResult(
            overall_risk_severity="Low",
            primary_concerns=[],
            red_flags=[],
            accounting_and_internal_controls=[],
            summary="No disclosure text provided.",
        )

    llm = client or LLMClient()
    messages = [
        {
            "role": "user",
            "content": (
                "You are an institutional equity research risk auditor. Carefully evaluate these SEC 10-K disclosures:\n\n"
                f"\"\"\"{text[:4000]}\"\"\""
            ),
        }
    ]
    return llm.parse_structured(messages, response_model=RiskAuditResult, temperature=0.0)


def scan_red_flags(text: str) -> dict[str, int]:
    """Lightweight indicator counter for database indexing."""
    terms = [
        "going concern", "material weakness", "restatement", "impairment",
        "litigation", "investigation", "covenant", "customer concentration",
        "supply chain", "cybersecurity", "inflation"
    ]
    text_lower = text.lower()
    return {t: text_lower.count(t) for t in terms if t in text_lower}
