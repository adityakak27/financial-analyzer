from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from finchat.chatbot.agent import FinChatAgent
from finchat.chatbot.tools import format_metric_value, tool_get_metric_history
from finchat.config import UNIVERSE
from finchat.engine.dcf import calculate_dcf
from finchat.engine.duel import compare_companies
from finchat.engine.research_agents import ResearchDirector

st.set_page_config(
    page_title="Equity Research Copilot",
    page_icon=":material/analytics:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# Palette & shared styling
# -----------------------------------------------------------------------------
BG = "#F7F5F0"
SURFACE = "#FFFFFF"
BORDER = "#E7E3D8"
TEXT = "#2B2824"
TEXT_MUTED = "#79756C"
ACCENT = "#C2633F"
ACCENT_SOFT = "#F1E0D3"
ACCENT_DARK = "#A14E30"
GOOD = "#3F7D58"
BAD = "#B14B3F"
FONT = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"

CHART_COLORWAY = [ACCENT, "#4C6E8A", GOOD, "#9C8A5A", BAD]


def style_fig(fig: go.Figure, height: int = 320, title: str | None = None) -> go.Figure:
    """Apply a single, calm visual language to every chart in the app."""
    layout_kwargs = dict(
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=TEXT, size=13),
        colorway=CHART_COLORWAY,
        height=height,
        margin=dict(l=36, r=24, t=48 if title else 20, b=36),
        hoverlabel=dict(bgcolor=SURFACE, font=dict(family=FONT, color=TEXT), bordercolor=BORDER),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, bgcolor="rgba(0,0,0,0)"),
    )
    if title:
        layout_kwargs["title"] = dict(text=title, font=dict(size=15, family=FONT, color=TEXT))
    fig.update_layout(**layout_kwargs)
    fig.update_xaxes(gridcolor=BORDER, zerolinecolor=BORDER, showline=True, linecolor=BORDER)
    fig.update_yaxes(gridcolor=BORDER, zerolinecolor=BORDER, showline=False)
    return fig


CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {{
    font-family: {FONT};
}}

.stApp {{
    background-color: {BG};
    color: {TEXT};
}}

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {{
    background-color: {SURFACE};
    border-right: 1px solid {BORDER};
}}
section[data-testid="stSidebar"] .block-container {{
    padding-top: 2rem;
}}

/* ---- Headings ---- */
h1, h2, h3, h4 {{
    font-family: {FONT};
    color: {TEXT};
    font-weight: 600;
    letter-spacing: -0.01em;
}}
p, span, label, .stMarkdown, .stCaption {{
    color: {TEXT};
}}
.stCaption, [data-testid="stCaptionContainer"] {{
    color: {TEXT_MUTED} !important;
}}

/* ---- Buttons ---- */
.stButton > button {{
    border-radius: 10px;
    border: 1px solid {BORDER};
    background-color: {SURFACE};
    color: {TEXT};
    font-weight: 500;
    padding: 0.5rem 1rem;
    transition: all 0.15s ease;
    box-shadow: none;
}}
.stButton > button:hover {{
    border-color: {ACCENT};
    color: {ACCENT_DARK};
}}
.stButton > button[kind="primary"] {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: #FFFFFF;
}}
.stButton > button[kind="primary"]:hover {{
    background-color: {ACCENT_DARK};
    border-color: {ACCENT_DARK};
    color: #FFFFFF;
}}

/* ---- Suggestion chips (quick prompts) ---- */
div[class*="st-key-chip-"] .stButton > button {{
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 400;
    color: {TEXT_MUTED};
    background-color: {BG};
    border: 1px solid {BORDER};
    white-space: normal;
    height: 100%;
}}
div[class*="st-key-chip-"] .stButton > button:hover {{
    color: {ACCENT_DARK};
    border-color: {ACCENT};
    background-color: {ACCENT_SOFT};
}}

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
    border-bottom: 1px solid {BORDER};
}}
.stTabs [data-baseweb="tab"] {{
    font-weight: 500;
    color: {TEXT_MUTED};
    padding: 10px 6px;
}}
.stTabs [aria-selected="true"] {{
    color: {ACCENT_DARK};
    border-bottom: 2px solid {ACCENT};
}}

