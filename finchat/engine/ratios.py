from __future__ import annotations

import math
from dataclasses import dataclass


def safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0 or (isinstance(a, float) and math.isnan(a)) or (isinstance(b, float) and math.isnan(b)):
        return None
    return a / b


@dataclass
class YearData:
    ticker: str
    fy: int
    m: dict[str, float | None]

    def __getitem__(self, key: str) -> float | None:
        return self.m.get(key)

    def get(self, key: str, default: float | None = None) -> float | None:
        return self.m.get(key, default)


RATIO_DEFS: dict[str, str] = {
    "gross_margin": "Gross profit / revenue",
    "operating_margin": "Operating income / revenue",
    "net_margin": "Net income / revenue",
    "roa": "Net income / total assets",
    "roe": "Net income / shareholders' equity",
    "roic": "(Net income + interest expense*(1-0)) / (debt + equity - cash)",
    "asset_turnover": "Revenue / total assets",
    "inventory_turnover": "COGS / inventory",
    "receivable_days": "Receivables / revenue * 365",
    "current_ratio": "Current assets / current liabilities",
    "quick_ratio": "(Cash + ST investments) / current liabilities",
    "cash_ratio": "Cash / current liabilities",
    "debt_to_equity": "Total debt / equity",
    "debt_to_assets": "Total debt / assets",
    "liabilities_to_assets": "Total liabilities / assets",
    "interest_coverage": "Operating income / interest expense",
    "working_capital_ratio": "Working capital / assets",
    "fcf_margin": "(CFO - capex) / revenue",
    "cfo_to_debt": "CFO / total debt",
    "rd_intensity": "R&D / revenue",
    "sga_intensity": "SG&A / revenue",
    "revenue_growth_pct": "YoY revenue growth (%)",
    "net_income_growth_pct": "YoY net income growth (%)",
    "earnings_yield": "EPS diluted / price",
}


def compute_ratios(cur: YearData, prev: YearData | None) -> dict[str, float | None]:
    m = dict(cur.m)
    if m.get("total_debt") is None and (m.get("debt_current") is not None
                                        or m.get("long_term_debt") is not None):
        m["total_debt"] = sum(v for v in (m.get("debt_current"), m.get("long_term_debt"))
                              if v is not None)
    r: dict[str, float | None] = {}

    rev = m.get("revenue")
    r["gross_margin"] = safe_div(m.get("gross_profit"), rev)
    r["operating_margin"] = safe_div(m.get("operating_income"), rev)
    r["net_margin"] = safe_div(m.get("net_income"), rev)
    r["roa"] = safe_div(m.get("net_income"), m.get("assets"))
    r["roe"] = safe_div(m.get("net_income"), m.get("equity"))

    nopat = None
    if m.get("net_income") is not None:
        nopat = m["net_income"] + ((m.get("interest_expense") or 0.0))
    invested = None
    if any(m.get(k) is not None for k in ("total_debt", "equity", "cash")):
        invested = sum(v for v in (m.get("total_debt"), m.get("equity"), -(m.get("cash") or 0.0))
                       if v is not None)
        if invested <= 0:
            invested = None
    r["roic"] = safe_div(nopat, invested)

    r["asset_turnover"] = safe_div(rev, m.get("assets"))
    r["inventory_turnover"] = safe_div(m.get("cogs"), m.get("inventory"))
    recv_days = safe_div(m.get("receivables"), rev)
    r["receivable_days"] = recv_days * 365 if recv_days is not None else None

    cl = m.get("liabilities_current")
    liquid = None
    if m.get("cash") is not None:
        liquid = m["cash"] + (m.get("short_term_investments") or 0.0)
    elif m.get("assets_current") is not None and m.get("inventory") is not None:
        liquid = m["assets_current"] - m["inventory"]
    r["quick_ratio"] = safe_div(liquid, cl)
    r["cash_ratio"] = safe_div(m.get("cash"), cl)

    wc = None
    if m.get("assets_current") is not None and cl is not None:
        wc = m["assets_current"] - cl
    r["working_capital_ratio"] = safe_div(wc, m.get("assets"))

    fcf = None
    if m.get("cfo") is not None and m.get("capex") is not None:
        fcf = m["cfo"] - m["capex"]
    r["fcf_margin"] = safe_div(fcf, rev)
    r["cfo_to_debt"] = safe_div(m.get("cfo"), m.get("total_debt"))
    r["rd_intensity"] = safe_div(m.get("rd"), rev)
    r["sga_intensity"] = safe_div(m.get("sga"), rev)

    if prev is not None and prev.get("revenue"):
        r["revenue_growth_pct"] = (rev / prev["revenue"] - 1) * 100 if rev is not None else None
    else:
        r["revenue_growth_pct"] = None
    if prev is not None and prev.get("net_income"):
        ni = m.get("net_income")
        r["net_income_growth_pct"] = (ni / prev["net_income"] - 1) * 100 if ni is not None else None
    else:
        r["net_income_growth_pct"] = None

    for name in ("current_ratio", "debt_to_equity", "debt_to_assets", "liabilities_to_assets",
                 "interest_coverage", "inventory_turnover"):
        num, den = {
            "current_ratio": (m.get("assets_current"), cl),
            "debt_to_equity": (m.get("total_debt"), m.get("equity")),
            "debt_to_assets": (m.get("total_debt"), m.get("assets")),
            "liabilities_to_assets": (m.get("liabilities"), m.get("assets")),
            "interest_coverage": (m.get("operating_income"), m.get("interest_expense")),
            "inventory_turnover": (m.get("cogs"), m.get("inventory")),
        }[name]
        r[name] = safe_div(num, den)

    return r


DUPONT_INPUTS = ("net_margin", "asset_turnover")


def dupont_3step(ratios: dict[str, float | None], equity: float | None,
                 net_income: float | None, assets: float | None) -> dict[str, float | None]:
    nm, at = ratios.get("net_margin"), ratios.get("asset_turnover")
    em = safe_div(assets, equity)
    roe_calc = None
    if nm is not None and at is not None and em is not None:
        roe_calc = nm * at * em
    return {"dupont_net_margin": nm, "dupont_asset_turnover": at,
            "dupont_equity_multiplier": em, "roe_dupont": roe_calc}
