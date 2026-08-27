from __future__ import annotations

import re
from typing import Any

FACTUAL_PATTERNS = [
    re.compile(r"\b(what|how much|which)\b.*\b(was|is|were|did|were the)\b", re.I),
    re.compile(r"\b(value|amount|number|figure|ratio|score|margin|growth|rank|percentile)\b", re.I),
    re.compile(r"\b(show|tell|give|list)\b.*\b(me\s+)?(the\s+)?(ratio|score|numbers?|line items?)\b", re.I),
    re.compile(r"^(and|now|then|what about|how about)\b", re.I),
    re.compile(r"\b(prior|previous|same|earlier)\s+(year|fiscal|period)", re.I),
]

QUALITATIVE_PATTERNS = [
    re.compile(r"\b(say|says|said|discuss|discussed|disclosure|disclose[d]?|mention(ed)?|report(ed)?)\b", re.I),
    re.compile(r"\b(tone|outlook|language|wording|commentary|management's view|management view)\b", re.I),
    re.compile(r"\bwhat (risks|risk factors|concerns).*(disclose|mention|identify|describe)\b", re.I),
    re.compile(r"\b(quote|passage|excerpt|section)\b", re.I),
]

ANALYTICAL_PATTERNS = [
    re.compile(r"\b(do you think|does it look|would you say|assess|assessment|evaluate|opinion|view on|interpret)\b", re.I),
    re.compile(r"\b(risky|riskiness|healthy|health(y)?|distress(ed)?|troubl(e|ing)|concerning|worry|red flags?)\b", re.I),
    re.compile(r"\b(compare|comparison|versus|vs\.?|better|worse|stronger|weaker)\b", re.I),
    re.compile(r"\b(why|what drove|explain.*(drop|decline|improvement|change))\b", re.I),
]

ADVICE_PATTERNS = re.compile(
    r"\b(should i (buy|sell|invest|hold)|is it a (good )?(buy|investment)|would you (buy|invest)|"
    r"price target|buy or sell|invest in)\b",
    re.I,
)
ADVICE_LOOSE_RE = re.compile(
    r"\bis\b.{0,40}\ba\s+good\s+(investment|buy|stock|pick)\b|\bworth investing in\b|\bgood stock to buy\b",
    re.I,
)

SCORE_WORDS = re.compile(r"\b(altman|z[- ]?score|piotroski|f[- ]?score|beneish|m[- ]?score)\b", re.I)


def classify_intent(question: str) -> str:
    q = question.strip()
    if SCORE_WORDS.search(q):
        analytical_cue = ANALYTICAL_PATTERNS[0].search(q) or re.search(
            r"\b(interpret|mean|suggest|tell us|raise|signal|indicate|concern|worry)\b", q, re.I)
        return "analytical" if analytical_cue else "factual"
    if ADVICE_PATTERNS.search(q) or ADVICE_LOOSE_RE.search(q):
        return "advice_probe"
    qualitative_hits = sum(1 for p in QUALITATIVE_PATTERNS if p.search(q))
    factual_hits = sum(1 for p in FACTUAL_PATTERNS if p.search(q))
    analytical_hits = sum(1 for p in ANALYTICAL_PATTERNS if p.search(q))

    if qualitative_hits and not factual_hits:
        return "qualitative"
    if analytical_hits and qualitative_hits == 0:
        return "analytical" if analytical_hits >= 1 else "factual"
    if analytical_hits and factual_hits:
        return "analytical"
    if qualitative_hits:
        return "qualitative"
    if factual_hits:
        return "factual"
    if re.search(r"\b(compare|vs\.?|versus)\b", q, re.I):
        return "analytical"
    return "qualitative"


def extract_metric_hint(question: str) -> str | None:
    from finchat.chatbot.tools import METRIC_ALIASES

    q = " ".join(question.lower().replace("-", " ").split())
    best: tuple[int, str] | None = None
    for alias, metric in METRIC_ALIASES.items():
        a = " ".join(alias.replace("-", " ").split())
        if re.search(rf"\b{re.escape(a)}\b", q):
            cand = (len(a), metric)
            if best is None or cand[0] > best[0]:
                best = cand
    return best[1] if best else None


def route(question: str, resolved: dict[str, Any]) -> dict[str, Any]:
    intent = classify_intent(question)
    tickers = resolved["tickers"]
    if len(tickers) >= 2:
        if intent == "factual":
            intent = "comparative_factual"
        elif intent in ("qualitative",):
            intent = "comparative_qualitative"
    elif intent == "factual":
        pass
    out: dict[str, Any] = {
        "intent": intent,
        **resolved,
    }
    return out