/* ---- Chat message bubbles (custom containers, see render_message()) ---- */
div[class*="st-key-chat-user-"] {{
    background-color: {ACCENT_SOFT};
    border-radius: 16px;
    padding: 12px 18px;
    margin: 6px 0 14px auto;
    max-width: 78%;
}}
div[class*="st-key-chat-assistant-"] {{
    padding: 2px 2px 18px 2px;
    margin-bottom: 6px;
    border-bottom: 1px solid {BORDER};
}}
div[class*="st-key-chat-assistant-"] p {{
    line-height: 1.6;
}}

/* ---- Metric tiles ---- */
div[data-testid="stMetric"] {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 14px 16px;
}}
div[data-testid="stMetricLabel"] {{
    color: {TEXT_MUTED};
}}
div[data-testid="stMetricValue"] {{
    color: {TEXT};
    font-weight: 600;
}}

/* ---- Inputs ---- */
.stTextInput input, .stSelectbox div[data-baseweb="select"], textarea {{
    border-radius: 8px !important;
}}
[data-testid="stChatInput"] {{
    border-radius: 14px;
}}

/* ---- Expanders / status ---- */
.streamlit-expanderHeader, [data-testid="stExpander"] summary {{
    font-weight: 500;
    color: {TEXT_MUTED};
}}

/* ---- Dataframe ---- */
[data-testid="stDataFrame"] {{
    border: 1px solid {BORDER};
    border-radius: 10px;
    overflow: hidden;
}}

/* Hide the default Streamlit chrome for a calmer canvas */
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Session state
# -----------------------------------------------------------------------------
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


def fmt_or_na(value: float | None, formatter) -> str:
    """Format a numeric value, correctly handling a real 0.0 (not just falsy values) as present."""
    return formatter(value) if value is not None else "N/A"


