from __future__ import annotations

import argparse
import sys
import time

from finchat.chatbot.agent import FinChatAgent
from finchat.collect.pipeline import collect_all
from finchat.collect.text_pipeline import collect_text
from finchat.config import RESULTS_DIR, UNIVERSE
from finchat.engine.dcf import calculate_dcf
from finchat.engine.pipeline import run_engine
from finchat.engine.research_agents import ResearchDirector
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
    ("Run a DCF valuation for Apple.", "valuation modeling"),
]


def cmd_chat(args) -> None:
    agent = FinChatAgent(model=getattr(args, "model", None))
    print(f"Institutional Equity Research Copilot - {agent.llm.display_name}")
    print("Covered Universe:", ", ".join(UNIVERSE.keys()))
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


def cmd_dcf(args) -> None:
    ticker = args.ticker.upper().strip()
    res = calculate_dcf(
        ticker,
        wacc=args.wacc,
        terminal_growth=args.terminal_growth,
        forecast_years=args.years,
    )
    if "error" in res:
        print(f"Error: {res['error']}")
        return
    print(f"\n=======================================================")
    print(f" DCF VALUATION: {ticker} (FY{res['latest_fy']})")
    print(f"=======================================================")
    print(f"Assumed WACC: {res['assumptions']['wacc'] * 100:.1f}%")
    print(f"Terminal Growth Rate: {res['assumptions']['terminal_growth'] * 100:.1f}%")
    print(f"PV of Projections: ${res['pv_projected_fcf']:,.0f}")
    print(f"PV of Terminal Value: ${res['pv_terminal_value']:,.0f} ({res['terminal_value_pct_of_ev'] * 100:.1f}% of EV)")
    print(f"Enterprise Value: ${res['enterprise_value']:,.0f}")
    print(f"Implied Equity Value: ${res['implied_equity_value']:,.0f}")
    price = res.get("implied_share_price")
    print(f"Implied Share Price: ${price:.2f}" if price else "Implied Share Price: N/A")
    print("\nSensitivity Matrix (WACC vs Terminal Growth):")
    cols = " | ".join(f"{g:.1f}%" for g in res["sensitivity_matrix"]["growth_axis"])
    print(f"WACC \\ Growth | {cols}")
    for row in res["sensitivity_matrix"]["rows"]:
        vals = " | ".join(f"${v['implied_share_price']:.2f}" if v['implied_share_price'] else "N/A" for v in row["values"])
        print(f"{row['wacc']:.1f}% | {vals}")
    print()


def cmd_research(args) -> None:
    ticker = args.ticker.upper().strip()
    print(f"\n[Multi-Agent Panel] Initiating coverage analysis for {ticker}...")
    rd = ResearchDirector()
    res = rd.generate_initiation_report(ticker, year=args.year)
    if "error" in res:
        print(f"Error: {res['error']}")
        return
    out_file = RESULTS_DIR / f"initiation_report_{ticker}.md"
    out_file.write_text(res["markdown_report"], encoding="utf-8")
    print(f"[Done] Generated Initiation Report ({len(res['markdown_report'])} bytes)")
    print(f"[Saved] {out_file}\n")
    print(res["markdown_report"][:1200] + "\n\n... (full report saved to file) ...\n")


def cmd_demo(args) -> None:
    agent = FinChatAgent()
    lines = ["# Sample Conversation Transcripts",
             "", f"_Mode: Google Gemini | Generated {time.strftime('%Y-%m-%d %H:%M')}_", ""]
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
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[demo] wrote {out}")


def json_dumps_key(c) -> str:
    import json

    return json.dumps(c, sort_keys=True, default=str)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="finchat",
                                description="Institutional Equity Research Copilot & Fundamental Analyst")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("collect", help="collect financial statement facts from SEC EDGAR")
    s.add_argument("tickers", nargs="*", default=None)

    s = sub.add_parser("analyze", help="compute ratios, DuPont, Altman/Piotroski/Beneish, peer ranks")
    s.add_argument("--market-data", action="store_true", help="use yfinance market caps when available")

    s = sub.add_parser("index-text", help="download 10-Ks, extract MD&A/Risk Factors, build text index")
    s.add_argument("tickers", nargs="*", default=None)

    s = sub.add_parser("build-eval", help="build evaluation question sets")

    s = sub.add_parser("chat", help="interactive terminal chat")
    s.add_argument("--model", default=None, help="Gemini model name")

    s = sub.add_parser("dcf", help="run interactive DCF valuation model")
    s.add_argument("ticker", help="company ticker (e.g. AAPL)")
    s.add_argument("--wacc", type=float, default=0.09, help="discount rate (default: 0.09)")
    s.add_argument("--terminal-growth", type=float, default=0.025, help="terminal growth rate (default: 0.025)")
    s.add_argument("--years", type=int, default=5, help="projection horizon in years (default: 5)")

    s = sub.add_parser("research", help="generate comprehensive initiation of coverage report")
    s.add_argument("ticker", help="company ticker (e.g. AAPL)")
    s.add_argument("--year", type=int, default=None, help="fiscal year (default: latest)")

    s = sub.add_parser("eval-grounding", help="run grounding accuracy eval")
    s.add_argument("--system", choices=["hybrid", "naive_rag"], default="hybrid")
    s.add_argument("--limit", type=int, default=None)

    s = sub.add_parser("eval-multiturn", help="run multi-turn context retention eval")
    s.add_argument("--limit", type=int, default=None)

    s = sub.add_parser("eval-consistency", help="run analytical-consistency + guardrail + qualitative eval")

    s = sub.add_parser("report", help="aggregate latest results into markdown report")

    s = sub.add_parser("demo", help="generate sample conversation transcripts")

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
    elif args.cmd == "dcf":
        cmd_dcf(args)
    elif args.cmd == "research":
        cmd_research(args)
    elif args.cmd == "eval-grounding":
        run_grounding(args.system, limit=args.limit)
    elif args.cmd == "eval-multiturn":
        run_multiturn(limit=args.limit)
    elif args.cmd == "eval-consistency":
        run_consistency()
    elif args.cmd == "report":
        build_report()
    elif args.cmd == "demo":
        cmd_demo(args)


if __name__ == "__main__":
    main(sys.argv[1:])
