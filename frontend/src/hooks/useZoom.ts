import { useEffect, useState } from "react";

export interface ZoomState {
  start: number;
  end: number;
  /** Changes identity only when start/end change via the zoom buttons/reset -
   *  pass as a Brush `key` so it remounts with a fresh initial range instead
   *  of being driven as a controlled component (see note below). */
  version: string;
  zoomIn: () => void;
  zoomOut: () => void;
  reset: () => void;
  isZoomed: boolean;
  canZoomIn: boolean;
  canZoomOut: boolean;
}

/**
 * Index-range zoom for any Recharts chart (Line/Bar) keyed by category index.
 *
 * Deliberately does NOT wire Recharts' <Brush onChange> back into this state.
 * Brush fires onChange itself once its ResizeObserver reports the container's
 * real measured width, which can report a narrower "corrected" range than
 * what was passed in - accepting that creates a feedback loop that can lock
 * the chart into a stuck, over-zoomed state before a user ever touches it
 * (confirmed via headless-browser testing). Instead, the zoom buttons set
 * `start`/`end` and the chart passes them as Brush's *initial* range via a
 * `key` that changes alongside them, forcing a clean remount with that range;
 * dragging the brush handles is left to Recharts' own uncontrolled behavior
 * in between button clicks.
 */
export function useZoom(length: number): ZoomState {
  const maxEnd = Math.max(length - 1, 0);
  const [range, setRangeState] = useState<[number, number]>([0, maxEnd]);

  // Reset to full range whenever the underlying data set changes size
  // (e.g. a new tool call replaces the series with a different length).
  useEffect(() => {
    setRangeState([0, Math.max(length - 1, 0)]);
  }, [length]);

  const [start, end] = range;

  function zoomIn() {
    setRangeState(([s, e]) => {
      const span = e - s;
      if (span <= 1) return [s, e];
      const step = Math.max(1, Math.round(span * 0.2));
      const ns = Math.min(s + step, e - 1);
      const ne = Math.max(e - step, ns + 1);
      return [ns, ne];
    });
  }

  function zoomOut() {
    setRangeState(([s, e]) => {
      const span = e - s;
      const step = Math.max(1, Math.round(span * 0.25) || 1);
      const ns = Math.max(0, s - step);
      const ne = Math.min(maxEnd, e + step);
      return [ns, ne];
    });
  }

  function reset() {
    setRangeState([0, maxEnd]);
  }

  return {
    start,
    end,
    version: `${start}-${end}`,
    zoomIn,
    zoomOut,
    reset,
    isZoomed: start > 0 || end < maxEnd,
    canZoomIn: end - start > 1,
    canZoomOut: start > 0 || end < maxEnd,
  };
}
