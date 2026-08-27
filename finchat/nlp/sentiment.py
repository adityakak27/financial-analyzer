from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from finchat.config import LM_LEXICON_PATH

FALLBACK_NEGATIVE = """
adverse adversely allegations alleged impairment impairments breach breached breaches claim claims
complaint complaints contingency contingencies criminal damages default defaults deficient deficiency
delinquency delinquencies deteriorate deteriorated deterioration difficulty difficulties disadvantage
disruption disruptions doubt doubts decline declines declined declining decrease decreased decreases
decreasing deficit deficits delay delayed delays devaluation downgrade downgraded downgrades failure
failures failed fraud guarantee guarantees hinder hindrance inability inadequate incur incurred infraction
injunction investigation investigations lawsuit lawsuits litigation loss losses lost material-weakness
materialweakness misstatement misstatements noncompliance nonconformity notice notices obligation obligations
penalties penalty proceeding proceedings recall recalls restructure restructuring restructurings restatement
restatements resignations sanction sanctions scrutiny settlement settlements terminated termination terminations
uncertainties uncertainty unfavorable unenforceable violation violations weaken weakened weakness weaknesses
write-off write-offs writedown writedowns risk risks risky threatened threat threats vulnerable volatility
challenging challenges challenge intensified competitive-pressure supply-chain disruption-in supply constraints
inflationary recession cybersecurity incident incidents breach exposure exposures concentration dependence
reliance obsolete obsolescence expiration expiring cancellation cancellations counterparty insolvency bankruptcy
""".split()

FALLBACK_POSITIVE = """
achieve achieved achieves advantage advantages improve improved improves improvement improvements
successful successfully exceed exceeded exceeds outperform outperformed growth grew increase increased
increases increasing strong stronger strongest profitable profitability efficiency efficiencies effective
effectively opportunity opportunities expand expanded expanding innovation innovative leading leader leading-edge
momentum favorable favourably resilient strength strengths robust streamlined optimize optimized gain gained
gains progress benefit benefits beneficial valuable value-driven commitment dedicated excellence quality
sustainable long-standing well-positioned positioned record higher best greater enhanced enhancement
""".split()


@lru_cache(maxsize=2)
def load_lexicon() -> tuple[set[str], set[str]]:
    path = Path(LM_LEXICON_PATH)
    if path.exists():
        neg: set[str] = set()
        pos: set[str] = set()
        with open(path, newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}
            word_col = cols.get("word")
            if word_col:
                neg_col = next((c for k, c in cols.items() if k == "negative"), None)
                pos_col = next((c for k, c in cols.items() if k.startswith("positive")), None)
                for row in reader:
                    w = (row.get(word_col) or "").strip().lower()
                    if not w:
                        continue
                    if neg_col and (row.get(neg_col) or "").strip().upper().startswith("Y"):
                        neg.add(w)
                    if pos_col and (row.get(pos_col) or "").strip().upper().startswith("Y"):
                        pos.add(w)
        if neg or pos:
            return neg, pos
    return set(w.lower() for w in FALLBACK_NEGATIVE), set(FALLBACK_POSITIVE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z\-']+", text)]


def sentiment_counts(text: str) -> dict[str, float]:
    tokens = _tokenize(text)
    n = len(tokens) or 1
    neg, pos = load_lexicon()
    neg_hits = sum(1 for t in tokens if t in neg)
    pos_hits = sum(1 for t in tokens if t in pos)
    neg_frac, pos_frac = neg_hits / n, pos_hits / n
    return {
        "n_words": len(tokens),
        "neg_frac": neg_frac,
        "pos_frac": pos_frac,
        "polarity": (pos_hits - neg_hits) / max(neg_hits + pos_hits, 1),
    }
