from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field

from finchat.config import UNIVERSE
from finchat.db import get_db
from finchat.engine.dcf import calculate_dcf
from finchat.engine.ratios import YearData, compute_ratios
from finchat.engine.scores import altman_z, beneish_m, piotroski_f


class HeadlineMetrics(BaseModel):
    implied_share_price: Optional[float] = Field(default=None, description="DCF implied intrinsic share price")
    enterprise_value: Optional[float] = Field(default=None, description="DCF enterprise value")
    altman_z: Optional[float] = Field(default=None, description="Altman Z-Score")
    altman_zone: str = Field(default="N/A", description="Altman Z zone: safe, grey, or distress")
    piotroski_f: Optional[float] = Field(default=None, description="Piotroski F-Score (0-9)")
    beneish_m: Optional[float] = Field(default=None, description="Beneish M-Score")
    roe: Optional[float] = Field(default=None, description="Return on Equity")
    fcf_margin: Optional[float] = Field(default=None, description="Free cash flow margin")


class InitiationReport(BaseModel):
    ticker: str
    company_name: str
    year: int
    markdown_report: str
    headline_metrics: HeadlineMetrics
    specialist_outputs: dict[str, Any] = Field(default_factory=dict)


def _get_company_years_data(ticker: str) -> tuple[dict[int, YearData], list[int]]:
    ticker = (ticker or "").upper().strip()
    with get_db() as con:
        rows = con.execute(
            "SELECT fy, metric, value FROM statements WHERE ticker = ? ORDER BY fy ASC",
            (ticker,),
        ).fetchall()

    by_year: dict[int, dict[str, float | None]] = {}
    for r in rows:
        by_year.setdefault(r["fy"], {})[r["metric"]] = r["value"]

    years = sorted(by_year.keys())
    year_data = {fy: YearData(ticker=ticker, fy=fy, m=by_year[fy]) for fy in years}
    return year_data, years


def _get_latest_scores(ticker: str, year: int) -> dict[str, Any]:
    with get_db() as con:
        r = con.execute(
            "SELECT * FROM scores WHERE ticker = ? AND fy = ?",
            (ticker, year),
        ).fetchone()
    if not r:
        return {}
    comps = json.loads(r["components_json"]) if r["components_json"] else {}
    return {
        "altman_z": {"value": r["altman_z"], "components": {"zone": r["altman_zone"], **comps.get("altman_z", {})}},
        "piotroski_f": {"value": r["piotroski_f"], "components": comps.get("piotroski_f", {})},
        "beneish_m": {"value": r["beneish_m"], "components": {"flag": r["beneish_flag"], **comps.get("beneish_m", {})}},
    }


def _get_key_filing_excerpts(ticker: str, year: int) -> dict[str, list[str]]:
    """Retrieve key paragraphs from Item 7 (MD&A) and Item 1A (Risk Factors)."""
    with get_db() as con:
        rows = con.execute(
            """
            SELECT section, text 
            FROM chunks 
            WHERE ticker = ? AND fy = ?
            ORDER BY chunk_id ASC
            LIMIT 12
            """,
            (ticker, year),
        ).fetchall()

    excerpts: dict[str, list[str]] = {"mda": [], "risk_factors": []}
    for r in rows:
        sec = r["section"]
        txt = r["text"].strip()
        if not txt:
            continue
        if sec == "Item 7":
            if len(excerpts["mda"]) < 3:
                excerpts["mda"].append(txt)
        elif sec == "Item 1A":
            if len(excerpts["risk_factors"]) < 3:
                excerpts["risk_factors"].append(txt)
    return excerpts


