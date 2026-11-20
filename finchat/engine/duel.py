from __future__ import annotations

from typing import Any

from finchat.chatbot.tools import (
    FRACTION_PCT_METRICS,
    PERCENT_METRICS,
    SCORE_METRICS,
    format_metric_value,
    get_available_years,
)
from finchat.config import UNIVERSE
from finchat.db import get_db

PILLARS = {
    "Profitability": [
        ("gross_margin", "Gross Margin", "higher"),
        ("operating_margin", "Operating Margin", "higher"),
        ("net_margin", "Net Profit Margin", "higher"),
        ("roe", "Return on Equity (ROE)", "higher"),
        ("roic", "Return on Invested Capital (ROIC)", "higher"),
        ("fcf_margin", "Free Cash Flow Margin", "higher"),
    ],
    "Financial Health & Solvency": [
        ("altman_z", "Altman Z-Score (Distress Risk)", "higher"),
        ("current_ratio", "Current Ratio (Liquidity)", "higher"),
        ("debt_to_equity", "Debt-to-Equity (Leverage)", "lower"),
    ],
    "Accounting Quality": [
        ("piotroski_f", "Piotroski F-Score (Health 0-9)", "higher"),
        ("beneish_m", "Beneish M-Score (Manipulation)", "lower"),
    ],
    "Growth": [
        ("revenue_growth_pct", "YoY Revenue Growth", "higher"),
        ("net_income_growth_pct", "YoY Net Income Growth", "higher"),
    ],
}


def compare_companies(ticker_a: str, ticker_b: str, year: int | None = None) -> dict[str, Any]:
    t_a = (ticker_a or "").upper().strip()
    t_b = (ticker_b or "").upper().strip()

    with get_db() as con:
        years_a = set(get_available_years(con, t_a))
        years_b = set(get_available_years(con, t_b))

        if not years_a:
            return {"error": f"No financial data available for {t_a}"}
        if not years_b:
            return {"error": f"No financial data available for {t_b}"}

        common = sorted(years_a & years_b)
        if not common:
            return {"error": f"No overlapping fiscal years found between {t_a} and {t_b}"}

        if year is None or year not in common:
            year = common[-1]

        # Fetch ratios for both
        ratios_a = {
            r["metric"]: r["value"]
            for r in con.execute(
                "SELECT metric, value FROM ratios WHERE ticker=? AND fy=?", (t_a, year)
            ).fetchall()
        }
        ratios_b = {
            r["metric"]: r["value"]
            for r in con.execute(
                "SELECT metric, value FROM ratios WHERE ticker=? AND fy=?", (t_b, year)
            ).fetchall()
        }

        # Fetch scores for both
        score_row_a = con.execute("SELECT * FROM scores WHERE ticker=? AND fy=?", (t_a, year)).fetchone()
        score_row_b = con.execute("SELECT * FROM scores WHERE ticker=? AND fy=?", (t_b, year)).fetchone()

    scores_a = dict(score_row_a) if score_row_a else {}
    scores_b = dict(score_row_b) if score_row_b else {}

    results_by_pillar: dict[str, list[dict[str, Any]]] = {}
    wins_a = 0
    wins_b = 0
    ties = 0

    for pillar, metrics in PILLARS.items():
        results_by_pillar[pillar] = []
        for metric_id, metric_label, direction in metrics:
            # Lookup value
            if metric_id in SCORE_METRICS:
                val_a = scores_a.get(metric_id)
                val_b = scores_b.get(metric_id)
            else:
                val_a = ratios_a.get(metric_id)
                val_b = ratios_b.get(metric_id)

            if val_a is None or val_b is None:
                winner = "N/A"
            else:
                # Comparison logic with small epsilon tolerance
                eps = 1e-4
                if abs(val_a - val_b) <= eps:
                    winner = "TIE"
                    ties += 1
                elif direction == "higher":
                    if val_a > val_b:
                        winner = t_a
                        wins_a += 1
                    else:
                        winner = t_b
                        wins_b += 1
                else:  # direction == "lower"
                    if val_a < val_b:
                        winner = t_a
                        wins_a += 1
                    else:
                        winner = t_b
                        wins_b += 1

            results_by_pillar[pillar].append({
                "metric_id": metric_id,
                "metric_label": metric_label,
                "val_a": val_a,
                "val_b": val_b,
                "formatted_a": format_metric_value(metric_id, val_a),
                "formatted_b": format_metric_value(metric_id, val_b),
                "winner": winner,
                "direction": direction,
            })

    pillar_winners: dict[str, str] = {}
    pillar_stats: dict[str, dict[str, int]] = {}
    for p_name, p_items in results_by_pillar.items():
        p_wins_a = sum(1 for m in p_items if m["winner"] == t_a)
        p_wins_b = sum(1 for m in p_items if m["winner"] == t_b)
        p_ties = sum(1 for m in p_items if m["winner"] in ("TIE", "Tie"))
        pillar_stats[p_name] = {"wins_a": p_wins_a, "wins_b": p_wins_b, "ties": p_ties}
        if p_wins_a > p_wins_b:
            pillar_winners[p_name] = f"{t_a} ({p_wins_a}-{p_wins_b})"
        elif p_wins_b > p_wins_a:
            pillar_winners[p_name] = f"{t_b} ({p_wins_b}-{p_wins_a})"
        else:
            pillar_winners[p_name] = f"Tie ({p_wins_a}-{p_wins_b})"

    if wins_a > wins_b:
        overall_winner = t_a
        verdict = f"{UNIVERSE.get(t_a, t_a)} ({t_a}) outperforms {UNIVERSE.get(t_b, t_b)} ({t_b}) winning {wins_a} to {wins_b}."
    elif wins_b > wins_a:
        overall_winner = t_b
        verdict = f"{UNIVERSE.get(t_b, t_b)} ({t_b}) outperforms {UNIVERSE.get(t_a, t_a)} ({t_a}) winning {wins_b} to {wins_a}."
    else:
        overall_winner = "TIE"
        verdict = f"A dead heat tie between {t_a} and {t_b} at {wins_a} wins each."

    return {
        "ticker_a": t_a,
        "ticker_b": t_b,
        "name_a": UNIVERSE.get(t_a, t_a),
        "name_b": UNIVERSE.get(t_b, t_b),
        "year": year,
        "available_common_years": common,
        "wins_a": wins_a,
        "wins_b": wins_b,
        "ties": ties,
        "overall_winner": overall_winner,
        "pillar_winners": pillar_winners,
        "pillar_stats": pillar_stats,
        "verdict": verdict,
        "pillars": results_by_pillar,
        "source": {
            "type": "structured_lookup",
            "table": "ratios and scores databases",
            "period": f"FY{year}",
        },
    }
