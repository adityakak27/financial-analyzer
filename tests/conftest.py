from __future__ import annotations

import pytest

import finchat.db as db
import finchat.chatbot.state as state_mod
from finchat.nlp.index import get_retriever

AAPL_2022 = {
    "revenue": 1000.0, "cogs": 600.0, "gross_profit": 400.0, "operating_income": 200.0,
    "net_income": 150.0, "assets": 800.0, "liabilities": 500.0, "equity": 300.0,
    "assets_current": 300.0, "liabilities_current": 200.0, "cash": 100.0,
    "receivables": 120.0, "inventory": 50.0, "ppe_net": 200.0, "retained_earnings": 90.0,
    "cfo": 180.0, "capex": 40.0, "ebitda_proxy_da": 60.0, "interest_expense": 20.0,
    "debt_current": 50.0, "long_term_debt": 200.0, "sga": 80.0, "rd": 60.0,
    "shares_diluted": 1000.0,
}
AAPL_2021 = {
    "revenue": 900.0, "cogs": 570.0, "gross_profit": 330.0, "operating_income": 160.0,
    "net_income": 120.0, "assets": 760.0, "liabilities": 480.0, "equity": 280.0,
    "assets_current": 290.0, "liabilities_current": 210.0, "cash": 80.0,
    "receivables": 100.0, "inventory": 55.0, "ppe_net": 190.0, "retained_earnings": 60.0,
    "cfo": 150.0, "capex": 45.0, "ebitda_proxy_da": 58.0, "interest_expense": 22.0,
    "debt_current": 55.0, "long_term_debt": 195.0, "sga": 78.0, "rd": 55.0,
    "shares_diluted": 1010.0,
}
MSFT_2022 = {
    "revenue": 500.0, "cogs": 420.0, "gross_profit": 80.0, "operating_income": -30.0,
    "net_income": -50.0, "assets": 700.0, "liabilities": 650.0, "equity": 50.0,
    "assets_current": 100.0, "liabilities_current": 220.0, "cash": 40.0,
    "receivables": 60.0, "inventory": 10.0, "ppe_net": 300.0, "retained_earnings": -80.0,
    "cfo": -20.0, "capex": 25.0, "ebitda_proxy_da": 35.0, "interest_expense": 40.0,
    "debt_current": 100.0, "long_term_debt": 300.0, "sga": 60.0, "rd": 40.0,
    "shares_diluted": 500.0,
}
MSFT_2021 = {
    "revenue": 550.0, "cogs": 450.0, "gross_profit": 100.0, "operating_income": -10.0,
    "net_income": -20.0, "assets": 720.0, "liabilities": 660.0, "equity": 60.0,
    "assets_current": 130.0, "liabilities_current": 200.0, "cash": 50.0,
    "receivables": 55.0, "inventory": 12.0, "ppe_net": 310.0, "retained_earnings": -30.0,
    "cfo": 5.0, "capex": 30.0, "ebitda_proxy_da": 34.0, "interest_expense": 38.0,
    "debt_current": 110.0, "long_term_debt": 310.0, "sga": 62.0, "rd": 42.0,
    "shares_diluted": 495.0,
}

SEED = {
    "AAPL": {"name": "Test Apple Inc.", 2021: AAPL_2021, 2022: AAPL_2022},
    "MSFT": {"name": "Test Microsoft Corp.", 2021: MSFT_2021, 2022: MSFT_2022},
}


@pytest.fixture()
def seed_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", db_path)
    con = db.connect(db_path)
    db.init_db(con)
    for ticker, payload in SEED.items():
        db.upsert(con, "companies", {"ticker": ticker, "cik": f"000{ticker}", "name": payload["name"]})
        for fy, metrics in ((k, v) for k, v in payload.items() if isinstance(k, int)):
            for metric, value in metrics.items():
                db.upsert(con, "statements", {
                    "ticker": ticker, "fy": fy, "metric": metric, "value": value,
                    "tag": f"Seed_{metric}", "accession": "0000000000-00-000000", "filed": "",
                })
        db.upsert(con, "filings", {"ticker": ticker, "fy": 2022, "form": "10-K",
                                   "accession": "acc", "filed": "2023-01-01", "url": "https://example.com/a.htm",
                                   "mda_chars": 10, "risk_chars": 10})
        db.upsert(con, "chunks", {"chunk_id": f"{ticker}_2022_risk_0", "ticker": ticker, "fy": 2022,
                                  "section": "risk", "idx": 0,
                                  "text": "Supply chain constraints and component shortages affected "
                                          "our ability to meet demand during the fiscal year."})
        db.upsert(con, "textstats", {"ticker": ticker, "fy": 2022, "section": "risk",
                                     "n_words": 20, "neg_frac": 0.15, "pos_frac": 0.05,
                                     "polarity": -0.5,
                                     'redflags_json': '{"supply_chain": 3}'})
    con.commit()
    con.close()

    from finchat.engine.pipeline import run_engine

    run_engine(use_market_data=False)

    get_retriever().invalidate()
    monkeypatch.setattr(state_mod, "ALIASES", {})
    monkeypatch.setattr(state_mod, "TWO_WORD_NAMES", [])
    yield db_path
