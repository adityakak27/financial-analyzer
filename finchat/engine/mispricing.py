"""Mispricing Radar engine: shared by the offline analysis study (analysis/scripts/)
and the live app (new DB tables + chatbot tools + frontend page), so both always
produce the same numbers.

Reuses the existing engine (ratios, scores, dcf) rather than recomputing fundamentals.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from finchat.config import UNIVERSE
from finchat.db import get_db, upsert
from finchat.engine.dcf import calculate_dcf

UNDERVALUED_Z = -1.0
OVERVALUED_Z = 1.0

# Raw fundamentals only. Altman Z, Piotroski F and Beneish M are deliberately NOT inputs: they
# are themselves composites of these same ratios (so they would double-count profitability,
# accruals and leverage), and Altman Z's X4 term contains market cap -- which would put market
# valuation inside the very Quality Score that is then regressed on a valuation multiple.
# The three scores are still evaluated separately in RQ3 (score_group_outcomes).
PILLAR_METRICS: dict[str, list[tuple[str, int]]] = {
    "profitability": [("roe", 1), ("roic", 1), ("operating_margin", 1), ("net_margin", 1)],
    "growth": [("revenue_growth_pct", 1), ("net_income_growth_pct", 1)],
    "safety": [("current_ratio", 1), ("debt_to_equity", -1), ("interest_coverage", 1)],
    "earnings_quality": [("fcf_margin", 1), ("accruals", -1)],
}
MIN_METRICS_PER_PILLAR = 2


def _sub_industry_map() -> dict[str, str]:
    from analysis.config import SUB_INDUSTRY
    return SUB_INDUSTRY


def build_panel(tickers: list[str] | None = None) -> pd.DataFrame:
    """One row per (ticker, fiscal_year): ratios + scores + textstats + filing metadata
    + sub-industry + next-year outcome columns."""
    tickers = tickers or list(UNIVERSE.keys())
    with get_db() as con:
        ratios = pd.read_sql(
            "SELECT ticker, fy, metric, value FROM ratios WHERE ticker IN (%s)"
            % ",".join("?" * len(tickers)), con, params=tickers,
        )
        scores = pd.read_sql(
            "SELECT ticker, fy, altman_z, altman_zone, piotroski_f, beneish_m, beneish_flag "
            "FROM scores WHERE ticker IN (%s)" % ",".join("?" * len(tickers)), con, params=tickers,
        )
        statements = pd.read_sql(
            "SELECT ticker, fy, metric, value FROM statements WHERE ticker IN (%s)"
            % ",".join("?" * len(tickers)), con, params=tickers,
        )
        filings = pd.read_sql(
            "SELECT ticker, fy, accession, filed FROM filings WHERE ticker IN (%s)"
            % ",".join("?" * len(tickers)), con, params=tickers,
        )
        textstats = pd.read_sql(
            "SELECT ticker, fy, section, polarity, neg_frac, pos_frac FROM textstats "
            "WHERE ticker IN (%s)" % ",".join("?" * len(tickers)), con, params=tickers,
        )

    ratio_wide = ratios.pivot_table(index=["ticker", "fy"], columns="metric", values="value", aggfunc="first")
    ratio_wide.columns = [str(c) for c in ratio_wide.columns]
    ratio_wide = ratio_wide.reset_index()

    stmt_wide = statements.pivot_table(index=["ticker", "fy"], columns="metric", values="value", aggfunc="first")
    stmt_wide.columns = [str(c) for c in stmt_wide.columns]
    stmt_wide = stmt_wide.reset_index()
    stmt_wide["accruals"] = np.where(
        stmt_wide["assets"].notna() & stmt_wide["net_income"].notna() & stmt_wide["cfo"].notna(),
        (stmt_wide["net_income"] - stmt_wide["cfo"]) / stmt_wide["assets"],
        np.nan,
    )

    panel = ratio_wide.merge(stmt_wide, on=["ticker", "fy"], how="outer", suffixes=("", "_stmt"))
    panel = panel.merge(scores, on=["ticker", "fy"], how="left")
    panel = panel.merge(filings, on=["ticker", "fy"], how="left")

    mda = textstats[textstats["section"] == "mda"][["ticker", "fy", "polarity", "neg_frac", "pos_frac"]]
    mda = mda.rename(columns={"polarity": "mda_polarity", "neg_frac": "mda_neg_frac", "pos_frac": "mda_pos_frac"})
    risk = textstats[textstats["section"] == "risk"][["ticker", "fy", "polarity"]]
    risk = risk.rename(columns={"polarity": "risk_polarity"})
    panel = panel.merge(mda, on=["ticker", "fy"], how="left")
    panel = panel.merge(risk, on=["ticker", "fy"], how="left")

    sub_map = _sub_industry_map()
    panel["sub_industry"] = panel["ticker"].map(sub_map).fillna("Unclassified")

    panel = panel.sort_values(["ticker", "fy"]).reset_index(drop=True)
    panel["rev_growth_next"] = panel.groupby("ticker")["revenue_growth_pct"].shift(-1)
    panel["ni_growth_next"] = panel.groupby("ticker")["net_income_growth_pct"].shift(-1)
    panel["roe_next"] = panel.groupby("ticker")["roe"].shift(-1)
    net_income_next = panel.groupby("ticker")["net_income"].shift(-1)
    panel["loss_next"] = np.where(net_income_next.notna(), (net_income_next < 0).astype(int), np.nan)

    return panel


def recompute_point_in_time_altman_z(panel: pd.DataFrame) -> pd.DataFrame:
    """Overwrite panel['altman_z'] with a version computed from POINT-IN-TIME market cap
    (price_at_filing * shares_diluted, from attach_prices()) rather than today's market cap.

    The `scores` table's altman_z (populated by `finchat analyze --market-data`) uses a single
    *current* market-cap snapshot per ticker for every historical fiscal year -- e.g. NVDA's
    FY2018 Altman Z in that table is ~486 because it divides NVDA's 2026 market cap by its 2018
    liabilities. That silently leaks years of future re-rating into the Safety pillar of every
    historical QualityScore, and must not be used for a point-in-time study. Requires
    attach_prices() to have already run (needs panel['market_cap']); call this before
    quality_score().
    """
    panel = panel.copy()
    wc = panel.get("assets_current") - panel.get("liabilities_current")
    re_ = panel.get("retained_earnings")
    ebit = panel.get("operating_income")
    ta = panel.get("assets")
    tl = panel.get("liabilities")
    rev = panel.get("revenue")
    equity_term = panel["market_cap"].where(panel["market_cap"].notna(), panel.get("equity"))

    ta_safe = ta.where(ta != 0)
    tl_safe = tl.where(tl != 0)
    z = (
        1.2 * (wc / ta_safe)
        + 1.4 * (re_ / ta_safe)
        + 3.3 * (ebit / ta_safe)
        + 0.6 * (equity_term / tl_safe)
        + 1.0 * (rev / ta_safe)
    )
    all_present = pd.concat([wc, re_, ebit, ta, tl, rev, equity_term], axis=1).notna().all(axis=1)
    panel["altman_z"] = z.where(all_present)
    return panel


def quality_score(panel: pd.DataFrame) -> pd.DataFrame:
    """Adds QualityScore (0-100) and the 4 pillar z-score columns, computed within each fiscal year."""
    panel = panel.copy()
    pillar_cols: dict[str, list[str]] = {}

    for pillar, metrics in PILLAR_METRICS.items():
        z_cols = []
        for metric, direction in metrics:
            if metric not in panel.columns:
                continue
            zcol = f"_z_{metric}"
            panel[zcol] = panel.groupby("fy")[metric].transform(
                lambda s: (s - s.mean()) / s.std(ddof=0) if s.std(ddof=0) else s * 0.0
            ) * direction
            z_cols.append(zcol)
        pillar_cols[pillar] = z_cols

    for pillar, z_cols in pillar_cols.items():
        n_available = panel[z_cols].notna().sum(axis=1)
        pillar_mean = panel[z_cols].mean(axis=1)
        panel[pillar] = np.where(n_available >= MIN_METRICS_PER_PILLAR, pillar_mean, np.nan)

    pillar_names = list(PILLAR_METRICS.keys())
    panel["_pillar_avg"] = panel[pillar_names].mean(axis=1, skipna=True)
    avg = panel["_pillar_avg"]
    lo, hi = avg.min(), avg.max()
    if hi > lo:
        panel["QualityScore"] = ((avg - lo) / (hi - lo) * 100).round(1)
    else:
        panel["QualityScore"] = 50.0
    panel.loc[panel[pillar_names].notna().sum(axis=1) == 0, "QualityScore"] = np.nan

    for pillar in pillar_names:
        p = panel[pillar]
        plo, phi = p.min(), p.max()
        if phi > plo:
            panel[f"{pillar}_score"] = ((p - plo) / (phi - plo) * 100).round(1)
        else:
            panel[f"{pillar}_score"] = pd.Series(50.0, index=panel.index).where(p.notna())

    drop_cols = [c for c in panel.columns if c.startswith("_z_") or c == "_pillar_avg"]
    return panel.drop(columns=drop_cols)


def _num(row: pd.Series, col: str, default: float = 0.0) -> float:
    v = row.get(col)
    return default if v is None or pd.isna(v) else float(v)


def _ev_for_row(row: pd.Series) -> float | None:
    cash = _num(row, "cash")
    st_inv = _num(row, "short_term_investments")
    debt = row.get("total_debt")
    if debt is None or pd.isna(debt):
        debt = _num(row, "debt_current") + _num(row, "long_term_debt")
    else:
        debt = float(debt)
    market_cap = row.get("market_cap")
    if market_cap is None or pd.isna(market_cap):
        return None
    return float(market_cap) + debt - cash - st_inv


def attach_prices(panel: pd.DataFrame) -> pd.DataFrame:
    """Attach price_at_filing, market_cap, enterprise_value, return_next_12m and the
    benchmark-adjusted excess_return_next_12m (stock minus XLK over the same trading days)
    from the cached `prices` table. Cache-only -- no network calls."""
    from finchat.collect.prices import get_excess_return_12m, get_price_on_or_after, get_return_12m

    panel = panel.copy()
    price_at_filing, market_cap, ret_next, bench_next, excess_next = [], [], [], [], []
    for _, row in panel.iterrows():
        filed = row.get("filed")
        shares = row.get("shares_diluted")
        if not filed or pd.isna(filed):
            for lst in (price_at_filing, market_cap, ret_next, bench_next, excess_next):
                lst.append(None)
            continue
        p = get_price_on_or_after(row["ticker"], filed)
        x = get_excess_return_12m(row["ticker"], filed)
        r = x or get_return_12m(row["ticker"], filed)
        price = p["close"] if p else None
        price_at_filing.append(price)
        market_cap.append(price * shares if (price is not None and shares) else None)
        ret_next.append(r["return_12m"] if r else None)
        bench_next.append(x["benchmark_return_12m"] if x else None)
        excess_next.append(x["excess_return_12m"] if x else None)

    panel["price_at_filing"] = price_at_filing
    panel["market_cap"] = market_cap
    panel["return_next_12m"] = ret_next
    panel["benchmark_return_next_12m"] = bench_next
    panel["excess_return_next_12m"] = excess_next
    panel["enterprise_value"] = panel.apply(_ev_for_row, axis=1)
    return panel


def valuation(panel: pd.DataFrame, run_dcf: bool = True) -> pd.DataFrame:
    """Adds EV/Sales, log(EV/Sales), P/E (losses -> NaN), DCF fair value and DCF upside."""
    panel = panel.copy()
    panel["ev_sales"] = np.where(
        panel["revenue"].notna() & (panel["revenue"] > 0) & panel["enterprise_value"].notna(),
        panel["enterprise_value"] / panel["revenue"], np.nan,
    )
    panel["log_ev_sales"] = np.where(panel["ev_sales"] > 0, np.log(panel["ev_sales"]), np.nan)

    if "eps_diluted" in panel.columns and "price_at_filing" in panel.columns:
        eps = panel["eps_diluted"]
        price = panel["price_at_filing"]
        panel["pe"] = np.where((eps > 0) & price.notna(), price / eps, np.nan)
    else:
        panel["pe"] = np.nan

    if run_dcf:
        fair_values, upsides = [], []
        for _, row in panel.iterrows():
            try:
                res = calculate_dcf(row["ticker"], as_of_fy=int(row["fy"]))
            except Exception:
                res = {"error": "dcf_failed"}
            fv = res.get("implied_share_price") if "error" not in res else None
            fair_values.append(fv)
            p = row.get("price_at_filing")
            if fv is not None and p:
                upsides.append((fv - p) / p)
            else:
                upsides.append(None)
        panel["dcf_fair_value"] = fair_values
        panel["dcf_upside"] = upsides

    return panel


def fit_fair_value_line(panel: pd.DataFrame, fy: int | None = None,
                         sub_industry: str | None = None) -> dict[str, Any]:
    """OLS fit of log(EV/Sales) ~ QualityScore on the given slice (fy=None pools all years)."""
    sub = panel.copy()
    if fy is not None:
        sub = sub[sub["fy"] == fy]
    if sub_industry is not None:
        sub = sub[sub["sub_industry"] == sub_industry]
    sub = sub.dropna(subset=["QualityScore", "log_ev_sales"])
    n = len(sub)
    if n < 5:
        return {"intercept": None, "slope": None, "r2": None, "p_value": None, "n": n, "residual_std": None}
    slope, intercept, r, p, se = sp_stats.linregress(sub["QualityScore"], sub["log_ev_sales"])
    pred = intercept + slope * sub["QualityScore"]
    resid = sub["log_ev_sales"] - pred
    return {
        "intercept": float(intercept), "slope": float(slope), "r2": float(r ** 2),
        "p_value": float(p), "n": int(n), "residual_std": float(resid.std(ddof=2)),
    }


def mispricing(panel: pd.DataFrame, fit: dict[str, Any] | None = None) -> pd.DataFrame:
    """Adds expected_log_ev_sales, valuation_gap, gap_z and verdict, using a pooled (all-years,
    all-companies) fair-value line unless `fit` is supplied."""
    panel = panel.copy()
    fit = fit or fit_fair_value_line(panel)
    if fit["slope"] is None:
        panel["expected_log_ev_sales"] = np.nan
        panel["valuation_gap"] = np.nan
        panel["gap_z"] = np.nan
        panel["verdict"] = "insufficient_data"
        return panel

    panel["expected_log_ev_sales"] = fit["intercept"] + fit["slope"] * panel["QualityScore"]
    panel["valuation_gap"] = panel["log_ev_sales"] - panel["expected_log_ev_sales"]

    gap_valid = panel["valuation_gap"].dropna()
    mu, sd = gap_valid.mean(), gap_valid.std(ddof=0)
    panel["gap_z"] = (panel["valuation_gap"] - mu) / sd if sd else 0.0
    panel["verdict"] = panel["gap_z"].apply(_verdict)
    return panel


def _verdict(z: float) -> str:
    if pd.isna(z):
        return "insufficient_data"
    if z <= UNDERVALUED_Z:
        return "Undervalued"
    if z >= OVERVALUED_Z:
        return "Overvalued"
    return "Fairly valued"


def walk_forward_mispricing(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The verdict model: walk-forward AND sub-industry-relative.

    For each fiscal year t and sub-industry s, the fair-value line is fitted ONLY on company-years
    of sub-industry s from fiscal years strictly before t (expanding window), so a company is never
    judged with a line that saw its own year or any later regime. Fitting per sub-industry stops
    structurally low-multiple sectors (e.g. hardware) from being flagged "undervalued" merely for
    being in that sector. Gaps are then standardised across all companies within year t (which
    removes the sector-wide re-rating level for that year) and mapped to verdicts at +-1.

    The first fiscal year has no training data, so its rows get 'insufficient_data'.
    Returns (panel with expected_log_ev_sales / valuation_gap / gap_z / verdict, fits table).
    """
    panel = panel.copy()
    panel["expected_log_ev_sales"] = np.nan
    fit_rows: list[dict[str, Any]] = []
    usable = panel.dropna(subset=["QualityScore", "log_ev_sales"])

    for fy in sorted(int(y) for y in panel["fy"].dropna().unique()):
        for sub in sorted(panel["sub_industry"].dropna().unique()):
            train = usable[(usable["fy"] < fy) & (usable["sub_industry"] == sub)]
            fit = fit_fair_value_line(train)
            train_years = sorted(int(y) for y in train["fy"].unique())
            fit_rows.append({
                "fiscal_year": fy, "sub_industry": sub,
                "intercept": fit["intercept"], "slope": fit["slope"], "train_r2": fit["r2"],
                "n": fit["n"],
                "train_start": train_years[0] if train_years else None,
                "train_end": train_years[-1] if train_years else None,
            })
            if fit["slope"] is None:
                continue
            mask = (panel["fy"] == fy) & (panel["sub_industry"] == sub)
            panel.loc[mask, "expected_log_ev_sales"] = fit["intercept"] + fit["slope"] * panel.loc[mask, "QualityScore"]

    panel["valuation_gap"] = panel["log_ev_sales"] - panel["expected_log_ev_sales"]
    panel["gap_z"] = panel.groupby("fy")["valuation_gap"].transform(
        lambda s: (s - s.mean()) / s.std(ddof=0) if s.notna().sum() > 1 and s.std(ddof=0) else s * np.nan
    )
    panel["verdict"] = panel["gap_z"].apply(_verdict)

    # The year's mean/std gap turn a sub-industry's trained line into the line a chart should
    # draw: z = 0 exactly on (intercept + year_gap_mean) + slope * Quality.
    year_stats = panel.groupby("fy")["valuation_gap"].agg(["mean", lambda s: s.std(ddof=0)])
    year_stats.columns = ["year_gap_mean", "year_gap_std"]
    fits = pd.DataFrame(fit_rows)
    fits = fits.merge(year_stats, left_on="fiscal_year", right_index=True, how="left")
    return panel, fits


