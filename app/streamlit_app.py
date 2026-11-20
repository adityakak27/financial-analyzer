from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from finchat.chatbot.agent import FinChatAgent
from finchat.chatbot.tools import tool_get_metric_history, tool_list_companies
from finchat.config import UNIVERSE
from finchat.engine.dcf import calculate_dcf
from finchat.engine.duel import compare_companies
from finchat.engine.research_agents import ResearchDirector

st.set_page_config(
    page_title="Institutional Equity Research Copilot",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
if "agent" not in st.session_state:
    try:
        st.session_state.agent = FinChatAgent()
    except Exception as e:
        st.session_state.agent_error = str(e)
        st.session_state.agent = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "research_report" not in st.session_state:
    st.session_state.research_report = None


# -----------------------------------------------------------------------------
# Chart & Interactive Visualization Helpers
# -----------------------------------------------------------------------------
def render_trace_chart(tool_trace: list[dict]):
    if not tool_trace:
        return
    for idx, t in enumerate(tool_trace):
        name = t.get("name")
        res = t.get("result", {})

        if name == "get_metric_history":
            series = res.get("series", [])
            if not series:
                continue
            ticker = res.get("ticker", "")
            metric = res.get("metric", "").replace("_", " ").title()
            is_pct = res.get("is_percentage", False)
            years = [s.get("period") or f"FY{s.get('year')}" for s in series]
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
                hovertemplate=f"<b>%{{x}}</b>: %{{y:.2f}}{suffix}<extra></extra>",
            ))
            fig.update_layout(
                title=f"<b>{ticker} — {metric} Trajectory ({years[0]}–{years[-1]})</b>",
                xaxis_title="Period",
                yaxis_title=f"{metric} ({suffix})" if suffix else metric,
                template="plotly_white",
                margin=dict(l=40, r=40, t=50, b=40),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True, key=f"hist_chart_{idx}")

        elif name == "compare_companies":
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
                    x=labels, y=vals_a, name=t_a, marker=dict(color="#2563EB"),
                    hovertemplate=f"<b>{t_a}</b> %{{x}}: %{{y:.1f}}%<extra></extra>",
                ))
                fig.add_trace(go.Bar(
                    x=labels, y=vals_b, name=t_b, marker=dict(color="#10B981"),
                    hovertemplate=f"<b>{t_b}</b> %{{x}}: %{{y:.1f}}%<extra></extra>",
                ))
                fig.update_layout(
                    title=f"<b>Profitability Duel: {t_a} vs {t_b} (FY{year})</b>",
                    barmode="group",
                    xaxis_title="Metric",
                    yaxis_title="Margin / Return (%)",
                    template="plotly_white",
                    margin=dict(l=40, r=40, t=50, b=40),
                    height=320,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                st.plotly_chart(fig, use_container_width=True, key=f"duel_chart_{idx}")

        elif name == "run_dcf_valuation":
            ticker = res.get("ticker", "")
            latest_fy = res.get("latest_fy", "")
            price = res.get("implied_share_price")
            ev = res.get("enterprise_value")
            eq = res.get("implied_equity_value")
            assumptions = res.get("assumptions", {})
            wacc_pct = assumptions.get("wacc", 0.09) * 100
            g_pct = assumptions.get("terminal_growth", 0.025) * 100

            st.markdown(f"#### 🎯 Valuation Visuals: **{ticker}** (FY{latest_fy})")
            m1, m2, m3 = st.columns(3)
            m1.metric("Implied Fair Share Price", f"${price:.2f}" if price else "N/A", f"WACC: {wacc_pct:.1f}%, g: {g_pct:.1f}%")
            m2.metric("Enterprise Value", f"${ev / 1e9:,.1f} B" if ev else "N/A")
            m3.metric("Implied Equity Value", f"${eq / 1e9:,.1f} B" if eq else "N/A")

            # Interactive Chart Views: Waterfall Bridge + Annual FCF Projections
            tab_wf, tab_proj = st.tabs(["📊 Enterprise Value Waterfall Bridge", "📈 Annual FCF Projections Schedule"])
            with tab_wf:
                waterfall_data = res.get("waterfall", [])
                if waterfall_data:
                    wf_fig = go.Figure(go.Waterfall(
                        name="EV Bridge",
                        orientation="v",
                        measure=[w["measure"] for w in waterfall_data],
                        x=[w["label"] for w in waterfall_data],
                        textposition="outside",
                        text=[f"${w['value']:.1f}B" for w in waterfall_data],
                        y=[w["value"] for w in waterfall_data],
                        connector=dict(line=dict(color="rgb(63, 63, 63)")),
                        decreasing=dict(marker=dict(color="#EF4444")),
                        increasing=dict(marker=dict(color="#10B981")),
                        totals=dict(marker=dict(color="#2563EB")),
                    ))
                    wf_fig.update_layout(
                        title=f"<b>{ticker} — Enterprise Value to Equity Value Bridge ($B)</b>",
                        template="plotly_white",
                        height=320,
                        margin=dict(l=40, r=40, t=50, b=40),
                    )
                    st.plotly_chart(wf_fig, use_container_width=True, key=f"dcf_wf_{idx}")
                    st.caption("💡 **How to read the waterfall:** Green bars are positive contributions (PV of 5-Yr cash flows + PV of terminal value). Blue columns are totals (Enterprise Value = $1,365.9B). Adding Cash (+$75.5B) and deducting Debt (-$44.9B) gives Implied Equity Value ($1,396.5B). Dividing by shares gives the fair value ($186.97/share).")

            with tab_proj:
                projections = res.get("projections", [])
                if projections:
                    fy_labels = [f"FY{p['projected_fy']}" for p in projections]
                    fcf_vals = [p["fcf"] / 1e9 for p in projections]
                    proj_fig = go.Figure()
                    proj_fig.add_trace(go.Bar(
                        x=fy_labels,
                        y=fcf_vals,
                        name="Projected FCF ($B)",
                        marker=dict(color="#059669"),
                        text=[f"${v:.1f}B" for v in fcf_vals],
                        textposition="outside",
                        hovertemplate="<b>%{x}</b>: $%{y:.2f}B<extra></extra>",
                    ))
                    proj_fig.update_layout(
                        title=f"<b>{ticker} — 5-Year Free Cash Flow Projections ($B)</b>",
                        xaxis_title="Forecast Year",
                        yaxis_title="Free Cash Flow ($ Billions)",
                        template="plotly_white",
                        margin=dict(l=40, r=40, t=50, b=40),
                        height=320,
                    )
                    st.plotly_chart(proj_fig, use_container_width=True, key=f"dcf_proj_{idx}")

            # 2. Interactive 2D Sensitivity Heatmap
            matrix = res.get("sensitivity_matrix", {})
            if matrix:
                wacc_axis = [f"{w:.1f}%" for w in matrix.get("wacc_axis", [])]
                growth_axis = [f"{g:.1f}%" for g in matrix.get("growth_axis", [])]
                heat_z = [[v["implied_share_price"] for v in r["values"]] for r in matrix.get("rows", [])]
                heat_fig = px.imshow(
                    heat_z,
                    x=growth_axis,
                    y=wacc_axis,
                    color_continuous_scale="Viridis",
                    labels=dict(x="Terminal Growth Rate (g)", y="WACC Discount Rate", color="Target Price ($)"),
                    text_auto=".2f",
                )
                heat_fig.update_layout(
                    title=f"<b>{ticker} — Intrinsic Valuation Sensitivity Heatmap ($)</b>",
                    template="plotly_white",
                    height=320,
                    margin=dict(l=40, r=40, t=50, b=40),
                )
                st.plotly_chart(heat_fig, use_container_width=True, key=f"dcf_heat_{idx}")


def render_citations(citations: list[dict]):
    if not citations:
        return
    with st.expander("📚 Sources & Provenance", expanded=False):
        for i, c in enumerate(citations, 1):
            url = c.get("url")
            parts = [f"{i}. **[{c.get('type', 'lookup')}]**"]
            if c.get("ticker"):
                parts.append(f"**{c['ticker']}**")
            if c.get("metric"):
                parts.append(c["metric"].replace("_", " "))
            if c.get("fy"):
                fy_str = str(c["fy"])
                if not fy_str.startswith("FY") and "–" not in fy_str:
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


# -----------------------------------------------------------------------------
# Sidebar Configuration
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🏛️ Equity Research Copilot")
    st.caption("Institutional SEC 10-K Fundamental Intelligence & DCF Modeling")

    st.markdown("---")
    st.markdown("### 🤖 Intelligence Engine")
    agent = st.session_state.agent
    if agent and agent.llm.available:
        st.success(f"🟢 **Active:** {agent.llm.display_name}")
        st.caption("Direct Google Gemini function calling enabled.")
    else:
        err = getattr(st.session_state, "agent_error", "No GEMINI_API_KEY set.")
        st.error(f"🔴 **LLM Error:** {err}")
        st.caption("Please ensure `GEMINI_API_KEY` is configured in `.env`.")

    st.markdown("---")
    st.markdown("### 📊 Covered Universe")
    st.write(f"**Sector:** Large-Cap US Technology ({len(UNIVERSE)} firms)")
    universe_tickers = sorted(list(UNIVERSE.keys()))
    st.caption(", ".join(universe_tickers))

    st.markdown("---")
    if st.button("🔄 Reset Conversation State", use_container_width=True):
        if agent:
            agent.reset()
        st.session_state.messages = []
        st.rerun()


# -----------------------------------------------------------------------------
# Main Application Tabs
# -----------------------------------------------------------------------------
tab_chat, tab_initiation, tab_dcf, tab_duel = st.tabs([
    "💬 Conversational Analyst",
    "📑 Equity Research Initiation Studio",
    "🧮 Interactive DCF & Valuation Lab",
    "⚔️ Company Duel & Trend Explorer",
])


# =============================================================================
# TAB 1: Conversational Analyst
# =============================================================================
with tab_chat:
    st.markdown("### 💬 Institutional Fundamental Analyst")
    st.caption("Ask questions about ratios, DuPont decomposition, credit risk (Altman Z), accounting quality (Beneish M), DCF valuation, or SEC 10-K risk disclosures.")

    # Quick prompt chips
    chips = [
        "What was Apple's gross margin in FY2023, and why did it change?",
        "Run an interactive DCF valuation for Microsoft.",
        "Does Intel look like an insolvency risk in FY2023?",
        "Compare NVIDIA and AMD profitability and growth.",
    ]
    cols = st.columns(len(chips))
    for i, col in enumerate(cols):
        if col.button(chips[i], key=f"chip_{i}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": chips[i]})
            if agent:
                with st.spinner("AI analyzing filings and querying structured database..."):
                    resp = agent.ask(chips[i])
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": resp.answer,
                        "tool_trace": resp.tool_trace,
                        "citations": resp.citations,
                    })
            st.rerun()

    # Chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("tool_trace"):
                render_trace_chart(msg["tool_trace"])
                with st.expander("🛠️ Tool Execution Trace", expanded=False):
                    for t in msg["tool_trace"]:
                        st.markdown(f"**Function:** `{t['name']}`")
                        st.json(t["args"])
            if msg.get("citations"):
                render_citations(msg["citations"])


