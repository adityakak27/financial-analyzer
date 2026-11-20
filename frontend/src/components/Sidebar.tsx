import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useSelection } from "../context/SelectionContext";
import {
  ChatIcon,
  ClockIcon,
  CompareIcon,
  DashboardIcon,
  FilingsIcon,
  PlusIcon,
  ResearchIcon,
  SearchIcon,
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
  const {
    companies,
    ticker,
    setTicker,
    years,
    year,
    setYear,
    llmAvailable,
    recentQuestions,
    askInChat,
    requestNewChat,
  } = useSelection();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  const visibleLinks = LINKS.filter((l) => l.label.toLowerCase().includes(query.toLowerCase()));
  const visibleRecents = recentQuestions.filter((q) => q.toLowerCase().includes(query.toLowerCase()));

  function handleNewChat() {
    requestNewChat();
    navigate("/");
  }

  function handleRecentClick(q: string) {
    navigate("/");
    askInChat(q);
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
        <input
          placeholder="Search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <nav className="sidebar-nav">
        {visibleLinks.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
          >
            <l.icon className="sidebar-icon" />
            {l.label}
          </NavLink>
        ))}
      </nav>

      {visibleRecents.length > 0 && (
        <>
          <div className="sidebar-section-label">Recents</div>
          <div className="sidebar-recents">
            {visibleRecents.map((q, i) => (
              <button
                key={i}
                className="sidebar-recent-item"
                title={q}
                onClick={() => handleRecentClick(q)}
              >
                <ClockIcon className="sidebar-icon" style={{ marginRight: 8, opacity: 0.6 }} />
                {q}
              </button>
            ))}
          </div>
        </>
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
