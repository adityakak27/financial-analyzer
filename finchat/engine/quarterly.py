from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from finchat.collect.edgar import Edgar
from finchat.collect.facts import METRIC_TAGS, PER_SHARE, SHARES, USD, _iter_entries, _span_days
from finchat.config import CACHE_DIR, FY_END, FY_START
from finchat.db import get_db, init_db, upsert

FLOW_METRICS = {
    "revenue", "cogs", "gross_profit", "operating_income", "sga", "rd",
    "net_income", "pretax_income", "income_tax", "interest_expense",
    "ebitda_proxy_da", "cfo", "capex",
}

BALANCE_METRICS = {
    "assets", "assets_current", "cash", "short_term_investments", "receivables",
    "inventory", "ppe_net", "goodwill", "intangibles", "liabilities",
    "liabilities_current", "debt_current", "long_term_debt", "equity",
    "retained_earnings", "total_debt",
}


def safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    try:
        return float(a) / float(b)
    except (ZeroDivisionError, OverflowError, ValueError):
        return None


def extract_quarterly_statements_for_facts(
    companyfacts: dict[str, Any],
    annual_statements: dict[int, dict[str, float]],
    fy_start: int = FY_START,
    fy_end: int = FY_END + 2,
) -> dict[tuple[int, str], dict[str, dict[str, Any]]]:
    """Extract discrete Q1, Q2, Q3 from 10-Q entries and reconstruct Q4 via 10-K reconciliation."""
    index = _iter_entries(companyfacts)
    # raw entries by (fy, fq, metric) -> list of entries
    raw_quarterly: dict[tuple[int, str], dict[str, list[dict[str, Any]]]] = {}
    ytd_cashflow: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}

    for metric, (tags, unit_class) in METRIC_TAGS.items():
        for tag in tags:
            units = index.get(tag, {})
            for unit_name, entries in units.items():
                if unit_class == USD and not unit_name.startswith("USD"):
                    continue
                if unit_class == SHARES and "shares" not in unit_name:
                    continue
                if unit_class == PER_SHARE and not unit_name.startswith("USD/shares"):
                    continue

                for e in entries:
                    if e.get("form") != "10-Q":
                        continue
                    fp = e.get("fp")
                    if fp not in ("Q1", "Q2", "Q3"):
                        continue
                    fy = e.get("fy")
                    if not fy or not (fy_start <= fy <= fy_end):
                        continue

                    start = e.get("start")
                    end = e.get("end")
                    span = _span_days(start, end)
                    key = (int(fy), str(fp))

                    if start is None:
                        # Instantaneous balance sheet item
                        raw_quarterly.setdefault(key, {}).setdefault(metric, []).append(e)
                    elif metric in ("cfo", "capex"):
                        # Cash flow in 10-Q is typically reported cumulatively (YTD)
                        # Save YTD entry if span is consistent with fp
                        # Q1: 60-115 days, Q2: 150-210 days, Q3: 240-300 days
                        is_valid_ytd = (
                            (fp == "Q1" and 60 <= (span or 0) <= 115) or
                            (fp == "Q2" and 150 <= (span or 0) <= 210) or
                            (fp == "Q3" and 240 <= (span or 0) <= 300)
                        )
                        if is_valid_ytd:
                            prev_ytd = ytd_cashflow.setdefault(key, {}).get(metric)
                            if prev_ytd is None or e.get("filed", "") > prev_ytd.get("filed", ""):
                                ytd_cashflow[key][metric] = e
                        if 60 <= (span or 0) <= 115:
                            raw_quarterly.setdefault(key, {}).setdefault(metric, []).append(e)
                    else:
                        # Income statement item: strictly 3-month discrete quarter
                        if span is not None and 60 <= span <= 115:
                            raw_quarterly.setdefault(key, {}).setdefault(metric, []).append(e)

    # Resolve best single entry per metric for Q1, Q2, Q3
    out: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}

    all_keys = sorted(set(raw_quarterly.keys()) | set(ytd_cashflow.keys()))
    for key in all_keys:
        slot: dict[str, dict[str, Any]] = {}
        # Balance sheet and income statement metrics
        metrics_dict = raw_quarterly.get(key, {})
        for metric, entries in metrics_dict.items():
            best = max(entries, key=lambda x: x.get("filed", ""))
            slot[metric] = {
                "value": float(best["val"]),
                "tag": best.get("tag", metric),
                "accession": best.get("accn", ""),
                "filed": best.get("filed", ""),
                "end": best.get("end", ""),
            }

        out[key] = slot

    # Compute discrete cash flow numbers from YTD if not directly given
    for fy in range(fy_start, fy_end + 1):
        for metric in ("cfo", "capex"):
            q1_entry = ytd_cashflow.get((fy, "Q1"), {}).get(metric)
            q2_entry = ytd_cashflow.get((fy, "Q2"), {}).get(metric)
            q3_entry = ytd_cashflow.get((fy, "Q3"), {}).get(metric)

            # Q1
            if (fy, "Q1") in out and metric not in out[(fy, "Q1")] and q1_entry:
                out[(fy, "Q1")][metric] = {
                    "value": float(q1_entry["val"]),
                    "tag": q1_entry.get("tag", metric),
                    "accession": q1_entry.get("accn", ""),
                    "filed": q1_entry.get("filed", ""),
                    "end": q1_entry.get("end", ""),
                }
            # Q2 = YTD2 - YTD1
            if (fy, "Q2") in out and metric not in out[(fy, "Q2")] and q2_entry and q1_entry:
                val = float(q2_entry["val"]) - float(q1_entry["val"])
                out[(fy, "Q2")][metric] = {
                    "value": val,
                    "tag": f"{q2_entry.get('tag', metric)}_discrete",
                    "accession": q2_entry.get("accn", ""),
                    "filed": q2_entry.get("filed", ""),
                    "end": q2_entry.get("end", ""),
                }
            # Q3 = YTD3 - YTD2
            if (fy, "Q3") in out and metric not in out[(fy, "Q3")] and q3_entry and q2_entry:
                val = float(q3_entry["val"]) - float(q2_entry["val"])
                out[(fy, "Q3")][metric] = {
                    "value": val,
                    "tag": f"{q3_entry.get('tag', metric)}_discrete",
                    "accession": q3_entry.get("accn", ""),
                    "filed": q3_entry.get("filed", ""),
                    "end": q3_entry.get("end", ""),
                }

    # Reconstruct Q4 for completed fiscal years where annual 10-K data exists
    for fy, annual_m in annual_statements.items():
        q1 = out.get((fy, "Q1"), {})
        q2 = out.get((fy, "Q2"), {})
        q3 = out.get((fy, "Q3"), {})

        q4_slot: dict[str, dict[str, Any]] = {}
        for metric, annual_val in annual_m.items():
            if annual_val is None:
                continue
            if metric in FLOW_METRICS:
                # Q4 = Annual - (Q1 + Q2 + Q3)
                v1 = q1.get(metric, {}).get("value")
                v2 = q2.get(metric, {}).get("value")
                v3 = q3.get(metric, {}).get("value")
                if v1 is not None and v2 is not None and v3 is not None:
                    q4_slot[metric] = {
                        "value": annual_val - (v1 + v2 + v3),
                        "tag": "reconciled_10K_minus_Q1_Q2_Q3",
                        "accession": "",
                        "filed": "",
                        "end": f"{fy}-12-31",
                    }
            elif metric in BALANCE_METRICS:
                # Q4 balance sheet is the fiscal year end 10-K balance sheet
                q4_slot[metric] = {
                    "value": annual_val,
                    "tag": "10K_fy_end",
                    "accession": "",
                    "filed": "",
                    "end": f"{fy}-12-31",
                }

        if q4_slot:
            out[(fy, "Q4")] = q4_slot

    # Synthesize total debt, gross profit, and liabilities if missing
    for key, slot in out.items():
        rev = slot.get("revenue", {}).get("value")
        cogs = slot.get("cogs", {}).get("value")
        if "gross_profit" not in slot and rev is not None and cogs is not None:
            slot["gross_profit"] = {
                "value": rev - cogs,
                "tag": "Revenue-COGS",
                "accession": "",
                "filed": "",
                "end": slot.get("revenue", {}).get("end", ""),
            }

        dc = slot.get("debt_current", {}).get("value") or 0.0
        ltd = slot.get("long_term_debt", {}).get("value") or 0.0
        if "total_debt" not in slot and (dc > 0 or ltd > 0):
            slot["total_debt"] = {
                "value": dc + ltd,
                "tag": "DebtCurrent+LongTermDebt",
                "accession": "",
                "filed": "",
                "end": "",
            }

        assets = slot.get("assets", {}).get("value")
        eq = slot.get("equity", {}).get("value")
        if "liabilities" not in slot and assets is not None and eq is not None:
            slot["liabilities"] = {
                "value": assets - eq,
                "tag": "Assets-Equity",
                "accession": "",
                "filed": "",
                "end": "",
            }

    return out


