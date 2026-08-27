from __future__ import annotations

import re
from datetime import date
from typing import Any

from finchat.collect.edgar import Edgar

USD = "usd"
SHARES = "shares"
PER_SHARE = "usd_per_share"

METRIC_TAGS: dict[str, tuple[list[str], str]] = {
    "revenue": ([
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
    ], USD),
    "cogs": ([
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
        "CostOfGoodsSold",
        "CostOfServices",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
    ], USD),
    "gross_profit": (["GrossProfit"], USD),
    "operating_income": (["OperatingIncomeLoss"], USD),
    "sga": (["SellingGeneralAndAdministrativeExpense"], USD),
    "rd": (["ResearchAndDevelopmentExpense"], USD),
    "net_income": (["NetIncomeLoss"], USD),
    "pretax_income": ([
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ], USD),
    "income_tax": (["IncomeTaxExpenseBenefit"], USD),
    "interest_expense": ([
        "InterestExpense",
        "InterestExpenseNonoperating",
        "InterestExpenseDebt",
        "InterestIncomeExpenseNet",
    ], USD),
    "ebitda_proxy_da": ([
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "Depreciation",
    ], USD),
    "assets": (["Assets"], USD),
    "assets_current": (["AssetsCurrent"], USD),
    "cash": (["CashAndCashEquivalentsAtCarryingValue"], USD),
    "short_term_investments": ([
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    ], USD),
    "receivables": ([
        "ReceivablesNetCurrent",
        "AccountsReceivableNetCurrent",
        "AccountsNotesAndLoansReceivableNetCurrent",
    ], USD),
    "inventory": (["InventoryNet", "FIFOInventoryAmountNetOfReserves", "InventoryFinishedGoodsNetOfReserves"], USD),
    "ppe_net": (["PropertyPlantAndEquipmentNet", "PropertyAndEquipmentNet"], USD),
    "goodwill": (["Goodwill"], USD),
    "intangibles": ([
        "IntangibleAssetsNetExcludingGoodwill",
        "FiniteLivedIntangibleAssetsNet",
        "IntangibleAssetsNetExcludingGoodwillAndFiniteLivedIntangibleAssetsNetComprisingOtherIntangibleAssets",
    ], USD),
    "liabilities": (["Liabilities"], USD),
    "liabilities_current": (["LiabilitiesCurrent"], USD),
    "debt_current": (["DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings", "CommercialPaper"], USD),
    "long_term_debt": (["LongTermDebtNoncurrent", "LongTermDebt", "SecuredLongTermDebt"], USD),
    "equity": ([
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ], USD),
    "retained_earnings": (["RetainedEarningsAccumulatedDeficit"], USD),
    "cfo": ([
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ], USD),
    "capex": ([
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquirePropertyPlantAndEquipmentAndIntangibleAssets",
    ], USD),
    "shares_diluted": ([
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfDilutedSharesOutstandingAfterAdjustmentForStockDistribution",
    ], SHARES),
    "shares_basic": (["WeightedAverageNumberOfSharesOutstandingBasic"], SHARES),
    "eps_diluted": (["EarningsPerShareDiluted"], PER_SHARE),
    "shares_outstanding_cover": (["EntityCommonStockSharesOutstanding"], SHARES),
}