# =============================================================================
# TAB 2: Equity Research Initiation Studio
# =============================================================================
with tab_initiation:
    st.markdown("### 📑 Institutional Initiation of Coverage Studio")
    st.write(
        "Deploy the **4-Agent Collaborative Research Panel** to synthesize a comprehensive, "
        "audit-proof initiation of coverage report with forensic scores, DuPont decomposition, DCF intrinsic value, and risk disclosures."
    )

    col1, col2, col3 = st.columns([2, 1, 1.5])
    with col1:
        selected_ticker = st.selectbox(
            "Select Target Corporation:",
            universe_tickers,
            index=universe_tickers.index("AAPL") if "AAPL" in universe_tickers else 0,
            key="init_ticker",
        )
    with col2:
        selected_year = st.selectbox(
            "Fiscal Year (optional):",
            ["Latest Available", 2024, 2023, 2022, 2021, 2020],
            key="init_year",
        )
    with col3:
        st.write("")
        st.write("")
        launch_btn = st.button("🚀 Launch 4-Agent Panel", use_container_width=True, type="primary")

    if launch_btn:
        with st.status("Executing 4-Agent Research Collaboration...", expanded=True) as status:
            st.write("📊 **1. Valuation & DCF Specialist:** Extracting cash flows, capital structure, and running DCF model...")
            st.write("🔍 **2. Forensic Accounting Auditor:** Calculating Altman Z, Piotroski F, Beneish M-Score, and accruals...")
            st.write("📖 **3. Strategic MD&A Analyst:** Dissecting Item 7 management commentary and Item 1A risk disclosures...")
            st.write("✍️ **4. Lead Research Director:** Synthesizing findings into institutional initiation dossier...")

            fy_arg = None if selected_year == "Latest Available" else int(selected_year)
            rd = ResearchDirector()
            report_res = rd.generate_initiation_report(selected_ticker, year=fy_arg)
            st.session_state.research_report = report_res
            status.update(label="✅ Initiation Report Successfully Generated!", state="complete", expanded=False)

    report_data = st.session_state.research_report
    if report_data and report_data.get("ticker") == selected_ticker:
        metrics = report_data.get("headline_metrics", {})
        st.markdown("---")
        st.markdown(f"## 🏢 {report_data.get('company_name')} (`{report_data.get('ticker')}`) — Initiation Summary")

        # KPI Headline Cards
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        with kpi1:
            p_val = metrics.get("implied_share_price")
            st.metric("DCF Intrinsic Value", f"${p_val:.2f}" if p_val else "N/A")
        with kpi2:
            z = metrics.get("altman_z")
            zone = metrics.get("altman_zone", "").upper()
            st.metric("Altman Z-Score", f"{z:.2f}" if z else "N/A", f"Zone: {zone}")
        with kpi3:
            f = metrics.get("piotroski_f")
            st.metric("Piotroski F-Score", f"{f:.0f}/9" if f else "N/A", "Fundamental Health")
        with kpi4:
            m = metrics.get("beneish_m")
            flag = "Safe" if (m and m < -1.78) else "Flagged"
            st.metric("Beneish M-Score", f"{m:.2f}" if m else "N/A", f"Status: {flag}")
        with kpi5:
            roe = metrics.get("roe")
            st.metric("Return on Equity", f"{roe * 100:.1f}%" if roe else "N/A")

        st.markdown("---")
        st.markdown(report_data.get("markdown_report", ""))

        st.download_button(
            label="📥 Download Full Research Report (.md)",
            data=report_data.get("markdown_report", ""),
            file_name=f"initiation_report_{selected_ticker}.md",
            mime="text/markdown",
            use_container_width=True,
        )


