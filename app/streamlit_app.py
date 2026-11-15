from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.graph_objects as go
import streamlit as st

from finchat.chatbot.agent import FinChatAgent
from finchat.chatbot.tools import tool_get_metric_history, tool_list_companies

st.set_page_config(page_title="Conversational Fundamental Analyst", page_icon=":chart:", layout="wide")

PROVIDER_MAP = {
    "Google Gemini": "gemini",
    "Offline Deterministic (No AI)": "offline",
}

if "provider_choice" not in st.session_state:
    st.session_state.provider_choice = "Google Gemini"

if "agent" not in st.session_state:
    is_offline = st.session_state.provider_choice == "Offline Deterministic (No AI)"
    st.session_state.agent = FinChatAgent(force_offline=is_offline)
if "messages" not in st.session_state:
    st.session_state.messages = []


def render_trace_chart(tool_trace: list[dict]):
    if not tool_trace:
        return
    for t in tool_trace:
        if t.get("name") == "get_metric_history":
            res = t.get("result", {})
            series = res.get("series", [])
            if not series:
                continue
            ticker = res.get("ticker", "")
            metric = res.get("metric", "").replace("_", " ").title()
            is_pct = res.get("is_percentage", False)
            years = [s["year"] for s in series]
            first_val = series[0]["value"]
            if is_pct and abs(first_val) <= 1.0:
                values = [s["value"] * 100 for s in series]
                suffix = "%"
            else:
                values = [s["value"] for s in series]
                suffix = "%" if is_pct else ""

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=years,
                y=values,
                mode="lines+markers",
                name=f"{ticker} {metric}",
                line=dict(color="#2563EB", width=3),
                marker=dict(size=9, color="#1D4ED8", symbol="circle"),
                hovertemplate=f"<b>FY%{{x}}</b>: %{{y:.2f}}{suffix}<extra></extra>",
            ))
            fig.update_layout(
                title=f"<b>{ticker} — {metric} Trend ({years[0]}–{years[-1]})</b>",
                xaxis_title="Fiscal Year",
                yaxis_title=f"{metric} ({suffix})" if suffix else metric,
                template="plotly_white",
                margin=dict(l=40, r=40, t=50, b=40),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)


def render_citations(citations: list[dict]):
    if not citations:
        return
    with st.expander("Sources & Provenance", expanded=False):
        for i, c in enumerate(citations, 1):
            url = c.get("url")
            parts = [f"{i}. **[{c.get('type', 'lookup')}]**"]
            if c.get("ticker"):
                parts.append(f"**{c['ticker']}**")
            if c.get("metric"):
                parts.append(c["metric"].replace("_", " "))
            if c.get("fy"):
                fy_str = str(c["fy"])
                if not fy_str.startswith("FY") and not "–" in fy_str:
                    fy_str = f"FY{fy_str}"
                parts.append(fy_str)
            if c.get("table"):
                parts.append(f"({c['table']})")
            if c.get("section"):
                parts.append(f"[{c['section'].upper()}]")

            label = " · ".join(parts)
            if url:
                st.markdown(f"[{label}]({url})")
            else:
                st.markdown(label)


with st.sidebar:
    st.title("Fundamental Analyst")
    st.caption("Hybrid design: exact structured lookups for numbers, retrieval for filing text.")

    choice = st.selectbox(
        "Mode",
        list(PROVIDER_MAP.keys()),
        index=list(PROVIDER_MAP.keys()).index(st.session_state.provider_choice),
    )
    if choice != st.session_state.provider_choice:
        st.session_state.provider_choice = choice
        is_offline = choice == "Offline Deterministic (No AI)"
        st.session_state.agent = FinChatAgent(force_offline=is_offline)
        st.rerun()

    active_agent = st.session_state.agent
    if active_agent.llm.available:
        st.success(f"🟢 **Engine:** {active_agent.llm.display_name}")
    else:
        st.info("⚡ **Engine:** Offline Deterministic (Rule-Based)")

    if st.button("Reset conversation"):
        st.session_state.agent.reset()
        st.session_state.messages = []
        st.rerun()
    st.divider()
    companies = tool_list_companies()["companies"]
    st.subheader(f"Coverage: {len(companies)} companies")
    st.write(", ".join(c["ticker"] for c in companies))
    st.caption("Data: SEC EDGAR XBRL + 10-K text. Educational use; not investment advice.")

tab_chat, tab_visualizer = st.tabs(["💬 Conversational Analyst", "📈 Visual Trend Explorer"])

with tab_chat:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            # For assistant, show the chart AT THE TOP of the response if available!
            if msg["role"] == "assistant" and msg.get("tool_trace"):
                render_trace_chart(msg["tool_trace"])
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("citations"):
                render_citations(msg["citations"])
            if msg["role"] == "assistant" and msg.get("tool_trace"):
                with st.expander("Tool calls made"):
                    st.json([{k: t[k] for k in ("name", "args")} for t in msg["tool_trace"]])

