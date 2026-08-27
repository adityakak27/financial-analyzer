from __future__ import annotations

import json
import re
import sys

from finchat.collect.edgar import Edgar
from finchat.config import CHUNK_OVERLAP, CHUNK_SIZE, FY_START, FY_END, UNIVERSE
from finchat.db import get_db, init_db, upsert
from finchat.nlp.redflags import scan_red_flags
from finchat.nlp.sections import extract_sections, html_to_text
from finchat.nlp.sentiment import sentiment_counts


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        if len(para) > size:
            if buf:
                chunks.append(buf)
                buf = ""
            step = size - overlap
            for i in range(0, len(para), step):
                piece = para[i:i + size]
                if len(piece) > 80:
                    chunks.append(piece)
            continue
        if len(buf) + len(para) + 1 > size:
            chunks.append(buf)
            buf = buf[-overlap:] + "\n" + para if overlap else para
        else:
            buf = f"{buf}\n{para}" if buf else para
    if buf.strip():
        chunks.append(buf)
    return [re.sub(r"\s+", " ", c).strip() for c in chunks if len(c) > 60]


def process_ticker(ticker: str, include_full_text: bool = True) -> dict[int, dict]:
    con_info: dict[int, dict] = {}
    edgar = Edgar()
    cik, name = edgar.cik_for(ticker)
    filings = edgar.tenk_filings(cik, FY_START - 1, FY_END + 1)

    with get_db() as con:
        row = con.execute("SELECT fy FROM filings WHERE ticker=?", (ticker,)).fetchall()
        done_fys = {r["fy"] for r in row}

    seen_labels: set[int] = set()
    for filing in filings:
        guess = filing["fy_label_guess"]
        label = None
        for cand in range(guess, guess - 2, -1):
            if cand not in seen_labels and FY_START <= cand <= FY_END:
                label = cand
                break
        if label is None or label in seen_labels:
            continue

        print(f"[text] {ticker} FY{label} <- filed {filing['filed']}", flush=True)
        try:
            path = edgar.download_filing(filing, cik)
        except Exception as exc:
            print(f"  download failed: {exc}", file=sys.stderr)
            continue
        raw_html = path.read_text(encoding="utf-8", errors="ignore")
        text = html_to_text(raw_html)
        sections = extract_sections(text)

        entry = {"mda": "", "risk": "", "full": ""}
        if sections:
            entry["mda"] = sections.get("mda", "")
            entry["risk"] = sections.get("risk", "")
        entry["full"] = text[:600_000]

        stats_by_section = {}
        chunk_rows = []
        for section_name, body in entry.items():
            if not body:
                continue
            counts = sentiment_counts(body)
            flags = scan_red_flags(body)
            stats_by_section[section_name] = {**counts, "redflags": flags}
            pieces = chunk_text(body)
            for idx, piece in enumerate(pieces):
                chunk_rows.append({
                    "chunk_id": f"{ticker}_{label}_{section_name}_{idx}",
                    "ticker": ticker, "fy": label, "section": section_name,
                    "idx": idx, "text": piece,
                })

        con_info[label] = {
            "filing": filing,
            "stats": stats_by_section,
            "chunks": chunk_rows,
        }
        seen_labels.add(label)

        with get_db() as con:
            upsert(con, "filings", {
                "ticker": ticker, "fy": label, "form": "10-K",
                "accession": filing["accession"], "filed": filing["filed"],
                "url": filing["url"],
                "mda_chars": len(entry.get("mda", "")),
                "risk_chars": len(entry.get("risk", "")),
            })
            for chunk in chunk_rows:
                upsert(con, "chunks", chunk)
            for section_name, stats in stats_by_section.items():
                upsert(con, "textstats", {
                    "ticker": ticker, "fy": label, "section": section_name,
                    "n_words": int(stats["n_words"]),
                    "neg_frac": stats["neg_frac"], "pos_frac": stats["pos_frac"],
                    "polarity": stats["polarity"],
                    "redflags_json": json.dumps(stats["redflags"]),
                })

    from finchat.nlp.index import get_retriever

    get_retriever().invalidate()
    return con_info


def collect_text(tickers: list[str] | None = None, include_full_text: bool = True) -> None:
    init_db()
    tickers = tickers or list(UNIVERSE.keys())
    for ticker in tickers:
        info = process_ticker(ticker, include_full_text)
        total_chunks = sum(len(v["chunks"]) for v in info.values())
        print(f"[text] {ticker}: {len(info)} filings, {total_chunks} chunks")


if __name__ == "__main__":
    args = sys.argv[1:]
    collect_text(args or None)
