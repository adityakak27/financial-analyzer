import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useSelection } from "../context/SelectionContext";
import { useChatHistory } from "../context/ChatHistoryContext";
import {
  ChatIcon,
  ClockIcon,
  CompareIcon,
  DashboardIcon,
  FilingsIcon,
  PlusIcon,
  ResearchIcon,
  SearchIcon,
  TrashIcon,
  ValuationIcon,
} from "./Icons";

const LINKS = [
  { to: "/", label: "Chat", icon: ChatIcon },
  { to: "/dashboard", label: "Company Dashboard", icon: DashboardIcon },
  { to: "/compare", label: "Compare / Duel", icon: CompareIcon },
  { to: "/valuation", label: "DCF Valuation", icon: ValuationIcon },
  { to: "/research", label: "Research Report", icon: ResearchIcon },
  { to: "/filings", label: "Filings Search", icon: FilingsIcon },
];

export default function Sidebar() {
  const { companies, ticker, setTicker, years, year, setYear, llmAvailable } = useSelection();
  const { conversations, activeId, selectConversation, startNewChat, deleteConversation } = useChatHistory();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const q = query.trim().toLowerCase();
  const visibleLinks = LINKS.filter((l) => l.label.toLowerCase().includes(q));
  const visibleConversations = [...conversations]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .filter((c) => {
      if (!q) return true;
      if (c.title.toLowerCase().includes(q)) return true;
      return c.messages.some((m) => m.content.toLowerCase().includes(q));
    });

  function handleNewChat() {
    startNewChat();
    navigate("/");
  }

  function handleSelect(id: string) {
    selectConversation(id);
    navigate("/");
  }

  function handleDelete(e: React.MouseEvent, id: string) {
    e.stopPropagation();
    deleteConversation(id);
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark" />
        Equity Research Copilot
      </div>

      <button className="sidebar-action" onClick={handleNewChat}>
        <PlusIcon className="sidebar-icon" />
        New chat
      </button>

      <div className="sidebar-search">
        <SearchIcon className="sidebar-icon" />
        <input placeholder="Search" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>

      <nav className="sidebar-nav">
        {visibleLinks.map((l) => (
          <NavLink key={l.to} to={l.to} className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}>
            <l.icon className="sidebar-icon" />
            {l.label}
          </NavLink>
        ))}
      </nav>

      {visibleConversations.length > 0 && (
        <>
          <div className="sidebar-section-label">Recents</div>
          <div className="sidebar-recents">
            {visibleConversations.map((c) => (
              <div
                key={c.id}
                className={"sidebar-recent-row" + (c.id === activeId ? " active" : "")}
              >
                <button className="sidebar-recent-item" title={c.title} onClick={() => handleSelect(c.id)}>
                  <ClockIcon className="sidebar-icon" style={{ marginRight: 8, opacity: 0.6, flexShrink: 0 }} />
                  <span className="sidebar-recent-title">{c.title}</span>
                </button>
                <button
                  className="sidebar-recent-delete"
                  title="Delete chat"
                  onClick={(e) => handleDelete(e, c.id)}
                >
                  <TrashIcon width={14} height={14} />
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {q && visibleLinks.length === 0 && visibleConversations.length === 0 && (
        <div className="sidebar-no-results">No matches for "{query}"</div>
      )}

      <div className="sidebar-footer">
        <label htmlFor="company-select">Company</label>
        <select
          id="company-select"
          className="sidebar-select"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
        >
          {companies.map((c) => (
            <option key={c.ticker} value={c.ticker}>
              {c.ticker} — {c.name}
            </option>
          ))}
        </select>

        <label htmlFor="year-select">Fiscal Year</label>
        <select
          id="year-select"
          className="sidebar-select"
          value={year ?? ""}
          onChange={(e) => setYear(e.target.value ? Number(e.target.value) : undefined)}
        >
          {years.map((y) => (
            <option key={y} value={y}>
              FY{y}
            </option>
          ))}
        </select>

        <div className="sidebar-status">
          <span className="sidebar-avatar">ER</span>
          <span style={{ flex: 1 }}>Equity Copilot</span>
          <span className={"status-dot" + (llmAvailable ? "" : " down")} />
        </div>
      </div>
    </aside>
  );
}
