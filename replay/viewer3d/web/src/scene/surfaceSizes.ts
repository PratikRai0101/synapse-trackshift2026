import type { TrackGeometry } from "../net/protocol";

/**
 * Track-surface sizing, derived from the width the payload declares.
 *
 * The ribbon is a schematic constant offset, not a surveyed circuit, so its
 * absolute width cannot be treated as truth. What *can* be consistent is the
 * relationship between markings and the surface they sit on: derive the kerb,
 * edge-line and run-off offsets from the declared width so a wider or narrower
 * ribbon does not end up with kerbs that are metres wide, or edge lines that
 * disappear. Values fall back to real-circuit proportions when a payload does
 * not declare a width.
 */

/** Real F1 circuits are roughly 12-15 m wide; used only as a fallback. */
export const FALLBACK_TRACK_WIDTH_M = 14;

export interface SurfaceSizes {
  /** Width of the declared ribbon in metres (not necessarily a real circuit). */
  trackWidth: number;
  /** Whether the width came from the payload or the fallback. */
  declared: boolean;
  /** True when the payload says the ribbon is a constant normal offset. */
  schematic: boolean;
  /** Kerb band on each edge, metres. */
  kerb: number;
  /** Painted edge line just inside the kerb, metres. */
  edgeLine: number;
  /** DRS marking inset from the outer edge, metres. */
  drsMarking: number;
  /** Half-width available to run-off, metres, measured from the outer edge. */
  runOffExtent: number;
}

const clamp = (value: number, lo: number, hi: number) =>
  Math.max(lo, Math.min(hi, value));

export function surfaceSizes(geometry: TrackGeometry | null): SurfaceSizes {
  const declaredWidth =
    geometry && Number.isFinite(geometry.track_width)
      ? Number(geometry.track_width)
      : 0;
  const declared = declaredWidth > 0;
  const trackWidth = declared ? declaredWidth : FALLBACK_TRACK_WIDTH_M;

  return {
    trackWidth,
    declared,
    schematic: geometry?.track_width_kind === "schematic_constant_offset",
    // Real kerbs are ~0.8-1.0 m regardless of circuit width, so this stays a
    // narrow band but can never eat a quarter of a narrow ribbon.
    kerb: clamp(trackWidth * 0.055, 0.6, 1.1),
    edgeLine: clamp(trackWidth * 0.009, 0.09, 0.2),
    drsMarking: clamp(trackWidth * 0.09, 0.9, 1.6),
    // Half the width beyond each edge before run-off/barriers would begin.
    runOffExtent: clamp(trackWidth * 0.55, 4, 14),
  };
}