# Bottom-docked sticky chat input
user_input = st.chat_input("Ask about ratios, scores, trends, peers, or disclosed risks...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with tab_chat:
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"), st.spinner("Analyzing..."):
            resp = st.session_state.agent.ask(user_input)
            # Render chart AT THE TOP of the response
            if resp.tool_trace:
                render_trace_chart(resp.tool_trace)
            st.markdown(resp.answer)
            if resp.citations:
                render_citations(resp.citations)
            if resp.tool_trace:
                with st.expander("Tool calls made"):
                    st.json([{k: t[k] for k in ("name", "args")} for t in resp.tool_trace])
    st.session_state.messages.append({
        "role": "assistant",
        "content": resp.answer,
        "citations": resp.citations,
        "tool_trace": resp.tool_trace,
    })
    st.rerun()

with tab_visualizer:
    st.subheader("Historical Multi-Year Financial Visualizer")
    st.caption("Interactively inspect 7-year metric trajectories directly from verified SEC XBRL filings.")

    col1, col2, col3 = st.columns([1, 1.5, 1])
    ticker_list = [c["ticker"] for c in companies] if companies else ["AAPL", "MSFT", "NVDA", "ADBE", "INTC"]
    with col1:
        selected_ticker = st.selectbox("Company", ticker_list, index=0)

    METRIC_OPTIONS = {
        "Gross Margin": "gross_margin",
        "Operating Margin": "operating_margin",
        "Net Profit Margin": "net_margin",
        "Return on Equity (ROE)": "roe",
        "Return on Assets (ROA)": "roa",
        "Return on Invested Capital (ROIC)": "roic",
        "Debt to Equity": "debt_to_equity",
        "Free Cash Flow Margin": "fcf_margin",
        "R&D Intensity": "rd_intensity",
        "Altman Z-Score (Insolvency Risk)": "altman_z",
        "Piotroski F-Score (Fundamental Health)": "piotroski_f",
        "Beneish M-Score (Earnings Manipulation)": "beneish_m",
        "Total Revenue": "revenue",
        "Net Income": "net_income",
    }

    with col2:
        selected_metric_label = st.selectbox("Financial Metric", list(METRIC_OPTIONS.keys()), index=0)
        selected_metric = METRIC_OPTIONS[selected_metric_label]

    with col3:
        chart_type = st.radio("Chart Type", ["Line with Markers", "Bar Chart"], horizontal=True)

    if selected_ticker and selected_metric:
        history = tool_get_metric_history(selected_ticker, selected_metric)
        series = history.get("series", [])
        if series:
            years = [s["year"] for s in series]
            is_pct = history.get("is_percentage", False)
            first_val = series[0]["value"]
            if is_pct and abs(first_val) <= 1.0:
                values = [s["value"] * 100 for s in series]
                suffix = "%"
            else:
                values = [s["value"] for s in series]
                suffix = "%" if is_pct else ""

            # Metric Cards
            m1, m2, m3, m4 = st.columns(4)
            latest_val = series[-1]["formatted"]
            min_val = min(values)
            max_val = max(values)
            min_year = [s["year"] for i, s in enumerate(series) if values[i] == min_val][0]
            max_year = [s["year"] for i, s in enumerate(series) if values[i] == max_val][0]

            with m1:
                st.metric(label=f"Latest (FY{years[-1]})", value=latest_val)
            with m2:
                st.metric(label="7-Year High", value=f"{max_val:.2f}{suffix} (FY{max_year})")
            with m3:
                st.metric(label="7-Year Low", value=f"{min_val:.2f}{suffix} (FY{min_year})")
            with m4:
                diff = values[-1] - values[0]
                st.metric(label="Net Change (FY18→24)", value=f"{diff:+.2f}{suffix}")

            # Plotly Chart
            fig = go.Figure()
            if chart_type == "Bar Chart":
                fig.add_trace(go.Bar(
                    x=years,
                    y=values,
                    marker=dict(color="#3B82F6"),
                    hovertemplate=f"<b>FY%{{x}}</b>: %{{y:.2f}}{suffix}<extra></extra>",
                ))
            else:
                fig.add_trace(go.Scatter(
                    x=years,
                    y=values,
                    mode="lines+markers",
                    line=dict(color="#2563EB", width=3.5),
                    marker=dict(size=10, color="#1D4ED8"),
                    hovertemplate=f"<b>FY%{{x}}</b>: %{{y:.2f}}{suffix}<extra></extra>",
                ))

            fig.update_layout(
                title=f"<b>{selected_ticker} — {selected_metric_label} ({years[0]}–{years[-1]})</b>",
                xaxis_title="Fiscal Year",
                yaxis_title=f"{selected_metric_label} ({suffix})" if suffix else selected_metric_label,
                template="plotly_white",
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Data Table
            with st.expander("View Underlying Data Table"):
                st.dataframe(
                    [{"Fiscal Year": f"FY{s['year']}", "Raw Value": s["value"], "Formatted Value": s["formatted"]} for s in series],
                    use_container_width=True,
                )
        else:
            st.warning(f"No multi-year data recorded for {selected_ticker} on metric '{selected_metric}'.")
