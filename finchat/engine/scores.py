from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from finchat.engine.ratios import YearData, safe_div


def _total_debt(m: dict[str, float | None]) -> float | None:
    if m.get("total_debt") is not None:
        return m["total_debt"]
    parts = [m.get(k) for k in ("debt_current", "long_term_debt")]
    if all(v is None for v in parts):
        return None
    return sum(v for v in parts if v is not None)


def altman_zone(z: float) -> str:
    if z < 1.81:
        return "distress"
    if z < 3.0:
        return "grey"
    return "safe"


def beneish_flag(m: float) -> str:
    return "likely-manipulator" if m > -1.78 else "unlikely"


@dataclass
class ScoreResult:
    name: str
    value: float | None
    components: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


def altman_z(cur: YearData, market_equity: float | None) -> ScoreResult:
    m = cur.m
    missing: list[str] = []
    ta = m.get("assets")
    wc = (m.get("assets_current") - m["liabilities_current"]) \
        if m.get("assets_current") is not None and m.get("liabilities_current") is not None else None
    re_ = m.get("retained_earnings")
    ebit = m.get("operating_income")
    tl = m.get("liabilities")

    for nm, v in (("working_capital", wc), ("retained_earnings", re_), ("ebit", ebit),
                  ("total_assets", ta), ("total_liabilities", tl)):
        if v is None:
            missing.append(nm)

    x4 = None
    if market_equity is not None and tl:
        x4 = safe_div(market_equity, tl)
        variant = "market_equity"
    elif m.get("equity") is not None and tl:
        x4 = safe_div(m["equity"], tl)
        variant = "book_equity_fallback"
        missing.append("market_cap(book-equity X4 used)")
    else:
        variant = "unavailable"

    def term(coef: float, num: float | None) -> float | None:
        val = safe_div(num, ta)
        return None if val is None else coef * val

    t1 = term(1.2, wc)
    t2 = term(1.4, re_)
    t3 = term(3.3, ebit)
    t5 = term(1.0, m.get("revenue"))
    terms = [t for t in (t1, t2, t3, x4 and 0.6 * x4, t5) if t is not None]
    z = sum(terms) if len(terms) == 5 else None
    if z is None:
        missing.append("z_not_computable")
    return ScoreResult(
        name="altman_z",
        value=z,
        components={
            "X1_working_capital_ta": safe_div(wc, ta),
            "X2_retained_earnings_ta": safe_div(re_, ta),
            "X3_ebit_ta": safe_div(ebit, ta),
            "X4_market_or_book_equity_tl": x4,
            "X4_variant": variant,
            "X5_sales_ta": safe_div(m.get("revenue"), ta),
            "zone": altman_zone(z) if z is not None else None,
        },
        missing=missing,
    )


def piotroski_f(cur: YearData, prev: YearData | None) -> ScoreResult:
    if prev is None:
        return ScoreResult("piotroski_f", None, {}, ["no_prior_year"])
    c, p = cur.m, prev.m
    comps: dict[str, int | float | None] = {}
    pts = 0

    def flag(key: str, cond: bool | None) -> None:
        nonlocal pts
        if cond is None:
            comps[key] = None
        else:
            comps[key] = 1 if cond else 0
            pts += 1 if cond else 0

    roa_c, roa_p = safe_div(c.get("net_income"), c.get("assets")), safe_div(p.get("net_income"), p.get("assets"))
    flag("positive_roa", None if roa_c is None else roa_c > 0)
    flag("positive_cfo", None if c.get("cfo") is None else c["cfo"] > 0)
    flag("roa_improved", None if (roa_c is None or roa_p is None) else roa_c > roa_p)
    if c.get("cfo") is None or c.get("net_income") is None:
        comps["accruals_quality"] = None
    else:
        ok = c["cfo"] > c["net_income"]
        comps["accruals_quality"] = 1 if ok else 0
        pts += 1 if ok else 0

    def lev(d: dict[str, float | None]) -> float | None:
        debt = _total_debt(d)
        if debt is None and d.get("liabilities") is None:
            return None
        base = debt if debt is not None else d.get("liabilities")
        den = d.get("assets")
        return safe_div(base, den)

    lev_c, lev_p = lev(c), lev(p)
    flag("leverage_down", None if (lev_c is None or lev_p is None) else lev_c < lev_p)

    cr_c = safe_div(c.get("assets_current"), c.get("liabilities_current"))
    cr_p = safe_div(p.get("assets_current"), p.get("liabilities_current"))
    flag("current_ratio_up", None if (cr_c is None or cr_p is None) else cr_c > cr_p)

    sh_c = c.get("shares_diluted") if c.get("shares_diluted") is not None else c.get("shares_basic")
    sh_p = p.get("shares_diluted") if p.get("shares_diluted") is not None else p.get("shares_basic")
    flag("no_new_shares", None if (sh_c is None or sh_p is None) else sh_c <= sh_p)

    gm_c, gm_p = safe_div(c.get("gross_profit"), c.get("revenue")), safe_div(p.get("gross_profit"), p.get("revenue"))
    flag("gross_margin_up", None if (gm_c is None or gm_p is None) else gm_c > gm_p)

    at_c, at_p = safe_div(c.get("revenue"), c.get("assets")), safe_div(p.get("revenue"), p.get("assets"))
    flag("asset_turnover_up", None if (at_c is None or at_p is None) else at_c > at_p)

    return ScoreResult("piotroski_f", float(pts), {"components": comps}, [])