# -----------------------------------------------------------------------------
# Chart & interactive visualization helpers
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
                x=years, y=values, mode="lines+markers", name=f"{ticker} {metric}",
                line=dict(color=ACCENT, width=3),
                marker=dict(size=8, color=ACCENT_DARK),
                hovertemplate=f"<b>%{{x}}</b>: %{{y:.2f}}{suffix}<extra></extra>",
            ))
            style_fig(fig, title=f"{ticker} — {metric} ({years[0]}–{years[-1]})")
            st.plotly_chart(fig, width="stretch", key=f"hist_chart_{idx}")

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
                fig.add_trace(go.Bar(x=labels, y=vals_a, name=t_a, marker=dict(color=ACCENT),
                                      hovertemplate=f"<b>{t_a}</b> %{{x}}: %{{y:.1f}}%<extra></extra>"))
                fig.add_trace(go.Bar(x=labels, y=vals_b, name=t_b, marker=dict(color="#4C6E8A"),
                                      hovertemplate=f"<b>{t_b}</b> %{{x}}: %{{y:.1f}}%<extra></extra>"))
                fig.update_layout(barmode="group")
                style_fig(fig, title=f"Profitability: {t_a} vs {t_b} (FY{year})")
                st.plotly_chart(fig, width="stretch", key=f"duel_chart_{idx}")

        elif name == "run_dcf_valuation":
            ticker = res.get("ticker", "")
            latest_fy = res.get("latest_fy", "")
            price = res.get("implied_share_price")
            ev = res.get("enterprise_value")
            eq = res.get("implied_equity_value")
            assumptions = res.get("assumptions", {})
            wacc_pct = assumptions.get("wacc", 0.09) * 100
            g_pct = assumptions.get("terminal_growth", 0.025) * 100

            st.markdown(f"**Valuation detail — {ticker} (FY{latest_fy})**")
            m1, m2, m3 = st.columns(3)
            m1.metric("Implied share price", fmt_or_na(price, lambda v: f"${v:.2f}"), f"WACC {wacc_pct:.1f}% · g {g_pct:.1f}%")
            m2.metric("Enterprise value", fmt_or_na(ev, lambda v: f"${v / 1e9:,.1f}B"))
            m3.metric("Implied equity value", fmt_or_na(eq, lambda v: f"${v / 1e9:,.1f}B"))

            tab_wf, tab_proj = st.tabs(["Value bridge", "FCF projections"])
            with tab_wf:
                waterfall_data = res.get("waterfall", [])
                if waterfall_data:
                    wf_fig = go.Figure(go.Waterfall(
                        orientation="v",
                        measure=[w["measure"] for w in waterfall_data],
                        x=[w["label"] for w in waterfall_data],
                        textposition="outside",
                        text=[f"${w['value']:.1f}B" for w in waterfall_data],
                        y=[w["value"] for w in waterfall_data],
                        connector=dict(line=dict(color=BORDER)),
                        decreasing=dict(marker=dict(color=BAD)),
                        increasing=dict(marker=dict(color=GOOD)),
                        totals=dict(marker=dict(color=ACCENT)),
                    ))
                    style_fig(wf_fig, title=f"{ticker} — enterprise to equity value bridge ($B)")
                    st.plotly_chart(wf_fig, width="stretch", key=f"dcf_wf_{idx}")

            with tab_proj:
                projections = res.get("projections", [])
                if projections:
                    fy_labels = [f"FY{p['projected_fy']}" for p in projections]
                    fcf_vals = [p["fcf"] / 1e9 for p in projections]
                    proj_fig = go.Figure()
                    proj_fig.add_trace(go.Bar(
                        x=fy_labels, y=fcf_vals, name="Projected FCF ($B)", marker=dict(color=GOOD),
                        text=[f"${v:.1f}B" for v in fcf_vals], textposition="outside",
                        hovertemplate="<b>%{x}</b>: $%{y:.2f}B<extra></extra>",
                    ))
                    style_fig(proj_fig, title=f"{ticker} — projected free cash flow ($B)")
                    st.plotly_chart(proj_fig, width="stretch", key=f"dcf_proj_{idx}")

            matrix = res.get("sensitivity_matrix", {})
            if matrix:
                wacc_axis = [f"{w:.1f}%" for w in matrix.get("wacc_axis", [])]
                growth_axis = [f"{g:.1f}%" for g in matrix.get("growth_axis", [])]
                heat_z = [[v["implied_share_price"] for v in r["values"]] for r in matrix.get("rows", [])]
                heat_fig = px.imshow(
                    heat_z, x=growth_axis, y=wacc_axis, color_continuous_scale="Oranges",
                    labels=dict(x="Terminal growth (g)", y="WACC", color="Price ($)"), text_auto=".2f",
                )
                style_fig(heat_fig, title=f"{ticker} — sensitivity: implied price ($)")
                st.plotly_chart(heat_fig, width="stretch", key=f"dcf_heat_{idx}")


def render_citations(citations: list[dict]):
    if not citations:
        return
    with st.expander("Sources", expanded=False):
        for i, c in enumerate(citations, 1):
            url = c.get("url")
            parts = [f"{i}. {c.get('type', 'lookup')}"]
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
            st.markdown(f"[{label}]({url})" if url else label)


def render_message(role: str, idx: int, content: str, tool_trace: list | None = None,
                    citations: list | None = None):
    with st.container(key=f"chat-{role}-{idx}"):
        st.markdown(content)
    if tool_trace:
        render_trace_chart(tool_trace)
        with st.expander("Tool calls", expanded=False):
            for t in tool_trace:
                st.markdown(f"`{t['name']}`")
                st.json(t["args"])
    if citations:
        render_citations(citations)


def ask_and_store(question: str):
    st.session_state.messages.append({"role": "user", "content": question})
    agent = st.session_state.agent
    if agent:
        with st.spinner("Thinking…"):
            resp = agent.ask(question)
            st.session_state.messages.append({
                "role": "assistant", "content": resp.answer,
                "tool_trace": resp.tool_trace, "citations": resp.citations,
            })


