from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from finchat.chatbot.llm import LLMClient
from finchat.chatbot.router import extract_metric_hint, route
from finchat.chatbot.state import ConversationState, resolve_question
from finchat.chatbot.tools import (
    TOOL_SCHEMAS,
    call_tool,
    format_metric_value,
    tool_get_line_items,
    tool_get_ratio,
    tool_get_scores,
    tool_get_text_sentiment,
)
from finchat.config import SYSTEM_PROMPT
from finchat.db import get_db


@dataclass
class AgentResponse:
    question: str
    answer: str
    intent: str | None = None
    mode: str = "offline"
    citations: list[dict[str, Any]] = field(default_factory=list)
    tool_trace: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question, "answer": self.answer, "intent": self.intent,
            "mode": self.mode, "citations": self.citations, "tool_trace": [
                {k: t[k] for k in ("name", "args")} for t in self.tool_trace
            ],
        }


def default_year_map() -> dict[str, int]:
    with get_db() as con:
        rows = con.execute(
            "SELECT ticker, MAX(fy) AS m FROM statements GROUP BY ticker").fetchall()
    return {r["ticker"]: int(r["m"]) for r in rows}


class FinChatAgent:
    def __init__(self, force_offline: bool = False) -> None:
        self.llm = LLMClient()
        if force_offline:
            self.llm.available = False
        self.state = ConversationState()
        self.history: list[dict[str, Any]] = []
        self._default_years: dict[str, int] | None = None

    def reset(self) -> None:
        self.state = ConversationState()
        self.history = []

    @property
    def default_years(self) -> dict[str, int]:
        if self._default_years is None:
            self._default_years = default_year_map()
        return self._default_years

    def ask(self, question: str) -> AgentResponse:
        if not question.strip():
            return AgentResponse(question, "Please ask a question about the covered companies.")
        resolved = resolve_question(question, self.state, self.default_years)
        routed = route(question, resolved)
        if self.llm.available:
            resp = self._ask_llm(question)
        else:
            resp = self._ask_offline(question, routed)
        new_tickers = resolved["tickers"]
        if new_tickers:
            self.state.update(ticker=new_tickers[0])
        if resolved["fy"]:
            self.state.update(fy=resolved["fy"])
        elif new_tickers and self.state.current_fy is None:
            self.state.update(fy=self.default_years.get(self.state.current_ticker or ""))
        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": resp.answer})
        return resp

    def _ask_llm(self, question: str) -> AgentResponse:
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in self.history[-12:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": question})

        citations: list[dict[str, Any]] = []
        trace: list[dict[str, Any]] = []
        final_text = None
        for _ in range(6):
            resp = self.llm.chat(messages, TOOL_SCHEMAS)
            content, calls = LLMClient.parse_response(resp)
            if not calls:
                final_text = content or "(empty response)"
                break
            messages.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": json_dumps(c["args"])}}
                    for c in calls
                ],
            })
            for call in calls:
                result = call_tool(call["name"], call["args"])
                trace.append({"name": call["name"], "args": call["args"], "result": result})
                citations.extend(extract_citations(call["name"], result))
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json_dumps(result),
                })
        if final_text is None:
            final_text = "(model stopped after maximum tool iterations)"
        return AgentResponse(question=question, answer=final_text, intent="llm",
                             mode="llm", citations=citations, tool_trace=trace)

    def _ask_offline(self, question: str, routed: dict[str, Any]) -> AgentResponse:
        intent = routed["intent"]
        tickers = routed["tickers"]
        if intent == "analytical":
            metric = extract_metric_hint(question)
            other = tickers[0] if tickers else None
            switch = bool(other and self.state.current_ticker and
                          other != self.state.current_ticker)
            if metric and (len(tickers) >= 2 or (switch and len(tickers) == 1)):
                intent = "comparative_factual"
        handler = {
            "advice_probe": self._offline_advice_probe,
            "factual": self._offline_factual,
            "comparative_factual": self._offline_comparative_factual,
            "qualitative": self._offline_qualitative,
            "comparative_qualitative": self._offline_qualitative,
            "analytical": self._offline_analytical,
        }.get(intent, self._offline_fallback)
        return handler(question, routed)

    def _offline_advice_probe(self, question: str, routed: dict[str, Any]) -> AgentResponse:
        lines = [
            "I can't recommend buying, selling, or investing in any security - this assistant describes "
            "and explains financial data; it does not make investment recommendations.",
            "",
        ]
        ticker = routed["ticker"]
        if ticker:
            fy = routed["fy"] or self.default_years.get(ticker)
            s = tool_get_scores(ticker, fy)
            az = s.get("altman_z", {})
            pf = s.get("piotroski_f", {})
            bm = s.get("beneish_m", {})
            lines.append(f"What the data does say for {ticker} FY{fy}: "
                         f"Altman Z = {az.get('value')} ({az.get('zone')} zone); "
                         f"Piotroski F = {pf.get('value')}/9 ({pf.get('interpretation')}); "
                         f"Beneish M = {bm.get('value')} ({bm.get('flag')}).")
            lines.append("These are descriptive research measures, not a view on whether the stock is a good investment.")
        return AgentResponse(question=question, answer="\n".join(lines), intent="advice_probe",
                             mode="offline",
                             citations=[{"type": "structured_lookup", "table": "scores"}] if ticker else [],
                             tool_trace=[{"name": "get_scores", "args": {"ticker": ticker}}] if ticker else [])

    def _offline_factual(self, question: str, routed: dict[str, Any]) -> AgentResponse:
        ticker = routed["ticker"]
        fy = routed["fy"] or self.state.current_fy or (self.default_years.get(ticker) if ticker else None)
        if not ticker:
            return self._offline_no_company(question)
        metric = extract_metric_hint(question)
        trace: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        name = company_name(ticker)

        if metric in ("altman_z", "piotroski_f", "beneish_m"):
            result = tool_get_scores(ticker, fy)
            trace.append({"name": "get_scores", "args": {"ticker": ticker, "year": fy}, "result": result})
            block = result.get(metric, {})
            lines = [f"**{name} ({ticker}) - {metric_label(metric)} FY{fy}: {format_metric_value(metric, block.get('value'))}**",
                     "", f"Interpretation: {block.get('interpretation', 'n/a')}"]
            py = block.get("prior_year_value")
            if py is not None:
                lines.insert(1, f"(prior year FY{fy - 1}: {format_metric_value(metric, py)})")
            missing = result.get("missing_inputs")
            lines += ["", "Source: structured lookup of scores computed from SEC XBRL statement data (see project docs)."]
            if missing:
                lines.append(f"Note: inputs unavailable for some model terms: {', '.join(sum(missing.values(), []))}.")
            citations.append({"type": "structured_lookup", "table": "scores",
                              "ticker": ticker, "fy": fy, "metric": metric})
            return AgentResponse(question, "\n".join(lines), "factual", "offline", citations, trace)

        if metric is None:
            metric = self.state.last_metric
        if metric is None:
            result = tool_get_line_items(ticker, fy)
            trace.append({"name": "get_line_items", "args": {"ticker": ticker, "year": fy}, "result": result})
            items = result.get("items", {})
            key_items = ["revenue", "net_income", "operating_income", "assets", "equity", "cfo"]
            lines = [f"**Key line items for {name} ({ticker}) FY{fy}:**", ""]
            for k in key_items:
                if k in items and items[k]["value"] is not None:
                    v = items[k]["value"]
                    lines.append(f"- {k}: ${v / 1e9:,.1f}B (XBRL tag: {items[k]['tag']})")
            lines += ["", "Source: normalized SEC XBRL facts (form 10-K). Ask for a specific ratio or score for computed metrics."]
            citations.append({"type": "structured_lookup", "table": "statements",
                              "ticker": ticker, "fy": fy})
            return AgentResponse(question, "\n".join(lines), "factual", "offline", citations, trace)

        result = tool_get_ratio(ticker, metric, fy)
        trace.append({"name": "get_ratio", "args": {"ticker": ticker, "metric": metric, "year": fy},
                      "result": result})
        if result.get("error") or result.get("value") is None:
            note = result.get("note") or result.get("error") or ""
            ans = (f"I don't have a value for **{metric}** for {name} ({ticker}) in FY{fy}. {note}\n\n"
                   f"I refuse to guess numbers - ask me about one of the available years.")
            citations.append({"type": "none"})
            return AgentResponse(question, ans, "factual", "offline", citations, trace)

        value_s = result["formatted"]
        peer = result.get("peer_rank")
        prev_v = result.get("prior_year_value")
        lines = [f"**{name} ({ticker}) {metric_label(metric)} in FY{fy}: {value_s}**"]
        if prev_v is not None:
            direction = "up" if (result["value"] or 0) >= prev_v else "down"
            lines.append(f"That's {direction} vs FY{fy - 1} ({format_metric_value(metric, prev_v)}).")
        if peer and peer.get("percentile") is not None:
            lines.append(f"Sector peer context: rank {peer['rank']} of {peer['n']} "
                         f"({peer['percentile']:.0f}th percentile).")
        lines += ["", f"How it's computed: {metric_definition(metric)}",
                  "Source: exact lookup against the structured ratio database built from SEC XBRL filings - "
                  "not recalled from text."]
        self.state.update(metric=metric)
        citations.append({"type": "structured_lookup", "table": "ratios",
                          "ticker": ticker, "fy": fy, "metric": metric})
        return AgentResponse(question, "\n".join(lines), "factual", "offline", citations, trace)

    def _offline_comparative_factual(self, question: str, routed: dict[str, Any]) -> AgentResponse:
        tickers = routed["tickers"][:2]
        if len(tickers) == 1 and self.state.current_ticker \
                and self.state.current_ticker != tickers[0]:
            tickers = [tickers[0], self.state.current_ticker]
        fy = routed["fy"] or self.state.current_fy or min(self.default_years.get(t, 0) for t in tickers) or None
        metric = extract_metric_hint(question) or self.state.last_metric or "roe"
        rows = []
        trace = []
        citations = []
        for t in tickers:
            r = tool_get_ratio(t, metric, fy)
            trace.append({"name": "get_ratio", "args": {"ticker": t, "metric": metric, "year": fy}, "result": r})
            rows.append((t, r))
            citations.append({"type": "structured_lookup", "table": "ratios", "ticker": t, "fy": fy,
                              "metric": metric})
        lines = [f"**{metric_label(metric)} comparison (FY{fy}):**", ""]
        valid = [(t, r) for t, r in rows if r.get("value") is not None]
        for t, r in rows:
            nm = company_name(t)
            if r.get("value") is None:
                lines.append(f"- {nm} ({t}): no data")
            else:
                lines.append(f"- {nm} ({t}): {r['formatted']}")
        if len(valid) == 2:
            hi, lo = (valid[0], valid[1]) if valid[0][1]["value"] >= valid[1][1]["value"] else (valid[1], valid[0])
            diff = abs(hi[1]["value"] - lo[1]["value"])
            lines += ["",
                      f"{company_name(hi[0])} ({hi[0]}) is higher than {company_name(lo[0])} ({lo[0]}) by "
                      f"{format_metric_value(metric, diff)} on this measure.",
                      "Source: exact structured lookups for each company-year."]
        self.state.update(metric=metric)
        return AgentResponse(question, "\n".join(lines), "comparative_factual", "offline", citations, trace)

    def _offline_qualitative(self, question: str, routed: dict[str, Any]) -> AgentResponse:
        ticker = routed["ticker"]
        fy = routed["fy"] or self.state.current_fy
        query = clean_query(question)
        section = "risk" if re.search(r"\brisks?\b|risk factors|supply chain|cyber|regulat|competition",
                                      question, re.I) else None
        args: dict[str, Any] = {"query": query}
        if ticker:
            args["ticker"] = ticker
        if fy:
            args["year"] = fy
        if section:
            args["section"] = section
        result = call_tool("search_filings", args)
        passages = result.get("results", [])
        trace = [{"name": "search_filings", "args": args, "result": {"n_results": len(passages)}}]
        citations = []
        lines = []
        if not passages:
            lines.append("I couldn't find relevant filing text for that. Try naming the company or topic more specifically.")
        else:
            focus = passages[0]
            lines.append(f'Here is what the {focus["ticker"]} FY{focus["year"]} 10-K says '
                         f'(top matching passage from the {section_label(focus["section"])}):')
            lines.append("")
            for p in passages[:3]:
                lines.append(f'> "{p["excerpt"][:450]}"')
                lines.append(f"> -- [{p['ticker']} FY{p['year']} 10-K, {section_label(p['section'])}]")
                lines.append("")
                citations.append({"type": "filing_text", "ticker": p["ticker"], "fy": p["year"],
                                  "section": p["section"], "chunk_id": p["chunk_id"],
                                  "url": p.get("citation_url")})
            sent = tool_get_text_sentiment(passages[0]["ticker"], passages[0]["year"])
            trace.append({"name": "get_text_sentiment",
                          "args": {"ticker": passages[0]["ticker"], "year": passages[0]["year"]},
                          "result": {"sections": sent.get("sections")}})
            secs = sent.get("sections", [])
            if secs:
                parts = "; ".join(
                    f'{s["section"]}: negative-word share {s["negative_word_share_pct"]}%' for s in secs)
                lines.append(f"Loughran-McDonald-style sentiment for that company-year - {parts}.")
                citations.append({"type": "structured_lookup", "table": "textstats",
                                  "ticker": passages[0]["ticker"], "fy": passages[0]["year"]})
        return AgentResponse(question, "\n".join(lines).strip(), routed["intent"], "offline", citations, trace)

    def _offline_analytical(self, question: str, routed: dict[str, Any]) -> AgentResponse:
        ticker = routed["ticker"]
        if not ticker:
            return self._offline_no_company(question)
        fy = routed["fy"] or self.state.current_fy or self.default_years.get(ticker)
        name = company_name(ticker)
        s = tool_get_scores(ticker, fy)
        trace: list[dict[str, Any]] = [{"name": "get_scores", "args": {"ticker": ticker, "year": fy},
                                        "result": {"ok": True}}]
        citations: list[dict[str, Any]] = [{"type": "structured_lookup", "table": "scores",
                                            "ticker": ticker, "fy": fy}]
        az, pf, bm = s.get("altman_z", {}), s.get("piotroski_f", {}), s.get("beneish_m", {})

        rm = tool_get_ratio(ticker, "net_margin", fy)
        rr = tool_get_ratio(ticker, "revenue_growth_pct", fy)
        trace.append({"name": "get_ratio", "args": {"ticker": ticker, "metric": "net_margin", "year": fy},
                      "result": {"value": rm.get("value")}})
        trace.append({"name": "get_ratio", "args": {"ticker": ticker, "metric": "revenue_growth_pct",
                                                    "year": fy}, "result": {"value": rr.get("value")}})
        citations.append({"type": "structured_lookup", "table": "ratios", "ticker": ticker, "fy": fy})

        sent = tool_get_text_sentiment(ticker, fy)
        red_flags: dict[str, int] = {}
        for sec in sent.get("sections", []):
            for k, v in (sec.get("red_flags") or {}).items():
                red_flags[k] = red_flags.get(k, 0) + v
        top_flags = sorted(red_flags.items(), key=lambda x: -x[1])[:4]

        points = 0
        stance_notes = []
        zone = az.get("zone")
        if zone == "safe":
            points += 1
            stance_notes.append(f"Altman Z of {az.get('value'):.2f} sits in the SAFE zone (low historical distress association)")
        elif zone == "grey":
            stance_notes.append(f"Altman Z of {az.get('value'):.2f} sits in the GREY zone (ambiguous)")
        elif zone == "distress":
            points -= 1
            stance_notes.append(f"Altman Z of {az.get('value'):.2f} sits in the DISTRESS zone (elevated historical risk)")
        f_val = pf.get("value")
        if isinstance(f_val, (int, float)):
            if f_val >= 7:
                points += 1
                stance_notes.append(f"Piotroski F of {int(f_val)}/9 indicates strong fundamental quality")
            elif f_val <= 3:
                points -= 1
                stance_notes.append(f"Piotroski F of {int(f_val)}/9 indicates weak fundamentals")
            else:
                stance_notes.append(f"Piotroski F of {int(f_val)}/9 is middling")
        m_val = bm.get("value")
        if isinstance(m_val, (int, float)):
            if m_val > -1.78:
                points -= 1
                stance_notes.append(f"Beneish M of {m_val:.2f} is above the -1.78 threshold Beneish associated "
                                    "with manipulation-prone samples")
            else:
                points += 1
                stance_notes.append(f"Beneish M of {m_val:.2f} is below the -1.78 manipulation-signal threshold")

        stance = "financially strong" if points >= 2 else ("financially weak / higher-risk" if points <= -2 else "mixed")

        lines = [f"**Assessment of {name} ({ticker}) for FY{fy}: the numbers point to a "
                 f"{stance} profile.**", ""]
        lines.append("What drives that reading:")
        for note in stance_notes:
            lines.append(f"- {note}")
        lines.append(f"- Net margin {rm.get('formatted')}"
                     + (f" and revenue growth {rr.get('formatted')}" if rr.get("value") is not None else "")
                     + " provide profitability/growth context.")
        if top_flags:
            flag_str = ", ".join(f"{k.replace('_', ' ')} (x{v})" for k, v in top_flags)
            lines.append(f"- Recurring disclosure red-flag topics in MD&A/Risk Factors: {flag_str}.")
        lines += ["",
                  "Every figure above came from the structured database or the indexed filing text - "
                  "the conclusion tracks those numbers rather than general impressions.",
                  "Reminder: this is a descriptive fundamental analysis, not investment advice."]

        metric = extract_metric_hint(question)
        if metric and metric not in ("altman_z", "piotroski_f", "beneish_m") \
                and re.search(r"\bwhy\b|\bwhat drove\b|\bexplain\b", question, re.I):
            series = []
            with get_db() as con:
                rows = con.execute("SELECT fy, value FROM ratios WHERE ticker=? AND metric=? ORDER BY fy",
                                   (ticker, metric)).fetchall()
            series = [(r["fy"], r["value"]) for r in rows]
            if len(series) >= 2:
                lines += ["", "Trend of the metric you asked about:"]
                for y_, v_ in series:
                    lines.append(f"- FY{y_}: {format_metric_value(metric, v_)}")

        return AgentResponse(question, "\n".join(lines), "analytical", "offline", citations, trace)

    def _offline_no_company(self, question: str) -> AgentResponse:
        companies = call_tool("list_companies", {})
        names = ", ".join(c["ticker"] for c in companies.get("companies", [])[:20])
        return AgentResponse(
            question,
            "I couldn't tell which company you're asking about. Covered companies include: "
            f"{names}.\nAsk e.g. \"What was Microsoft's operating margin in FY2023?\" and I'll pull the exact number.",
            "clarify", "offline", [], [])

    def _offline_fallback(self, question: str, routed: dict[str, Any]) -> AgentResponse:
        return self._offline_qualitative(question, routed)