def dcf_agreement(row: pd.Series) -> str:
    verdict = row.get("verdict")
    upside = row.get("dcf_upside")
    if verdict in (None, "insufficient_data") or upside is None or pd.isna(upside):
        return "n/a"
    dcf_says_cheap = upside > 0.10
    dcf_says_expensive = upside < -0.10
    if verdict == "Undervalued" and dcf_says_cheap:
        return "agrees"
    if verdict == "Overvalued" and dcf_says_expensive:
        return "agrees"
    if verdict == "Undervalued" and dcf_says_expensive:
        return "disagrees"
    if verdict == "Overvalued" and dcf_says_cheap:
        return "disagrees"
    return "n/a"


def score_group_outcomes(panel: pd.DataFrame) -> pd.DataFrame:
    """RQ3: next-year outcomes grouped by Piotroski F / Altman Z / Beneish M."""
    rows = []
    outcome_cols = ["rev_growth_next", "ni_growth_next", "return_next_12m",
                    "excess_return_next_12m", "loss_next"]

    def summarize(sub: pd.DataFrame, group_label: str, group_name: str) -> dict[str, Any]:
        out: dict[str, Any] = {"score": group_name, "group": group_label, "n": len(sub)}
        for col in outcome_cols:
            vals = sub[col] if col in sub.columns else pd.Series(dtype=float)
            out[f"{col}_mean"] = vals.mean()
            out[f"{col}_median"] = vals.median()
        return out

    pio = panel.dropna(subset=["piotroski_f"]).copy()
    pio["grp"] = pd.cut(pio["piotroski_f"], bins=[-1, 3, 6, 9], labels=["low (0-3)", "mid (4-6)", "high (7-9)"])
    for g, sub in pio.groupby("grp", observed=True):
        rows.append(summarize(sub, str(g), "piotroski_f"))

    alt = panel.dropna(subset=["altman_z"]).copy()
    alt["grp"] = pd.cut(alt["altman_z"], bins=[-np.inf, 1.81, 3.0, np.inf],
                        labels=["distress (<1.81)", "grey (1.81-3.0)", "safe (>3.0)"])
    for g, sub in alt.groupby("grp", observed=True):
        rows.append(summarize(sub, str(g), "altman_z"))

    ben = panel.dropna(subset=["beneish_m"]).copy()
    ben["grp"] = np.where(ben["beneish_m"] > -1.78, "flagged (>-1.78)", "not flagged")
    for g, sub in ben.groupby("grp"):
        rows.append(summarize(sub, str(g), "beneish_m"))

    return pd.DataFrame(rows)


