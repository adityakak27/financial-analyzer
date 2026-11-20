import type { ToolTraceEntry } from "../types";

function Card({ kicker, title, value, meta }: { kicker: string; title: string; value?: string; meta?: string }) {
  return (
    <div className="output-card">
      <div className="output-card-kicker">{kicker}</div>
      <div className="output-card-title">{title}</div>
      {value && <div className="output-card-value">{value}</div>}
      {meta && <div className="output-card-meta">{meta}</div>}
    </div>
  );
}

function renderEntry(entry: ToolTraceEntry, idx: number) {
  const r = entry.result || {};
  switch (entry.name) {
    case "get_ratio":
      return (
        <Card
          key={idx}
          kicker={`${r.ticker ?? ""} · FY${r.year ?? ""}`}
          title={r.metric ?? "ratio"}
          value={r.formatted ?? "N/A"}
          meta={
            r.prior_year_formatted
              ? `FY${r.prior_year}: ${r.prior_year_formatted}` +
                (r.peer_rank ? ` · peer rank #${r.peer_rank.rank}/${r.peer_rank.n}` : "")
              : undefined
          }
        />
      );
    case "get_scores":
      return (
        <div className="output-card" key={idx}>
          <div className="output-card-kicker">
            {r.ticker ?? ""} · FY{r.year ?? ""}
          </div>
          <div className="output-card-title">Credit & quality scores</div>
          <div className="output-card-meta">
            Altman Z: {r.altman_z?.value?.toFixed ? r.altman_z.value.toFixed(2) : "N/A"} ({r.altman_z?.zone ?? "—"})
            <br />
            Piotroski F: {r.piotroski_f?.value ?? "N/A"}/9
            <br />
            Beneish M: {r.beneish_m?.value?.toFixed ? r.beneish_m.value.toFixed(2) : "N/A"} ({r.beneish_m?.flag ?? "—"})
          </div>
        </div>
      );
    case "get_metric_history":
      return (
        <Card
          key={idx}
          kicker={`${r.ticker ?? ""} · ${r.year_range ?? ""}`}
          title={`${r.metric ?? "metric"} history`}
          meta={`${r.series?.length ?? 0} data points`}
        />
      );
    case "compare_companies":
      return (
        <Card
          key={idx}
          kicker={`FY${r.year ?? ""}`}
          title={`${r.ticker_a ?? ""} vs ${r.ticker_b ?? ""}`}
          value={r.overall_winner ?? "—"}
          meta={`${r.wins_a ?? 0}–${r.wins_b ?? 0}–${r.ties ?? 0}`}
        />
      );
    case "get_peer_ranking":
      return (
        <Card
          key={idx}
          kicker={`${r.ticker ?? ""} · FY${r.year ?? ""}`}
          title={`${r.metric ?? ""} peer rank`}
          value={r.rank ? `#${r.rank} / ${r.n_peers}` : "N/A"}
          meta={r.percentile ? `${r.percentile}th percentile` : undefined}
        />
      );
    case "search_filings":
      return (
        <Card
          key={idx}
          kicker="10-K filing search"
          title={`"${r.query ?? entry.args.query ?? ""}"`}
          value={`${r.n_results ?? 0} passages`}
        />
      );
    case "get_text_sentiment":
      return (
        <Card
          key={idx}
          kicker={`${r.ticker ?? ""} · FY${r.year ?? ""}`}
          title="Filing sentiment"
          meta={r.sections?.map((s: any) => `${s.section}: ${s.negative_word_share_pct}% neg`).join(" · ")}
        />
      );
    case "run_dcf_valuation":
      return (
        <Card
          key={idx}
          kicker={`${r.ticker ?? ""} · FY${r.latest_fy ?? ""}`}
          title="DCF valuation"
          value={r.implied_share_price ? `$${r.implied_share_price.toFixed(2)}` : "N/A"}
          meta={r.enterprise_value ? `EV $${(r.enterprise_value / 1e9).toFixed(1)}B` : undefined}
        />
      );
    case "generate_equity_research":
      return (
        <Card
          key={idx}
          kicker={`${r.ticker ?? ""} · FY${r.year ?? ""}`}
          title="Equity research report"
          meta={r.markdown_report ? `${r.markdown_report.length.toLocaleString()} chars generated` : undefined}
        />
      );
    case "get_line_items":
      return (
        <Card
          key={idx}
          kicker={`${r.ticker ?? ""} · FY${r.year ?? ""}`}
          title="Raw line items"
          value={r.count ? `${r.count} fields` : undefined}
        />
      );
    case "list_companies":
      return <Card key={idx} kicker="database" title="Covered companies" value={`${r.companies?.length ?? 0}`} />;
    case "list_years":
      return (
        <Card key={idx} kicker={r.ticker ?? ""} title="Available fiscal years" value={(r.years || []).join(", ")} />
      );
    default:
      return (
        <Card
          key={idx}
          kicker="tool call"
          title={entry.name}
          meta={Object.entries(entry.args)
            .map(([k, v]) => `${k}=${v}`)
            .join(", ")}
        />
      );
  }
}

export default function OutputsPanel({ trace }: { trace: ToolTraceEntry[] | undefined }) {
  return (
    <aside className="outputs-rail">
      <div className="outputs-header">Outputs</div>
      <div className="outputs-body">
        {trace && trace.length > 0 ? (
          trace.map(renderEntry)
        ) : (
          <div className="outputs-empty">
            Tool calls behind the assistant's last answer will appear here — the exact database lookups and
            computed values it used, with no numbers invented by the model.
          </div>
        )}
      </div>
    </aside>
  );
}
