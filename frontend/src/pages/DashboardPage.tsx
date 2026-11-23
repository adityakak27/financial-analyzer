import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import MetricTile from "../components/MetricTile";
import MetricHistoryChart from "../components/MetricHistoryChart";
import { useSelection } from "../context/SelectionContext";

const RATIO_METRICS: { key: string; label: string }[] = [
  { key: "gross_margin", label: "Gross Margin" },
  { key: "operating_margin", label: "Operating Margin" },
  { key: "net_margin", label: "Net Margin" },
  { key: "roe", label: "Return on Equity" },
  { key: "roa", label: "Return on Assets" },
  { key: "roic", label: "Return on Invested Capital" },
  { key: "current_ratio", label: "Current Ratio" },
  { key: "debt_to_equity", label: "Debt / Equity" },
  { key: "fcf_margin", label: "FCF Margin" },
  { key: "revenue_growth_pct", label: "Revenue Growth YoY" },
  { key: "net_income_growth_pct", label: "Net Income Growth YoY" },
  { key: "asset_turnover", label: "Asset Turnover" },
];

function deltaInfo(current: number | null, prior: number | null): { label?: string; dir?: "up" | "down" } {
  if (current === null || prior === null || prior === 0) return {};
  const diff = current - prior;
  const dir = diff >= 0 ? "up" : "down";
  const pct = (diff / Math.abs(prior)) * 100;
  return { label: `${diff >= 0 ? "+" : ""}${pct.toFixed(1)}% vs prior year`, dir };
}

function scoreBadgeClass(kind: "altman" | "piotroski" | "beneish", value: any): string {
  if (kind === "altman") {
    if (value === "safe") return "positive";
    if (value === "grey") return "warning";
    if (value === "distress") return "negative";
  }
  if (kind === "piotroski") {
    if (value >= 7) return "positive";
    if (value >= 4) return "warning";
    return "negative";
  }
  if (kind === "beneish") {
    return value && value > -1.78 ? "warning" : "positive";
  }
  return "neutral";
}

export default function DashboardPage() {
  const { ticker, year, companies } = useSelection();
  const [ratios, setRatios] = useState<Record<string, any>>({});
  const [scores, setScores] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [historyMetric, setHistoryMetric] = useState("roe");
  const [loading, setLoading] = useState(true);
  const [valuationCheck, setValuationCheck] = useState<any>(null);

  const company = companies.find((c) => c.ticker === ticker);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    Promise.all(RATIO_METRICS.map((m) => api.ratio(ticker, m.key, year)))
      .then((results) => {
        const map: Record<string, any> = {};
        results.forEach((r, i) => (map[RATIO_METRICS[i].key] = r));
        setRatios(map);
      })
      .catch(() => setRatios({}));
    api
      .scores(ticker, year)
      .then(setScores)
      .catch(() => setScores(null));
    api
      .mispricingCompany(ticker, year)
      .then(setValuationCheck)
      .catch(() => setValuationCheck(null));
  }, [ticker, year]);

  useEffect(() => {
    if (!ticker) return;
    api
      .metricHistory(ticker, historyMetric, 2018, 2026, "annual")
      .then(setHistory)
      .catch(() => setHistory(null))
      .finally(() => setLoading(false));
  }, [ticker, historyMetric]);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">
          {company ? `${company.name} (${ticker})` : ticker} — FY{year ?? "—"}
          {valuationCheck && !valuationCheck.error && (
            <Link
              to={`/mispricing?ticker=${ticker}`}
              className={`badge ${valuationCheck.verdict === "Undervalued" ? "positive" : valuationCheck.verdict === "Overvalued" ? "warning" : "neutral"}`}
              style={{ marginLeft: 12, fontSize: 12, textDecoration: "none" }}
              title={`Gap z-score: ${valuationCheck.gap_z?.toFixed?.(2)} — open the Mispricing Radar`}
            >
              Valuation Check: {valuationCheck.verdict === "insufficient_data" ? "no verdict" : valuationCheck.verdict}
            </Link>
          )}
        </h1>
        <p className="page-subtitle">Ratio analysis, DuPont-adjacent returns, and credit/quality scores from SEC XBRL filings.</p>
      </div>

      <div className="grid grid-4" style={{ marginBottom: 20 }}>
        {RATIO_METRICS.map((m) => {
          const r = ratios[m.key];
          const d = r ? deltaInfo(r.value, r.prior_year_value) : {};
          return (
            <MetricTile
              key={m.key}
              label={m.label}
              value={r ? r.formatted : "…"}
              deltaLabel={d.label}
              deltaDirection={d.dir}
            />
          );
        })}
      </div>

      <div className="grid grid-3" style={{ marginBottom: 20 }}>
        <div className="card">
          <div className="card-title">Altman Z-Score</div>
          {scores?.altman_z ? (
            <>
              <div className="metric-value" style={{ marginBottom: 8 }}>
                {scores.altman_z.value?.toFixed ? scores.altman_z.value.toFixed(2) : scores.altman_z.value}
                <span className={`badge ${scoreBadgeClass("altman", scores.altman_z.zone)}`} style={{ marginLeft: 10 }}>
                  {scores.altman_z.zone}
                </span>
              </div>
              <p className="muted" style={{ fontSize: 12.5 }}>{scores.altman_z.interpretation}</p>
            </>
          ) : (
            <div className="empty-state">Not available</div>
          )}
        </div>
        <div className="card">
          <div className="card-title">Piotroski F-Score</div>
          {scores?.piotroski_f ? (
            <>
              <div className="metric-value" style={{ marginBottom: 8 }}>
                {scores.piotroski_f.value} / 9
                <span className={`badge ${scoreBadgeClass("piotroski", scores.piotroski_f.value)}`} style={{ marginLeft: 10 }}>
                  {scores.piotroski_f.value >= 7 ? "strong" : scores.piotroski_f.value >= 4 ? "moderate" : "weak"}
                </span>
              </div>
              <p className="muted" style={{ fontSize: 12.5 }}>{scores.piotroski_f.interpretation}</p>
            </>
          ) : (
            <div className="empty-state">Not available</div>
          )}
        </div>
        <div className="card">
          <div className="card-title">Beneish M-Score</div>
          {scores?.beneish_m ? (
            <>
              <div className="metric-value" style={{ marginBottom: 8 }}>
                {scores.beneish_m.value?.toFixed ? scores.beneish_m.value.toFixed(2) : scores.beneish_m.value}
                <span className={`badge ${scoreBadgeClass("beneish", scores.beneish_m.value)}`} style={{ marginLeft: 10 }}>
                  {scores.beneish_m.flag}
                </span>
              </div>
              <p className="muted" style={{ fontSize: 12.5 }}>{scores.beneish_m.interpretation}</p>
            </>
          ) : (
            <div className="empty-state">Not available</div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-title">
          Historical Trend
          <select
            className="select"
            value={historyMetric}
            onChange={(e) => setHistoryMetric(e.target.value)}
            style={{ fontSize: 12.5 }}
          >
            {RATIO_METRICS.map((m) => (
              <option key={m.key} value={m.key}>
                {m.label}
              </option>
            ))}
            <option value="altman_z">Altman Z-Score</option>
            <option value="revenue">Revenue</option>
            <option value="net_income">Net Income</option>
          </select>
        </div>
        {!loading && <MetricHistoryChart series={history?.series || []} />}
      </div>
    </div>
  );
}