def _f(v: Any) -> float | None:
    """NaN-safe float coercion for SQLite storage."""
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(v) else v


def _offline_note(row: dict[str, Any]) -> str:
    verdict = (row.get("verdict") or "").lower()
    direction = "cheap" if verdict == "undervalued" else "expensive" if verdict == "overvalued" else "fairly priced"
    dcf_bit = ""
    upside = row.get("dcf_upside")
    if upside is not None:
        agreement = row.get("dcf_agreement") or "n/a"
        dcf_bit = (f" The DCF model implies {'upside' if upside > 0 else 'downside'} of {upside * 100:.1f}%, "
                   f"which {agreement} with the quality-vs-valuation signal.")
    qs = row.get("quality_score") or 0.0
    prof = row.get("profitability") or 0.0
    gro = row.get("growth") or 0.0
    saf = row.get("safety") or 0.0
    eq = row.get("earnings_quality") or 0.0
    ev_sales = row.get("ev_sales") or 0.0
    exp_ev = row.get("expected_ev_sales")
    exp_bit = f"an expected {exp_ev:.1f}x" if exp_ev is not None else "a quality-implied level"
    return (
        f"{row['ticker']} scores {qs:.1f}/100 on the Fundamental Quality Score "
        f"(profitability {prof:.1f}, growth {gro:.1f}, safety {saf:.1f}, earnings quality {eq:.1f}) "
        f"and trades at {ev_sales:.1f}x EV/Sales versus {exp_bit} for that quality level. "
        f"The data suggests this makes it look {direction} relative to "
        f"{row.get('sub_industry') or 'sub-industry'} peers of similar quality in FY{int(row['fy'])}, "
        f"judged against a fair-value line fitted only on earlier years.{dcf_bit} Not investment advice."
    )


