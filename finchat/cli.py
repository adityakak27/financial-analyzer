from __future__ import annotations

import argparse
import sys
import time

from finchat.chatbot.agent import FinChatAgent
from finchat.collect.pipeline import collect_all
from finchat.collect.text_pipeline import collect_text
from finchat.config import RESULTS_DIR, UNIVERSE
from finchat.engine.pipeline import run_engine
from finchat.evaluation.build_eval_set import main as build_eval
from finchat.evaluation.report import build_report
from finchat.evaluation.run_consistency import run_consistency
from finchat.evaluation.run_grounding import run_grounding
from finchat.evaluation.run_multiturn import run_multiturn


DEMO_QUESTIONS = [
    ("What was Apple's gross margin in FY2022?", "factual (single number)"),
    ("What about operating margin?", "multi-turn follow-up"),
    ("And the year before?", "relative-year follow-up"),
    ("How does Microsoft compare on ROE for FY2022?", "peer comparison"),
    ("Show me Microsoft's Altman Z-Score for FY2023.", "distress score"),
    ("Does Intel look like a distress risk in FY2023?", "analytical"),
    ("What supply chain risks did NVIDIA disclose in FY2023?", "qualitative retrieval"),
    ("Should I buy NVDA stock right now?", "advice guardrail probe"),
]


def cmd_chat(args) -> None:
    agent = FinChatAgent(force_offline=args.offline)
    mode = "OFFLINE deterministic" if not agent.llm.available or args.offline else f"LLM ({args.model or 'default'})"
    print(f"Conversational Fundamental Analyst - {mode}")
    print("Covered:", ", ".join(UNIVERSE.keys()))
    print("Type your question (empty line or 'quit' to exit).\n")
    while True:
        try:
            q = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in {"quit", "exit"}:
            break
        t0 = time.time()
        resp = agent.ask(q)
        print(f"\nanalyst> {resp.answer}")
        if resp.citations:
            print("\nsources:")
            for c in resp.citations[:6]:
                extra = c.get("url") or c.get("table") or ""
                print(f"  - [{c['type']}] {c.get('ticker', '')} {c.get('fy', '')} {c.get('section', '')} {extra}")
        print(f"({time.time() - t0:.1f}s, intent={resp.intent}, mode={resp.mode})\n")


def cmd_demo(args) -> None:
    agent = FinChatAgent(force_offline=args.offline)
    lines = ["# Sample Conversation Transcripts",
             "", f"_Mode: {'offline-deterministic' if args.offline or not agent.llm.available else 'LLM'} | "
                 f"Generated {time.strftime('%Y-%m-%d %H:%M')}_", ""]
    agent.reset()
    for q, label in DEMO_QUESTIONS:
        resp = agent.ask(q)
        lines += [f"## [{label}]", "", f"**User:** {q}", "",
                  f"**Analyst:**", "", resp.answer, ""]
        if resp.tool_trace:
            lines += ["**Tool calls:** " + ", ".join(
                f"`{t['name']}({t['args']})`" for t in resp.tool_trace), ""]
        if resp.citations:
            lines += ["**Sources:**"]
            seen = set()
            for c in resp.citations:
                key = json_dumps_key(c)
                if key in seen:
                    continue
                seen.add(key)
                url = c.get("url")
                desc = f"{c['type']}" + (f" - {c.get('table')}" if c.get('table') else "") \
                    + (f" - {c.get('ticker')} FY{c.get('fy')}" if c.get('ticker') else "") \
                    + (f" - {c.get('section')}" if c.get('section') else "")
                lines.append(f"- {desc}" + (f" ([filing]({url}))" if url else ""))
            lines.append("")
    out = RESULTS_DIR / "demo_transcript.md"
    out.write_text("\n".join(lines))
    print(f"[demo] wrote {out}")


def json_dumps_key(c) -> str:
    import json

    return json.dumps(c, sort_keys=True, default=str)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="finchat",
                                description="Conversational fundamental-analysis assistant")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("collect", help="collect financial statement facts from SEC EDGAR")
    s.add_argument("tickers", nargs="*", default=None)

    s = sub.add_parser("analyze", help="compute ratios, DuPont, Altman/Piotroski/Beneish, peer ranks")
    s.add_argument("--market-data", action="store_true", help="use yfinance market caps when available")

    s = sub.add_parser("index-text", help="download 10-Ks, extract MD&A/Risk Factors, build text index")
    s.add_argument("tickers", nargs="*", default=None)

    s = sub.add_parser("build-eval", help="build evaluation question sets")

    s = sub.add_parser("chat", help="interactive terminal chat")
    s.add_argument("--offline", action="store_true")
    s.add_argument("--model", default=None)

    s = sub.add_parser("eval-grounding", help="run grounding accuracy eval")
    s.add_argument("--system", choices=["hybrid", "naive_rag"], default="hybrid")
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--offline", action="store_true")

    s = sub.add_parser("eval-multiturn", help="run multi-turn context retention eval")
    s.add_argument("--offline", action="store_true")
    s.add_argument("--limit", type=int, default=None)

    s = sub.add_parser("eval-consistency", help="run analytical-consistency + guardrail + qualitative eval")
    s.add_argument("--offline", action="store_true")

    s = sub.add_parser("report", help="aggregate latest results into markdown report")

    s = sub.add_parser("demo", help="generate sample conversation transcripts")
    s.add_argument("--offline", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "collect":
        tickers = args.tickers or list(UNIVERSE.keys())
        counts = collect_all(tickers)
        print(f"[collect] done: {counts}")
    elif args.cmd == "analyze":
        run_engine(use_market_data=args.market_data)
    elif args.cmd == "index-text":
        collect_text(args.tickers or list(UNIVERSE.keys()))
    elif args.cmd == "build-eval":
        build_eval()
    elif args.cmd == "chat":
        cmd_chat(args)
    elif args.cmd == "eval-grounding":
        run_grounding(args.system, limit=args.limit, force_offline=args.offline)
    elif args.cmd == "eval-multiturn":
        run_multiturn(force_offline=args.offline, limit=args.limit)
    elif args.cmd == "eval-consistency":
        run_consistency(force_offline=args.offline)
    elif args.cmd == "report":
        build_report()
    elif args.cmd == "demo":
        cmd_demo(args)


if __name__ == "__main__":
    main(sys.argv[1:])
