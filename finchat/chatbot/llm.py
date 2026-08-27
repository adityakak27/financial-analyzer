from __future__ import annotations

import json
from typing import Any

from finchat.chatbot import tools as T
from finchat.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        self._client: Any = None
        self.available = bool(LLM_API_KEY)
        if self.available:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
            except Exception:
                self.available = False

    def chat(self, messages: list[dict[str, Any]], tool_schemas: list[dict[str, Any]] | None = None,
             temperature: float = 0.0) -> Any:
        if not self.available or self._client is None:
            raise LLMUnavailable("No LLM API key configured; running offline mode.")
        kwargs: dict[str, Any] = {
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
        }
        if tool_schemas:
            kwargs["tools"] = tool_schemas
        return self._client.chat.completions.create(**kwargs)

    @staticmethod
    def parse_response(resp: Any) -> tuple[str | None, list[dict[str, Any]]]:
        msg = resp.choices[0].message
        content = getattr(msg, "content", None)
        calls = []
        for tc in (getattr(msg, "tool_calls", None) or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            calls.append({"id": tc.id, "name": tc.function.name, "args": args})
        return content, calls