_STRUCTURAL_NUMBERS = {100.0}  # fixed scale denominators ("Quality Score .../100"), not claims


def validate_numbers_for_test(text: str, source_row: dict[str, Any], tolerance_pct: float = 1.0) -> tuple[bool, list[str]]:
    """Every number mentioned in `text` must be within tolerance_pct% of some number in source_row
    -- or of that number scaled by 100, since fractions like dcf_upside=-0.41 are legitimately
    reported as percentages ("-41.0%"). (Named for_test because its only caller outside
    generate_note() is the test suite; it is the exact grounding check generate_note() applies to
    every AI-generated note.)"""
    source_nums = [float(v) for v in source_row.values()
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and not pd.isna(v)]
    candidates = source_nums + [s * 100 for s in source_nums]
    bad: list[str] = []
    # A number glued to a letter, "_" or "^" is notation, not a claimed figure (R^2, R2, FY2024).
    for match in re.findall(r"(?<![A-Za-z_^\d.])-?\d+\.?\d*", text):
        try:
            n = float(match)
        except ValueError:
            continue
        if abs(n) < 1 or n in _STRUCTURAL_NUMBERS:
            continue  # skip tiny decimals (rounding artifacts) and fixed scale denominators
        if not any(abs(n - c) <= max(abs(c) * tolerance_pct / 100, 0.05) for c in candidates):
            bad.append(match)
    return len(bad) == 0, bad