def compute_quarterly_and_ttm_ratios(
    quarterly_stmts: dict[tuple[int, str], dict[str, dict[str, Any]]],
) -> tuple[dict[tuple[int, str], dict[str, float]], dict[tuple[int, str], dict[str, float]]]:
    """Compute both discrete quarterly ratios and continuous Trailing Twelve Month (TTM) ratios."""
    sorted_quarters = sorted(quarterly_stmts.keys())
    quarterly_ratios: dict[tuple[int, str], dict[str, float]] = {}
    ttm_ratios: dict[tuple[int, str], dict[str, float]] = {}

    # 1. Discrete Quarterly Ratios
    for idx, key in enumerate(sorted_quarters):
        slot = quarterly_stmts[key]
        vals = {m: d["value"] for m, d in slot.items() if d.get("value") is not None}

        rev = vals.get("revenue")
        gp = vals.get("gross_profit")
        oi = vals.get("operating_income")
        ni = vals.get("net_income")
        cfo = vals.get("cfo")
        capex = vals.get("capex")
        fcf = (cfo - capex) if cfo is not None and capex is not None else None

        ca = vals.get("assets_current")
        cl = vals.get("liabilities_current")
        cash = vals.get("cash")
        debt = vals.get("total_debt")
        eq = vals.get("equity")
        assets = vals.get("assets")

        q_r: dict[str, float] = {}
        for r_name, r_val in [
            ("gross_margin", safe_div(gp, rev)),
            ("operating_margin", safe_div(oi, rev)),
            ("net_margin", safe_div(ni, rev)),
            ("fcf_margin", safe_div(fcf, rev)),
            ("current_ratio", safe_div(ca, cl)),
            ("cash_ratio", safe_div(cash, cl)),
            ("debt_to_equity", safe_div(debt, eq)),
            ("debt_to_assets", safe_div(debt, assets)),
        ]:
            if r_val is not None:
                q_r[r_name] = r_val

        # YoY growth for this quarter (vs 4 quarters ago)
        if idx >= 4:
            prev_key = sorted_quarters[idx - 4]
            prev_vals = {m: d["value"] for m, d in quarterly_stmts[prev_key].items() if d.get("value") is not None}
            prev_rev = prev_vals.get("revenue")
            if rev is not None and prev_rev is not None and prev_rev != 0:
                q_r["revenue_growth_pct"] = ((rev - prev_rev) / abs(prev_rev)) * 100.0

            prev_ni = prev_vals.get("net_income")
            if ni is not None and prev_ni is not None and prev_ni != 0:
                q_r["net_income_growth_pct"] = ((ni - prev_ni) / abs(prev_ni)) * 100.0

        quarterly_ratios[key] = q_r

    # 2. TTM Ratios (4-quarter rolling window)
    for idx in range(3, len(sorted_quarters)):
        key = sorted_quarters[idx]
        window_keys = sorted_quarters[idx - 3 : idx + 1]

        # Latest balance sheet at end of quarter
        cur_slot = quarterly_stmts[key]
        cur_vals = {m: d["value"] for m, d in cur_slot.items() if d.get("value") is not None}

        # Sum flow items across the 4 quarters
        ttm_flows: dict[str, float] = {}
        for flow_m in FLOW_METRICS:
            win_vals = [quarterly_stmts[k].get(flow_m, {}).get("value") for k in window_keys]
            if all(v is not None for v in win_vals):
                ttm_flows[flow_m] = sum(win_vals)

        ttm_r: dict[str, float] = {}
        rev = ttm_flows.get("revenue")
        gp = ttm_flows.get("gross_profit")
        oi = ttm_flows.get("operating_income")
        ni = ttm_flows.get("net_income")
        cfo = ttm_flows.get("cfo")
        capex = ttm_flows.get("capex")
        fcf = (cfo - capex) if cfo is not None and capex is not None else None

        ca = cur_vals.get("assets_current")
        cl = cur_vals.get("liabilities_current")
        cash = cur_vals.get("cash")
        debt = cur_vals.get("total_debt")
        eq = cur_vals.get("equity")
        assets = cur_vals.get("assets")
        interest = ttm_flows.get("interest_expense", 0.0)

        # Store TTM totals as ratios/metrics too for easy plotting
        if rev is not None:
            ttm_r["revenue"] = rev
        if ni is not None:
            ttm_r["net_income"] = ni
        if fcf is not None:
            ttm_r["fcf"] = fcf

        for r_name, r_val in [
            ("gross_margin", safe_div(gp, rev)),
            ("operating_margin", safe_div(oi, rev)),
            ("net_margin", safe_div(ni, rev)),
            ("fcf_margin", safe_div(fcf, rev)),
            ("roe", safe_div(ni, eq)),
            ("roa", safe_div(ni, assets)),
            ("roic", safe_div(ni + (interest or 0.0), (debt or 0.0) + (eq or 0.0) - (cash or 0.0)) if (ni is not None and (debt or eq)) else None),
            ("current_ratio", safe_div(ca, cl)),
            ("debt_to_equity", safe_div(debt, eq)),
            ("debt_to_assets", safe_div(debt, assets)),
        ]:
            if r_val is not None:
                ttm_r[r_name] = r_val

        ttm_ratios[key] = ttm_r

    return quarterly_ratios, ttm_ratios