# =============================================================================
# TAB 3: Interactive DCF & Valuation Lab
# =============================================================================
with tab_dcf:
    st.markdown("### 🧮 Interactive Discounted Cash Flow (DCF) Valuation Lab")
    st.caption("Fine-tune fundamental cost of capital assumptions, model terminal growth, and inspect the real-time implied share price sensitivity matrix.")

    dcf_col_left, dcf_col_right = st.columns([1, 2.2])

    with dcf_col_left:
        st.markdown("#### ⚙️ Valuation Assumptions")
        dcf_ticker = st.selectbox("Company:", universe_tickers, index=0, key="dcf_ticker")
        wacc_input = st.slider("WACC / Discount Rate (%):", min_value=6.0, max_value=15.0, value=9.0, step=0.25) / 100.0
        tg_input = st.slider("Terminal Growth Rate (%):", min_value=1.0, max_value=4.5, value=2.5, step=0.25) / 100.0
        horizon_input = st.slider("Forecast Horizon (Years):", min_value=3, max_value=8, value=5, step=1)

        custom_growth = st.checkbox("Specify Custom FCF Growth Rate Override")
        growth_override = None
        if custom_growth:
            growth_override = st.slider("FCF Growth Rate (%):", min_value=-5.0, max_value=30.0, value=8.0, step=0.5) / 100.0

    dcf_res = calculate_dcf(
        dcf_ticker,
        wacc=wacc_input,
        terminal_growth=tg_input,
        forecast_years=horizon_input,
        custom_growth_rate=growth_override,
    )

    with dcf_col_right:
        if "error" in dcf_res:
            st.error(dcf_res["error"])
        else:
            p_val = dcf_res.get("implied_share_price")
            ev_val = dcf_res.get("enterprise_value")
            eq_val = dcf_res.get("implied_equity_value")
            tv_pct = dcf_res.get("terminal_value_pct_of_ev", 0) * 100

            st.markdown(f"#### 🎯 Valuation Summary: **{dcf_ticker}** (FY{dcf_res['latest_fy']})")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Implied Fair Share Price", f"${p_val:.2f}" if p_val else "N/A")
            c2.metric("Enterprise Value", f"${ev_val / 1e9:,.1f} B" if ev_val else "N/A")
            c3.metric("Implied Equity Value", f"${eq_val / 1e9:,.1f} B" if eq_val else "N/A")
            c4.metric("Terminal Value Share", f"{tv_pct:.1f}% of EV")

            # Enterprise Value to Equity Waterfall Bridge Chart
            waterfall_data = dcf_res.get("waterfall", [])
            if waterfall_data:
                fig_wf = go.Figure(go.Waterfall(
                    name="EV Bridge",
                    orientation="v",
                    measure=[w["measure"] for w in waterfall_data],
                    x=[w["label"] for w in waterfall_data],
                    textposition="outside",
                    text=[f"${w['value']:.1f}B" for w in waterfall_data],
                    y=[w["value"] for w in waterfall_data],
                    connector=dict(line=dict(color="rgb(63, 63, 63)")),
                    decreasing=dict(marker=dict(color="#EF4444")),
                    increasing=dict(marker=dict(color="#10B981")),
                    totals=dict(marker=dict(color="#2563EB")),
                ))
                fig_wf.update_layout(
                    title=f"<b>{dcf_ticker} — Enterprise Value to Equity Value Bridge ($B)</b>",
                    template="plotly_white",
                    height=280,
                    margin=dict(l=40, r=40, t=40, b=30),
                )
                st.plotly_chart(fig_wf, use_container_width=True)

    if "sensitivity_matrix" in dcf_res:
        st.markdown("---")
        st.markdown("#### 🔬 2D Sensitivity Matrix: Implied Share Price ($WACC \\times g$)")
        st.caption("How target price shifts across discount rates and perpetual terminal growth rates:")

        matrix = dcf_res["sensitivity_matrix"]
        wacc_labels = [f"{w:.1f}%" for w in matrix["wacc_axis"]]
        growth_labels = [f"{g:.1f}%" for g in matrix["growth_axis"]]
        z_values = [[v["implied_share_price"] for v in r["values"]] for r in matrix["rows"]]

        fig_heat = px.imshow(
            z_values,
            x=growth_labels,
            y=wacc_labels,
            color_continuous_scale="Viridis",
            labels=dict(x="Terminal Growth Rate (g)", y="WACC Discount Rate", color="Implied Price ($)"),
            text_auto=".2f",
        )
        fig_heat.update_layout(
            title="<b>Intrinsic Share Price Sensitivity Heatmap ($)</b>",
            template="plotly_white",
            height=360,
            margin=dict(l=50, r=50, t=50, b=40),
        )
        st.plotly_chart(fig_heat, use_container_width=True)


