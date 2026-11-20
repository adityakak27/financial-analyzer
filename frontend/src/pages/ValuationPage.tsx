import { useState } from "react";
import { api } from "../api/client";
import MetricTile from "../components/MetricTile";
import WaterfallChart from "../components/charts/WaterfallChart";
import DcfSensitivityChart from "../components/charts/DcfSensitivityChart";
import SensitivityHeatmap from "../components/charts/SensitivityHeatmap";
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
            <WaterfallChart steps={result.waterfall} height={240} />
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-title">Implied Share Price vs WACC (click a line in the legend to isolate it)</div>
            <DcfSensitivityChart matrix={sens} height={280} />
          </div>

          <div className="card">
            <div className="card-title">Sensitivity Heatmap: Implied Share Price (WACC × Terminal Growth)</div>
            <SensitivityHeatmap matrix={sens} />
          </div>
        </>
      )}
    </div>
  );
}
