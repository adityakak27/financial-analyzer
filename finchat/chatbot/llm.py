from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

from finchat.config import GEMINI_API_KEY, GEMINI_BASE_URL, GEMINI_MODEL

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, model: str | None = None) -> None:
        self.model = (model or GEMINI_MODEL).strip()
        if not GEMINI_API_KEY:
            raise LLMUnavailable(
                "GEMINI_API_KEY is not set in environment or .env. "
                "Offline mode has been removed; a valid Google Gemini API key is required."
            )

        from openai import OpenAI

        self._client = OpenAI(
            api_key=GEMINI_API_KEY,
            base_url=GEMINI_BASE_URL,
        )
        self.available = True

    @property
    def display_name(self) -> str:
        return f"Google Gemini ({self.model})"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tool_schemas: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tool_schemas:
            kwargs["tools"] = tool_schemas
        return self._client.chat.completions.create(**kwargs)

    def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.2) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    def parse_structured(
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
        temperature: float = 0.0,
    ) -> T:
        """Enforce strict structured output conforming to a Pydantic BaseModel."""
        # 1. Attempt beta.chat.completions.parse (native structured outputs)
        try:
            resp = self._client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=response_model,
                temperature=temperature,
            )
            parsed = getattr(resp.choices[0].message, "parsed", None)
            if parsed is not None:
                return parsed
        except Exception:
            pass

        # 2. Fallback to json_object with schema instruction
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        system_instruction = {
            "role": "system",
            "content": f"You are a strict data formatter. Return ONLY valid JSON adhering strictly to this JSON schema:\n{schema_json}",
        }
        all_messages = [system_instruction] + [m for m in messages if m.get("role") != "system"]

        resp = self._client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            response_format={"type": "json_object"},
            temperature=temperature,
        )
        content = resp.choices[0].message.content or "{}"
        return response_model.model_validate_json(content)

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