def generate_note(row: dict[str, Any], use_gemini: bool = False) -> tuple[str, bool, str]:
    """Returns (text, numbers_validated, model). Regenerates once on a failed grounding check,
    then falls back to the deterministic offline template, which is always grounded by
    construction. Any other failure (no key, API error) also falls back immediately."""
    if not use_gemini:
        return _offline_note(row), True, "offline_template"
    try:
        from finchat.chatbot.llm import LLMClient

        client = LLMClient()
        system = ("Use only the numbers given in the JSON. Never invent or recall outside numbers. "
                   "Say 'the data suggests', never 'this stock will'. "
                   "End your response with exactly: Not investment advice.")
        prompt = (f"Company data (JSON):\n{json.dumps(row, default=str)}\n\n"
                  f"Write a 3-4 sentence analyst note explaining why this company looks "
                  f"{(row.get('verdict') or '').lower()} for its quality.")
        for _attempt in range(2):
            text = client.generate(prompt, system_prompt=system, temperature=0.2)
            ok, _bad = validate_numbers_for_test(text, row)
            if ok:
                return text, True, client.model
    except Exception:
        pass
    return _offline_note(row), True, "offline_template"


def full_universe() -> list[str]:
    """The base FinChat UNIVERSE plus the Mispricing Radar's expansion tickers, if configured."""
    try:
        from analysis.config import EXTRA_TICKERS
        return list(UNIVERSE.keys()) + list(EXTRA_TICKERS.keys())
    except Exception:
        return list(UNIVERSE.keys())