def _iter_entries(companyfacts: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    facts = companyfacts.get("facts", {})
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for ns in ("us-gaap", "dei"):
        for tag, payload in facts.get(ns, {}).items():
            for unit_name, unit_entries in payload.get("units", {}).items():
                out.setdefault(tag, {}).setdefault(unit_name, []).extend(unit_entries)
    return out


def _span_days(start: str | None, end: str) -> int | None:
    if not start:
        return None
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except Exception:
        return None


def extract_annual_facts(companyfacts: dict[str, Any], fy_start: int, fy_end: int) -> dict[int, dict[str, dict[str, Any]]]:
    """Return {fy_label: {metric: {value, tag, accession, filed}}}.

    Fiscal-year label is derived from the period end date's calendar year,
    which matches the FY naming convention of the selected universe. When a
    metric has several candidate tags, the first tag present wins; ties within
    a tag are resolved by latest filing date (restated values).
    """
    index = _iter_entries(companyfacts)
    per_metric: dict[int, dict[str, dict[str, Any]]] = {}

    for metric, (tags, unit_class) in METRIC_TAGS.items():
        best_by_period: dict[tuple[str, str], dict[str, Any]] = {}
        for tag in tags:
            units = index.get(tag)
            if not units:
                continue
            for unit_name, entries in units.items():
                if unit_class == USD and not unit_name.startswith("USD"):
                    continue
                if unit_class == SHARES and "shares" not in unit_name:
                    continue
                if unit_class == PER_SHARE and not unit_name.startswith("USD/shares"):
                    continue
                for e in entries:
                    end = e.get("end")
                    if not end or e.get("form") != "10-K":
                        continue
                    start = e.get("start")
                    span = _span_days(start, end)
                    if start is None:
                        pass
                    elif span is None or not (300 <= span <= 400):
                        continue
                    elif e.get("fp") != "FY":
                        continue
                    label = int(end[:4])
                    if not (fy_start <= label <= fy_end):
                        continue
                    key = (tag, end)
                    prev = best_by_period.get(key)
                    if prev is None or (e.get("filed", "") > prev["filed"]):
                        best_by_period[key] = {
                            "value": float(e["val"]),
                            "tag": tag,
                            "accession": e.get("accn"),
                            "filed": e.get("filed", ""),
                            "end": end,
                        }
        for (tag, end), chosen in best_by_period.items():
            label = int(end[:4])
            slot = per_metric.setdefault(label, {})
            cur = slot.get(metric)
            if cur is None or chosen["tag"] == cur["tag"]:
                slot[metric] = chosen
            else:
                slot.setdefault(f"_{metric}_alts", {})[chosen["tag"]] = chosen

    for year in list(per_metric):
        row = per_metric[year]
        rev, cogs, gp = row.get("revenue"), row.get("cogs"), row.get("gross_profit")
        if gp is None and rev and cogs:
            row["gross_profit"] = {**rev, "value": rev["value"] - cogs["value"], "tag": f"{rev['tag']}-{cogs['tag']}"}
        assets, liab, eq = row.get("assets"), row.get("liabilities"), row.get("equity")
        if liabilities_missing(liab, assets, eq):
            base = assets or eq
            if assets and eq:
                src = max(assets, eq, key=lambda x: x.get("filed", ""))
                row["liabilities"] = {**src, "value": assets["value"] - eq["value"], "tag": "Assets-StockholdersEquity"}
        dc, ltd = row.get("debt_current"), row.get("long_term_debt")
        if dc or ltd:
            parts = [x for x in (dc, ltd) if x]
            base = parts[0]
            total_debt = sum(x["value"] for x in parts)
            row["total_debt"] = {**base, "value": total_debt, "tag": "+".join(x["tag"] for x in parts)}
    return per_metric


def liabilities_missing(liab: dict | None, assets: dict | None, eq: dict | None) -> bool:
    return liab is None and assets is not None and eq is not None


def collect_ticker(ticker: str, cik: str | None, name_hint: str | None,
                   fy_start: int, fy_end: int) -> tuple[str, str, dict[int, dict[str, dict[str, Any]]]]:
    edgar = Edgar()
    cik, title = edgar.cik_for(ticker)
    cf = edgar.companyfacts(cik)
    entity = cf.get("entityName") or name_hint or ticker
    data = extract_annual_facts(cf, fy_start, fy_end)
    sic = ""
    try:
        sic = str(cf.get("sic", "") or "")
    except Exception:
        pass
    return cik, entity or title, data


def normalize_accession(accn: str | None) -> str:
    if not accn:
        return ""
    return re.sub(r"[^0-9A-Za-z-]", "", accn)
