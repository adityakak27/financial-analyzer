from __future__ import annotations

import json
import time
from pathlib import Path

from finchat.chatbot.agent import FinChatAgent
from finchat.config import EVAL_DIR, RESULTS_DIR
from finchat.evaluation.baseline_rag import NaiveRAG
from finchat.evaluation.checks import matches_ground_truth


def run_grounding(system: str = "hybrid", limit: int | None = None,
                  force_offline: bool = False) -> dict:
    items = json.loads((EVAL_DIR / "grounding_qa.json").read_text())
    if limit:
        items = items[:limit]
    agent = FinChatAgent(force_offline=force_offline)
    rag = NaiveRAG(llm=agent.llm) if system == "naive_rag" else None

    results = []
    for item in items:
        agent.reset()
        if rag is None:
            resp = agent.ask(item["question"])
            answer_text = resp.answer
            mode = resp.mode
        else:
            out = rag.answer(item["question"])
            answer_text = out["answer"]
            mode = out["mode"]
        ok, err = matches_ground_truth(answer_text, item["ground_truth"],
                                       item.get("tolerance_pct", 1.0),
                                       item.get("is_percent", False))
        results.append({
            "id": item["id"], "question": item["question"], "ticker": item["ticker"],
            "fy": item["fy"], "metric": item["metric"],
            "ground_truth": item["ground_truth"], "correct": ok, "err_pct": round(err, 3) if err is not None else None,
            "answer_head": answer_text[:220].replace("\n", " "), "mode": mode,
        })

    n_ok = sum(1 for r in results if r["correct"])
    summary = {
        "system": system if rag else ("hybrid_llm" if agent.llm.available and not force_offline else "hybrid_offline"),
        "n": len(results), "n_correct": n_ok,
        "grounding_accuracy_pct": round(n_ok / max(len(results), 1) * 100, 1),
        "by_subtype": {},
    }
    for sub in ("ratio", "score"):
        subset = [r for r in results if r["id"].startswith(f"gr_{sub}")]
        if subset:
            summary["by_subtype"][sub] = {
                "n": len(subset),
                "accuracy_pct": round(sum(1 for r in subset if r["correct"]) / len(subset) * 100, 1),
            }

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"grounding_{summary['system']}_{stamp}.json"
    out_path.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"[eval] full results -> {out_path}")
    return summary


if __name__ == "__main__":
    import sys

    sys_name = sys.argv[1] if len(sys.argv) > 1 else "hybrid"
    run_grounding(sys_name)
