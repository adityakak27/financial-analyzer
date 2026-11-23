from __future__ import annotations

import math

import pandas as pd

import finchat.db as db
from finchat.collect.prices import get_excess_return_12m, get_price_on_or_after, get_return_12m
from finchat.engine.mispricing import (PILLAR_METRICS, fit_fair_value_line, mispricing, quality_score,
                                        recompute_point_in_time_altman_z, walk_forward_mispricing)


def approx(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol


def test_quality_score_hand_calculated():
    # 3 company-years, one fiscal year. Only roe and operating_margin are supplied, with
    # identical values, so the profitability pillar's z-score equals each metric's own
    # z-score (mean of two identical numbers) -- easy to hand-check.
    panel = pd.DataFrame({
        "ticker": ["A", "B", "C"],
        "fy": [2024, 2024, 2024],
        "roe": [0.0, 10.0, 20.0],
        "operating_margin": [0.0, 10.0, 20.0],
    })
    out = quality_score(panel)

    mean, std = 10.0, math.sqrt(200.0 / 3.0)  # population std of [0, 10, 20]
    expected_z = [(v - mean) / std for v in (0.0, 10.0, 20.0)]
    lo, hi = min(expected_z), max(expected_z)
    expected_quality = [round((z - lo) / (hi - lo) * 100, 1) for z in expected_z]

    assert out["QualityScore"].tolist() == expected_quality
    assert expected_quality == [0.0, 50.0, 100.0]
    # growth/safety/earnings_quality were never supplied -> those pillar columns are all-NaN
    assert out["growth_score"].isna().all()
    assert out["safety_score"].isna().all()
    assert out["earnings_quality_score"].isna().all()


def test_quality_score_pillar_needs_minimum_metrics():
    # Only ONE profitability metric supplied (roe) -> below MIN_METRICS_PER_PILLAR=2 ->
    # the whole pillar, and therefore QualityScore, must be NaN for that company-year.
    panel = pd.DataFrame({
        "ticker": ["A", "B"],
        "fy": [2024, 2024],
        "roe": [0.0, 10.0],
    })
    out = quality_score(panel)
    assert out["QualityScore"].isna().all()


def test_fit_fair_value_line_recovers_known_slope_and_intercept():
    # Perfectly linear toy dataset: log_ev_sales = 2.0 + 0.03 * QualityScore, no noise.
    quality = [10.0, 20.0, 30.0, 40.0, 50.0]
    panel = pd.DataFrame({
        "fy": [2024] * 5,
        "sub_industry": ["Software"] * 5,
        "QualityScore": quality,
        "log_ev_sales": [2.0 + 0.03 * q for q in quality],
    })
    fit = fit_fair_value_line(panel)
    assert approx(fit["intercept"], 2.0, tol=1e-9)
    assert approx(fit["slope"], 0.03, tol=1e-9)
    assert approx(fit["r2"], 1.0, tol=1e-9)
    assert fit["n"] == 5


def test_fit_fair_value_line_insufficient_data_returns_none():
    panel = pd.DataFrame({
        "fy": [2024, 2024],
        "sub_industry": ["Software", "Software"],
        "QualityScore": [10.0, 20.0],
        "log_ev_sales": [1.0, 1.1],
    })
    fit = fit_fair_value_line(panel)  # N=2 < the function's minimum of 5
    assert fit["slope"] is None
    assert fit["n"] == 2


def test_verdict_thresholds_at_the_boundary():
    # 5 company-years all at the same QualityScore, so valuation_gap = log_ev_sales - expected
    # is just whatever constant we add. Gaps of [-3, -1, 0, 1, 3] have mean 0 and population
    # std 2 (hand-checkable), giving clean z-scores of [-1.5, -0.5, 0, 0.5, 1.5] -- one clearly
    # on each side of both the -1 and +1 verdict thresholds (UNDERVALUED_Z / OVERVALUED_Z).
    quality = [10.0, 20.0, 30.0, 40.0, 50.0]
    fit_panel = pd.DataFrame({
        "fy": [2024] * 5, "QualityScore": quality,
        "log_ev_sales": [2.0 + 0.03 * q for q in quality],
    })
    fit = fit_fair_value_line(fit_panel)

    gaps = [-3.0, -1.0, 0.0, 1.0, 3.0]
    std = math.sqrt(sum(g * g for g in gaps) / len(gaps))
    assert approx(std, 2.0)

    panel = pd.DataFrame({
        "ticker": ["UNDER", "LOW_FAIR", "FAIR", "HIGH_FAIR", "OVER"],
        "fy": [2024] * 5,
        "QualityScore": [30.0] * 5,
    })
    panel["log_ev_sales"] = fit["intercept"] + fit["slope"] * panel["QualityScore"] + gaps
    out = mispricing(panel, fit=fit)

    expected_z = [-1.5, -0.5, 0.0, 0.5, 1.5]
    for z, row in zip(expected_z, out.itertuples()):
        assert approx(row.gap_z, z, tol=1e-6)

    assert out.loc[0, "verdict"] == "Undervalued"   # z = -1.5 <= -1
    assert out.loc[1, "verdict"] == "Fairly valued"  # z = -0.5
    assert out.loc[2, "verdict"] == "Fairly valued"  # z = 0.0
    assert out.loc[3, "verdict"] == "Fairly valued"  # z = 0.5
    assert out.loc[4, "verdict"] == "Overvalued"     # z = 1.5 >= 1


def test_price_lookup_never_uses_a_future_price(tmp_path, monkeypatch):
    db_path = str(tmp_path / "prices_test.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    con = db.connect(db_path)
    db.init_db(con)
    con.commit()
    con.close()

    # Seed prices around a filing date of 2024-03-15 (a Friday): nothing before it should
    # ever be picked, and the result must be the FIRST trading day on/after it.
    con = db.connect(db_path)
    for date, close in [
        ("2024-03-14", 100.0),  # before the filing -- must never be chosen
        ("2024-03-18", 110.0),  # Monday after the filing (first trading day on/after)
        ("2024-03-19", 111.0),
        ("2025-03-17", 150.0),  # ~12 months later, for the return calc
    ]:
        db.upsert(con, "prices", {"ticker": "TST", "date": date, "close": close, "adj_close": close})
    con.commit()
    con.close()

    picked = get_price_on_or_after("TST", "2024-03-15")
    assert picked is not None
    assert picked["date"] == "2024-03-18"  # not the 03-14 price, which is in the past
    assert picked["close"] == 110.0

    ret = get_return_12m("TST", "2024-03-15")
    assert ret is not None
    assert ret["start_date"] == "2024-03-18"
    assert approx(ret["return_12m"], (150.0 - 110.0) / 110.0)

    # A filing date after every cached price has nothing to return (no silent future leak).
    assert get_price_on_or_after("TST", "2026-01-01") is None


def _wf_panel(n_per_group: int = 6) -> pd.DataFrame:
    """Two sub-industries over 3 fiscal years. 'Cheap' sector trades ~1.0 log point below 'Rich'
    at every quality level -- a structural sector gap, not mispricing."""
    rows = []
    for fy in (2020, 2021, 2022):
        for sector, offset in (("Cheap", 0.0), ("Rich", 1.0)):
            for i in range(n_per_group):
                q = 20.0 + 10.0 * i
                noise = 0.05 * ((i % 3) - 1)
                rows.append({"ticker": f"{sector[0]}{i}", "fy": fy, "sub_industry": sector,
                             "QualityScore": q, "log_ev_sales": offset + 0.02 * q + noise})
    return pd.DataFrame(rows)


def test_walk_forward_first_year_has_no_verdict():
    out, fits = walk_forward_mispricing(_wf_panel())
    assert (out[out.fy == 2020]["verdict"] == "insufficient_data").all()
    assert fits[fits.fiscal_year == 2020]["slope"].isna().all()
    assert out[out.fy == 2021]["gap_z"].notna().all()


def test_walk_forward_never_uses_future_years():
    """Changing FY2022 data must not move any FY2021 expected value, gap or verdict."""
    base, _ = walk_forward_mispricing(_wf_panel())
    shocked = _wf_panel()
    shocked.loc[shocked.fy == 2022, "log_ev_sales"] += 5.0  # a wild future re-rating
    after, fits = walk_forward_mispricing(shocked)

    cols = ["expected_log_ev_sales", "valuation_gap", "gap_z", "verdict"]
    pd.testing.assert_frame_equal(base[base.fy <= 2021][cols].reset_index(drop=True),
                                  after[after.fy <= 2021][cols].reset_index(drop=True))
    f22 = fits[fits.fiscal_year == 2022]
    assert (f22["train_end"] == 2021).all()  # FY2022's line was trained only on <= FY2021


def test_walk_forward_does_not_flag_a_whole_cheap_sector():
    """A pooled line would flag every 'Cheap' company as undervalued; sub-industry lines must not."""
    out, _ = walk_forward_mispricing(_wf_panel())
    tested = out[out.fy >= 2021]
    assert not (tested[tested.sub_industry == "Cheap"]["verdict"] == "Undervalued").all()

    pooled = mispricing(tested, fit=fit_fair_value_line(tested))
    assert pooled[pooled.sub_industry == "Cheap"]["gap_z"].mean() < -0.5  # the bias being avoided
    assert abs(tested[tested.sub_industry == "Cheap"]["gap_z"].mean()) < 0.5


def test_quality_score_excludes_composite_scores():
    used = {m for metrics in PILLAR_METRICS.values() for m, _ in metrics}
    assert not used & {"altman_z", "piotroski_f", "beneish_m"}


def test_altman_z_uses_point_in_time_market_cap():
    panel = pd.DataFrame([{
        "assets_current": 50.0, "liabilities_current": 30.0, "retained_earnings": 40.0,
        "operating_income": 20.0, "assets": 200.0, "liabilities": 100.0, "revenue": 150.0,
        "equity": 100.0, "market_cap": 300.0, "altman_z": 999.0,  # 999 = a stale, contaminated value
    }])
    out = recompute_point_in_time_altman_z(panel)
    expected = 1.2 * 20 / 200 + 1.4 * 40 / 200 + 3.3 * 20 / 200 + 0.6 * 300 / 100 + 1.0 * 150 / 200
    assert approx(out.loc[0, "altman_z"], expected)

    panel.loc[0, "market_cap"] = float("nan")  # no price that day -> falls back to book equity
    out = recompute_point_in_time_altman_z(panel)
    assert approx(out.loc[0, "altman_z"], expected - 0.6 * 300 / 100 + 0.6 * 100 / 100)


def test_excess_return_subtracts_benchmark_over_same_days(tmp_path, monkeypatch):
    db_path = str(tmp_path / "excess_test.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    con = db.connect(db_path)
    db.init_db(con)
    for ticker, start, end in (("TST", 100.0, 150.0), ("XLK", 200.0, 220.0)):
        for date, px in (("2024-03-18", start), ("2025-03-17", end)):
            db.upsert(con, "prices", {"ticker": ticker, "date": date, "close": px, "adj_close": px})
    con.commit()
    con.close()

    x = get_excess_return_12m("TST", "2024-03-15")
    assert approx(x["return_12m"], 0.50)
    assert approx(x["benchmark_return_12m"], 0.10)
    assert approx(x["excess_return_12m"], 0.40)
