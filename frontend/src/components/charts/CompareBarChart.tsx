import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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
  if (!pillarStats) return null;
  const data = Object.entries(pillarStats).map(([pillar, s]) => ({
    pillar: pillar.length > 14 ? pillar.split(" ")[0] : pillar,
    [tickerA]: s.wins_a,
    [tickerB]: s.wins_b,
  }));

  return (
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
      </BarChart>
    </ResponsiveContainer>
  );
}
