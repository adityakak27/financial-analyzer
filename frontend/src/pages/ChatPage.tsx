import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import Markdown from "../components/Markdown";
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

export default function ChatPage() {
  const { llmAvailable } = useSelection();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || sending) return;
    setMessages((m) => [...m, { role: "user", content: q }, { role: "assistant", content: "", pending: true }]);
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
        };
        return copy;
      });
    } catch (err: any) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: `⚠️ ${err.message || "Request failed."}` };
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

  return (
    <div className="chat-wrap">
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
              {m.citations && m.citations.length > 0 ? (
                <div className="msg-citations">
                  {m.citations.slice(0, 6).map((c, ci) => (
                    <span className="citation-chip" key={ci}>
                      {citationLabel(c)}
                    </span>
                  ))}
                </div>
              ) : null}
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
          <button className="btn" disabled={sending || !input.trim()} onClick={() => send(input)}>
            Send
          </button>
          <button className="btn secondary" onClick={handleReset} disabled={sending}>
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}
