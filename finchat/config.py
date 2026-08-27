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

        load_dotenv(PROJECT_ROOT / ".env")
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

LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1") or None
LLM_MODEL = os.getenv("FINCHAT_MODEL", "gpt-4o-mini")

LM_LEXICON_PATH = Path(os.getenv("LM_LEXICON_PATH", str(DATA_DIR / "lm_lexicon.csv")))

RETRIEVAL_TOP_K = 5
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150

GROUNDING_TOLERANCE_PCT = 1.0

SYSTEM_PROMPT = """You are a conversational fundamental-analysis assistant for equity research education.
You answer questions about companies' financial statements, ratios, scores (Altman Z, Piotroski F, Beneish M),
trends and peer comparisons, and the text of their 10-K filings (MD&A, Risk Factors).

Rules you must always follow:
1. NEVER invent or recall numbers from memory. For every numeric fact (line items, ratios, scores, ranks,
   sentiment stats) call the provided tools and use only what they return.
2. Cite provenance: name the company, fiscal year, metric, and source (XBRL tag / filing section) behind each claim.
3. For qualitative questions, ground your answer in retrieved passages and say which filing/section they come from.
4. You describe and explain; you never give investment advice. If asked "should I buy/invest", decline politely,
   explain what the data says instead, and note this assistant does not make recommendations.
5. Track conversation focus: remember which company and fiscal year are under discussion and apply follow-up
   questions ("what about the year before?") to that focus unless the user changes it explicitly.
6. If data for a requested company/year is not in the database, say so plainly rather than guessing.
"""


@dataclass
class Settings:
    tickers: list[str] = field(default_factory=lambda: list(UNIVERSE.keys()))
    fy_start: int = FY_START
    fy_end: int = FY_END


def llm_available() -> bool:
    return bool(LLM_API_KEY)
