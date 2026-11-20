import { useEffect, useState } from "react";
import { api } from "../api/client";
import { useSelection } from "../context/SelectionContext";

export default function ComparePage() {
  const { companies, ticker, tickerB, setTicker, setTickerB } = useSelection();
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.compare(ticker, tickerB);
      if (res.error) setError(res.error);
      else setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Company Duel</h1>
        <p className="page-subtitle">
          Head-to-head scorecard across profitability, solvency, accounting quality, and growth pillars.
        </p>
      </div>

      <div className="row" style={{ marginBottom: 20 }}>
        <select className="select" value={ticker} onChange={(e) => setTicker(e.target.value)}>
          {companies.map((c) => (
            <option key={c.ticker} value={c.ticker}>
              {c.ticker}
            </option>
          ))}
        </select>
        <span className="muted">vs</span>
        <select className="select" value={tickerB} onChange={(e) => setTickerB(e.target.value)}>
          {companies.map((c) => (
            <option key={c.ticker} value={c.ticker}>
              {c.ticker}
            </option>
          ))}
        </select>
        <button className="btn" onClick={run} disabled={loading}>
          {loading ? "Comparing…" : "Compare"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {result && !error && (
        <>
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-title">
              FY{result.year} Verdict
              <span className="badge neutral">
                {result.wins_a}–{result.wins_b}–{result.ties}
              </span>
            </div>
            <p style={{ margin: 0 }}>{result.verdict}</p>
          </div>

          <div className="grid grid-4" style={{ marginBottom: 20 }}>
            {Object.entries(result.pillar_winners).map(([pillar, winner]) => (
              <div className="metric-tile" key={pillar}>
                <div className="metric-label">{pillar}</div>
                <div className="metric-value" style={{ fontSize: 15 }}>
                  {String(winner)}
                </div>
              </div>
            ))}
          </div>

          {Object.entries(result.pillars).map(([pillar, rows]: [string, any]) => (
            <div className="card" style={{ marginBottom: 18 }} key={pillar}>
              <div className="card-title">{pillar}</div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Metric</th>
                    <th className="num">{result.ticker_a}</th>
                    <th className="num">{result.ticker_b}</th>
                    <th>Winner</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r: any) => (
                    <tr key={r.metric_id}>
                      <td>{r.metric_label}</td>
                      <td className="num">{r.formatted_a}</td>
                      <td className="num">{r.formatted_b}</td>
                      <td>
                        <span
                          className={
                            "badge " +
                            (r.winner === "TIE" ? "neutral" : r.winner === result.ticker_a ? "positive" : "negative")
                          }
                        >
                          {r.winner}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
