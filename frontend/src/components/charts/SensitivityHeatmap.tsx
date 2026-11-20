import { useState } from "react";
import { ZoomInIcon, ZoomOutIcon, ZoomResetIcon } from "../Icons";

const MIN_SCALE = 0.75;
const MAX_SCALE = 1.75;
const DEFAULT_SCALE = 1;

interface SensitivityMatrix {
  wacc_axis: number[];
  growth_axis: number[];
  rows: { wacc: number; values: { terminal_growth: number; implied_share_price: number | null }[] }[];
}

export default function SensitivityHeatmap({ matrix }: { matrix: SensitivityMatrix }) {
  const [hover, setHover] = useState<{ row: number; col: number } | null>(null);
  const [scale, setScale] = useState(DEFAULT_SCALE);

  if (!matrix || !matrix.rows?.length) return null;

  const allValues = matrix.rows.flatMap((r) => r.values.map((v) => v.implied_share_price)).filter((v): v is number => v !== null);
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const baseRow = Math.floor(matrix.wacc_axis.length / 2);
  const baseCol = Math.floor(matrix.growth_axis.length / 2);

  function heat(v: number | null): string {
    if (v === null || max === min) return "transparent";
    const t = (v - min) / (max - min);
    // low -> negative-tinted, high -> positive-tinted, interpolated through the accent for the middle.
    const alpha = 0.08 + t * 0.3;
    return t < 0.5
      ? `rgba(224, 120, 109, ${0.08 + (0.5 - t) * 0.5})`
      : `rgba(95, 185, 138, ${alpha})`;
  }

  return (
    <div className="heatmap-zoom-wrap">
      <div className="chart-zoom-controls">
        <span className="output-chart-label" style={{ margin: 0 }}>
          Scroll or zoom to see all columns
        </span>
        <div className="chart-zoom-buttons">
          <button
            className="chart-zoom-btn"
            title="Zoom out"
            disabled={scale <= MIN_SCALE}
            onClick={() => setScale((s) => Math.max(MIN_SCALE, +(s - 0.15).toFixed(2)))}
          >
            <ZoomOutIcon width={13} height={13} />
          </button>
          <button
            className="chart-zoom-btn"
            title="Reset zoom"
            disabled={scale === DEFAULT_SCALE}
            onClick={() => setScale(DEFAULT_SCALE)}
          >
            <ZoomResetIcon width={13} height={13} />
          </button>
          <button
            className="chart-zoom-btn"
            title="Zoom in"
            disabled={scale >= MAX_SCALE}
            onClick={() => setScale((s) => Math.min(MAX_SCALE, +(s + 0.15).toFixed(2)))}
          >
            <ZoomInIcon width={13} height={13} />
          </button>
        </div>
      </div>
      <div style={{ overflowX: "auto", width: "100%", maxWidth: "100%" }}>
    <table
      className="data-table heatmap-table"
      style={{ width: "max-content", fontSize: `${11 * scale}px` }}
    >
      <thead>
        <tr>
          <th style={{ whiteSpace: "nowrap" }}>WACC \ Growth</th>
          {matrix.growth_axis.map((g, ci) => (
            <th
              className={"num" + (hover?.col === ci ? " hm-hover" : "")}
              key={ci}
              onMouseEnter={() => setHover({ row: -1, col: ci })}
              onMouseLeave={() => setHover(null)}
            >
              {g.toFixed(2)}%
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {matrix.rows.map((row, ri) => (
          <tr key={ri} className={hover?.row === ri ? "hm-hover" : undefined}>
            <td
              onMouseEnter={() => setHover({ row: ri, col: -1 })}
              onMouseLeave={() => setHover(null)}
              className={hover?.row === ri ? "hm-hover" : undefined}
            >
              {row.wacc.toFixed(2)}%
            </td>
            {row.values.map((v, ci) => (
              <td
                className={
                  "num" +
                  (hover?.col === ci || hover?.row === ri ? " hm-hover" : "") +
                  (ri === baseRow && ci === baseCol ? " hm-base" : "")
                }
                key={ci}
                style={{ background: heat(v.implied_share_price) }}
                onMouseEnter={() => setHover({ row: ri, col: ci })}
                onMouseLeave={() => setHover(null)}
              >
                {v.implied_share_price !== null ? `$${v.implied_share_price.toFixed(2)}` : "N/A"}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
      </div>
    </div>
  );
}
