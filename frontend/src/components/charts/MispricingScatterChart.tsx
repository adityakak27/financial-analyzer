import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

export interface MispricingPoint {
  ticker: string;
  name?: string;
  sub_industry?: string;
  quality_score: number;
  ev_sales: number;
  valuation_gap: number | null;
  gap_z: number | null;
  verdict: string | null;
}

export interface VerdictLine {
  sub_industry: string;
  intercept: number;
  slope: number;
}

export const SECTOR_LINE_COLORS: Record<string, string> = {
  "Hardware & Equipment": "#a8a299",
  Semiconductors: "#5b8def",
  "Software & Services": "#e2a187",
};

function verdictColor(verdict: string | null): string {
  if (verdict === "Undervalued") return "#4caf6e";
  if (verdict === "Overvalued") return "#e2a187";
  return "var(--text-secondary)";
}

export default function MispricingScatterChart({
  points,
  lines,
  onSelect,
  height = 420,
}: {
  points: MispricingPoint[];
  lines: VerdictLine[];
  onSelect?: (ticker: string) => void;
  height?: number;
}) {
  const data = points
    .filter((p) => p.ev_sales > 0)
    .map((p) => ({ ...p, logEvSales: Math.log(p.ev_sales) }));

  const lineSeries = lines
    .map((l) => {
      const xs = data.filter((d) => d.sub_industry === l.sub_industry).map((d) => d.quality_score);
      if (!xs.length) return null;
      const lo = Math.min(...xs);
      const hi = Math.max(...xs);
      return {
        sub_industry: l.sub_industry,
        data: [
          { quality_score: lo, fit: l.intercept + l.slope * lo },
          { quality_score: hi, fit: l.intercept + l.slope * hi },
        ],
      };
    })
    .filter((s): s is { sub_industry: string; data: { quality_score: number; fit: number }[] } => s !== null);

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart margin={{ top: 8, right: 16, left: 8, bottom: 24 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          type="number"
          dataKey="quality_score"
          name="Quality Score"
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: "var(--text-secondary)" }}
          label={{ value: "Fundamental Quality Score (0-100)", position: "bottom", fontSize: 11, fill: "var(--text-secondary)" }}
        />
        <YAxis
          type="number"
          dataKey="logEvSales"
          name="log(EV/Sales)"
          tick={{ fontSize: 11, fill: "var(--text-secondary)" }}
          label={{ value: "log(EV / Sales)", angle: -90, position: "insideLeft", fontSize: 11, fill: "var(--text-secondary)" }}
        />
        <ZAxis range={[60, 60]} />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as MispricingPoint & { logEvSales: number };
            if (p.ticker === undefined) return null;
            return (
              <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 10px", fontSize: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 2 }}>
                  {p.ticker} {p.name ? `— ${p.name}` : ""}
                </div>
                <div>{p.sub_industry}</div>
                <div>Quality Score: {p.quality_score?.toFixed(1)}</div>
                <div>EV/Sales: {p.ev_sales?.toFixed(2)}x</div>
                <div>Gap (z-score): {p.gap_z != null ? p.gap_z.toFixed(2) : "no verdict"}</div>
                <div style={{ color: verdictColor(p.verdict) }}>{p.verdict}</div>
              </div>
            );
          }}
        />
        <Scatter
          name="Companies"
          data={data}
          onClick={(d: any) => onSelect?.(d.ticker)}
          cursor={onSelect ? "pointer" : "default"}
          shape={(props: any) => {
            const { cx, cy, payload } = props;
            return <circle cx={cx} cy={cy} r={5} fill={verdictColor(payload.verdict)} fillOpacity={0.85} stroke="var(--bg-elevated)" strokeWidth={1} />;
          }}
        />
        {lineSeries.map((s) => (
          <Line
            key={s.sub_industry}
            data={s.data}
            dataKey="fit"
            dot={false}
            stroke={SECTOR_LINE_COLORS[s.sub_industry] ?? "var(--text-secondary)"}
            strokeWidth={2}
            legendType="none"
            isAnimationActive={false}
            name={`${s.sub_industry} line`}
          />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  );
}
