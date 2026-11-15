from __future__ import annotations

import json
from typing import Any

from finchat.config import GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, force_offline: bool = False, model: str | None = None) -> None:
        self.available = False
        self._client: Any = None
        self.model = (model or GEMINI_MODEL).strip()
        
        if force_offline or not GEMINI_API_KEY:
            return

        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=GEMINI_API_KEY,
                base_url=GEMINI_BASE_URL,
            )
            self.available = True
        except Exception:
            self.available = False

    @property
    def display_name(self) -> str:
        if not self.available:
            return "Offline (Deterministic)"
        return f"Google Gemini ({self.model})"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> Any:
        if not self.available or self._client is None:
            raise LLMUnavailable("No GEMINI_API_KEY configured; running in offline mode.")
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tool_schemas:
            kwargs["tools"] = tool_schemas
        return self._client.chat.completions.create(**kwargs)

    @staticmethod
    def parse_response(resp: Any) -> tuple[str | None, list[dict[str, Any]]]:
        if not resp or not getattr(resp, "choices", None):
            return None, []
        msg = resp.choices[0].message
        content = getattr(msg, "content", None)
        calls: list[dict[str, Any]] = []
        for i, tc in enumerate(getattr(msg, "tool_calls", None) or []):
            fn = getattr(tc, "function", None)
            if not fn:
                continue
            name = getattr(fn, "name", "")
            raw_args = getattr(fn, "arguments", "{}")
            if isinstance(raw_args, dict):
                args = raw_args
            elif isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args or "{}")
                except Exception:
                    args = {}
            else:
                args = {}
            call_id = getattr(tc, "id", None) or f"call_{i}_{name}"
            calls.append({"id": call_id, "name": name, "args": args})
        return content, calls
