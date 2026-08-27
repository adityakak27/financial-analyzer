from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from finchat.db import get_db


@dataclass
class Passage:
    chunk_id: str
    ticker: str
    fy: int
    section: str
    idx: int
    text: str
    score: float = 0.0


@dataclass
class _IndexData:
    metas: list[Passage] = field(default_factory=list)
    matrix: object = None
    vectorizer: object = None


class Retriever:
    def __init__(self) -> None:
        self._cache: dict[tuple, _IndexData] = {}

    def _load(self, ticker: str | None, section: str | None) -> _IndexData:
        key = (ticker or "*", section or "*")
        if key in self._cache:
            return self._cache[key]
        q = "SELECT chunk_id, ticker, fy, section, idx, text FROM chunks WHERE 1=1"
        params: list = []
        if ticker:
            q += " AND ticker=?"
            params.append(ticker)
        if section:
            q += " AND section=?"
            params.append(section)
        with get_db() as con:
            rows = con.execute(q + " ORDER BY ticker, fy, section, idx", params).fetchall()
        data = _IndexData()
        data.metas = [
            Passage(r["chunk_id"], r["ticker"], r["fy"], r["section"], r["idx"], r["text"])
            for r in rows
        ]
        if data.metas:
            vec = TfidfVectorizer(stop_words="english", sublinear_tf=True,
                                  ngram_range=(1, 2), max_features=120_000)
            data.vectorizer = vec
            data.matrix = vec.fit_transform([m.text for m in data.metas])
        self._cache[key] = data
        return data

    def invalidate(self) -> None:
        self._cache.clear()

    def search(self, query: str, k: int = 5, ticker: str | None = None,
               section: str | None = None, fy: int | None = None) -> list[Passage]:
        data = self._load(ticker, section)
        if not data.metas:
            return []
        qv = data.vectorizer.transform([query])
        sims = (data.matrix @ qv.T).toarray().ravel()
        order = np.argsort(-sims)[: max(k * 3, k)]
        results = []
        for i in order:
            p = data.metas[int(i)]
            p.score = float(sims[int(i)])
            results.append(p)
        if fy is not None:
            results.sort(key=lambda p: (abs(p.fy - fy), -p.score))
        else:
            results.sort(key=lambda p: -p.score)
        return results[:k]


_default_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = Retriever()
    return _default_retriever
