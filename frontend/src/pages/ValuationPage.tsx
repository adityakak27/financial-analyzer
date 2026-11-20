import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import MetricTile from "../components/MetricTile";
import { useSelection } from "../context/SelectionContext";

function fmtUsd(v: number | null | undefined): string {
  if (v === null || v === undefined) return "N/A";
  const abs = Math.abs(v);
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  return `$${v.toFixed(2)}`;
}

export default function ValuationPage() {
  const { ticker, companies } = useSelection();
  const [selectedTicker, setSelectedTicker] = useState(ticker);
  const [wacc, setWacc] = useState(9.0);
  const [terminalGrowth, setTerminalGrowth] = useState(2.5);
  const [years, setYears] = useState(5);
  const [customGrowth, setCustomGrowth] = useState<string>("");
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await api.dcf({
        ticker: selectedTicker || ticker,
        wacc: wacc / 100,
        terminal_growth: terminalGrowth / 100,
        forecast_years: years,
        custom_growth_rate: customGrowth.trim() ? Number(customGrowth) / 100 : null,
      });
      setResult(res);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const sens = result?.sensitivity_matrix;
  const baseWaccIdx = sens ? Math.floor(sens.wacc_axis.length / 2) : -1;
  const baseGrowthIdx = sens ? Math.floor(sens.growth_axis.length / 2) : -1;

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">DCF Intrinsic Valuation</h1>
        <p className="page-subtitle">
          Discounted cash flow model: projected FCF, Gordon Growth terminal value, and WACC × growth sensitivity.
        </p>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="row">
          <select className="select" value={selectedTicker} onChange={(e) => setSelectedTicker(e.target.value)}>
            {companies.map((c) => (
              <option key={c.ticker} value={c.ticker}>
                {c.ticker}
              </option>
            ))}
          </select>
          <label className="muted">WACC %</label>
          <input
            className="input"
            type="number"
            step="0.1"
            value={wacc}
            onChange={(e) => setWacc(Number(e.target.value))}
            style={{ width: 80 }}
          />
          <label className="muted">Terminal Growth %</label>
          <input
            className="input"
            type="number"
            step="0.1"
            value={terminalGrowth}
            onChange={(e) => setTerminalGrowth(Number(e.target.value))}
            style={{ width: 80 }}
          />
          <label className="muted">Forecast Years</label>
          <input
            className="input"
            type="number"
            value={years}
            onChange={(e) => setYears(Number(e.target.value))}
            style={{ width: 70 }}
          />
          <label className="muted">Custom Growth % (optional)</label>
          <input
            className="input"
            placeholder="auto"
            value={customGrowth}
            onChange={(e) => setCustomGrowth(e.target.value)}
            style={{ width: 90 }}
          />
          <button className="btn" onClick={run} disabled={loading}>
            {loading ? "Running…" : "Run DCF"}
          </button>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {result && !error && (
        <>
          <div className="grid grid-4" style={{ marginBottom: 20 }}>
            <MetricTile label="Enterprise Value" value={fmtUsd(result.enterprise_value)} />
            <MetricTile label="Implied Equity Value" value={fmtUsd(result.implied_equity_value)} />
            <MetricTile
              label="Implied Share Price"
              value={result.implied_share_price ? `$${result.implied_share_price.toFixed(2)}` : "N/A"}
            />
            <MetricTile
              label="Growth Rate Used"
              value={`${(result.assumptions.growth_rate_used * 100).toFixed(1)}%`}
              deltaLabel={result.assumptions.growth_method}
            />
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-title">Valuation Bridge (Enterprise → Equity, $B)</div>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={result.waterfall} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="label" tick={{ fontSize: 10.5, fill: "var(--text-secondary)" }} interval={0} angle={-12} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
                <Tooltip
                  contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                />
                <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <div className="card-title">Sensitivity: Implied Share Price (WACC × Terminal Growth)</div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>WACC \ Growth</th>
                  {sens.growth_axis.map((g: number, gi: number) => (
                    <th className="num" key={gi}>
                      {g.toFixed(2)}%
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sens.rows.map((row: any, ri: number) => (
                  <tr key={ri}>
                    <td>{row.wacc.toFixed(2)}%</td>
                    {row.values.map((v: any, ci: number) => (
                      <td
                        className="num"
                        key={ci}
                        style={
                          ri === baseWaccIdx && ci === baseGrowthIdx
                            ? { background: "var(--accent-soft)", fontWeight: 700 }
                            : undefined
                        }
                      >
                        {v.implied_share_price !== null ? `$${v.implied_share_price.toFixed(2)}` : "N/A"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