def json_dumps(obj: Any) -> str:
    import json

    try:
        return json.dumps(obj, default=str)
    except Exception:
        return str(obj)


def company_name(ticker: str) -> str:
    with get_db() as con:
        row = con.execute("SELECT name FROM companies WHERE ticker=?", ((ticker or "").upper(),)).fetchone()
    return row["name"] if row else ticker


def clean_query(question: str) -> str:
    q = re.sub(r"\b(what|did|does|do|tell me about|the|a|an|say|says|discuss|company)\b",
               " ", question, flags=re.I)
    q = re.sub(r"[?.!]", " ", q)
    return " ".join(q.split())[:180]


def section_label(section: str) -> str:
    return {"mda": "MD&A (Item 7)", "risk": "Risk Factors (Item 1A)", "full": "10-K full text"}.get(section, section)


def metric_label(metric: str) -> str:
    labels = {
        "roe": "return on equity (ROE)", "roa": "return on assets (ROA)", "roic": "ROIC",
        "net_margin": "net profit margin", "gross_margin": "gross margin",
        "operating_margin": "operating margin", "current_ratio": "current ratio",
        "quick_ratio": "quick ratio", "debt_to_equity": "debt-to-equity",
        "asset_turnover": "asset turnover", "fcf_margin": "free-cash-flow margin",
        "rd_intensity": "R&D intensity", "revenue_growth_pct": "revenue growth",
        "net_income_growth_pct": "net income growth", "altman_z": "Altman Z-Score",
        "piotroski_f": "Piotroski F-Score", "beneish_m": "Beneish M-Score",
        "interest_coverage": "interest coverage", "receivable_days": "days receivables outstanding",
    }
    return labels.get(metric, metric.replace("_", " "))


def metric_definition(metric: str) -> str:
    defs = {
        "roe": "net income / shareholders' equity", "roa": "net income / total assets",
        "gross_margin": "gross profit / revenue", "operating_margin": "operating income / revenue",
        "net_margin": "net income / revenue", "current_ratio": "current assets / current liabilities",
        "quick_ratio": "liquid assets / current liabilities", "debt_to_equity": "total debt / equity",
        "asset_turnover": "revenue / total assets", "fcf_margin": "free cash flow / revenue",
        "rd_intensity": "R&D expense / revenue", "revenue_growth_pct": "YoY revenue growth",
        "interest_coverage": "operating income / interest expense",
    }
    return defs.get(metric, "computed from XBRL line items")


def extract_citations(tool_name: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    src = result.get("source") or {}
    if src.get("type") == "structured_lookup":
        out.append({"type": "structured_lookup", "table": src.get("table"),
                    "ticker": result.get("ticker"), "fy": result.get("year"),
                    "metric": result.get("metric")})
    for p in result.get("results", []) or []:
        out.append({"type": "filing_text", "ticker": p.get("ticker"), "fy": p.get("year"),
                    "section": p.get("section"), "chunk_id": p.get("chunk_id"),
                    "url": p.get("citation_url")})
    return out