# -----------------------------------------------------------------------------
# Sidebar
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Equity Research Copilot")
    st.caption("Fundamental analysis & DCF modeling, grounded in SEC 10-K filings.")

    st.markdown("---")
    agent = st.session_state.agent
    if agent and agent.llm.available:
        st.markdown(f"**Model**　{agent.llm.display_name}")
        st.caption("Connected")
    else:
        err = getattr(st.session_state, "agent_error", "No GEMINI_API_KEY set.")
        st.markdown("**Model**　Unavailable")
        st.caption(err)

    st.markdown("---")
    st.markdown("**Coverage universe**")
    universe_tickers = sorted(UNIVERSE.keys())
    st.caption(f"{len(universe_tickers)} companies · " + ", ".join(universe_tickers))

    st.markdown("---")
    if st.button("Reset conversation", width="stretch"):
        if agent:
            agent.reset()
        st.session_state.messages = []
        st.rerun()


# -----------------------------------------------------------------------------
# Main tabs
# -----------------------------------------------------------------------------
tab_chat, tab_initiation, tab_dcf, tab_duel = st.tabs([
    "Analyst", "Research report", "DCF lab", "Compare & trends",
])


# =============================================================================
# TAB 1: Conversational analyst
# =============================================================================
with tab_chat:
    st.markdown("#### Ask a question")
    st.caption("Ratios, DuPont decomposition, credit risk, accounting quality, DCF valuation, or filing disclosures.")

    chips = [
        "What was Apple's gross margin in FY2023, and why did it change?",
        "Run an interactive DCF valuation for Microsoft.",
        "Does Intel look like an insolvency risk in FY2023?",
        "Compare NVIDIA and AMD profitability and growth.",
    ]
    cols = st.columns(len(chips))
    for i, col in enumerate(cols):
        with col:
            with st.container(key=f"chip-{i}"):
                if st.button(chips[i], key=f"chip_btn_{i}", width="stretch"):
                    ask_and_store(chips[i])
                    st.rerun()

    st.write("")
    for i, msg in enumerate(st.session_state.messages):
        render_message(msg["role"], i, msg["content"], msg.get("tool_trace"), msg.get("citations"))


# =============================================================================
# TAB 2: Research report
# =============================================================================
with tab_initiation:
    st.markdown("#### Initiation of coverage report")
    st.caption(
        "Synthesizes DuPont decomposition, Altman/Piotroski/Beneish scores, DCF intrinsic value, "
        "and filing disclosures into a single report."
    )

    col1, col2, col3 = st.columns([2, 1, 1.5])
    with col1:
        selected_ticker = st.selectbox(
            "Company", universe_tickers,
            index=universe_tickers.index("AAPL") if "AAPL" in universe_tickers else 0,
            key="init_ticker",
        )
    with col2:
        selected_year = st.selectbox("Fiscal year", ["Latest", 2024, 2023, 2022, 2021, 2020], key="init_year")
    with col3:
        st.write("")
        st.write("")
        launch_btn = st.button("Generate report", width="stretch", type="primary")

    if launch_btn:
        with st.spinner("Generating report…"):
            fy_arg = None if selected_year == "Latest" else int(selected_year)
            rd = ResearchDirector()
            st.session_state.research_report = rd.generate_initiation_report(selected_ticker, year=fy_arg)

    report_data = st.session_state.research_report
    if report_data and report_data.get("ticker") == selected_ticker:
        metrics = report_data.get("headline_metrics", {})
        st.markdown("---")
        st.markdown(f"### {report_data.get('company_name')} ({report_data.get('ticker')})")

        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        kpi1.metric("DCF intrinsic value", fmt_or_na(metrics.get("implied_share_price"), lambda v: f"${v:.2f}"))
        z = metrics.get("altman_z")
        kpi2.metric("Altman Z-Score", fmt_or_na(z, lambda v: f"{v:.2f}"), (metrics.get("altman_zone") or "").upper() or None)
        f = metrics.get("piotroski_f")
        kpi3.metric("Piotroski F-Score", fmt_or_na(f, lambda v: f"{v:.0f}/9"))
        m = metrics.get("beneish_m")
        kpi4.metric("Beneish M-Score", fmt_or_na(m, lambda v: f"{v:.2f}"),
                    ("Flagged" if (m is not None and m > -1.78) else "Within norm") if m is not None else None)
        roe = metrics.get("roe")
        kpi5.metric("Return on equity", fmt_or_na(roe, lambda v: f"{v * 100:.1f}%"))

        st.markdown("---")
        st.markdown(report_data.get("markdown_report", ""))

        st.download_button(
            "Download report (.md)", data=report_data.get("markdown_report", ""),
            file_name=f"initiation_report_{selected_ticker}.md", mime="text/markdown",
            width="stretch",
        )


