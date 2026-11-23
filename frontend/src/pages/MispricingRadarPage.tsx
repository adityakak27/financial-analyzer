import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import MetricTile from "../components/MetricTile";
import MispricingScatterChart, { SECTOR_LINE_COLORS } from "../components/charts/MispricingScatterChart";

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "N/A";
  return `${(v * 100).toFixed(digits)}%`;
}

function fmtX(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "N/A";
  return `${v.toFixed(1)}x`;
}

function verdictBadgeClass(verdict: string | null | undefined): string {
  if (verdict === "Undervalued") return "positive";
  if (verdict === "Overvalued") return "warning";
  return "neutral";
}

function agreementBadgeClass(agreement: string | null | undefined): string {
  if (agreement === "agrees") return "positive";
  if (agreement === "disagrees") return "negative";
  return "neutral";
}

const SCORE_OPTIONS: { key: "piotroski" | "altman" | "beneish"; label: string }[] = [
  { key: "piotroski", label: "Piotroski F-Score" },
  { key: "altman", label: "Altman Z-Score" },
  { key: "beneish", label: "Beneish M-Score" },
];

export default function MispricingRadarPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [overview, setOverview] = useState<any>(null);
  const [year, setYear] = useState<number | undefined>(undefined);
  const [subIndustry, setSubIndustry] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [under, setUnder] = useState<any[]>([]);
  const [over, setOver] = useState<any[]>([]);

  const [selectedTicker, setSelectedTicker] = useState<string | null>(searchParams.get("ticker"));
  const [companyDetail, setCompanyDetail] = useState<any>(null);
  const [companyLoading, setCompanyLoading] = useState(false);

  const [scoreKey, setScoreKey] = useState<"piotroski" | "altman" | "beneish">("piotroski");
  const [scoreEffectiveness, setScoreEffectiveness] = useState<any>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .mispricingOverview(year, subIndustry || undefined)
      .then((res) => {
        setOverview(res);
        if (year === undefined) setYear(res.fiscal_year);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [year, subIndustry]);

  useEffect(() => {
    if (year === undefined) return;
    api.mispricingLeaderboard("under", year, subIndustry || undefined, 10).then((r) => setUnder(r.companies || []));
    api.mispricingLeaderboard("over", year, subIndustry || undefined, 10).then((r) => setOver(r.companies || []));
  }, [year, subIndustry]);

  useEffect(() => {
    if (!selectedTicker) {
      setCompanyDetail(null);
      return;
    }
    setCompanyLoading(true);
    setSearchParams((p) => {
      p.set("ticker", selectedTicker);
      return p;
    });
    Promise.all([
      api.mispricingCompany(selectedTicker, year),
      api.scores(selectedTicker, year).catch(() => null),
      api.textSentiment(selectedTicker, year, "mda").catch(() => null),
    ])
      .then(([valuation, scores, tone]) => setCompanyDetail({ valuation, scores, tone }))
      .catch(() => setCompanyDetail(null))
      .finally(() => setCompanyLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedTicker, year]);

  useEffect(() => {
    api
      .mispricingScoreEffectiveness(scoreKey)
      .then(setScoreEffectiveness)
      .catch(() => setScoreEffectiveness(null));
  }, [scoreKey]);

  const fit = overview?.fit;
  const correlationDirection = fit?.slope > 0 ? "Positive" : fit?.slope < 0 ? "Negative" : "None";
  const verdictLines: any[] = overview?.verdict_lines || [];
  const trainSpan = verdictLines.length
    ? `FY${verdictLines[0].train_start}–FY${verdictLines[0].train_end}`
    : null;

  const scoreChartData = useMemo(() => {
    if (!scoreEffectiveness?.groups) return [];
    return scoreEffectiveness.groups.map((g: any) => ({
      group: g.group,
      return_pct: g.avg_next_12m_excess_return_vs_xlk_pct,
      n: g.n,
    }));
  }, [scoreEffectiveness]);

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Mispricing Radar</h1>
        <p className="page-subtitle">
          Fundamental Quality Score vs market valuation across the covered universe. A statistical comparison with
          peers, not a recommendation — every number traces back to the underlying SEC filings. Not investment advice.
        </p>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="row">
          <label className="muted">Fiscal Year</label>
          <select
            className="select"
            value={year ?? ""}
            onChange={(e) => setYear(e.target.value ? Number(e.target.value) : undefined)}
          >
            {(overview?.available_years || []).map((y: number) => (
              <option key={y} value={y}>
                FY{y}
              </option>
            ))}
          </select>
          <label className="muted">Sub-Industry</label>
          <select className="select" value={subIndustry} onChange={(e) => setSubIndustry(e.target.value)}>
            <option value="">All</option>
            {(overview?.sub_industries || []).map((s: string) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {!error && !loading && overview && overview.n_companies === 0 && (
        <div className="empty-state">
          Run <code>python -m finchat mispricing</code> to build the radar.
        </div>
      )}

      {!loading && overview && overview.n_companies > 0 && (
        <>
          <div className="grid grid-4" style={{ marginBottom: 20 }}>
            <MetricTile
              label="Quality explains valuation"
              value={fit?.r2 != null ? `${(fit.r2 * 100).toFixed(1)}% (R²)` : "N/A"}
              deltaLabel="same-year fit"
            />
            <MetricTile label="Relationship" value={fit ? correlationDirection : "N/A"} />
            <MetricTile
              label="Companies with a verdict"
              value={`${overview.n_with_verdict} / ${overview.n_companies}`}
            />
            <MetricTile label="Fiscal Year" value={`FY${overview.fiscal_year}`} />
          </div>

          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-title">Quality vs Valuation — click a point for detail</div>
            <MispricingScatterChart points={overview.points} lines={verdictLines} onSelect={setSelectedTicker} />
            {verdictLines.length > 0 ? (
              <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
                Each company is judged against its own sub-industry's line, fitted only on {trainSpan} (no
                future data).{" "}
                {verdictLines.map((l) => (
                  <span key={l.sub_industry} style={{ marginRight: 12, whiteSpace: "nowrap" }}>
                    <span
                      style={{
                        display: "inline-block", width: 14, height: 2, verticalAlign: "middle", marginRight: 4,
                        background: SECTOR_LINE_COLORS[l.sub_industry] ?? "var(--text-secondary)",
                      }}
                    />
                    {l.sub_industry}
                  </span>
                ))}
                In back-tests, these verdicts did not predict next-year returns.
              </p>
            ) : (
              <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
                FY{overview.fiscal_year} has no earlier fiscal years to fit a fair-value line on, so it has no
                verdicts. Pick a later year.
              </p>
            )}
          </div>

          <div className="grid grid-2" style={{ marginBottom: 20 }}>
            <div className="card">
              <div className="card-title">Top 10 Undervalued</div>
              <LeaderboardTable rows={under} onSelect={setSelectedTicker} />
            </div>
            <div className="card">
              <div className="card-title">Top 10 Overvalued</div>
              <LeaderboardTable rows={over} onSelect={setSelectedTicker} />
            </div>
          </div>

          {selectedTicker && (
            <div className="card" style={{ marginBottom: 20 }}>
              <div className="card-title">
                {selectedTicker} — Company Card
                <button className="btn" style={{ marginLeft: 12, fontSize: 12 }} onClick={() => setSelectedTicker(null)}>
                  Close
                </button>
              </div>
              {companyLoading && <div className="empty-state">Loading…</div>}
              {!companyLoading && companyDetail?.valuation && <CompanyCard detail={companyDetail} />}
              {!companyLoading && !companyDetail?.valuation && (
                <div className="empty-state">No Mispricing Radar data for {selectedTicker} in FY{year}.</div>
              )}
            </div>
          )}

          <div className="card">
            <div className="card-title">
              Do the Scores Work?
              <select
                className="select"
                style={{ fontSize: 12.5, marginLeft: 12 }}
                value={scoreKey}
                onChange={(e) => setScoreKey(e.target.value as any)}
              >
                {SCORE_OPTIONS.map((o) => (
                  <option key={o.key} value={o.key}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
            <p className="muted" style={{ fontSize: 12.5, marginBottom: 8 }}>
              Average next-12-month return in excess of the XLK tech ETF, by score group (a grouped comparison,
              not a trained model).
            </p>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={scoreChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="group" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} />
                <YAxis tick={{ fontSize: 11, fill: "var(--text-secondary)" }} width={40} unit="%" />
                <Tooltip
                  contentStyle={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                  formatter={(v: any, _name: any, p: any) => [`${v}%`, `n=${p.payload.n}`]}
                />
                <Bar dataKey="return_pct" fill="var(--accent)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

function LeaderboardTable({ rows, onSelect }: { rows: any[]; onSelect: (t: string) => void }) {
  if (!rows.length) return <div className="empty-state">No data</div>;
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Quality</th>
          <th>EV/Sales</th>
          <th>Gap (z)</th>
          <th>Verdict</th>
          <th>DCF Upside</th>
          <th>DCF</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.ticker} onClick={() => onSelect(r.ticker)} style={{ cursor: "pointer" }}>
            <td>{r.ticker}</td>
            <td>{r.quality_score?.toFixed(1)}</td>
            <td>{fmtX(r.ev_sales)}</td>
            <td>{r.gap_z?.toFixed(2)}</td>
            <td>
              <span className={`badge ${verdictBadgeClass(r.verdict)}`}>{r.verdict}</span>
            </td>
            <td>{fmtPct(r.dcf_upside)}</td>
            <td>
              <span className={`badge ${agreementBadgeClass(r.dcf_agreement)}`}>{r.dcf_agreement}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CompanyCard({ detail }: { detail: any }) {
  const v = detail.valuation;
  const scores = detail.scores;
  const tone = detail.tone;

  return (
    <div>
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <MetricTile label="Quality Score" value={`${v.quality_score?.toFixed(1)} / 100`} />
        <MetricTile label="EV/Sales (actual vs expected)" value={`${fmtX(v.ev_sales)} vs ${fmtX(v.expected_ev_sales)}`} />
        <MetricTile
          label="Verdict"
          value={v.verdict}
          deltaLabel={`gap z=${v.gap_z?.toFixed(2)}, ${v.gap_percentile_among_all_companies_this_year}th pct of all companies`}
        />
        <MetricTile label="DCF Upside" value={fmtPct(v.dcf_upside)} deltaLabel={v.dcf_agreement} />
      </div>

      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <MetricTile label="Profitability" value={v.pillars?.profitability?.toFixed(1) ?? "N/A"} />
        <MetricTile label="Growth" value={v.pillars?.growth?.toFixed(1) ?? "N/A"} />
        <MetricTile label="Safety" value={v.pillars?.safety?.toFixed(1) ?? "N/A"} />
        <MetricTile label="Earnings Quality" value={v.pillars?.earnings_quality?.toFixed(1) ?? "N/A"} />
      </div>

      <div className="grid grid-3" style={{ marginBottom: 16 }}>
        <MetricTile label="Altman Z" value={scores?.altman_z?.value?.toFixed?.(2) ?? "N/A"} deltaLabel={scores?.altman_z?.zone} />
        <MetricTile label="Piotroski F" value={scores?.piotroski_f?.value != null ? `${scores.piotroski_f.value} / 9` : "N/A"} />
        <MetricTile label="Beneish M" value={scores?.beneish_m?.value?.toFixed?.(2) ?? "N/A"} deltaLabel={scores?.beneish_m?.flag} />
      </div>

      <p className="muted" style={{ fontSize: 12.5, marginBottom: 12 }}>
        {v.verdict_model?.train_years
          ? `Verdict model: ${v.verdict_model.sub_industry} fair-value line fitted on ${v.verdict_model.train_years} ` +
            `(R² ${v.fair_value_line_r2 != null ? v.fair_value_line_r2.toFixed(2) : "N/A"}, n=${v.verdict_model.train_n}).`
          : "No verdict: there are no earlier fiscal years to fit a fair-value line on."}
        {v.next_12m_excess_return_vs_xlk != null &&
          ` Next 12 months vs XLK: ${fmtPct(v.next_12m_excess_return_vs_xlk)}.`}
        {tone?.polarity != null && ` Management tone (MD&A polarity): ${tone.polarity.toFixed(2)}.`}
      </p>

      {v.analyst_note && (
        <div className="card" style={{ background: "var(--bg-elevated-hover)" }}>
          <div className="card-title" style={{ fontSize: 12.5 }}>
            AI-written from the numbers above · Not investment advice
          </div>
          <p style={{ fontSize: 13, lineHeight: 1.5 }}>{v.analyst_note}</p>
        </div>
      )}
    </div>
  );
}
