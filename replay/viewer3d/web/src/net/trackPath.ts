import type { TrackGeometry } from "./protocol";

/**
 * A closed centreline in raw source metres, with arc-length lookup.
 *
 * Used for two things: resolving a lap fraction to a heading, and reconstructing
 * a path between sparse samples along the track instead of a straight chord
 * across a corner. Both need the same cumulative-distance array, so it lives
 * here once rather than being recomputed per caller.
 *
 * Coordinates are the same absolute metres as `frame.drivers[CODE].x/y`, before
 * the scene's origin subtraction, so no conversion is needed here.
 */
export interface TrackProjection {
  /** Distance along the centreline, metres from station 0. */
  s: number;
  /** Signed perpendicular offset, metres. Positive is left of travel. */
  lateral: number;
  /** Absolute perpendicular distance, metres. */
  offCentre: number;
}

const wrap = (value: number, total: number) =>
  ((value % total) + total) % total;

export class TrackPath {
  readonly total: number;
  readonly halfWidth: number;
  private readonly x: number[];
  private readonly y: number[];
  /** cum[i] is the arc length at station i; cum has one extra closing entry. */
  private readonly cum: Float64Array;
  /** Coarse probe spacing, so `locate` is ~200 checks rather than one per point. */
  private readonly stride: number;

  constructor(geometry: TrackGeometry, fallbackHalfWidth = 10) {
    this.x = geometry.x;
    this.y = geometry.y;
    const count = Math.min(geometry.x.length, geometry.y.length);
    this.cum = new Float64Array(count + 1);
    for (let i = 0; i < count; i += 1) {
      const next = (i + 1) % count;
      this.cum[i + 1] =
        this.cum[i] + Math.hypot(this.x[next] - this.x[i], this.y[next] - this.y[i]);
    }
    this.total = count >= 2 ? this.cum[count] : 0;
    this.stride = Math.max(1, Math.floor(count / 200));
    const declared = Number(geometry.track_width);
    this.halfWidth = Number.isFinite(declared) && declared > 0
      ? declared / 2
      : fallbackHalfWidth;
  }

  get usable(): boolean {
    return this.total > 0 && this.x.length >= 3;
  }

  /** Tangent heading (atan2(x, y), matching the replay's convention) at an arc length. */
  headingAt(s: number): number {
    const index = this.segmentAt(s);
    const next = (index + 1) % this.x.length;
    return Math.atan2(this.x[next] - this.x[index], this.y[next] - this.y[index]);
  }

  /** Scene/world position at an arc length, displaced along the local normal. */
  pointAt(s: number, lateral = 0): { x: number; y: number } {
    const index = this.segmentAt(s);
    const next = (index + 1) % this.x.length;
    const ax = this.x[index], ay = this.y[index];
    const bx = this.x[next], by = this.y[next];
    const length = Math.hypot(bx - ax, by - ay) || 1;
    const along = Math.max(0, Math.min(1, (this.arc(s) - this.cum[index]) / length));
    const px = ax + (bx - ax) * along;
    const py = ay + (by - ay) * along;
    // Rotate the tangent 90 degrees for the outward normal.
    const nx = -(by - ay) / length;
    const ny = (bx - ax) / length;
    return { x: px + nx * lateral, y: py + ny * lateral };
  }

  /**
   * Nearest point on the centreline. A projection is a good along-track
   * coordinate only while the car is near the line, so callers check
   * `offCentre` before trusting it.
   */
  locate(x: number, y: number): TrackProjection | null {
    const count = this.x.length;
    if (!this.usable) return null;

    let best = 0;
    let bestDistance = Infinity;
    for (let i = 0; i < count; i += this.stride) {
      const d = (this.x[i] - x) ** 2 + (this.y[i] - y) ** 2;
      if (d < bestDistance) {
        bestDistance = d;
        best = i;
      }
    }
    const from = Math.max(0, best - this.stride);
    const to = Math.min(count - 1, best + this.stride);
    for (let i = from; i <= to; i += 1) {
      const d = (this.x[i] - x) ** 2 + (this.y[i] - y) ** 2;
      if (d < bestDistance) {
        bestDistance = d;
        best = i;
      }
    }

    // Project onto the two segments touching the nearest station and keep the
    // closer one, so `s` and `lateral` stay continuous between stations.
    let result: TrackProjection | null = null;
    for (const index of [(best - 1 + count) % count, best]) {
      const candidate = this.projectOnSegment(x, y, index);
      if (!candidate) continue;
      if (!result || candidate.offCentre < result.offCentre) result = candidate;
    }
    return result;
  }

  private arc(s: number): number {
    return this.total > 0 ? wrap(s, this.total) : 0;
  }

  private segmentAt(s: number): number {
    const count = this.x.length;
    const target = this.arc(s);
    // Binary search the cumulative array for the containing segment.
    let low = 0;
    let high = count - 1;
    while (low < high) {
      const mid = (low + high + 1) >> 1;
      if (this.cum[mid] <= target) low = mid;
      else high = mid - 1;
    }
    return low;
  }

  private projectOnSegment(x: number, y: number, index: number): TrackProjection | null {
    const count = this.x.length;
    const next = (index + 1) % count;
    const ax = this.x[index], ay = this.y[index];
    const dx = this.x[next] - ax, dy = this.y[next] - ay;
    const lengthSq = dx * dx + dy * dy;
    if (lengthSq === 0) return null;
    const t = Math.max(0, Math.min(1, ((x - ax) * dx + (y - ay) * dy) / lengthSq));
    const px = ax + dx * t, py = ay + dy * t;
    const length = Math.sqrt(lengthSq);
    // Signed offset along the outward normal, consistent with `pointAt`.
    const lateral = ((x - px) * -dy + (y - py) * dx) / length;
    return {
      s: this.cum[index] + length * t,
      lateral,
      offCentre: Math.hypot(x - px, y - py),
    };
  }
}

const pathCache = new WeakMap<TrackGeometry, TrackPath>();

/** Cached so a session builds its arc-length table once, not per frame. */
export function trackPath(geometry: TrackGeometry | null): TrackPath | null {
  if (!geometry || !geometry.x?.length) return null;
  let path = pathCache.get(geometry);
  if (!path) {
    path = new TrackPath(geometry);
    pathCache.set(geometry, path);
  }
  return path.usable ? path : null;
}