# =============================================================================
# TAB 3: DCF lab
# =============================================================================
with tab_dcf:
    st.markdown("#### Discounted cash flow model")
    st.caption("Adjust assumptions and inspect the implied share-price sensitivity in real time.")

    dcf_col_left, dcf_col_right = st.columns([1, 2.2])

    with dcf_col_left:
        dcf_ticker = st.selectbox("Company", universe_tickers, index=0, key="dcf_ticker")
        wacc_input = st.slider("WACC / discount rate (%)", 6.0, 15.0, 9.0, 0.25) / 100.0
        tg_input = st.slider("Terminal growth rate (%)", 1.0, 4.5, 2.5, 0.25) / 100.0
        horizon_input = st.slider("Forecast horizon (years)", 3, 8, 5, 1)

        custom_growth = st.checkbox("Override FCF growth rate")
        growth_override = None
        if custom_growth:
            growth_override = st.slider("FCF growth rate (%)", -5.0, 30.0, 8.0, 0.5) / 100.0

    dcf_res = calculate_dcf(dcf_ticker, wacc=wacc_input, terminal_growth=tg_input,
                            forecast_years=horizon_input, custom_growth_rate=growth_override)

    with dcf_col_right:
        if "error" in dcf_res:
            st.error(dcf_res["error"])
        else:
            p_val = dcf_res.get("implied_share_price")
            ev_val = dcf_res.get("enterprise_value")
            eq_val = dcf_res.get("implied_equity_value")
            tv_pct = (dcf_res.get("terminal_value_pct_of_ev") or 0) * 100

            st.markdown(f"**{dcf_ticker} — FY{dcf_res['latest_fy']}**")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Implied share price", fmt_or_na(p_val, lambda v: f"${v:.2f}"))
            c2.metric("Enterprise value", fmt_or_na(ev_val, lambda v: f"${v / 1e9:,.1f}B"))
            c3.metric("Implied equity value", fmt_or_na(eq_val, lambda v: f"${v / 1e9:,.1f}B"))
            c4.metric("Terminal value share", f"{tv_pct:.1f}% of EV")

            waterfall_data = dcf_res.get("waterfall", [])
            if waterfall_data:
                fig_wf = go.Figure(go.Waterfall(
                    orientation="v",
                    measure=[w["measure"] for w in waterfall_data],
                    x=[w["label"] for w in waterfall_data],
                    textposition="outside",
                    text=[f"${w['value']:.1f}B" for w in waterfall_data],
                    y=[w["value"] for w in waterfall_data],
                    connector=dict(line=dict(color=BORDER)),
                    decreasing=dict(marker=dict(color=BAD)),
                    increasing=dict(marker=dict(color=GOOD)),
                    totals=dict(marker=dict(color=ACCENT)),
                ))
                style_fig(fig_wf, height=280, title=f"{dcf_ticker} — enterprise to equity value bridge ($B)")
                st.plotly_chart(fig_wf, width="stretch")

    if "sensitivity_matrix" in dcf_res:
        st.markdown("---")
        st.markdown("**Sensitivity: implied share price vs. WACC × terminal growth**")

        matrix = dcf_res["sensitivity_matrix"]
        wacc_labels = [f"{w:.1f}%" for w in matrix["wacc_axis"]]
        growth_labels = [f"{g:.1f}%" for g in matrix["growth_axis"]]
        z_values = [[v["implied_share_price"] for v in r["values"]] for r in matrix["rows"]]

        fig_heat = px.imshow(
            z_values, x=growth_labels, y=wacc_labels, color_continuous_scale="Oranges",
            labels=dict(x="Terminal growth (g)", y="WACC", color="Price ($)"), text_auto=".2f",
        )
        style_fig(fig_heat, height=360)
        st.plotly_chart(fig_heat, width="stretch")


