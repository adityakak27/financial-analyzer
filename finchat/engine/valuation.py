from __future__ import annotations

from typing import Any

from finchat.engine.ratios import safe_div


def _yf_ticker(ticker: str) -> Any | None:
    try:
        import yfinance as yf
    except Exception:
        return None
    try:
        return yf.Ticker(ticker)
    except Exception:
        return None


def fetch_market_snapshot(ticker: str) -> dict[str, float | None]:
    tk = _yf_ticker(ticker)
    if tk is None:
        return {"price": None, "market_cap": None}
    out: dict[str, float | None] = {"price": None, "market_cap": None}
    try:
        info = tk.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        mc = info.get("marketCap")
        out["price"] = float(price) if price else None
        out["market_cap"] = float(mc) if mc else None
    except Exception:
        pass
    return out


def valuation_multiples(m: dict[str, float | None], price: float | None,
                        shares_diluted: float | None, market_cap: float | None) -> dict[str, float | None]:
    eps = m.get("eps_diluted")
    bvps = safe_div(m.get("equity"), shares_diluted)
    sps = safe_div(m.get("revenue"), shares_diluted)
    ebitda = None
    if m.get("operating_income") is not None:
        da = m.get("ebitda_proxy_da") or 0.0
        ebitda = m["operating_income"] + da

    def ratio(price_over: float | None, per_share: float | None) -> float | None:
        return safe_div(price_over, per_share)

    out = {
        "pe_ratio": ratio(price, eps),
        "pb_ratio": ratio(price, bvps),
        "ps_ratio": ratio(price, sps),
    }
    if market_cap is not None and ebitda:
        out["ev_ebitda_approx"] = safe_div(market_cap + (m.get("total_debt") or 0.0) - ((m.get("cash") or 0.0) + (m.get("short_term_investments") or 0.0)), ebitda)
    else:
        out["ev_ebitda_approx"] = None
    out["market_cap"] = market_cap
    return out


def altman_market_equity(ticker: str) -> float | None:
    snap = fetch_market_snapshot(ticker)
    return snap.get("market_cap")