def _idx(cur_val: float | None, prev_val: float | None) -> float | None:
    return safe_div(cur_val, prev_val)


def beneish_m(cur: YearData, prev: YearData | None) -> ScoreResult:
    if prev is None:
        return ScoreResult("beneish_m", None, {}, ["no_prior_year"])
    c, p = cur.m, prev.m
    missing: list[str] = []

    rev_c, rev_p = c.get("revenue"), p.get("revenue")
    gp_c, gp_p = c.get("gross_profit"), p.get("gross_profit")
    rec_c, rec_p = c.get("receivables"), p.get("receivables")
    ni_c, ni_p = c.get("net_income"), p.get("net_income")
    assets_c, assets_p = c.get("assets"), p.get("assets")
    ppe_c, ppe_p = c.get("ppe_net"), p.get("ppe_net")
    sga_c, sga_p = c.get("sga"), p.get("sga")
    da_c, da_p = c.get("ebitda_proxy_da"), p.get("ebitda_proxy_da")
    cfo_c = c.get("cfo")

    soft_c = None
    if assets_c is not None and (ppe_c is not None or assets_c is not None):
        if ppe_c is None:
            missing.append("ppe_net")
            soft_c = None
        else:
            soft_c = assets_c - ppe_c
    soft_p = None
    if assets_p is not None and ppe_p is not None:
        soft_p = assets_p - ppe_p

    dep_rate_c = safe_div(da_c, (da_c or 0) + (ppe_c or 0)) if (da_c is not None and ppe_c is not None) else None
    dep_rate_p = safe_div(da_p, (da_p or 0) + (ppe_p or 0)) if (da_p is not None and ppe_p is not None) else None

    tata = None
    if ni_c is not None and cfo_c is not None and assets_c:
        tata = (ni_c - cfo_c) / assets_c
    tata_p = None
    if ni_p is not None and p.get("cfo") is not None and assets_p:
        tata_p = (ni_p - p["cfo"]) / assets_p

    dsri = _idx(rec_c and safe_div(rec_c, rev_c), rec_p and safe_div(rec_p, rev_p))
    gmi = _idx(gp_p and safe_div(gp_p, rev_p), gp_c and safe_div(gp_c, rev_c))
    aqi = _idx(soft_c and safe_div(soft_c, assets_c), soft_p and safe_div(soft_p, assets_p))
    sgi = _idx(rev_c, rev_p)
    depi = _idx(dep_rate_p, dep_rate_c)
    sgai = _idx(sga_c and safe_div(sga_c, rev_c), sga_p and safe_div(sga_p, rev_p))
    lvgi = _idx(
        safe_div(_total_debt(c) if _total_debt(c) is not None else c.get("liabilities"), assets_c),
        safe_div(_total_debt(p) if _total_debt(p) is not None else p.get("liabilities"), assets_p),
    )

    lvgi_ok = lvgi
    parts = {
        "DSRI": dsri, "GMI": gmi, "AQI": aqi, "SGI": sgi,
        "DEPI": depi, "SGAI": sgai, "LVGI": lvgi_ok, "TATA": tata,
    }
    for k, v in parts.items():
        if v is None:
            missing.append(k)

    if all(parts[k] is not None for k in ("DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI")) and tata is not None:
        m_score = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
                   + 0.115 * depi - 0.172 * sgai + 4.679 * lvgi_ok - 0.327 * tata)
    else:
        m_score = None
    if m_score is None:
        missing.append("m_not_computable")

    return ScoreResult(
        "beneish_m", m_score,
        {**parts, "TATA_prior": tata_p,
         "flag": beneish_flag(m_score) if m_score is not None else None,
         "note": "8-variable model; DEPI uses depreciation rate proxy"},
        missing,
    )
