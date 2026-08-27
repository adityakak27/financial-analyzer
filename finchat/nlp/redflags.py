from __future__ import annotations

import re

RED_FLAG_PATTERNS: dict[str, str] = {
    "going_concern": r"going concern",
    "material_weakness": r"material weakness",
    "restatement": r"restat(e|ed|ement|ements)",
    "impairment": r"impair(ment|ments|ed)",
    "litigation": r"litigation|lawsuit",
    "regulatory_investigation": r"investigation|subpoena|enforcement action",
    "covenant_or_default": r"default(ed)? (on|under)|covenant",
    "customer_concentration": r"(customer|client) concentration|a significant portion of our revenue",
    "supply_chain": r"supply chain|component shortag|constrained supply",
    "cybersecurity": r"cybersecurity|data breach|security incident",
    "competition_intensity": r"highly competitive|intense competition|aggressive pricing",
    "macro_inflation": r"inflation(ary)?|interest rate (rises|increases)|recession",
    "key_personnel": r"key (personnel|employees|management)",
    "ip_protection": r"intellectual property.*(protect|infring)",
    "foreign_operations": r"international operations|foreign currency|tariffs?",
}

COMPILED = {k: re.compile(v, re.IGNORECASE) for k, v in RED_FLAG_PATTERNS.items()}


def scan_red_flags(text: str) -> dict[str, int]:
    return {name: len(rx.findall(text)) for name, rx in COMPILED.items() if rx.search(text)}


def red_flag_snippets(text: str, flag: str, max_snippets: int = 2, window: int = 240) -> list[str]:
    rx = COMPILED.get(flag)
    if rx is None:
        return []
    snippets = []
    for m in rx.finditer(text):
        start = max(0, m.start() - window // 2)
        end = min(len(text), m.end() + window // 2)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        snippets.append(snippet)
        if len(snippets) >= max_snippets:
            break
    return snippets
