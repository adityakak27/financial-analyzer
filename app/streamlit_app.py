from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import plotly.graph_objects as go
import streamlit as st

from finchat.chatbot.agent import FinChatAgent
from finchat.chatbot.tools import tool_get_metric_history, tool_list_companies
from finchat.engine.duel import compare_companies

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
        elif t.get("name") == "compare_companies":
            res = t.get("result", {})
            if "error" in res or not res.get("pillars"):
                continue
            t_a = res.get("ticker_a", "A")
            t_b = res.get("ticker_b", "B")
            year = res.get("year", "")
            prof = res.get("pillars", {}).get("Profitability", [])
            if prof:
                labels = [m["metric_label"] for m in prof if m["val_a"] is not None and m["val_b"] is not None]
                vals_a = [m["val_a"] * 100 if abs(m["val_a"]) <= 1.5 else m["val_a"] for m in prof if m["val_a"] is not None and m["val_b"] is not None]
                vals_b = [m["val_b"] * 100 if abs(m["val_b"]) <= 1.5 else m["val_b"] for m in prof if m["val_a"] is not None and m["val_b"] is not None]

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=labels,
                    y=vals_a,
                    name=t_a,
                    marker=dict(color="#2563EB"),
                    hovertemplate=f"<b>{t_a}</b> %{{x}}: %{{y:.1f}}%<extra></extra>",
                ))
                fig.add_trace(go.Bar(
                    x=labels,
                    y=vals_b,
                    name=t_b,
                    marker=dict(color="#10B981"),
                    hovertemplate=f"<b>{t_b}</b> %{{x}}: %{{y:.1f}}%<extra></extra>",
                ))
                fig.update_layout(
                    title=f"<b>Profitability Duel: {t_a} vs {t_b} (FY{year})</b>",
                    barmode="group",
                    xaxis_title="Profitability Metric",
                    yaxis_title="Margin / Return (%)",
                    template="plotly_white",
                    margin=dict(l=40, r=40, t=50, b=40),
                    height=320,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
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

tab_chat, tab_visualizer, tab_duel = st.tabs(["💬 Conversational Analyst", "📈 Visual Trend Explorer", "⚔️ Company Duel"])

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

with tab_duel:
    st.subheader("⚔️ Company Duel: Head-to-Head Fundamental Scorecard")
    st.caption("Benchmark two companies head-to-head across Profitability, Financial Health & Solvency, Accounting Quality, and Growth.")

    col1, col2, col3 = st.columns([1.2, 1.2, 1])
    ticker_list = [c["ticker"] for c in companies] if companies else ["AAPL", "MSFT", "NVDA", "ADBE", "INTC"]
    with col1:
        ticker_a = st.selectbox("Company A", ticker_list, index=0, key="duel_select_a")
    with col2:
        idx_b = 1 if len(ticker_list) > 1 else 0
        ticker_b = st.selectbox("Company B", ticker_list, index=idx_b, key="duel_select_b")

    # Fetch available overlapping years
    preview = compare_companies(ticker_a, ticker_b)
    common_years = preview.get("available_common_years", [2024, 2023, 2022, 2021, 2020, 2019, 2018])
    with col3:
        selected_year = st.selectbox("Fiscal Year", sorted(common_years, reverse=True), index=0, key="duel_select_year")

    duel_res = compare_companies(ticker_a, ticker_b, selected_year)
    if "error" in duel_res:
        st.error(duel_res["error"])
    else:
        wins_a = duel_res["wins_a"]
        wins_b = duel_res["wins_b"]
        ties = duel_res["ties"]
        overall = duel_res["overall_winner"]
        verdict = duel_res["verdict"]

        st.markdown("---")
        m_a, m_verdict, m_b = st.columns([1.2, 2, 1.2])
        with m_a:
            st.metric(
                label=f"{duel_res['name_a']} ({ticker_a})",
                value=f"{wins_a} Wins",
                delta=f"{wins_a - wins_b:+d} Net" if wins_a != wins_b else "Tied",
            )
        with m_verdict:
            if overall == ticker_a:
                st.success(f"🏆 **Winner: {ticker_a}**\n\n{verdict}")
            elif overall == ticker_b:
                st.success(f"🏆 **Winner: {ticker_b}**\n\n{verdict}")
            else:
                st.info(f"🤝 **Dead Heat Tie**\n\n{verdict}")
        with m_b:
            st.metric(
                label=f"{duel_res['name_b']} ({ticker_b})",
                value=f"{wins_b} Wins",
                delta=f"{wins_b - wins_a:+d} Net" if wins_b != wins_a else "Tied",
            )

        # Plotly Comparison Chart of Margins
        prof_metrics = duel_res.get("pillars", {}).get("Profitability", [])
        if prof_metrics:
            p_labels = [m["metric_label"] for m in prof_metrics if m["val_a"] is not None and m["val_b"] is not None]
            p_vals_a = [m["val_a"] * 100 if abs(m["val_a"]) <= 1.5 else m["val_a"] for m in prof_metrics if m["val_a"] is not None and m["val_b"] is not None]
            p_vals_b = [m["val_b"] * 100 if abs(m["val_b"]) <= 1.5 else m["val_b"] for m in prof_metrics if m["val_a"] is not None and m["val_b"] is not None]

            fig_duel = go.Figure()
            fig_duel.add_trace(go.Bar(
                x=p_labels,
                y=p_vals_a,
                name=f"{ticker_a}",
                marker=dict(color="#2563EB"),
                hovertemplate=f"<b>{ticker_a}</b> %{{x}}: %{{y:.1f}}%<extra></extra>",
            ))
            fig_duel.add_trace(go.Bar(
                x=p_labels,
                y=p_vals_b,
                name=f"{ticker_b}",
                marker=dict(color="#10B981"),
                hovertemplate=f"<b>{ticker_b}</b> %{{x}}: %{{y:.1f}}%<extra></extra>",
            ))
            fig_duel.update_layout(
                title=f"<b>Profitability Margins Face-Off: {ticker_a} vs {ticker_b} (FY{selected_year})</b>",
                barmode="group",
                xaxis_title="Metric",
                yaxis_title="Margin / Return (%)",
                template="plotly_white",
                height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_duel, use_container_width=True)

        # Scorecard Breakdown Table
        st.subheader("Pillar Breakdown & Metrics Scorecard")
        table_rows = []
        for pillar_name, metrics in duel_res.get("pillars", {}).items():
            for m in metrics:
                winner = m["winner"]
                if winner == ticker_a:
                    advantage = f"🟢 {ticker_a}"
                elif winner == ticker_b:
                    advantage = f"🟢 {ticker_b}"
                elif winner == "TIE":
                    advantage = "🤝 Tie"
                else:
                    advantage = "N/A"
                table_rows.append({
                    "Pillar": pillar_name,
                    "Metric": m["metric_label"],
                    f"{ticker_a} ({duel_res['name_a']})": m["formatted_a"],
                    f"{ticker_b} ({duel_res['name_b']})": m["formatted_b"],
                    "Advantage": advantage,
                })

        st.dataframe(table_rows, use_container_width=True, hide_index=True)
