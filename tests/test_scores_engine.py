from __future__ import annotations

import math

from finchat.engine.ratios import YearData, compute_ratios, dupont_3step, safe_div
from finchat.engine.scores import altman_z, beneish_m, piotroski_f

from tests.conftest import AAPL_2021, AAPL_2022


def approx(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol


def test_safe_div():
    assert safe_div(10, 4) == 2.5
    assert safe_div(1, 0) is None
    assert safe_div(None, 2) is None


def test_core_ratios():
    cur = YearData("AAPL", 2022, dict(AAPL_2022))
    prev = YearData("AAPL", 2021, dict(AAPL_2021))
    r = compute_ratios(cur, prev)
    assert approx(r["roe"], 0.5)
    assert approx(r["gross_margin"], 0.4)
    assert approx(r["net_margin"], 0.15)
    assert approx(r["current_ratio"], 1.5)
    assert approx(r["debt_to_equity"], 250.0 / 300.0)
    assert approx(r["revenue_growth_pct"], (1000 / 900 - 1) * 100)
    assert approx(r["fcf_margin"], (180 - 40) / 1000)


def test_dupont_identity():
    cur = YearData("AAPL", 2022, dict(AAPL_2022))
    prev = YearData("AAPL", 2021, dict(AAPL_2021))
    r = compute_ratios(cur, prev)
    dup = dupont_3step(r, cur.get("equity"), cur.get("net_income"), cur.get("assets"))
    assert approx(dup["roe_dupont"], r["roe"], tol=1e-9)
    assert approx(dup["dupont_equity_multiplier"], 800 / 300)


def test_altman_book_and_market_variants():
    cur = YearData("AAPL", 2022, dict(AAPL_2022))
    res_book = altman_z(cur, market_equity=None)
    terms = (0.15, 0.1575, 0.825, 0.6 * (300 / 500), 1.25)
    assert approx(res_book.value, sum(terms))
    assert res_book.components["X4_variant"] == "book_equity_fallback"
    assert res_book.components["zone"] == "grey"

    res_mkt = altman_z(cur, market_equity=600.0)
    assert approx(res_mkt.value, sum(terms[:3]) + 0.6 * (600 / 500) + 1.25)
    assert res_mkt.components["zone"] == "safe"


def test_piotroski_all_nine():
    cur = YearData("AAPL", 2022, dict(AAPL_2022))
    prev = YearData("AAPL", 2021, dict(AAPL_2021))
    res = piotroski_f(cur, prev)
    assert res.value == 9.0
    comps = res.components["components"]
    assert all(v == 1 for v in comps.values())


def test_beneish_hand_computed():
    cur = YearData("AAPL", 2022, dict(AAPL_2022))
    prev = YearData("AAPL", 2021, dict(AAPL_2021))
    res = beneish_m(cur, prev)
    dsri = (120 / 1000) / (100 / 900)
    gmi = (330 / 900) / (400 / 1000)
    aqi = ((800 - 200) / 800) / ((760 - 190) / 760)
    sgi = 1000 / 900
    depi = (58 / (58 + 190)) / (60 / (60 + 200))
    sgai = (80 / 1000) / (78 / 900)
    lvgi = (250 / 800) / (250 / 760)
    tata = (150 - 180) / 800
    expected = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
                + 0.115 * depi - 0.172 * sgai + 4.679 * lvgi - 0.327 * tata)
    assert approx(res.value, expected, tol=1e-6)
    assert not math.isnan(res.value)


def test_beneish_constant_company_all_indices_one():
    flat = {
        "revenue": 1000.0, "gross_profit": 300.0, "receivables": 100.0,
        "assets": 800.0, "ppe_net": 400.0, "ebitda_proxy_da": 40.0, "sga": 100.0,
        "total_debt": 200.0, "net_income": 50.0, "cfo": 50.0,
    }
    cur = YearData("X", 2022, dict(flat))
    prev = YearData("X", 2021, dict(flat))
    res = beneish_m(cur, prev)
    expected = -4.84 + (0.92 + 0.528 + 0.404 + 0.892 + 0.115 - 0.172 + 4.679)
    assert approx(res.value, expected, tol=1e-6)
