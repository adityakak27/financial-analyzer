interface Props {
  label: string;
  value: string;
  deltaLabel?: string;
  deltaDirection?: "up" | "down" | "flat";
}

export default function MetricTile({ label, value, deltaLabel, deltaDirection }: Props) {
  return (
    <div className="metric-tile">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {deltaLabel ? (
        <div className={"metric-delta" + (deltaDirection ? ` ${deltaDirection}` : "")}>{deltaLabel}</div>
      ) : null}
    </div>
  );
}
