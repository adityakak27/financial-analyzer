import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import Markdown from "../components/Markdown";
import OutputsPanel from "../components/OutputsPanel";
import { ArrowUpIcon, CopyIcon, MicIcon, PlusIcon, RetryIcon, ThumbsDownIcon, ThumbsUpIcon } from "../components/Icons";
import type { ChatMessage, Citation } from "../types";
import { useSelection } from "../context/SelectionContext";

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

interface Turn extends ChatMessage {
  ts: number;
  liked?: boolean;
  disliked?: boolean;
}

export default function ChatPage() {
  const { llmAvailable, ticker, year, addRecentQuestion, chatSignal } = useSelection();
  const [messages, setMessages] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastSignalNonce = useRef<number | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || sending) return;
    addRecentQuestion(q);
    setMessages((m) => [
      ...m,
      { role: "user", content: q, ts: Date.now() },
      { role: "assistant", content: "", pending: true, ts: Date.now() },
    ]);
    setInput("");
    setSending(true);
    try {
      const res = await api.chat({ question: q, session_id: sessionId });
      setSessionId(res.session_id);
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = {
          role: "assistant",
          content: res.answer,
          citations: res.citations,
          toolTrace: res.tool_trace,
          ts: Date.now(),
        };
        return copy;
      });
    } catch (err: any) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: `⚠️ ${err.message || "Request failed."}`, ts: Date.now() };
        return copy;
      });
    } finally {
      setSending(false);
    }
  }

  async function handleReset() {
    if (sessionId) {
      try {
        await api.chatReset(sessionId);
      } catch {
        /* no-op */
      }
    }
    setMessages([]);
    setSessionId(null);
  }

  useEffect(() => {
    if (!chatSignal || chatSignal.nonce === lastSignalNonce.current) return;
    lastSignalNonce.current = chatSignal.nonce;
    if (chatSignal.type === "reset") {
      handleReset();
    } else if (chatSignal.type === "ask" && chatSignal.question) {
      handleReset().then(() => send(chatSignal.question!));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatSignal]);

  function retryLast() {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) send(lastUser.content);
  }

  function toggleReaction(idx: number, kind: "liked" | "disliked") {
    setMessages((m) => {
      const copy = [...m];
      const other = kind === "liked" ? "disliked" : "liked";
      copy[idx] = { ...copy[idx], [kind]: !copy[idx][kind], [other]: false };
      return copy;
    });
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
                    <span className="msg-timestamp">{timeAgo(m.ts)}</span>
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
                <button className="icon-btn-round" title="New chat" onClick={handleReset}>
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
