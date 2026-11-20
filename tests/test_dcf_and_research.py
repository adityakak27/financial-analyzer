from __future__ import annotations

import pytest

from finchat.engine.dcf import calculate_dcf, get_historical_cash_flows
from finchat.engine.research_agents import (
    ForensicAuditor,
    InitiationReport,
    ResearchDirector,
    StrategicAnalyst,
    ValuationSpecialist,
)
from finchat.nlp.redflags import RiskAuditResult
from finchat.nlp.sentiment import SentimentAnalysisResult
from finchat.chatbot.router import IntentClassificationResult


def test_dcf_calculation_with_real_data():
    res = calculate_dcf("AAPL", wacc=0.09, terminal_growth=0.025, forecast_years=5)
    assert "error" not in res
    assert res["ticker"] == "AAPL"
    assert res["assumptions"]["wacc"] == 0.09
    assert res["assumptions"]["terminal_growth"] == 0.025
    assert len(res["projections"]) == 5
    assert res["pv_projected_fcf"] > 0
    assert res["pv_terminal_value"] > 0
    assert res["enterprise_value"] > res["pv_projected_fcf"]
    assert res["implied_share_price"] is not None
    assert res["implied_share_price"] > 0

    # Test 2D sensitivity matrix
    matrix = res["sensitivity_matrix"]
    assert len(matrix["wacc_axis"]) == 5
    assert len(matrix["growth_axis"]) == 5
    assert len(matrix["rows"]) == 5
    for row in matrix["rows"]:
        assert len(row["values"]) == 5


def test_dcf_wacc_terminal_growth_safety():
    # If WACC <= terminal growth, model automatically adjusts WACC to prevent division by zero or negative EV
    res = calculate_dcf("AAPL", wacc=0.02, terminal_growth=0.025)
    assert "error" not in res
    assert res["assumptions"]["wacc"] > res["assumptions"]["terminal_growth"]


def test_specialist_agents_execution():
    val_specialist = ValuationSpecialist()
    val_out = val_specialist.analyze("AAPL", 2024)
    assert "findings" in val_out
    assert "dcf" in val_out["findings"]

    forensic_auditor = ForensicAuditor()
    for_out = forensic_auditor.analyze("AAPL", 2024)
    assert "findings" in for_out
    assert "altman_z" in for_out["findings"]
    assert "piotroski_f" in for_out["findings"]
    assert "beneish_m" in for_out["findings"]

    strategic_analyst = StrategicAnalyst()
    strat_out = strategic_analyst.analyze("AAPL", 2024)
    assert "findings" in strat_out
    assert "mda_excerpts" in strat_out["findings"]


def test_research_director_initiation_report():
    rd = ResearchDirector()
    report = rd.generate_initiation_report("AAPL")
    assert "error" not in report
    assert report["ticker"] == "AAPL"
    assert report["company_name"] == "Apple Inc."
    assert "EQUITY RESEARCH INITIATION REPORT" in report["markdown_report"]
    assert "Forensic Accounting & Solvency Audit" in report["markdown_report"]
    assert "Discounted Cash Flow (DCF) Model" in report["markdown_report"]

    # Verify structured Pydantic model integrity
    validated = InitiationReport.model_validate(report)
    assert validated.ticker == "AAPL"
    assert validated.headline_metrics.altman_z is not None
    assert validated.headline_metrics.implied_share_price is not None


def test_pydantic_structured_models():
    # Test RiskAuditResult
    risk = RiskAuditResult(
        overall_risk_severity="Moderate",
        primary_concerns=["Supply chain delays"],
        red_flags=[],
        accounting_and_internal_controls=[],
        summary="Moderate supply chain risk noted.",
    )
    assert risk.overall_risk_severity == "Moderate"

    # Test SentimentAnalysisResult
    sent = SentimentAnalysisResult(
        tone="Optimistic",
        management_confidence="High",
        forward_looking_hedging="Low",
        key_drivers=["Strong cloud growth"],
        commentary="Management expressed high confidence in product roadmap.",
    )
    assert sent.tone == "Optimistic"

    # Test IntentClassificationResult
    intent = IntentClassificationResult(
        intent="valuation",
        primary_ticker="AAPL",
        fiscal_year=2024,
        metric_name="dcf",
        reasoning="User is asking for intrinsic valuation of Apple.",
    )
    assert intent.intent == "valuation"
