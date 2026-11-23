"""Step 9: ask the live FinChat agent (Gemini + tools) the Radar questions and record the answers,
the tools it called, and whether every number in each answer traces to tool output.
Output: analysis/outputs/chat_demo.md + outputs/tables/chat_demo_log.csv."""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.config import OUTPUTS_DIR, TABLES_DIR
from finchat.chatbot.agent import FinChatAgent

QUESTIONS = [
    "Is Nvidia overvalued for its quality?",
    "Which tech companies look cheapest right now?",
    "Do high Piotroski scores lead to better returns?",
]
NUM_RE = re.compile(r"(?<![A-Za-z_^\d.])-?\d+\.?\d*")


def _numbers(obj) -> list[float]:
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in _numbers(v)]
    if isinstance(obj, (list, tuple)):
        return [n for v in obj for n in _numbers(v)]
    if isinstance(obj, str):
        return [float(m) for m in NUM_RE.findall(obj)]
    return []


def untraced_numbers(answer: str, tool_results: list) -> list[str]:
    """Numbers in the answer that match no tool-output value (as-is, x100 for percentages, or rounded)."""
    src = _numbers(tool_results)
    cands = src + [s * 100 for s in src]
    # Layout, not claims: numbered-list markers, numbered headings and a table's rank column.
    answer = re.sub(r"(?m)^\s*(#+\s*)?\d+\.\s", "", answer)
    answer = re.sub(r"(?m)^\|\s*\d+\s*\|", "|", answer)
    bad = []
    for m in NUM_RE.findall(answer):
        n = float(m)
        if abs(n) < 1 or n == 100.0:
            continue
        if not any(abs(n - c) <= max(abs(c) * 0.01, 0.05) for c in cands):
            bad.append(m)
    return bad


def ask(agent: FinChatAgent, q: str):
    for wait in (0, 20, 45, 60):
        time.sleep(wait)
        try:
            return agent.ask(q)
        except Exception as exc:
            if "429" not in str(exc) and "503" not in str(exc):
                raise
            print(f"  [gemini busy] retrying in a moment")
    raise RuntimeError("Gemini unavailable")


def main():
    agent = FinChatAgent()
    sections, log = ["# Live chat demo: FinChat agent on the Mispricing Radar\n"], []
    for q in QUESTIONS:
        agent.reset()
        resp = ask(agent, q)
        tools = [t["name"] for t in resp.tool_trace]
        results = [t.get("result") for t in resp.tool_trace]
        bad = untraced_numbers(resp.answer, results)
        log.append({"question": q, "tools_called": ", ".join(tools), "numbers_untraced": len(bad),
                    "untraced": " ".join(bad)})
        sections.append(f"\n## Q: {q}\n\n**Tools called:** {', '.join(f'`{t}`' for t in tools) or 'none'}\n\n"
                        f"**Answer:**\n\n{resp.answer.strip()}\n\n"
                        f"*Numbers in the answer not found in tool output: {len(bad)}*\n")
        print(f"[chat] {q} -> tools={tools}, untraced={bad}")
        time.sleep(15)
    (OUTPUTS_DIR / "chat_demo.md").write_text("\n".join(sections), encoding="utf-8")
    pd.DataFrame(log).to_csv(TABLES_DIR / "chat_demo_log.csv", index=False)
    print("[saved] chat_demo.md, chat_demo_log.csv")


if __name__ == "__main__":
    main()
