import { Bar, BarChart, Brush, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useZoom } from "../../hooks/useZoom";
import ZoomControls from "./ZoomControls";

export default function CompareBarChart({
  pillarStats,
  tickerA,
  tickerB,
  height = 200,
}: {
  pillarStats: Record<string, { wins_a: number; wins_b: number; ties: number }>;
  tickerA: string;
  tickerB: string;
  height?: number;
}) {
  const entries = Object.entries(pillarStats || {});
  const zoom = useZoom(entries.length);

  if (!pillarStats) return null;

  const data = entries.map(([pillar, s]) => ({
    pillar: pillar.length > 14 ? pillar.split(" ")[0] : pillar,
    [tickerA]: s.wins_a,
    [tickerB]: s.wins_b,
  }));
  const showControls = data.length > 2;

  return (
    <div>
      {showControls && <ZoomControls zoom={zoom} />}
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="pillar" tick={{ fontSize: 10, fill: "var(--text-secondary)" }} />
          <YAxis tick={{ fontSize: 11, fill: "var(--text-secondary)" }} width={24} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey={tickerA} fill="var(--accent)" radius={[3, 3, 0, 0]} />
          <Bar dataKey={tickerB} fill="#5b8def" radius={[3, 3, 0, 0]} />
          {showControls && (
            <Brush
              key={zoom.version}
              dataKey="pillar"
              height={18}
              stroke="var(--accent)"
              fill="var(--bg-elevated)"
              travellerWidth={8}
              tickFormatter={() => ""}
              startIndex={zoom.start}
              endIndex={zoom.end}
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
