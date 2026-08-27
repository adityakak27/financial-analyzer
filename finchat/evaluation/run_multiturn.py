from __future__ import annotations

import json
import time

from finchat.chatbot.agent import FinChatAgent
from finchat.config import EVAL_DIR, RESULTS_DIR
from finchat.evaluation.checks import tool_trace_tickers_years


def run_multiturn(force_offline: bool = False, limit: int | None = None) -> dict:
    scripts = json.loads((EVAL_DIR / "multiturn_scripts.json").read_text())
    if limit:
        scripts = scripts[:limit]
    agent = FinChatAgent(force_offline=force_offline)

    all_step_results: list[dict] = []
    transcripts = []
    for script in scripts:
        agent.reset()
        transcript = {"script_id": script["script_id"], "steps": []}
        for i, step in enumerate(script["steps"]):
            resp = agent.ask(step["q"])
            trace_tickers, trace_fys = tool_trace_tickers_years(resp)
            exp_tickers = set(t.upper() for t in step.get("expect_ticker", []))
            ticker_ok = (not exp_tickers) or bool(exp_tickers & trace_tickers)
            fy_expected = step.get("expect_fy")
            fy_ok = True if fy_expected is None else (fy_expected in trace_fys)
            step_result = {
                "script_id": script["script_id"], "step": i,
                "question": step["q"],
                "expected_tickers": sorted(exp_tickers), "trace_tickers": sorted(trace_tickers),
                "expected_fy": fy_expected, "trace_fys": sorted(trace_fys),
                "ticker_ok": ticker_ok, "fy_ok": fy_ok,
                "passed": ticker_ok and fy_ok,
                "answer_head": resp.answer[:200].replace("\n", " "),
            }
            all_step_results.append(step_result)
            transcript["steps"].append({"q": step["q"], "a": resp.answer})
        transcripts.append(transcript)

    n_pass = sum(1 for s in all_step_results if s["passed"])
    summary = {
        "mode": "offline" if force_offline or not agent.llm.available else "llm",
        "n_steps": len(all_step_results),
        "n_passed": n_pass,
        "context_retention_pct": round(n_pass / max(len(all_step_results), 1) * 100, 1),
        "failed_steps": [s for s in all_step_results if not s["passed"]],
    }

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"multiturn_{summary['mode']}_{stamp}.json"
    out_path.write_text(json.dumps({"summary": summary, "steps": all_step_results,
                                    "transcripts": transcripts}, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "failed_steps"}, indent=2))
    print(f"[eval] full results -> {out_path}")
    return summary


if __name__ == "__main__":
    run_multiturn()