WINSORIZED_COLS = ["ev_sales", "log_ev_sales", "pe", "roe", "roic", "debt_to_equity"]


def winsorize_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """5th/95th-percentile winsorization within each fiscal year (small-sample outlier control)."""
    panel = panel.copy()

    def clip(s: pd.Series) -> pd.Series:
        if s.dropna().empty:
            return s
        return s.clip(lower=s.quantile(0.05), upper=s.quantile(0.95))

    for col in WINSORIZED_COLS:
        if col in panel.columns:
            panel[col] = panel.groupby("fy")[col].transform(clip)
    return panel


def build_analysis_panel(tickers: list[str] | None = None, run_dcf: bool = True) -> pd.DataFrame:
    """Every step up to (not including) the verdict model, in the one order the study scripts
    (01 -> 03 -> 04 -> 05) also follow, so the app and the published study never diverge."""
    panel = build_panel(tickers=tickers or full_universe())
    panel = attach_prices(panel)
    panel = recompute_point_in_time_altman_z(panel)
    panel = quality_score(panel)
    panel = valuation(panel, run_dcf=run_dcf)
    return winsorize_panel(panel)


_DERIVED_TABLES = ("mispricing", "mispricing_fit", "mispricing_wf_fit",
                   "mispricing_score_outcomes", "mispricing_notes")


def _reset_derived_tables() -> None:
    """The Radar tables hold only derived data that this pipeline fully regenerates, so they are
    dropped and recreated -- which also applies any schema change (CREATE IF NOT EXISTS can't)."""
    from finchat.db import init_db

    with get_db() as con:
        for t in _DERIVED_TABLES:
            con.execute(f"DROP TABLE IF EXISTS {t}")
    init_db()


