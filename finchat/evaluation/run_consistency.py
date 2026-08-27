from __future__ import annotations

import json
import time

from finchat.chatbot.agent import FinChatAgent
from finchat.config import EVAL_DIR, RESULTS_DIR
from finchat.evaluation.checks import (
    extract_stance,
    guardrail_respected,
    answer_mentions_number,
)


def run_consistency(force_offline: bool = False) -> dict:
    agent = FinChatAgent(force_offline=force_offline)
    mode = "offline" if force_offline or not agent.llm.available else "llm"

    analytical = json.loads((EVAL_DIR / "analytical_rubric.json").read_text())
    guardrail = json.loads((EVAL_DIR / "guardrail_qa.json").read_text())
    qualitative = json.loads((EVAL_DIR / "qualitative_qa.json").read_text())

    an_results = []
    for item in analytical:
        agent.reset()
        resp = agent.ask(item["question"])
        stance = extract_stance(resp.answer)
        stance_ok = (stance == item["expected_stance"]) or (item["expected_stance"] == "mixed"
                                                            and stance in ("mixed", "unknown"))
        numbers_ok = all(answer_mentions_number(resp.answer, v, tol_pct=2.0)
                         for v in item.get("required_numbers", {}).values())
        contradiction = (stance != "unknown" and stance != item["expected_stance"]
                         and not (item["expected_stance"] == "mixed"))
        an_results.append({
            "id": item["id"], "question": item["question"], "ticker": item["ticker"],
            "fy": item["fy"], "expected_stance": item["expected_stance"],
            "observed_stance": stance, "stance_ok": bool(stance_ok),
            "required_numbers_cited": bool(numbers_ok),
            "contradiction": bool(contradiction),
            "answer_head": resp.answer[:250].replace("\n", " "),
        })

    gd_results = []
    for item in guardrail:
        agent.reset()
        resp = agent.ask(item["question"])
        gd_results.append({
            "id": item["id"], "question": item["question"],
            "guardrail_ok": guardrail_respected(resp.answer),
            "answer_head": resp.answer[:200].replace("\n", " "),
        })

    ql_results = []
    for item in qualitative:
        agent.reset()
        resp = agent.ask(item["question"])
        cite_tickers = {c.get("ticker", "").upper() for c in resp.citations if c.get("type") == "filing_text"}
        ticker_ok = item["ticker"].upper() in cite_tickers
        low = resp.answer.lower()
        terms_hit = [t for t in item["expected_terms"] if t.lower() in low]
        ql_results.append({
            "id": item["id"], "question": item["question"], "ticker": item["ticker"],
            "fy": item["fy"], "citation_ticker_ok": ticker_ok,
            "terms_expected": item["expected_terms"], "terms_found": terms_hit,
            "passed": ticker_ok and len(terms_hit) >= 1,
            "answer_head": resp.answer[:200].replace("\n", " "),
        })

    summary = {
        "mode": mode,
        "analytical": {
            "n": len(an_results),
            "stance_consistency_pct": round(sum(1 for r in an_results if r["stance_ok"])
                                            / max(len(an_results), 1) * 100, 1),
            "numbers_cited_pct": round(sum(1 for r in an_results if r["required_numbers_cited"])
                                       / max(len(an_results), 1) * 100, 1),
            "contradictions": [r for r in an_results if r["contradiction"]],
        },
        "guardrail": {
            "n": len(gd_results),
            "respected_pct": round(sum(1 for r in gd_results if r["guardrail_ok"])
                                   / max(len(gd_results), 1) * 100, 1),
            "failures": [r for r in gd_results if not r["guardrail_ok"]],
        },
        "qualitative": {
            "n": len(ql_results),
            "grounded_retrieval_pct": round(sum(1 for r in ql_results if r["passed"])
                                            / max(len(ql_results), 1) * 100, 1),
            "failures": [r for r in ql_results if not r["passed"]],
        },
    }

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"consistency_{mode}_{stamp}.json"
    out_path.write_text(json.dumps({
        "summary": {k: ({kk: vv for kk, vv in v.items()} if isinstance(v, dict) else v)
                    for k, v in summary.items()},
        "analytical_results": an_results,
        "guardrail_results": gd_results,
        "qualitative_results": ql_results,
    }, indent=2))
    printable = json.dumps(summary, indent=2, default=str)
    print(printable)
    print(f"[eval] full results -> {out_path}")
    return summary


if __name__ == "__main__":
    run_consistency()
