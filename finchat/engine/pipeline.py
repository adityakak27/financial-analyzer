from __future__ import annotations

import json

import pandas as pd

from finchat.config import UNIVERSE
from finchat.db import get_db, init_db, upsert
from finchat.engine.peers import peer_percentiles
from finchat.engine.ratios import YearData, compute_ratios, dupont_3step
from finchat.engine.scores import altman_z, beneish_m, piotroski_f
from finchat.engine.valuation import fetch_market_snapshot, valuation_multiples


def load_statements() -> pd.DataFrame:
    with get_db() as con:
        df = pd.read_sql("SELECT ticker, fy, metric, value FROM statements", con)
    return df


def statement_matrix(df: pd.DataFrame) -> dict[tuple[str, int], dict[str, float | None]]:
    out: dict[tuple[str, int], dict[str, float | None]] = {}
    for (ticker, fy), grp in df.groupby(["ticker", "fy"]):
        out[(ticker, int(fy))] = dict(zip(grp["metric"], grp["value"]))
    return out


def run_engine(use_market_data: bool = False) -> None:
    init_db()
    mat = statement_matrix(load_statements())

    ratio_rows: list[dict] = []
    score_rows: list[dict] = []
    val_rows: list[dict] = []

    tickers = sorted({t for t, _ in mat})
    market_cache: dict[str, dict[str, float | None]] = {}

    for ticker in tickers:
        years = sorted(fy for t, fy in mat if t == ticker)
        snapshot = {"price": None, "market_cap": None}
        if use_market_data:
            try:
                snapshot = fetch_market_snapshot(ticker)
            except Exception:
                pass
        market_cache[ticker] = snapshot

        for fy in years:
            cur = YearData(ticker, fy, mat[(ticker, fy)])
            prev = YearData(ticker, fy - 1, mat.get((ticker, fy - 1), {})) if (ticker, fy - 1) in mat else None

            ratios = compute_ratios(cur, prev)
            dup = dupont_3step(ratios, cur.get("equity"), cur.get("net_income"), cur.get("assets"))
            all_ratios = {**ratios, **dup}

            val = valuation_multiples(cur.m, snapshot["price"],
                                      cur.get("shares_diluted"), snapshot["market_cap"])
            for metric, value in {**all_ratios, **val}.items():
                if value is not None:
                    ratio_rows.append({"ticker": ticker, "fy": fy,
                                       "metric": f"valuation_{metric}" if metric in val else metric,
                                       "value": value})

            az = altman_z(cur, snapshot["market_cap"])
            pf = piotroski_f(cur, prev)
            bm = beneish_m(cur, prev)
            score_rows.append({
                "ticker": ticker, "fy": fy,
                "altman_z": az.value, "altman_zone": az.components.get("zone"),
                "piotroski_f": pf.value,
                "beneish_m": bm.value, "beneish_flag": bm.components.get("flag"),
                "components_json": json.dumps({"altman": az.components, "piotroski": pf.components,
                                               "beneish": bm.components}),
                "missing_json": json.dumps({"altman": az.missing, "piotroski": pf.missing,
                                            "beneish": bm.missing}),
            })

    ratios_df = pd.DataFrame(ratio_rows)
    rank_rows = []
    if not ratios_df.empty:
        core_metrics = [m for m in ratios_df["metric"].unique()
                        if not m.startswith("valuation_")]
        ranks_df = peer_percentiles(ratios_df[ratios_df["metric"].isin(core_metrics)], core_metrics)
        rank_rows = ranks_df.to_dict("records")

    with get_db() as con:
        con.execute("DELETE FROM ratios")
        con.execute("DELETE FROM scores")
        con.execute("DELETE FROM peer_ranks")
        for r in ratio_rows:
            upsert(con, "ratios", r)
        for s in score_rows:
            upsert(con, "scores", s)
        for rk in rank_rows:
            upsert(con, "peer_ranks", {
                "ticker": rk["ticker"], "fy": int(rk["fy"]), "metric": rk["metric"],
                "rank": rk["rank"], "n": rk["n"], "percentile": rk["percentile"],
            })
    print(f"[engine] {len(ratio_rows)} ratio rows, {len(score_rows)} score rows, "
          f"{len(rank_rows)} peer-rank rows across {len(tickers)} companies")


if __name__ == "__main__":
    run_engine(use_market_data=False)