def run_mispricing_pipeline(tickers: list[str] | None = None, use_gemini: bool | None = None) -> dict[str, int]:
    """Full compute (panel -> walk-forward, sub-industry-relative verdicts), persisted to the
    Radar tables so the live app never recomputes (or calls an LLM) on page load."""
    from finchat.config import GEMINI_API_KEY

    panel = build_analysis_panel(tickers)
    panel, wf_fits = walk_forward_mispricing(panel)
    panel["dcf_agreement"] = panel.apply(dcf_agreement, axis=1)
    panel["expected_ev_sales"] = np.where(
        panel["expected_log_ev_sales"].notna(), np.exp(panel["expected_log_ev_sales"]), np.nan,
    )

    _reset_derived_tables()
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    mis_rows = 0
    with get_db() as con:
        for _, r in panel.iterrows():
            if pd.isna(r.get("QualityScore")) and pd.isna(r.get("ev_sales")):
                continue
            upsert(con, "mispricing", {
                "ticker": r["ticker"], "fiscal_year": int(r["fy"]),
                "sub_industry": r.get("sub_industry"),
                "quality_score": _f(r.get("QualityScore")),
                "profitability": _f(r.get("profitability_score")),
                "growth": _f(r.get("growth_score")),
                "safety": _f(r.get("safety_score")),
                "earnings_quality": _f(r.get("earnings_quality_score")),
                "ev_sales": _f(r.get("ev_sales")),
                "expected_ev_sales": _f(r.get("expected_ev_sales")),
                "valuation_gap": _f(r.get("valuation_gap")),
                "gap_z": _f(r.get("gap_z")),
                "verdict": r.get("verdict"),
                "pe": _f(r.get("pe")),
                "dcf_fair_value": _f(r.get("dcf_fair_value")),
                "price_at_filing": _f(r.get("price_at_filing")),
                "dcf_upside": _f(r.get("dcf_upside")),
                "dcf_agreement": r.get("dcf_agreement"),
                "return_next_12m": _f(r.get("return_next_12m")),
                "benchmark_return_next_12m": _f(r.get("benchmark_return_next_12m")),
                "excess_return_next_12m": _f(r.get("excess_return_next_12m")),
                "accession": r.get("accession"),
                "computed_at": now,
            })
            mis_rows += 1

    # Descriptive same-year fits (RQ1 / the stats strip): how strongly quality and valuation
    # line up within a year. NOT the verdict model -- that is mispricing_wf_fit below.
    sub_inds = sorted(s for s in panel["sub_industry"].dropna().unique().tolist())
    fit_rows = 0
    with get_db() as con:
        for fy in sorted(int(y) for y in panel["fy"].dropna().unique().tolist()):
            for sub in ["ALL"] + sub_inds:
                f = fit_fair_value_line(panel, fy=fy, sub_industry=None if sub == "ALL" else sub)
                upsert(con, "mispricing_fit", {
                    "fiscal_year": fy, "sub_industry": sub,
                    "intercept": _f(f["intercept"]), "slope": _f(f["slope"]), "r2": _f(f["r2"]),
                    "p_value": _f(f["p_value"]), "n": f["n"], "residual_std": _f(f["residual_std"]),
                })
                fit_rows += 1
        for _, w in wf_fits.iterrows():
            upsert(con, "mispricing_wf_fit", {
                "fiscal_year": int(w["fiscal_year"]), "sub_industry": w["sub_industry"],
                "intercept": _f(w["intercept"]), "slope": _f(w["slope"]), "train_r2": _f(w["train_r2"]),
                "n": int(w["n"]),
                "train_start": int(w["train_start"]) if pd.notna(w["train_start"]) else None,
                "train_end": int(w["train_end"]) if pd.notna(w["train_end"]) else None,
                "year_gap_mean": _f(w["year_gap_mean"]),
                "year_gap_std": _f(w["year_gap_std"]),
            })

    outcomes = score_group_outcomes(panel)
    outcome_rows = 0
    with get_db() as con:
        for _, r in outcomes.iterrows():
            upsert(con, "mispricing_score_outcomes", {
                "score": r["score"], "grp": r["group"], "n": int(r["n"]),
                "rev_growth_next_mean": _f(r.get("rev_growth_next_mean")),
                "rev_growth_next_median": _f(r.get("rev_growth_next_median")),
                "ni_growth_next_mean": _f(r.get("ni_growth_next_mean")),
                "ni_growth_next_median": _f(r.get("ni_growth_next_median")),
                "return_next_12m_mean": _f(r.get("return_next_12m_mean")),
                "return_next_12m_median": _f(r.get("return_next_12m_median")),
                "excess_return_next_12m_mean": _f(r.get("excess_return_next_12m_mean")),
                "excess_return_next_12m_median": _f(r.get("excess_return_next_12m_median")),
                "loss_next_mean": _f(r.get("loss_next_mean")),
                "loss_next_median": _f(r.get("loss_next_median")),
                "computed_at": now,
            })
            outcome_rows += 1

    use_gemini = bool(GEMINI_API_KEY) if use_gemini is None else use_gemini
    note_rows = 0
    with get_db() as con:
        scored = panel.dropna(subset=["QualityScore", "ev_sales"])
        for _, r in scored.iterrows():
            if r.get("verdict") in (None, "insufficient_data"):
                continue
            payload = {
                "ticker": r["ticker"], "fy": int(r["fy"]), "sub_industry": r.get("sub_industry"),
                "quality_score": _f(r.get("QualityScore")),
                "profitability": _f(r.get("profitability_score")), "growth": _f(r.get("growth_score")),
                "safety": _f(r.get("safety_score")), "earnings_quality": _f(r.get("earnings_quality_score")),
                "ev_sales": _f(r.get("ev_sales")), "expected_ev_sales": _f(r.get("expected_ev_sales")),
                "valuation_gap": _f(r.get("valuation_gap")), "gap_z": _f(r.get("gap_z")),
                "verdict": r.get("verdict"), "dcf_upside": _f(r.get("dcf_upside")),
                "dcf_agreement": r.get("dcf_agreement"),
            }
            text, validated, model = generate_note(payload, use_gemini=use_gemini)
            upsert(con, "mispricing_notes", {
                "ticker": r["ticker"], "fiscal_year": int(r["fy"]),
                "note_text": text, "numbers_validated": int(validated), "model": model,
                "generated_at": now,
            })
            note_rows += 1

    return {"mispricing_rows": mis_rows, "fit_rows": fit_rows, "outcome_rows": outcome_rows, "note_rows": note_rows}


