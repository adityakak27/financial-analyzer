from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from finchat.db import get_db


@dataclass
class ConversationState:
    current_ticker: str | None = None
    current_fy: int | None = None
    last_metric: str | None = None

    def update(self, ticker: str | None = None, fy: int | None = None,
               metric: str | None = None) -> None:
        if ticker:
            self.current_ticker = ticker.upper()
        if fy:
            self.current_fy = int(fy)
        if metric:
            self.last_metric = metric


ALIASES: dict[str, str] = {}


def _build_aliases() -> dict[str, str]:
    global ALIASES
    if ALIASES:
        return ALIASES
    with get_db() as con:
        rows = con.execute("SELECT ticker, name FROM companies").fetchall()
    for r in rows:
        ALIASES[r["ticker"].lower()] = r["ticker"]
        name = (r["name"] or "").lower()
        stop = {"inc", "corp", "corporation", "company", "co", "ltd", "plc", "technologies",
                "technology", "systems", "international", "holdings"}
        tokens = [re.sub(r"[^a-z0-9&.]", "", t) for t in name.split()]
        tokens = [t for t in tokens if t and t not in stop]
        if len(tokens) >= 2 or not tokens:
            pass
        for t in tokens:
            ALIASES.setdefault(t, r["ticker"])
        if tokens:
            ALIASES.setdefault(tokens[0], r["ticker"])
    return ALIASES


TWO_WORD_NAMES: list[tuple[str, str]] = []


def _build_two_word() -> list[tuple[str, str]]:
    global TWO_WORD_NAMES
    if TWO_WORD_NAMES:
        return TWO_WORD_NAMES
    with get_db() as con:
        rows = con.execute("SELECT ticker, name FROM companies").fetchall()
    stop = {"inc", "corp", "corporation", "company", "co", "ltd", "plc", "the", "group",
            "technologies", "technology", "systems", "international", "devices", "inc."}
    for r in rows:
        toks = [t.strip(".,") for t in (r["name"] or "").split()]
        core = [t.lower() for t in toks if t.lower().strip(".,") not in stop]
        if len(core) >= 2:
            phrase = f"{core[0]} {core[1]}"
            TWO_WORD_NAMES.append((phrase, r["ticker"]))
    return TWO_WORD_NAMES


def find_tickers(text: str) -> list[str]:
    aliases = _build_aliases()
    found: list[str] = []
    lowered = text.lower()
    for phrase, ticker in sorted(_build_two_word(), key=lambda x: -len(x[0])):
        if phrase in lowered and ticker not in found:
            found.append(ticker)
            lowered = lowered.replace(phrase, " ")
    for token in re.findall(r"[A-Za-z][A-Za-z0-9&.\-]*", text):
        low = token.lower().strip(".,")
        t = aliases.get(low)
        if not t or t in found:
            continue
        stripped = token.strip(".")
        if stripped.isupper() and len(stripped) >= 2:
            found.append(t)
        elif stripped[:1].isupper() and len(low) >= 4:
            found.append(t)
    return found


YEAR_RE = re.compile(r"(?<!\d)(20[0-2]\d)(?!\d)")
FOLLOWUP_PRIOR_RE = re.compile(
    r"(year before|previous year|prior year|years? earlier|before that|twelve months earlier)",
    re.I,
)
COUNT_EARLIER_RE = re.compile(r"(one|two|three|four|five|\d+)\s+years?\s+earlier", re.I)
WORD_TO_N = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def resolve_question(question: str, state: ConversationState,
                     default_years: dict[str, int] | None = None) -> dict[str, Any]:
    tickers = find_tickers(question)
    fy = None
    m = YEAR_RE.search(question)
    if m:
        fy = int(m.group(1))
    elif FOLLOWUP_PRIOR_RE.search(question):
        base = state.current_fy
        if base is None:
            base_ticker = tickers[0] if tickers else state.current_ticker
            if base_ticker and default_years:
                base = default_years.get(base_ticker)
        if base is not None:
            n = 1
            m2 = COUNT_EARLIER_RE.search(question)
            if m2:
                token = m2.group(1).lower()
                n = int(token) if token.isdigit() else WORD_TO_N.get(token, 1)
            fy = base - n
    resolved_ticker = tickers[0] if tickers else state.current_ticker
    return {
        "tickers": tickers,
        "ticker": resolved_ticker,
        "fy": fy,
        "explicit_year": m is not None,
    }
