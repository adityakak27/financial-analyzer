import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const PALETTE = ["#cc785c", "#5b8def", "#5fb98a", "#d4ab54", "#b98ccf", "#e0786d"];

interface SensitivityMatrix {
  wacc_axis: number[];
  growth_axis: number[];
  rows: { wacc: number; values: { terminal_growth: number; implied_share_price: number | null }[] }[];
}

export default function DcfSensitivityChart({ matrix, height = 220 }: { matrix: SensitivityMatrix; height?: number }) {
  const [hidden, setHidden] = useState<Set<string>>(new Set());

  if (!matrix || !matrix.rows?.length) return <div className="empty-state">No sensitivity data available.</div>;

  const growthKeys = matrix.growth_axis.map((g, i) => ({ key: `g${i}`, label: `${g.toFixed(2)}%` }));
  const data = matrix.rows.map((row) => {
    const point: Record<string, number | string | null> = { wacc: `${row.wacc.toFixed(1)}%` };
    row.values.forEach((v, i) => {
      point[`g${i}`] = v.implied_share_price;
    });
    return point;
  });

  function toggle(key: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="wacc" tick={{ fontSize: 11, fill: "var(--text-secondary)" }} label={{ value: "WACC", position: "insideBottom", offset: -2, fontSize: 10, fill: "var(--text-tertiary)" }} />
        <YAxis tick={{ fontSize: 11, fill: "var(--text-secondary)" }} width={44} />
        <Tooltip
          formatter={(v: any) => (v === null ? ["N/A", ""] : [`$${Number(v).toFixed(2)}`, ""])}
          contentStyle={{
            background: "var(--bg-elevated)",
            border: "1px solid var(--border)",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Legend
          onClick={(e: any) => toggle(e.dataKey as string)}
          wrapperStyle={{ fontSize: 11, cursor: "pointer", paddingTop: 6 }}
        />
        {growthKeys.map((gk, i) => (
          <Line
            key={gk.key}
            dataKey={gk.key}
            name={`g ${gk.label}`}
            stroke={PALETTE[i % PALETTE.length]}
            strokeWidth={2}
            dot={{ r: 2.5 }}
            activeDot={{ r: 5 }}
            hide={hidden.has(gk.key)}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