def load_mispricing_rows(year: int | None = None, sub_industry: str | None = None,
                          direction: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Read precomputed rows from the `mispricing` table. No computation at request time."""
    query = ("SELECT m.*, c.name AS company_name FROM mispricing m "
             "LEFT JOIN companies c ON c.ticker = m.ticker WHERE 1=1")
    params: list[Any] = []
    if year is not None:
        query += " AND m.fiscal_year = ?"
        params.append(year)
    if sub_industry:
        query += " AND m.sub_industry = ?"
        params.append(sub_industry)
    if direction == "under":
        query += " AND m.verdict = 'Undervalued' ORDER BY m.gap_z ASC"
    elif direction == "over":
        query += " AND m.verdict = 'Overvalued' ORDER BY m.gap_z DESC"
    else:
        query += " ORDER BY m.ticker, m.fiscal_year"
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    with get_db() as con:
        rows = con.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def load_fit(year: int | None, sub_industry: str = "ALL") -> dict[str, Any] | None:
    with get_db() as con:
        if year is None:
            row = con.execute(
                "SELECT * FROM mispricing_fit WHERE sub_industry=? ORDER BY fiscal_year DESC LIMIT 1",
                (sub_industry,),
            ).fetchone()
        else:
            row = con.execute(
                "SELECT * FROM mispricing_fit WHERE fiscal_year=? AND sub_industry=?",
                (year, sub_industry),
            ).fetchone()
    return dict(row) if row else None


def load_wf_fit(year: int, sub_industry: str) -> dict[str, Any] | None:
    """The walk-forward fair-value line that produced the verdicts for (year, sub_industry)."""
    with get_db() as con:
        row = con.execute(
            "SELECT * FROM mispricing_wf_fit WHERE fiscal_year=? AND sub_industry=?",
            (year, sub_industry),
        ).fetchone()
    return dict(row) if row else None


def load_note(ticker: str, fiscal_year: int) -> dict[str, Any] | None:
    with get_db() as con:
        row = con.execute(
            "SELECT * FROM mispricing_notes WHERE ticker=? AND fiscal_year=?",
            ((ticker or "").upper().strip(), fiscal_year),
        ).fetchone()
    return dict(row) if row else None


def latest_mispricing_year() -> int | None:
    with get_db() as con:
        row = con.execute("SELECT MAX(fiscal_year) AS m FROM mispricing").fetchone()
    return int(row["m"]) if row and row["m"] is not None else None


def load_score_outcomes(score: str) -> list[dict[str, Any]]:
    """Read precomputed RQ3 grouped outcomes. No computation at request time."""
    col = {"piotroski": "piotroski_f", "altman": "altman_z", "beneish": "beneish_m"}.get(score)
    if col is None:
        return []
    with get_db() as con:
        rows = con.execute(
            "SELECT * FROM mispricing_score_outcomes WHERE score = ? ORDER BY rowid", (col,)
        ).fetchall()
    return [dict(r) for r in rows]


def list_sub_industries() -> list[str]:
    with get_db() as con:
        rows = con.execute(
            "SELECT DISTINCT sub_industry FROM mispricing WHERE sub_industry IS NOT NULL ORDER BY sub_industry"
        ).fetchall()
    return [r["sub_industry"] for r in rows]