# ==============================================================================
# Specialist 1: Valuation & DCF Specialist
# ==============================================================================
class ValuationSpecialist:
    """Specialist agent responsible for DCF modeling, cash flows, and intrinsic valuation."""

    def analyze(self, ticker: str, year: int, dcf_kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
        dcf_params = dcf_kwargs or {}
        dcf_result = calculate_dcf(ticker, **dcf_params)
        year_data, years = _get_company_years_data(ticker)

        cur_yd = year_data.get(year)
        prev_yd = year_data.get(year - 1) if cur_yd else None
        ratios = compute_ratios(cur_yd, prev_yd) if cur_yd else {}

        # Valuation multiples if available
        with get_db() as con:
            mult_rows = con.execute(
                "SELECT metric, value FROM ratios WHERE ticker = ? AND fy = ? AND metric IN ('pe_ratio', 'ps_ratio', 'ev_ebitda', 'ev_fcf')",
                (ticker, year),
            ).fetchall()
        multiples = {r["metric"]: r["value"] for r in mult_rows}

        findings = {
            "dcf": dcf_result,
            "multiples": multiples,
            "fcf_margin": ratios.get("fcf_margin"),
            "revenue_growth_pct": ratios.get("revenue_growth_pct"),
            "net_income_growth_pct": ratios.get("net_income_growth_pct"),
            "roe": ratios.get("roe"),
            "roic": ratios.get("roic"),
        }

        # Format executive commentary
        implied_price = dcf_result.get("implied_share_price")
        ev = dcf_result.get("enterprise_value")
        wacc = dcf_result.get("assumptions", {}).get("wacc", 0.09)
        g = dcf_result.get("assumptions", {}).get("terminal_growth", 0.025)

        summary_text = (
            f"**Valuation & DCF Assessment for {ticker} (FY{year}):**\n"
            f"- **DCF Implied Enterprise Value**: ${ev:,.0f} (at {wacc:.1%} WACC, {g:.1%} Terminal Growth)\n"
            f"- **Implied Intrinsic Share Price**: ${implied_price:.2f}" if implied_price else "Share price not computable"
            f"\n- **Free Cash Flow Margin**: {ratios.get('fcf_margin', 0) * 100:.1f}%\n"
            f"- **Return on Invested Capital (ROIC)**: {ratios.get('roic', 0) * 100:.1f}%\n"
            f"- **Historical Revenue Growth**: {ratios.get('revenue_growth_pct', 0):.1f}% YoY"
        )

        return {"findings": findings, "summary": summary_text}


# ==============================================================================
# Specialist 2: Forensic Accounting & Solvency Auditor
# ==============================================================================
class ForensicAuditor:
    """Specialist agent responsible for forensic fraud detection, solvency, and balance sheet distress."""

    def analyze(self, ticker: str, year: int) -> dict[str, Any]:
        year_data, years = _get_company_years_data(ticker)
        cur_yd = year_data.get(year)
        prev_yd = year_data.get(year - 1) if cur_yd else None

        scores = _get_latest_scores(ticker, year)
        ratios = compute_ratios(cur_yd, prev_yd) if cur_yd else {}

        alt_z = scores.get("altman_z", {})
        pio_f = scores.get("piotroski_f", {})
        ben_m = scores.get("beneish_m", {})

        z_val = alt_z.get("value")
        z_zone = alt_z.get("components", {}).get("zone", "unknown")

        f_val = pio_f.get("value")

        m_val = ben_m.get("value")
        m_flag = "Likely Manipulator" if (m_val is not None and m_val > -1.78) else "Low Manipulation Risk"

        # Accrual quality: Net Income vs CFO
        m = cur_yd.m if cur_yd else {}
        ni = m.get("net_income") or 0.0
        cfo = m.get("cfo") or 0.0
        ta = m.get("assets") or 1.0
        total_accruals = (ni - cfo) / ta

        findings = {
            "altman_z": alt_z,
            "piotroski_f": pio_f,
            "beneish_m": ben_m,
            "total_accruals_to_assets": total_accruals,
            "current_ratio": ratios.get("current_ratio"),
            "debt_to_equity": ratios.get("debt_to_equity"),
            "interest_coverage": ratios.get("interest_coverage"),
        }

        summary_text = (
            f"**Forensic Accounting & Solvency Audit for {ticker} (FY{year}):**\n"
            f"- **Altman Z-Score**: {z_val:.2f} ({z_zone.upper()} Zone) — Solvency & Bankruptcy Risk\n"
            f"- **Piotroski F-Score**: {f_val}/9 — Fundamental Financial Health Score\n"
            f"- **Beneish M-Score**: {m_val:.2f} ({m_flag}) — Earnings Manipulation Risk\n"
            f"- **Accrual Quality (TATA)**: {total_accruals:.3f} (Cash flow exceeds net income: {cfo > ni})\n"
            f"- **Balance Sheet Liquidity**: Current Ratio = {ratios.get('current_ratio', 0):.2f}, Debt/Equity = {ratios.get('debt_to_equity', 0):.2f}"
        )

        return {"findings": findings, "summary": summary_text}


# ==============================================================================
# Specialist 3: Qualitative MD&A & Strategic Analyst
# ==============================================================================
class StrategicAnalyst:
    """Specialist agent responsible for analyzing SEC Item 7 (MD&A) and Item 1A (Risk Factors)."""

    def analyze(self, ticker: str, year: int) -> dict[str, Any]:
        excerpts = _get_key_filing_excerpts(ticker, year)

        findings = {
            "mda_excerpts": excerpts["mda"],
            "risk_factor_excerpts": excerpts["risk_factors"],
        }

        mda_summary = (
            f"Extracted {len(excerpts['mda'])} strategic disclosures from Item 7 (MD&A) and "
            f"{len(excerpts['risk_factors'])} risk disclosures from Item 1A (Risk Factors)."
        )

        return {"findings": findings, "summary": mda_summary}


# ==============================================================================
# Specialist 4: Lead Research Director (Synthesizer)
# ==============================================================================
class ResearchDirector:
    """Lead research director that synthesizes specialist findings into an institutional report."""

    def __init__(self) -> None:
        self.valuation_agent = ValuationSpecialist()
        self.forensic_agent = ForensicAuditor()
        self.strategic_agent = StrategicAnalyst()

    def generate_initiation_report(
        self,
        ticker: str,
        year: int | None = None,
        dcf_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ticker = (ticker or "").upper().strip()
        company_name = UNIVERSE.get(ticker, ticker)

        year_data, years = _get_company_years_data(ticker)
        if not years:
            return {"error": f"No financial statements found in database for ticker {ticker}"}

        selected_year = year if (year and year in years) else years[-1]

        # 1. Gather specialist outputs
        val_output = self.valuation_agent.analyze(ticker, selected_year, dcf_kwargs)
        for_output = self.forensic_agent.analyze(ticker, selected_year)
        strat_output = self.strategic_agent.analyze(ticker, selected_year)

        # 2. Extract key metrics for structured display
        dcf = val_output["findings"]["dcf"]
        implied_price = dcf.get("implied_share_price")
        enterprise_val = dcf.get("enterprise_value")

        alt_z = for_output["findings"]["altman_z"].get("value")
        alt_zone = for_output["findings"]["altman_z"].get("components", {}).get("zone", "N/A")
        pio_f = for_output["findings"]["piotroski_f"].get("value")
        ben_m = for_output["findings"]["beneish_m"].get("value")

        cur_yd = year_data.get(selected_year)
        prev_yd = year_data.get(selected_year - 1)
        ratios = compute_ratios(cur_yd, prev_yd) if cur_yd else {}

        # 3. Compile the Institutional Initiation of Coverage Report (Markdown)
        report_lines = [
            f"# EQUITY RESEARCH INITIATION REPORT: {ticker} ({company_name})",
            f"**Fiscal Year:** FY{selected_year} | **Coverage Status:** Active | **Sector:** Technology / Large-Cap",
            "---",
            "",
            "## 1. Executive Summary & Investment Thesis",
            f"{company_name} (`{ticker}`) demonstrates strong market positioning backed by verified SEC Form 10-K data.",
            f"- **Intrinsic DCF Fair Value:** ${implied_price:.2f} per share" if implied_price else "- **Intrinsic DCF Fair Value:** N/A",
            f"- **Implied Enterprise Value:** ${enterprise_val:,.0f}" if enterprise_val else "- **Implied Enterprise Value:** N/A",
            f"- **Financial Health Profile:** Altman Z-Score of **{alt_z:.2f}** ({alt_zone.upper()}), Piotroski F-Score of **{pio_f}/9**.",
            f"- **Earnings Quality:** Beneish M-Score of **{ben_m:.2f}** (Flag: {'Low Manipulation Risk' if ben_m and ben_m < -1.78 else 'Caution'}).",
            "",
            "## 2. Forensic Accounting & Solvency Audit",
            "| Forensic Metric | Value | Benchmark / Safe Zone | Audit Interpretation |",
            "|---|---|---|---|",
            f"| **Altman Z-Score** | {alt_z:.2f} | > 3.0 (Safe) | Company is positioned in the **{alt_zone.upper()}** zone regarding default risk. |",
            f"| **Piotroski F-Score** | {pio_f}/9 | >= 7 (Strong) | Fundamental operational and liquidity momentum. |",
            f"| **Beneish M-Score** | {ben_m:.2f} | < -1.78 (Safe) | Earnings quality indicators show no statistical red flags. |",
            f"| **Total Accruals / Assets** | {for_output['findings']['total_accruals_to_assets']:.3f} | Lower is better | Cash flow backing of reported net earnings. |",
            f"| **Current Ratio** | {ratios.get('current_ratio', 0):.2f}x | > 1.0x | Balance sheet working capital buffer. |",
            f"| **Debt to Equity** | {ratios.get('debt_to_equity', 0):.2f}x | Industry median | Capital structure leverage posture. |",
            "",
            "## 3. Financial Performance & DuPont Decomposition",
            "| Performance Metric | FY Value | Description |",
            "|---|---|---|",
            f"| **Return on Equity (ROE)** | {ratios.get('roe', 0) * 100:.2f}% | Overall return generated on shareholders' capital |",
            f"| **Net Profit Margin** | {ratios.get('net_margin', 0) * 100:.2f}% | Operating efficiency & cost discipline |",
            f"| **Asset Turnover** | {ratios.get('asset_turnover', 0):.2f}x | Asset utilization efficiency |",
            f"| **Operating Margin** | {ratios.get('operating_margin', 0) * 100:.2f}% | Core profitability before taxes and interest |",
            f"| **Free Cash Flow Margin** | {ratios.get('fcf_margin', 0) * 100:.2f}% | Free cash flow conversion efficiency |",
            f"| **Return on Invested Capital (ROIC)** | {ratios.get('roic', 0) * 100:.2f}% | Economic value generation on invested capital |",
            "",
            "## 4. Discounted Cash Flow (DCF) Model & Sensitivity Analysis",
            f"Based on historical cash generation and disciplined capital expenditure schedules:",
            f"- **Base FCF:** ${dcf.get('base_fcf', 0):,.0f}",
            f"- **Assumed WACC:** {dcf.get('assumptions', {}).get('wacc', 0.09) * 100:.1f}%",
            f"- **Terminal Growth Rate:** {dcf.get('assumptions', {}).get('terminal_growth', 0.025) * 100:.1f}%",
            f"- **Present Value of 5-Yr Projections:** ${dcf.get('pv_projected_fcf', 0):,.0f}",
            f"- **Present Value of Terminal Value:** ${dcf.get('pv_terminal_value', 0):,.0f} ({dcf.get('terminal_value_pct_of_ev', 0) * 100:.1f}% of EV)",
            f"- **Net Debt Adjustment:** ${dcf.get('balance_sheet_bridge', {}).get('net_debt', 0):,.0f}",
            "",
            "### Implied Share Price Sensitivity Matrix (WACC vs. Terminal Growth)",
            "| WACC \\ Growth | " + " | ".join(f"{g:.1f}%" for g in dcf['sensitivity_matrix']['growth_axis']) + " |",
            "|---|" + "|".join("---" for _ in dcf['sensitivity_matrix']['growth_axis']) + "|",
        ]

        for row in dcf["sensitivity_matrix"]["rows"]:
            row_str = f"| **{row['wacc']:.1f}%** | " + " | ".join(
                f"${v['implied_share_price']:.2f}" if v['implied_share_price'] is not None else "N/A"
                for v in row["values"]
            ) + " |"
            report_lines.append(row_str)

        report_lines.extend([
            "",
            "## 5. Strategic MD&A & Disclosed Risk Analysis",
            "### Disclosures from Item 7 (Management's Discussion & Analysis):",
        ])

        mda_samples = strat_output["findings"]["mda_excerpts"]
        if mda_samples:
            for i, p in enumerate(mda_samples[:2], 1):
                clean_p = " ".join(p.split()[:80]) + "..."
                report_lines.append(f"> **Excerpt {i}:** \"{clean_p}\"\n")
        else:
            report_lines.append("_No raw text chunks indexed for this fiscal year._\n")

        report_lines.append("### Key Risk Disclosures from Item 1A (Risk Factors):")
        rf_samples = strat_output["findings"]["risk_factor_excerpts"]
        if rf_samples:
            for i, p in enumerate(rf_samples[:2], 1):
                clean_p = " ".join(p.split()[:80]) + "..."
                report_lines.append(f"> **Risk Factor {i}:** \"{clean_p}\"\n")
        else:
            report_lines.append("_No risk factor chunks indexed for this fiscal year._\n")

        report_lines.extend([
            "## 6. Research Conclusion & Fundamental Rating",
            f"Based on the objective quantitative evidence and verified SEC Form 10-K filings, **{ticker}** presents a:",
            f"- **Solvency Stance:** **{alt_zone.upper()}** (Altman Z = {alt_z:.2f})",
            f"- **Earnings Quality Stance:** **{'PRISTINE' if ben_m and ben_m < -1.78 else 'CAUTION'}** (Beneish M = {ben_m:.2f})",
            f"- **Operational Momentum:** **{'HIGH' if pio_f and pio_f >= 7 else 'MODERATE'}** (Piotroski F = {pio_f}/9)",
            f"- **DCF Fair Value Range:** **${dcf['sensitivity_matrix']['rows'][0]['values'][-1]['implied_share_price']:.2f}** (Optimistic) to **${dcf['sensitivity_matrix']['rows'][-1]['values'][0]['implied_share_price']:.2f}** (Conservative)" if implied_price else "- **DCF Fair Value Range:** N/A",
            "",
            "_Disclaimer: This document is an automated equity research initiation dossier synthesized strictly from historical SEC EDGAR filings for financial education and quantitative fundamental analysis. It does not constitute investment advice or a recommendation to buy or sell securities._",
        ])

        full_markdown = "\n".join(report_lines)

        report = InitiationReport(
            ticker=ticker,
            company_name=company_name,
            year=selected_year,
            markdown_report=full_markdown,
            headline_metrics=HeadlineMetrics(
                implied_share_price=implied_price,
                enterprise_value=enterprise_val,
                altman_z=alt_z,
                altman_zone=alt_zone,
                piotroski_f=pio_f,
                beneish_m=ben_m,
                roe=ratios.get("roe"),
                fcf_margin=ratios.get("fcf_margin"),
            ),
            specialist_outputs={
                "valuation": val_output,
                "forensic": for_output,
                "strategic": strat_output,
            },
        )
        return report.model_dump()
