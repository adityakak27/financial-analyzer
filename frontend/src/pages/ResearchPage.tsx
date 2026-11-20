import { useState } from "react";
import { api } from "../api/client";
import Markdown from "../components/Markdown";
import { useSelection } from "../context/SelectionContext";

export default function ResearchPage() {
  const { ticker, year } = useSelection();
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.research({ ticker, year });
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">4-Agent Equity Research Panel</h1>
        <p className="page-subtitle">
          Valuation Specialist, Forensic Auditor, Strategic Analyst, and Research Director synthesize an
          institutional-style Initiation of Coverage report.
        </p>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="row">
          <span className="muted">
            Company and fiscal year follow the sidebar selection: <strong>{ticker} FY{year ?? "—"}</strong>
          </span>
          <button className="btn" onClick={run} disabled={loading || !ticker}>
            {loading ? "Generating… (can take ~10-20s)" : "Generate Report"}
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {result?.markdown_report && (
        <div className="card">
          <Markdown className="markdown-report">{result.markdown_report}</Markdown>
        </div>
      )}
    </div>
  );
}