# =============================================================================
# TAB 4: Compare & trends
# =============================================================================
with tab_duel:
    st.markdown("#### Head-to-head comparison")
    st.caption("Pick two companies to compare across profitability, solvency, accounting quality, and growth.")

    d_col1, d_col2, d_col3 = st.columns([2, 2, 1])
    with d_col1:
        comp_a = st.selectbox("Company A", universe_tickers, index=0, key="duel_a")
    with d_col2:
        comp_b = st.selectbox("Company B", universe_tickers, index=1 if len(universe_tickers) > 1 else 0, key="duel_b")
    with d_col3:
        duel_year = st.selectbox("Fiscal year", ["Latest", 2024, 2023, 2022, 2021], key="duel_yr")

    fy_param = None if duel_year == "Latest" else int(duel_year)
    duel_result = compare_companies(comp_a, comp_b, fy_param)

    if "error" in duel_result:
        st.error(duel_result["error"])
    else:
        st.markdown(f"**Winner: {duel_result.get('overall_winner', 'Tie')}** · FY{duel_result.get('year')}")

        p1, p2, p3, p4 = st.columns(4)
        pillar_winners = duel_result.get("pillar_winners", {})
        p1.metric("Profitability", pillar_winners.get("Profitability", "Tie"))
        p2.metric("Solvency & health", pillar_winners.get("Financial Health & Solvency", "Tie"))
        p3.metric("Accounting quality", pillar_winners.get("Accounting Quality", "Tie"))
        p4.metric("Growth", pillar_winners.get("Growth", "Tie"))

        pillars = duel_result.get("pillars", {})
        scorecard_rows = []
        for p_name, metrics_list in pillars.items():
            for m in metrics_list:
                scorecard_rows.append({
                    "Pillar": p_name,
                    "Metric": m["metric_label"],
                    comp_a: format_metric_value(m["metric_id"], m["val_a"]) if m["val_a"] is not None else "N/A",
                    comp_b: format_metric_value(m["metric_id"], m["val_b"]) if m["val_b"] is not None else "N/A",
                    "Winner": m["winner"],
                })
        st.dataframe(pd.DataFrame(scorecard_rows), width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("#### Trend explorer")
    t_col1, t_col2, t_col3 = st.columns([1.5, 2, 1.5])
    with t_col1:
        trend_ticker = st.selectbox("Company", universe_tickers, index=0, key="trend_t")
    with t_col2:
        trend_metric = st.selectbox(
            "Metric", ["gross_margin", "operating_margin", "net_margin", "roe", "roa", "roic",
                      "fcf_margin", "altman_z", "current_ratio", "revenue", "cfo"],
            format_func=lambda m: m.replace("_", " ").title(), key="trend_m",
        )
    with t_col3:
        trend_period = st.selectbox("Granularity", ["annual", "quarterly", "ttm"], key="trend_p")

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
            x=x_vals, y=y_vals, mode="lines+markers",
            line=dict(color=ACCENT, width=3), marker=dict(size=8, color=ACCENT_DARK),
            hovertemplate=f"<b>%{{x}}</b>: %{{y:.2f}}{sfx}<extra></extra>",
        ))
        style_fig(fig_trend, height=340, title=f"{trend_ticker} — {trend_metric.replace('_', ' ').title()}")
        st.plotly_chart(fig_trend, width="stretch")
    else:
        st.info(f"No {trend_period} data available for {trend_ticker} / {trend_metric}.")


# =============================================================================
# Persistent bottom chat input
# =============================================================================
user_input = st.chat_input("Ask about ratios, valuation, or filing disclosures…")
if user_input:
    ask_and_store(user_input)
    st.rerun()
