from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from finchat.chatbot.llm import LLMClient
from finchat.chatbot.state import ConversationState, resolve_question
from finchat.chatbot.tools import (
    TOOL_SCHEMAS,
    call_tool,
    format_metric_value,
)
from finchat.config import SYSTEM_PROMPT, UNIVERSE
from finchat.db import get_db


@dataclass
class AgentResponse:
    question: str
    answer: str
    intent: str | None = "llm"
    mode: str = "gemini"
    citations: list[dict[str, Any]] = field(default_factory=list)
    tool_trace: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "intent": self.intent,
            "mode": self.mode,
            "citations": self.citations,
            "tool_trace": [
                {k: t[k] for k in ("name", "args")} for t in self.tool_trace
            ],
        }


def default_year_map() -> dict[str, int]:
    with get_db() as con:
        rows = con.execute("SELECT ticker, MAX(fy) AS m FROM statements GROUP BY ticker").fetchall()
    return {r["ticker"]: int(r["m"]) for r in rows}


class FinChatAgent:
    def __init__(self, model: str | None = None) -> None:
        self.llm = LLMClient(model=model)
        self.state = ConversationState()
        self.history: list[dict[str, Any]] = []
        self._default_years: dict[str, int] | None = None

    def reset(self) -> None:
        self.state = ConversationState()
        self.history = []

    @property
    def default_years(self) -> dict[str, int]:
        if self._default_years is None:
            self._default_years = default_year_map()
        return self._default_years

    def ask(self, question: str) -> AgentResponse:
        if not question.strip():
            return AgentResponse(question, "Please ask a question about the covered companies.", mode="gemini")

        # Resolve context and focus tickers/years
        resolved = resolve_question(question, self.state, self.default_years)

        resp = self._ask_llm(question)

        # Update conversation state
        new_tickers = resolved.get("tickers", [])
        if new_tickers:
            self.state.update(ticker=new_tickers[0])
        if resolved.get("fy"):
            self.state.update(fy=resolved["fy"])
        elif new_tickers and self.state.current_fy is None:
            self.state.update(fy=self.default_years.get(self.state.current_ticker or ""))

        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": resp.answer})
        return resp

    def _ask_llm(self, question: str) -> AgentResponse:
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in self.history[-12:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": question})

        citations: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        final_text = None

        for _ in range(7):
            resp = self.llm.chat(messages, TOOL_SCHEMAS)
            content, calls = LLMClient.parse_response(resp)
            if not calls:
                final_text = content or "(empty response)"
                break

            if hasattr(resp.choices[0].message, "model_dump"):
                raw_msg = resp.choices[0].message.model_dump(exclude_unset=True)
                clean_msg = {k: v for k, v in raw_msg.items() if v is not None}
                messages.append(clean_msg)
            else:
                messages.append({
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {"name": c["name"], "arguments": json_dumps(c["args"])},
                        }
                        for c in calls
                    ],
                })

            for call in calls:
                result = call_tool(call["name"], call["args"])
                trace.append({"name": call["name"], "args": call["args"], "result": result})
                citations.extend(extract_citations(call["name"], result))
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json_dumps(result),
                })

        if final_text is None:
            final_text = "(The model completed tool executions and reached maximum iterations.)"

        final_text = sanitize_markdown(final_text)
        primary_intent = trace[0]["name"] if trace else "direct_synthesis"
        return AgentResponse(
            question=question,
            answer=final_text,
            intent=primary_intent,
            mode="gemini",
            citations=citations,
            tool_trace=trace,
        )


def sanitize_markdown(text: str) -> str:
    if not text:
        return ""
    import re

    # Fix numbers broken with spaces after commas (e.g. 74, 071, 000 -> 74,071,000)
    t = re.sub(r"(\d+),[ \t]+(\d{3})", r"\1,\2", text)
    t = re.sub(r"(\d+),[ \t]+(\d{3})", r"\1,\2", t)

    # Ensure space after markdown header hashes: ####Header -> #### Header
    t = re.sub(r"^(#{1,6})([^\s#])", r"\1 \2", t, flags=re.MULTILINE)

    # Ensure clean blank line before headers so Streamlit renders them as proper HTML headings
    t = re.sub(r"([^\n])\n(#{1,6}\s)", r"\1\n\n\2", t)
    return t


def json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, default=str)
    except Exception:
        return str(obj)


def company_name(ticker: str) -> str:
    with get_db() as con:
        row = con.execute("SELECT name FROM companies WHERE ticker=?", ((ticker or "").upper(),)).fetchone()
    return row["name"] if row else ticker


def extract_citations(tool_name: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    src = result.get("source") or {}
    if src.get("type") == "structured_lookup":
        fy_val = result.get("year_range") or result.get("year") or result.get("latest_fy")
        tbl = src.get("table", "statements")
        if "ticker_a" in result and "ticker_b" in result:
            out.append({
                "type": "structured_lookup",
                "table": tbl,
                "ticker": f"{result.get('ticker_a')} vs {result.get('ticker_b')}",
                "fy": fy_val,
                "metric": "company_duel",
            })
        else:
            out.append({
                "type": "structured_lookup",
                "table": tbl,
                "ticker": result.get("ticker"),
                "fy": fy_val,
                "metric": result.get("metric", tool_name),
            })
    for p in result.get("results", []) or []:
        out.append({
            "type": "filing_text",
            "ticker": p.get("ticker"),
            "fy": p.get("year"),
            "section": p.get("section"),
            "chunk_id": p.get("chunk_id"),
            "url": p.get("citation_url"),
        })
    return out
