import { NavLink } from "react-router-dom";
import { useSelection } from "../context/SelectionContext";

const LINKS = [
  { to: "/", label: "Chat", icon: "💬" },
  { to: "/dashboard", label: "Company Dashboard", icon: "📊" },
  { to: "/compare", label: "Compare / Duel", icon: "⚖️" },
  { to: "/valuation", label: "DCF Valuation", icon: "📈" },
  { to: "/research", label: "Research Report", icon: "🗂️" },
  { to: "/filings", label: "Filings Search", icon: "🔎" },
];

export default function Sidebar() {
  const { companies, ticker, setTicker, years, year, setYear, llmAvailable } = useSelection();

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-brand-mark" />
        Equity Research Copilot
      </div>

      <nav className="sidebar-nav">
        {LINKS.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) => "sidebar-link" + (isActive ? " active" : "")}
          >
            <span>{l.icon}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-picker">
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
          <span className={"status-dot" + (llmAvailable ? "" : " down")} />
          {llmAvailable === null ? "Checking backend…" : llmAvailable ? "LLM connected" : "LLM key missing"}
        </div>
      </div>
    </aside>
  );
}
