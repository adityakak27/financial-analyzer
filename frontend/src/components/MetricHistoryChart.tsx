import { Brush, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useZoom } from "../hooks/useZoom";
import ZoomControls from "./charts/ZoomControls";

interface Point {
  year?: number;
  period?: string;
  value: number;
  formatted: string;
}

export default function MetricHistoryChart({
  series,
  height = 220,
  color = "var(--accent)",
}: {
  series: Point[];
  height?: number;
  color?: string;
}) {
  const data = (series || []).map((p) => ({ x: p.period || `FY${p.year}`, value: p.value, formatted: p.formatted }));
  const zoom = useZoom(data.length);

  if (!series || series.length === 0) {
    return <div className="empty-state">No historical series available.</div>;
  }

  const showControls = data.length > 2;

  return (
    <div>
      {showControls && <ZoomControls zoom={zoom} />}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="x" tick={{ fontSize: 11, fill: "var(--text-secondary)" }} />
          <YAxis tick={{ fontSize: 11, fill: "var(--text-secondary)" }} width={48} />
          <Tooltip
            formatter={(_: any, __: any, item: any) => [item.payload.formatted, "value"]}
            contentStyle={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 6 }} />
          {showControls && (
            <Brush
              key={zoom.version}
              dataKey="x"
              height={20}
              stroke="var(--accent)"
              fill="var(--bg-elevated)"
              travellerWidth={8}
              tickFormatter={() => ""}
              startIndex={zoom.start}
              endIndex={zoom.end}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
