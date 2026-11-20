import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface WaterfallStep {
  measure: "relative" | "total";
  label: string;
  value: number;
}

export default function WaterfallChart({ steps, height = 220 }: { steps: WaterfallStep[]; height?: number }) {
  if (!steps || steps.length === 0) return <div className="empty-state">No valuation bridge available.</div>;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={steps} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 10, fill: "var(--text-secondary)" }}
          interval={0}
          angle={-14}
          textAnchor="end"
          height={54}
        />
        <YAxis tick={{ fontSize: 11, fill: "var(--text-secondary)" }} width={40} />
        <Tooltip
          formatter={(v: any) => [`$${v}B`, "value"]}
          contentStyle={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Bar dataKey="value" radius={[4, 4, 0, 0]}>
          {steps.map((s, i) => (
            <Cell
              key={i}
              fill={s.measure === "total" ? "var(--accent)" : s.value >= 0 ? "var(--positive)" : "var(--negative)"}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
