from __future__ import annotations

import re
from typing import Any

from finchat.chatbot.llm import LLMClient
from finchat.nlp.index import get_retriever
from finchat.config import CHUNK_SIZE


BASELINE_PROMPT = """You are answering financial-analysis questions using ONLY the filing excerpts below.
Do not use outside knowledge. If the excerpts do not contain the answer, say you cannot find it.

FILING EXCERPTS:
{context}

QUESTION: {question}

Answer concisely. Lead with the number if the question asks for one.
"""


class NaiveRAG:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.retriever = get_retriever()
        self.llm = llm or LLMClient()

    def answer(self, question: str) -> dict[str, Any]:
        passages = self.retriever.search(question, k=6)
        context = "\n\n---\n\n".join(
            f"[{p.ticker} FY{p.fy} {p.section}] {p.text[:CHUNK_SIZE]}" for p in passages)
        mode = "extractive"
        text: str | None = None
        if self.llm.available:
            try:
                resp = self.llm.chat([
                    {"role": "user", "content": BASELINE_PROMPT.format(context=context, question=question)},
                ])
                content, _ = LLMClient.parse_response(resp)
                text = content
                mode = "llm_context_stuffing"
            except Exception:
                text = None
        if not text:
            text = self._extractive_answer(question, passages)
            mode = "extractive_offline"
        return {
            "answer": text,
            "mode": mode,
            "retrieved": [{"ticker": p.ticker, "fy": p.fy, "section": p.section,
                           "score": round(p.score, 3)} for p in passages],
        }

    def _extractive_answer(self, question: str, passages: list) -> str:
        q_tokens = set(re.findall(r"[a-z]+", question.lower()))
        best_sentence, best_hits = "", 0
        for p in passages[:3]:
            for sent in re.split(r"(?<=[.!?])\s+", p.text):
                toks = set(re.findall(r"[a-z]+", sent.lower()))
                overlap = len(toks & q_tokens)
                has_number = bool(re.search(r"\d", sent))
                score = overlap + (1 if has_number else 0)
                if score > best_hits and len(sent) > 40:
                    best_hits = score
                    best_sentence = sent.strip()
        if not best_sentence:
            return "I could not find relevant filing text to answer this."
        src = f"[{passages[0].ticker} FY{passages[0].fy} {passages[0].section}]" if passages else ""
        return f"Based on retrieved filing text {src}: \"{best_sentence}\""