# =============================================================================
# TAB 4: Company Duel & Trend Explorer
# =============================================================================
with tab_duel:
    st.markdown("### ⚔️ Company Duel (Head-to-Head Scorecard)")
    st.caption("Select any two corporations from the universe to pit them against each other across 4 financial pillars.")

    d_col1, d_col2, d_col3 = st.columns([2, 2, 1])
    with d_col1:
        comp_a = st.selectbox("Company A:", universe_tickers, index=0, key="duel_a")
    with d_col2:
        comp_b = st.selectbox(
            "Company B:",
            universe_tickers,
            index=1 if len(universe_tickers) > 1 else 0,
            key="duel_b",
        )
    with d_col3:
        duel_year = st.selectbox("Fiscal Year:", ["Latest", 2024, 2023, 2022, 2021], key="duel_yr")

    fy_param = None if duel_year == "Latest" else int(duel_year)
    duel_result = compare_companies(comp_a, comp_b, fy_param)

    if "error" in duel_result:
        st.error(duel_result["error"])
    else:
        st.markdown(f"#### 🏆 Duel Winner: **{duel_result.get('overall_winner', 'Tie')}**")
        st.caption(f"Comparing {comp_a} vs {comp_b} for FY{duel_result.get('year')}")

        p1, p2, p3, p4 = st.columns(4)
        pillar_winners = duel_result.get("pillar_winners", {})
        p1.metric("Profitability", pillar_winners.get("Profitability", "Tie"))
        p2.metric("Solvency & Health", pillar_winners.get("Financial Health & Solvency", "Tie"))
        p3.metric("Accounting Quality", pillar_winners.get("Accounting Quality", "Tie"))
        p4.metric("Growth", pillar_winners.get("Growth", "Tie"))

        # Detailed scorecard table
        pillars = duel_result.get("pillars", {})
        scorecard_rows = []
        for p_name, metrics_list in pillars.items():
            for m in metrics_list:
                val_a = m["val_a"]
                val_b = m["val_b"]
                is_pct = abs(val_a or 0) <= 1.0 or "Margin" in m["metric_label"] or "Growth" in m["metric_label"]
                fmt_a = f"{val_a * 100:.1f}%" if (val_a is not None and is_pct) else (f"{val_a:.2f}" if val_a is not None else "N/A")
                fmt_b = f"{val_b * 100:.1f}%" if (val_b is not None and is_pct) else (f"{val_b:.2f}" if val_b is not None else "N/A")
                scorecard_rows.append({
                    "Pillar": p_name,
                    "Metric": m["metric_label"],
                    f"{comp_a}": fmt_a,
                    f"{comp_b}": fmt_b,
                    "Winner": m["winner"],
                })

        st.dataframe(pd.DataFrame(scorecard_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 📈 Visual Trajectory & Trend Explorer")
    t_col1, t_col2, t_col3 = st.columns([1.5, 2, 1.5])
    with t_col1:
        trend_ticker = st.selectbox("Select Corporation:", universe_tickers, index=0, key="trend_t")
    with t_col2:
        trend_metric = st.selectbox(
            "Select Metric to Chart:",
            ["gross_margin", "operating_margin", "net_margin", "roe", "roa", "roic", "fcf_margin", "altman_z", "current_ratio", "revenue", "cfo"],
            format_func=lambda m: m.replace("_", " ").title(),
            key="trend_m",
        )
    with t_col3:
        trend_period = st.selectbox("Period Granularity:", ["annual", "quarterly", "ttm"], key="trend_p")

    hist_data = tool_get_metric_history(trend_ticker, trend_metric, period_type=trend_period)
    series = hist_data.get("series", [])
    if series:
        is_pct = hist_data.get("is_percentage", False)
        x_vals = [s.get("period") or f"FY{s.get('year')}" for s in series]
        first_val = series[0]["value"]
        if is_pct and abs(first_val) <= 1.0:
            y_vals = [s["value"] * 100 for s in series]
            sfx = "%"
        else:
            y_vals = [s["value"] for s in series]
            sfx = "%" if is_pct else ""

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="lines+markers",
            line=dict(color="#2563EB", width=3),
            marker=dict(size=9, color="#1D4ED8"),
            hovertemplate=f"<b>%{{x}}</b>: %{{y:.2f}}{sfx}<extra></extra>",
        ))
        fig_trend.update_layout(
            title=f"<b>{trend_ticker} — {trend_metric.replace('_', ' ').title()} Trajectory</b>",
            xaxis_title="Period",
            yaxis_title=f"{trend_metric.replace('_', ' ').title()} ({sfx})" if sfx else trend_metric.replace('_', ' ').title(),
            template="plotly_white",
            height=340,
            margin=dict(l=40, r=40, t=50, b=40),
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info(f"No historical {trend_period} data available for {trend_ticker} {trend_metric}.")


# =============================================================================
# GLOBAL PERSISTENT BOTTOM CHAT INPUT BAR
# =============================================================================
user_input = st.chat_input("Ask a fundamental analysis, DCF valuation, or SEC disclosure question...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    if agent:
        with st.spinner("AI analyzing filings and querying structured database..."):
            resp = agent.ask(user_input)
            st.session_state.messages.append({
                "role": "assistant",
                "content": resp.answer,
                "tool_trace": resp.tool_trace,
                "citations": resp.citations,
            })
    st.rerun()
