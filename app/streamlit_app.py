from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from finchat.chatbot.agent import FinChatAgent
from finchat.chatbot.tools import tool_list_companies

st.set_page_config(page_title="Conversational Fundamental Analyst", page_icon=":chart:", layout="wide")

if "agent" not in st.session_state:
    st.session_state.agent = FinChatAgent(force_offline=st.session_state.get("force_offline", False))
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("Fundamental Analyst Chat")
    st.caption("Hybrid design: exact structured lookups for numbers, retrieval for filing text.")
    mode = st.radio("Answer mode", ["Auto", "Force offline (deterministic)"], index=0)
    if (mode == "Force offline (deterministic)") != st.session_state.get("force_offline", False):
        st.session_state.force_offline = mode == "Force offline (deterministic)"
        st.session_state.agent = FinChatAgent(force_offline=st.session_state.force_offline)
        st.rerun()
    if st.button("Reset conversation"):
        st.session_state.agent.reset()
        st.session_state.messages = []
        st.rerun()
    st.divider()
    companies = tool_list_companies()["companies"]
    st.subheader(f"Coverage: {len(companies)} companies")
    st.write(", ".join(c["ticker"] for c in companies))
    st.caption("Data: SEC EDGAR XBRL + 10-K text. Educational use; not investment advice.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("citations"):
            with st.expander("Sources & provenance"):
                for i, c in enumerate(msg["citations"], 1):
                    url = c.get("url")
                    label = f"{i}. {c['type']}" + (f" | {c.get('table', '')}" if c.get("table") else "") \
                        + (f" | {c.get('ticker', '')} FY{c.get('fy')}" if c.get("ticker") else "") \
                        + (f" | {c.get('section', '')}" if c.get("section") else "")
                    if url:
                        st.markdown(f"[{label}]({url})")
                    else:
                        st.text(label)
        if msg["role"] == "assistant" and msg.get("tool_trace"):
            with st.expander("Tool calls made"):
                st.json(msg["tool_trace"])

user_input = st.chat_input("Ask about ratios, scores, trends, peers, or disclosed risks...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    with st.chat_message("assistant"), st.spinner("Analyzing..."):
        resp = st.session_state.agent.ask(user_input)
        st.markdown(resp.answer)
        if resp.citations:
            with st.expander("Sources & provenance"):
                for i, c in enumerate(resp.citations, 1):
                    url = c.get("url")
                    label = f"{i}. {c['type']}" + (f" | {c.get('table', '')}" if c.get("table") else "") \
                        + (f" | {c.get('ticker', '')} FY{c.get('fy')}" if c.get("ticker") else "") \
                        + (f" | {c.get('section', '')}" if c.get("section") else "")
                    if url:
                        st.markdown(f"[{label}]({url})")
                    else:
                        st.text(label)
        if resp.tool_trace:
            with st.expander("Tool calls made"):
                st.json([{k: t[k] for k in ("name", "args")} for t in resp.tool_trace])
    st.session_state.messages.append({
        "role": "assistant", "content": resp.answer,
        "citations": resp.citations, "tool_trace": [
            {k: t[k] for k in ("name", "args")} for t in resp.tool_trace
        ],
    })
