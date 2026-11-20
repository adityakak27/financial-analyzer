from __future__ import annotations

import math
from typing import Any

from finchat.db import get_db


def safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0 or (isinstance(a, float) and math.isnan(a)) or (isinstance(b, float) and math.isnan(b)):
        return None
    return a / b


def get_historical_cash_flows(ticker: str) -> list[dict[str, Any]]:
    """Retrieve historical CFO, CapEx, FCF, Revenue, and Net Income for all available FYs."""
    ticker = (ticker or "").upper().strip()
    with get_db() as con:
        rows = con.execute(
            """
            SELECT fy, metric, value 
            FROM statements 
            WHERE ticker = ? AND metric IN ('cfo', 'capex', 'revenue', 'net_income')
            ORDER BY fy ASC
            """,
            (ticker,),
        ).fetchall()

    by_year: dict[int, dict[str, float | None]] = {}
    for r in rows:
        fy = r["fy"]
        by_year.setdefault(fy, {})[r["metric"]] = r["value"]

    history: list[dict[str, Any]] = []
    for fy in sorted(by_year.keys()):
        m = by_year[fy]
        cfo = m.get("cfo")
        capex = m.get("capex") or 0.0
        fcf = (cfo - capex) if cfo is not None else None
        history.append({
            "fy": fy,
            "revenue": m.get("revenue"),
            "net_income": m.get("net_income"),
            "cfo": cfo,
            "capex": capex,
            "fcf": fcf,
        })
    return history