def populate_quarterly_data(tickers: list[str] | None = None) -> dict[str, int]:
    """Ingest and compute quarterly statements and ratios into sqlite db."""
    init_db()
    with get_db() as con:
        if not tickers:
            tickers = [r["ticker"] for r in con.execute("SELECT DISTINCT ticker FROM companies").fetchall()]

        # load annual statements for reconciliation
        annual_stmts: dict[str, dict[int, dict[str, float]]] = {}
        for r in con.execute("SELECT ticker, fy, metric, value FROM statements").fetchall():
            if r["value"] is not None:
                annual_stmts.setdefault(r["ticker"], {}).setdefault(int(r["fy"]), {})[r["metric"]] = float(r["value"])

    edgar = Edgar()
    counts: dict[str, int] = {}

    for ticker in tickers:
        t = ticker.upper().strip()
        try:
            cik, _ = edgar.cik_for(t)
            companyfacts = edgar.companyfacts(cik)
        except Exception as exc:
            print(f"[quarterly] Skipping {t}: {exc}")
            continue

        q_stmts = extract_quarterly_statements_for_facts(
            companyfacts,
            annual_stmts.get(t, {}),
            FY_START,
            FY_END + 2,
        )
        q_ratios, ttm_ratios = compute_quarterly_and_ttm_ratios(q_stmts)

        with get_db() as con:
            # Upsert quarterly statements
            for (fy, fq), metrics in q_stmts.items():
                for m, d in metrics.items():
                    upsert(con, "quarterly_statements", {
                        "ticker": t,
                        "fy": fy,
                        "fq": fq,
                        "metric": m,
                        "value": d.get("value"),
                        "tag": d.get("tag", m),
                        "accession": d.get("accession", ""),
                        "filed": d.get("filed", ""),
                        "end_date": d.get("end", ""),
                    })

            # Upsert quarterly ratios
            for (fy, fq), ratios in q_ratios.items():
                for m, val in ratios.items():
                    upsert(con, "quarterly_ratios", {
                        "ticker": t,
                        "fy": fy,
                        "fq": fq,
                        "period_type": "quarterly",
                        "metric": m,
                        "value": val,
                    })

            # Upsert TTM ratios
            for (fy, fq), ratios in ttm_ratios.items():
                for m, val in ratios.items():
                    upsert(con, "quarterly_ratios", {
                        "ticker": t,
                        "fy": fy,
                        "fq": fq,
                        "period_type": "ttm",
                        "metric": m,
                        "value": val,
                    })

        counts[t] = len(q_stmts)
        print(f"[quarterly] {t}: {len(q_stmts)} quarters ingested.")

    return counts


