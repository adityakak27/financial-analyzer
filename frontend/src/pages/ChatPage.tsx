import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import Markdown from "../components/Markdown";
import OutputsPanel from "../components/OutputsPanel";
import { ArrowUpIcon, CopyIcon, MicIcon, PlusIcon, RetryIcon, ThumbsDownIcon, ThumbsUpIcon } from "../components/Icons";
import type { Citation } from "../types";
import { useSelection } from "../context/SelectionContext";
import { useChatHistory } from "../context/ChatHistoryContext";

const SUGGESTIONS = [
  "What was Apple's gross margin in FY2023?",
  "Compare MSFT and NVDA on ROE",
  "Does Intel look like a distress risk?",
  "Run a DCF valuation for AAPL",
  "What supply chain risks did NVIDIA disclose?",
];

function citationLabel(c: Citation): string {
  if (c.type === "filing_text") {
    return `${c.ticker ?? ""} FY${c.fy ?? ""} ${c.section ?? ""}`.trim();
  }
  return `${c.ticker ?? ""} ${c.fy ?? ""} ${c.metric ?? ""}`.trim();
}

function timeAgo(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} minute${m === 1 ? "" : "s"} ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} hour${h === 1 ? "" : "s"} ago`;
  const d = Math.floor(h / 24);
  return `${d} day${d === 1 ? "" : "s"} ago`;
}

export default function ChatPage() {
  const { llmAvailable, ticker, year } = useSelection();
  const { activeConversation, startNewChat, ensureActiveConversation, setConversationMessages, setConversationSessionId } =
    useChatHistory();
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const messages = activeConversation?.messages ?? [];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, messages[messages.length - 1]?.content]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || sending) return;
    const baseMessages = activeConversation?.messages ?? [];
    const priorSessionId = activeConversation?.sessionId ?? null;
    const id = ensureActiveConversation(q);
    const withPending = [
      ...baseMessages,
      { role: "user" as const, content: q, ts: Date.now() },
      { role: "assistant" as const, content: "", pending: true, ts: Date.now() },
    ];
    setConversationMessages(id, withPending);
    setInput("");
    setSending(true);
    try {
      const res = await api.chat({ question: q, session_id: priorSessionId });
      setConversationSessionId(id, res.session_id);
      const final = [...withPending];
      final[final.length - 1] = {
        role: "assistant",
        content: res.answer,
        citations: res.citations,
        toolTrace: res.tool_trace,
        ts: Date.now(),
      };
      setConversationMessages(id, final);
    } catch (err: any) {
      const final = [...withPending];
      final[final.length - 1] = { role: "assistant", content: `⚠️ ${err.message || "Request failed."}`, ts: Date.now() };
      setConversationMessages(id, final);
    } finally {
      setSending(false);
    }
  }

  function retryLast() {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) send(lastUser.content);
  }

  function toggleReaction(idx: number, kind: "liked" | "disliked") {
    if (!activeConversation) return;
    const copy = [...activeConversation.messages];
    const other = kind === "liked" ? "disliked" : "liked";
    copy[idx] = { ...copy[idx], [kind]: !copy[idx][kind], [other]: false };
    setConversationMessages(activeConversation.id, copy);
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant" && !m.pending);

  return (
    <div style={{ display: "flex", height: "100%", flex: 1, minWidth: 0 }}>
      <div className="chat-wrap" style={{ flex: 1, minWidth: 0 }}>
        <div className="chat-topbar">
          <span>
            Focused on <strong>{ticker}</strong> · FY{year ?? "—"}
          </span>
          <span className={"status-dot" + (llmAvailable ? "" : " down")} />
        </div>

        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="empty-state" style={{ marginTop: 60 }}>
              {llmAvailable === false
                ? "GEMINI_API_KEY is not set on the backend — add it to .env and restart the server."
                : "Ask about ratios, scores, DCF valuations, peer comparisons, or 10-K disclosures for the covered universe."}
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`msg ${m.role}`}>
                <div className="msg-bubble">
                  {m.pending ? (
                    <span className="typing-dots">
                      <span />
                      <span />
                      <span />
                    </span>
                  ) : m.role === "assistant" ? (
                    <Markdown>{m.content}</Markdown>
                  ) : (
                    m.content
                  )}
                </div>

                {m.citations && m.citations.length > 0 && (
                  <div className="msg-citations">
                    {m.citations.slice(0, 6).map((c, ci) => (
                      <span className="citation-chip" key={ci}>
                        {citationLabel(c)}
                      </span>
                    ))}
                  </div>
                )}

                {m.role === "assistant" && !m.pending && (
                  <div className="msg-actions">
                    <button className="msg-icon-btn" title="Copy" onClick={() => navigator.clipboard?.writeText(m.content)}>
                      <CopyIcon />
                    </button>
                    <button
                      className="msg-icon-btn"
                      title="Good response"
                      style={m.liked ? { color: "var(--positive)" } : undefined}
                      onClick={() => toggleReaction(i, "liked")}
                    >
                      <ThumbsUpIcon />
                    </button>
                    <button
                      className="msg-icon-btn"
                      title="Bad response"
                      style={m.disliked ? { color: "var(--negative)" } : undefined}
                      onClick={() => toggleReaction(i, "disliked")}
                    >
                      <ThumbsDownIcon />
                    </button>
                    {i === messages.length - 1 && (
                      <button className="msg-icon-btn" title="Retry" onClick={retryLast}>
                        <RetryIcon />
                      </button>
                    )}
                    <span className="msg-timestamp">{timeAgo(m.ts ?? Date.now())}</span>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {messages.length === 0 && (
          <div className="chat-suggestions">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="suggestion-chip" onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="chat-input-bar">
          <div className="chat-input-inner">
            <textarea
              rows={1}
              placeholder="Ask about a company's fundamentals…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
            />
            <div className="chat-input-toolbar">
              <div className="chat-input-toolbar-left">
                <button className="icon-btn-round" title="New chat" onClick={startNewChat}>
                  <PlusIcon />
                </button>
                <button className="icon-btn-round" title="Voice input (not available)" disabled>
                  <MicIcon />
                </button>
              </div>
              <div className="chat-input-toolbar-right">
                <span className="model-pill">Gemini · Tool-calling</span>
                <button className="send-btn" disabled={sending || !input.trim()} onClick={() => send(input)}>
                  <ArrowUpIcon width={16} height={16} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <OutputsPanel trace={lastAssistant?.toolTrace} />
    </div>
  );
}