def calculate_dcf(
    ticker: str,
    wacc: float = 0.09,
    terminal_growth: float = 0.025,
    forecast_years: int = 5,
    custom_growth_rate: float | None = None,
) -> dict[str, Any]:
    """Execute a full DCF valuation model with bridge to equity value and sensitivity analysis.

    Parameters:
        ticker: Stock ticker (e.g. AAPL)
        wacc: Weighted Average Cost of Capital / Discount rate (e.g. 0.09 for 9.0%)
        terminal_growth: Perpetual terminal growth rate (e.g. 0.025 for 2.5%)
        forecast_years: Number of discrete projection years (typically 5)
        custom_growth_rate: Optional annual FCF growth rate override (e.g. 0.08 for 8.0%)
    """
    ticker = (ticker or "").upper().strip()
    history = get_historical_cash_flows(ticker)
    if not history:
        return {"error": f"No financial statements found for {ticker}"}

    # Fetch latest balance sheet and capital structure items
    latest_fy = history[-1]["fy"]
    with get_db() as con:
        bs_rows = con.execute(
            """
            SELECT metric, value 
            FROM statements 
            WHERE ticker = ? AND fy = ? AND metric IN (
                'cash', 'short_term_investments', 'debt_current', 'long_term_debt',
                'shares_diluted', 'equity'
            )
            """,
            (ticker, latest_fy),
        ).fetchall()

    bs = {r["metric"]: r["value"] for r in bs_rows}

    cash = bs.get("cash") or 0.0
    st_inv = bs.get("short_term_investments") or 0.0
    total_cash = cash + st_inv

    debt_curr = bs.get("debt_current") or 0.0
    lt_debt = bs.get("long_term_debt") or 0.0
    total_debt = debt_curr + lt_debt
    net_debt = total_debt - total_cash

    shares_diluted = bs.get("shares_diluted")

    # Base year FCF: use latest year FCF or 3-year average if negative/erratic
    valid_fcfs = [h["fcf"] for h in history if h.get("fcf") is not None]
    if not valid_fcfs:
        return {"error": f"Free cash flow cannot be determined from statements for {ticker}"}

    base_fcf = valid_fcfs[-1]

    # Determine projection growth rate
    if custom_growth_rate is not None:
        growth_rate = custom_growth_rate
        growth_method = "user_specified"
    else:
        # Calculate historical 3-year CAGR if available
        if len(valid_fcfs) >= 3 and valid_fcfs[-3] > 0 and valid_fcfs[-1] > 0:
            cagr = (valid_fcfs[-1] / valid_fcfs[-3]) ** (1 / 2) - 1.0
            # Clamp to reasonable bounds (-5% to +25%)
            growth_rate = max(-0.05, min(cagr, 0.25))
            growth_method = f"historical_3yr_cagr ({growth_rate:.1%})"
        elif len(valid_fcfs) >= 2 and valid_fcfs[-2] > 0 and valid_fcfs[-1] > 0:
            yoy = (valid_fcfs[-1] / valid_fcfs[-2]) - 1.0
            growth_rate = max(-0.05, min(yoy, 0.20))
            growth_method = f"historical_yoy ({growth_rate:.1%})"
        else:
            growth_rate = 0.06
            growth_method = "conservative_default (6.0%)"

    # Validate WACC vs Terminal Growth
    if wacc <= terminal_growth:
        wacc = terminal_growth + 0.01

    # Project FCFs
    projections: list[dict[str, Any]] = []
    current_fcf = base_fcf
    pv_projected_fcf = 0.0

    for t in range(1, forecast_years + 1):
        # Slightly taper growth toward terminal rate in later years
        taper_factor = 1.0 - (0.15 * (t - 1) / max(1, forecast_years - 1))
        period_growth = growth_rate * taper_factor
        current_fcf = current_fcf * (1.0 + period_growth)
        discount_factor = 1.0 / ((1.0 + wacc) ** t)
        pv = current_fcf * discount_factor
        pv_projected_fcf += pv
        projections.append({
            "year": t,
            "projected_fy": latest_fy + t,
            "growth_rate": period_growth,
            "fcf": current_fcf,
            "discount_factor": discount_factor,
            "pv": pv,
        })

    # Terminal Value using Gordon Growth
    final_fcf = projections[-1]["fcf"]
    terminal_fcf = final_fcf * (1.0 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    terminal_discount_factor = 1.0 / ((1.0 + wacc) ** forecast_years)
    pv_terminal_value = terminal_value * terminal_discount_factor

    # Enterprise Value & Equity Bridge
    enterprise_value = pv_projected_fcf + pv_terminal_value
    implied_equity_value = enterprise_value - net_debt  # EV + Cash - Debt

    implied_share_price = (
        implied_equity_value / shares_diluted
        if shares_diluted and shares_diluted > 0
        else None
    )

    # 2D Sensitivity Matrix: WACC vs Terminal Growth
    wacc_steps = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
    growth_steps = [
        terminal_growth - 0.01,
        terminal_growth - 0.005,
        terminal_growth,
        terminal_growth + 0.005,
        terminal_growth + 0.01,
    ]

    sensitivity_matrix: list[dict[str, Any]] = []
    for w in wacc_steps:
        row: dict[str, Any] = {"wacc": round(w * 100, 2), "values": []}
        for g in growth_steps:
            if w <= g:
                implied_price = None
            else:
                # PV of projections with specific w
                sum_pv = 0.0
                fcf_cur = base_fcf
                for t in range(1, forecast_years + 1):
                    taper = 1.0 - (0.15 * (t - 1) / max(1, forecast_years - 1))
                    fcf_cur = fcf_cur * (1.0 + growth_rate * taper)
                    sum_pv += fcf_cur / ((1.0 + w) ** t)
                tv = (fcf_cur * (1.0 + g)) / (w - g)
                pv_tv = tv / ((1.0 + w) ** forecast_years)
                ev = sum_pv + pv_tv
                eq_val = ev - net_debt
                implied_price = (
                    eq_val / shares_diluted
                    if shares_diluted and shares_diluted > 0
                    else None
                )
            row["values"].append({
                "terminal_growth": round(g * 100, 2),
                "implied_share_price": round(implied_price, 2) if implied_price is not None else None,
            })
        sensitivity_matrix.append(row)

    # Valuation Bridge Waterfall steps ($ in billions)
    waterfall = [
        {"measure": "relative", "label": "PV of Projections", "value": round(pv_projected_fcf / 1e9, 2)},
        {"measure": "relative", "label": "PV of Terminal Value", "value": round(pv_terminal_value / 1e9, 2)},
        {"measure": "total", "label": "Enterprise Value", "value": round(enterprise_value / 1e9, 2)},
        {"measure": "relative", "label": "(+) Cash & Investments", "value": round(total_cash / 1e9, 2)},
        {"measure": "relative", "label": "(-) Total Debt", "value": round(-total_debt / 1e9, 2)},
        {"measure": "total", "label": "Implied Equity Value", "value": round(implied_equity_value / 1e9, 2)},
    ]

    return {
        "ticker": ticker,
        "latest_fy": latest_fy,
        "assumptions": {
            "wacc": wacc,
            "terminal_growth": terminal_growth,
            "forecast_years": forecast_years,
            "growth_rate_used": growth_rate,
            "growth_method": growth_method,
        },
        "historical_fcf": history,
        "base_fcf": base_fcf,
        "projections": projections,
        "pv_projected_fcf": pv_projected_fcf,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "terminal_value_pct_of_ev": safe_div(pv_terminal_value, enterprise_value),
        "enterprise_value": enterprise_value,
        "balance_sheet_bridge": {
            "cash_and_equivalents": total_cash,
            "total_debt": total_debt,
            "net_debt": net_debt,
            "shares_diluted": shares_diluted,
        },
        "implied_equity_value": implied_equity_value,
        "implied_share_price": implied_share_price,
        "waterfall": waterfall,
        "sensitivity_matrix": {
            "wacc_axis": [round(w * 100, 2) for w in wacc_steps],
            "growth_axis": [round(g * 100, 2) for g in growth_steps],
            "rows": sensitivity_matrix,
        },
    }
