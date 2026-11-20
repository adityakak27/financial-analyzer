import { ZoomInIcon, ZoomOutIcon, ZoomResetIcon } from "../Icons";
import type { ZoomState } from "../../hooks/useZoom";

export default function ZoomControls({ zoom, label }: { zoom: ZoomState; label?: string }) {
  return (
    <div className="chart-zoom-controls">
      {label && <span className="output-chart-label" style={{ margin: 0 }}>{label}</span>}
      <div className="chart-zoom-buttons">
        <button className="chart-zoom-btn" title="Zoom out" disabled={!zoom.canZoomOut} onClick={zoom.zoomOut}>
          <ZoomOutIcon width={13} height={13} />
        </button>
        <button className="chart-zoom-btn" title="Reset zoom" disabled={!zoom.isZoomed} onClick={zoom.reset}>
          <ZoomResetIcon width={13} height={13} />
        </button>
        <button className="chart-zoom-btn" title="Zoom in" disabled={!zoom.canZoomIn} onClick={zoom.zoomIn}>
          <ZoomInIcon width={13} height={13} />
        </button>
      </div>
    </div>
  );
}
