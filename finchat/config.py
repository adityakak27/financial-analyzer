from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
FILINGS_DIR = DATA_DIR / "raw" / "filings"
DB_PATH = DATA_DIR / "finchat.db"
EVAL_DIR = PROJECT_ROOT / "data" / "eval"
RESULTS_DIR = PROJECT_ROOT / "eval_results"

for _d in (DATA_DIR, RAW_DIR, CACHE_DIR, FILINGS_DIR, EVAL_DIR, RESULTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env", override=True)
    except Exception:
        pass


_load_dotenv()


SECTOR = "Information Technology (US large cap)"

UNIVERSE: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "NVDA": "NVIDIA Corp.",
    "AVGO": "Broadcom Inc.",
    "ORCL": "Oracle Corp.",
    "CRM": "Salesforce Inc.",
    "ADBE": "Adobe Inc.",
    "AMD": "Advanced Micro Devices Inc.",
    "QCOM": "QUALCOMM Inc.",
    "TXN": "Texas Instruments Inc.",
    "INTU": "Intuit Inc.",
    "NOW": "ServiceNow Inc.",
    "MU": "Micron Technology Inc.",
    "AMAT": "Applied Materials Inc.",
    "ADI": "Analog Devices Inc.",
    "SNPS": "Synopsys Inc.",
    "CDNS": "Cadence Design Systems Inc.",
    "PANW": "Palo Alto Networks Inc.",
    "INTC": "Intel Corp.",
}

FY_START = 2018
FY_END = 2024

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "FinChat Research research@example.com")
SEC_RATE_SLEEP = float(os.getenv("SEC_RATE_SLEEP", "0.15"))

# Google Gemini (https://aistudio.google.com/app/apikey)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

LM_LEXICON_PATH = Path(os.getenv("LM_LEXICON_PATH", str(DATA_DIR / "lm_lexicon.csv")))

RETRIEVAL_TOP_K = 5
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150

GROUNDING_TOLERANCE_PCT = 1.0

SYSTEM_PROMPT = """You are an institutional equity research copilot and fundamental-analysis specialist.
You answer questions about companies' financial statements, financial ratios, credit/forensic scores (Altman Z, Piotroski F, Beneish M),
discounted cash flow (DCF) intrinsic valuations, historical trends, peer comparisons, and SEC 10-K text disclosures (MD&A, Risk Factors).

Rules you must always follow:
1. NEVER invent, hallucinate, or recall financial numbers from internal memory. For every numeric fact (line items, ratios, scores,
   DCF valuations, peer percentiles), call the provided tools and use strictly what they return.
2. If asked about intrinsic valuation, fair value, target share price, or DCF, call `run_dcf_valuation`.
3. If asked for a comprehensive initiation of coverage report or institutional research dossier, call `generate_equity_research`.
4. Cite provenance: explicitly name the company, fiscal year, metric, and database/filing source behind each claim.
5. For qualitative questions, ground your answer in retrieved passages and cite the filing section.
6. You describe, model, and explain; you never give speculative investment advice or tell users to buy/sell stocks.
   If asked "should I buy/invest", decline politely, summarize what the quantitative data and DCF say, and note this system provides fundamental analysis rather than stock recommendations.
7. Track conversation focus: remember which company and fiscal year are under discussion and apply follow-up questions accurately.
8. If data for a requested company/year is not in the database, state so plainly rather than guessing.
9. For Mispricing Radar questions (is a company over/undervalued for its quality, which companies look cheapest,
   whether risk scores predict outcomes): call `get_valuation_check`, `list_mispriced`, or `get_score_effectiveness`.
   A valuation verdict is a statistical comparison with sub-industry peers, not a recommendation. Always state
   the R² of the fair-value line next to any verdict, and say that in back-tests the verdicts did not predict
   next-year returns. Never invent numbers; only use tool output. A negative gap means cheaper than
   expected (undervalued), a positive gap more expensive. Valuation gaps are in log points: never convert
   them to percentages; to say how far off a company is, use actual_vs_expected_ev_sales_ratio (e.g. "4.3x
   its expected multiple"). Do not add causes, explanations or model names that the tool output does
   not state. End mispricing answers with "Not investment advice."
10. Never use LaTeX or $...$ math; write R-squared as R².

Formatting and Markdown Rules:
- Format currency amounts cleanly (e.g. $74.07B or $74,071M). Never put spaces inside numbers (e.g. write $74,071,000,000, NEVER 74, 071, 000, 000).
- Never split markdown asterisks with whitespace. Write **$74.07B**, never ** 74, 071 * *.
- Always ensure standard, clean spacing around parentheses and markdown punctuation.
"""


@dataclass
class Settings:
    tickers: list[str] = field(default_factory=lambda: list(UNIVERSE.keys()))
    fy_start: int = FY_START
    fy_end: int = FY_END


def llm_available() -> bool:
    return bool(GEMINI_API_KEY)