def get_quarterly_metric_series(
    ticker: str,
    metric: str,
    period_type: str = "quarterly",
) -> dict[str, Any]:
    """Retrieve multi-quarter historical metric series for plotting and analysis."""
    t = ticker.upper().strip()
    p_type = period_type.lower().strip()
    if p_type not in ("quarterly", "ttm"):
        p_type = "quarterly"

    with get_db() as con:
        # Check quarterly_ratios first
        rows = con.execute(
            """
            SELECT fy, fq, value FROM quarterly_ratios
            WHERE ticker=? AND metric=? AND period_type=?
            ORDER BY fy ASC, fq ASC
            """,
            (t, metric, p_type),
        ).fetchall()

        if not rows:
            # Fallback to quarterly_statements
            rows = con.execute(
                """
                SELECT fy, fq, value FROM quarterly_statements
                WHERE ticker=? AND metric=?
                ORDER BY fy ASC, fq ASC
                """,
                (t, metric),
            ).fetchall()

    from finchat.chatbot.tools import FRACTION_PCT_METRICS, PERCENT_METRICS, format_metric_value

    is_pct = metric in PERCENT_METRICS or metric in FRACTION_PCT_METRICS or metric.endswith("_pct") or metric.endswith("_margin")

    series = []
    for r in rows:
        val = r["value"]
        if val is None:
            continue
        period_label = f"FY{r['fy']}{r['fq']}"
        series.append({
            "period": period_label,
            "year": int(r["fy"]),
            "quarter": r["fq"],
            "value": float(val),
            "formatted": format_metric_value(metric, val),
        })

    return {
        "ticker": t,
        "metric": metric,
        "period_type": p_type,
        "is_percentage": is_pct,
        "series": series,
    }
