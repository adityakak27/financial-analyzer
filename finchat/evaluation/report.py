from __future__ import annotations

import json
import time
from pathlib import Path

from finchat.config import RESULTS_DIR


def _latest(prefix: str) -> Path | None:
    files = sorted(RESULTS_DIR.glob(f"{prefix}_*.json"))
    return files[-1] if files else None


def build_report() -> Path:
    lines = ["# Evaluation Report - Conversational Fundamental Analyst",
             "", f"_Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}_", ""]

    g_files = sorted(RESULTS_DIR.glob("grounding_*.json"))
    if g_files:
        lines += ["## Grounding accuracy (H1, H2)", "",
                  "| System | N | Accuracy | Ratio acc. | Score acc. |", "|---|---|---|---|---|"]
        seen_systems: set[str] = set()
        for f in reversed(g_files):
            data = json.loads(f.read_text())
            s = data["summary"]
            if s["system"] in seen_systems:
                continue
            seen_systems.add(s["system"])
            by = s.get("by_subtype", {})
            lines.append(f"| {s['system']} | {s['n']} | {s['grounding_accuracy_pct']}% "
                         f"| {by.get('ratio', {}).get('accuracy_pct', '-')}% "
                         f"| {by.get('score', {}).get('accuracy_pct', '-')}% |")
        lines += ["", "### Failure cases (most recent hybrid run)", ""]
        latest_hybrid = next((f for f in reversed(g_files) if json.loads(f.read_text())
                              ["summary"]["system"].startswith("hybrid")), None)
        if latest_hybrid:
            data = json.loads(latest_hybrid.read_text())
            failures = [r for r in data["results"] if not r["correct"]]
            if failures:
                for r in failures[:15]:
                    lines.append(f"- `{r['id']}` {r['question']} - expected {r['ground_truth']}, "
                                 f"answer head: \"{r['answer_head'][:120]}\"")
            else:
                lines.append("- none in this run")
    else:
        lines += ["## Grounding accuracy", "", "_No grounding runs yet._"]

    m_file = _latest("multiturn")
    if m_file:
        s = json.loads(m_file.read_text())["summary"]
        lines += ["", "## Multi-turn context retention (H4)", "",
                  f"- Steps passed: {s['n_passed']}/{s['n_steps']} ({s['context_retention_pct']}%)"]
        if s.get("failed_steps"):
            for fs in s["failed_steps"][:10]:
                lines.append(f"  - FAIL [{fs['script_id']} step {fs['step']}] \"{fs['question']}\" "
                             f"(trace tickers {fs['trace_tickers']}, fys {fs['trace_fys']})")

    c_file = _latest("consistency")
    if c_file:
        s = json.loads(c_file.read_text())["summary"]
        lines += ["", "## Analytical consistency & guardrails (H3)", ""]
        an = s.get("analytical", {})
        lines.append(f"- Stance consistent with underlying scores: {an.get('stance_consistency_pct')}% "
                     f"of {an.get('n')} questions")
        lines.append(f"- Required numbers explicitly cited: {an.get('numbers_cited_pct')}%")
        gd = s.get("guardrail", {})
        lines.append(f"- Advice guardrail respected: {gd.get('respected_pct')}% of {gd.get('n')} probes")
        ql = s.get("qualitative", {})
        lines.append(f"- Qualitative answers grounded in correct filing text: {ql.get('grounded_retrieval_pct')}% "
                     f"of {ql.get('n')} questions")

    lines += ["", "## Limitations", "",
              "- Hand-built evaluation set (small N); results are indicative, not statistically definitive.",
              "- Offline (no-LLM) baseline uses extractive heuristics; the cleanest H1 comparison requires "
              "an LLM API key so both arms use generation.",
              "- Peer percentiles compare fiscal-year labels across companies with different FY end months.",
              "- Beneish DEPI uses a depreciation-rate proxy from available XBRL tags."]

    out = RESULTS_DIR / "summary_report.md"
    out.write_text("\n".join(lines))
    print(f"[report] wrote {out}")
    return out
