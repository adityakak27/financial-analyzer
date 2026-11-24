"""Step 1a: recompute 10-K tone (textstats table) with the official Loughran-McDonald dictionary.

Reads each 10-K already saved under data/raw/filings (no SEC downloads), re-extracts the MD&A,
Risk Factors and full-text sections exactly as the text pipeline does, recounts positive and
negative words with the dictionary at data/lm_lexicon.csv, and overwrites the textstats rows.
Run before 01_build_panel.py. Also writes a dictionary-coverage table for the report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.utils import save_table
from finchat.config import FILINGS_DIR, LM_LEXICON_PATH
from finchat.db import get_db, upsert
from finchat.nlp.redflags import scan_red_flags
from finchat.nlp.sections import extract_sections, html_to_text
from finchat.nlp.sentiment import load_lexicon, sentiment_counts


def _filing_path(accession: str) -> Path | None:
    hits = [p for p in FILINGS_DIR.glob(f"*/{accession.replace('-', '')}/*") if p.is_file()]
    return hits[0] if hits else None


def main():
    if not Path(LM_LEXICON_PATH).exists():
        sys.exit(f"Loughran-McDonald dictionary not found at {LM_LEXICON_PATH}")
    neg, pos = load_lexicon()
    print(f"Dictionary: {len(neg)} negative, {len(pos)} positive words ({LM_LEXICON_PATH})")

    with get_db() as con:
        filings = [dict(r) for r in con.execute("SELECT ticker, fy, accession FROM filings ORDER BY ticker, fy")]

    coverage, missing = [], []
    for f in filings:
        path = _filing_path(f["accession"])
        if path is None:
            missing.append(f)
            continue
        text = html_to_text(path.read_text(encoding="utf-8", errors="ignore"))
        sections = extract_sections(text) or {}
        entry = {"mda": sections.get("mda", ""), "risk": sections.get("risk", ""), "full": text[:600_000]}
        with get_db() as con:
            for section, body in entry.items():
                if not body:
                    continue
                stats = sentiment_counts(body)
                upsert(con, "textstats", {
                    "ticker": f["ticker"], "fy": f["fy"], "section": section,
                    "n_words": int(stats["n_words"]),
                    "neg_frac": stats["neg_frac"], "pos_frac": stats["pos_frac"],
                    "polarity": stats["polarity"],
                    "redflags_json": json.dumps(scan_red_flags(body)),
                })
                if section == "mda":
                    n = stats["n_words"]
                    coverage.append({"ticker": f["ticker"], "fy": f["fy"], "n_words": n,
                                     "neg_words": round(stats["neg_frac"] * n),
                                     "pos_words": round(stats["pos_frac"] * n),
                                     "polarity": stats["polarity"]})

    cov = pd.DataFrame(coverage)
    print(f"Recomputed MD&A tone for {len(cov)} filings; {len(missing)} filings not found on disk")
    for m in missing:
        print(f"  missing: {m['ticker']} FY{m['fy']} {m['accession']}")
    summary = pd.DataFrame([{
        "mda_sections": len(cov),
        "median_words": int(cov.n_words.median()),
        "median_negative_words": int(cov.neg_words.median()),
        "median_positive_words": int(cov.pos_words.median()),
        "median_share_of_words_matched_pct": round(100 * ((cov.neg_words + cov.pos_words) / cov.n_words).median(), 2),
        "sections_with_zero_matches": int(((cov.neg_words + cov.pos_words) == 0).sum()),
        "mean_polarity": round(cov.polarity.mean(), 3),
        "min_polarity": round(cov.polarity.min(), 3),
        "max_polarity": round(cov.polarity.max(), 3),
    }])
    print(summary.T.to_string(header=False))
    save_table(summary, "Table7b_Tone_Dictionary_Coverage")


if __name__ == "__main__":
    main()
