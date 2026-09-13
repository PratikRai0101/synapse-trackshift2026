import type { TelemetryMessage, TrackGeometry } from "./protocol";

const scaledGeometry = new WeakMap<TrackGeometry, Map<number, TrackGeometry>>();

/** Normalize at the wire boundary, never in individual render components.
 * Unknown legacy units are left untouched and explicitly flagged in the HUD. */
export function toMetres(message: TelemetryMessage): TelemetryMessage {
  const scale = message.coordinate_units === "dm" ? .1 : 1;
  const xy = <T extends { x: number; y: number }>(point: T): T =>
    ({ ...point, x: point.x * scale, y: point.y * scale });
  let geometry = message.track_geometry;
  if (geometry && scale !== 1) {
    let cache = scaledGeometry.get(geometry);
    if (!cache) { cache = new Map(); scaledGeometry.set(geometry, cache); }
    let converted = cache.get(scale);
    if (!converted) {
      converted = { ...geometry };
      for (const key of ["x", "y", "x_inner", "y_inner", "x_outer", "y_outer"] as const) {
        converted[key] = geometry[key].map((value) => value * scale);
      }
      // The declared ribbon width is in the same units as X/Y, so it converts too.
      if (Number.isFinite(geometry.track_width)) {
        converted.track_width = geometry.track_width! * scale;
      }
      cache.set(scale, converted);
    }
    geometry = converted;
  }
  return {
    ...message, track_geometry: geometry,
    frame: message.frame ? { ...message.frame,
      drivers: Object.fromEntries(Object.entries(message.frame.drivers).map(([code, point]) => [code, xy(point)])),
      safety_car: message.frame.safety_car ? xy(message.frame.safety_car) : null,
    } : null,
    // Makes a second normalization idempotent, including metadata-free streams.
    coordinate_units: "m",
  };
}
