import type { DriverState, Frame, TelemetryMessage, TrackGeometry } from "./protocol";
import { trackPath } from "./trackPath";

interface Sample { frame: Frame; index: number }

/** Below this straight-line separation between two samples, interpolation cannot
 * visibly cut a corner, so no projection work is done at all. At 30 Hz this is
 * never reached even at 350 km/h. */
const ROUTE_MIN_CHORD_M = 6;
/** The arc must be at least this much longer than the chord before the samples
 * are treated as straddling a corner. */
const ROUTE_MIN_ARC_RATIO = 1.02;

/**
 * Reconstruct a path between two sparse samples by following the centreline.
 *
 * The racing line between two observations is unknown, so this does not invent
 * one: it follows the track between the two known arc positions and carries the
 * observed lateral offset across, keeping the car on the side of the track it
 * was recorded on. Returns null whenever the projection cannot be trusted, in
 * which case the caller keeps the straight chord.
 */
function arcRoute(
  path: ReturnType<typeof trackPath>,
  from: DriverState,
  to: DriverState,
  blend: number,
): { x: number; y: number; heading: number; lateral: number } | null {
  if (!path) return null;
  const a = path.locate(from.x, from.y);
  const b = path.locate(to.x, to.y);
  if (!a || !b) return null;
  // A car in the pit lane or off the track has no reliable along-track
  // coordinate, so leave those segments on the straight chord.
  if (a.offCentre > path.halfWidth || b.offCentre > path.halfWidth) return null;

  let delta = b.s - a.s;
  // Around the start/finish wrap: take the shorter way round, which is the
  // way the car actually travelled for any realistic sample interval.
  if (Math.abs(delta) > path.total / 2) delta -= Math.sign(delta) * path.total;

  const chord = Math.hypot(to.x - from.x, to.y - from.y);
  if (Math.abs(delta) < chord * ROUTE_MIN_ARC_RATIO) return null;

  const s = a.s + delta * blend;
  const lateral = a.lateral + (b.lateral - a.lateral) * blend;
  const point = path.pointAt(s, lateral);
  return { x: point.x, y: point.y, heading: path.headingAt(s), lateral };
}

/** Monotone cubic interpolation through neighbouring recorded positions. The
 * harmonic slope limiter prevents overshoot without projecting pit cars onto
 * the racing line. Geometry remains uncertain between sparse observations. */
function cubic(a: number, b: number, c: number, d: number, ta: number, tb: number, tc: number, td: number, t: number) {
  const span = tc - tb, u = (t - tb) / span;
  const mid = (c - b) / span;
  const slope = (left: number, right: number, h0: number, h1: number) => {
    if (left * right <= 0) return 0;
    const w0 = 2 * h1 + h0, w1 = h1 + 2 * h0;
    return (w0 + w1) / (w0 / left + w1 / right);
  };
  const m0 = ta < tb ? slope((b - a) / (tb - ta), mid, tb - ta, span) : mid;
  const m1 = td > tc ? slope(mid, (d - c) / (td - tc), span, td - tc) : mid;
  const value = (2*u*u*u-3*u*u+1)*b + (u*u*u-2*u*u+u)*span*m0 +
    (-2*u*u*u+3*u*u)*c + (u*u*u-u*u)*span*m1;
  const velocity = ((6*u*u-6*u)*b + (3*u*u-4*u+1)*span*m0 +
    (-6*u*u+6*u)*c + (3*u*u-2*u)*span*m1) / span;
  return { value, velocity };
}

export class PlaybackBuffer {
  private samples: Sample[] = [];
  private epochT = 0;
  private epochWall = 0;
  private rate = 1;
  private paused = false;
  private source = "";
  private renderedTime = -Infinity;
  private path: ReturnType<typeof trackPath> = null;

  /** Registered by the store when track geometry arrives. */
  setTrack(geometry: TrackGeometry | null): void {
    this.path = trackPath(geometry);
  }
  /** Increments only on discontinuities, so actors/cameras reset together. */
  revision = 0;

  push(message: TelemetryMessage, now = performance.now() / 1000): void {
    const frame = message.frame;
    const source = `${message.source_id ?? "legacy"}:${message.run_mode ?? "recorded"}`;
    if (!frame || !Number.isFinite(frame.t)) {
      this.samples = []; this.revision++; return;
    }
    const last = this.samples.at(-1);
    const rate = Math.max(.01, Number.isFinite(message.playback_speed) ? message.playback_speed : 1);
    const discontinuity = !last || source !== this.source || frame.t < last.frame.t ||
      message.frame_index < last.index || frame.t - last.frame.t > Math.max(.5, rate * .5);
    if (discontinuity) { this.samples = []; this.renderedTime = -Infinity; this.revision++; }
    if (discontinuity || rate !== this.rate || message.is_paused !== this.paused) {
      this.epochT = frame.t; this.epochWall = now;
    } else if (last && frame.t !== last.frame.t) {
      const error = frame.t - (this.epochT + (now - this.epochWall) * rate);
      this.epochT += Math.max(-.005 * rate, Math.min(.005 * rate, error * .02));
    }
    this.source = source; this.rate = rate; this.paused = message.is_paused;
    if (last && !discontinuity && frame.t === last.frame.t) return;
    this.samples.push({ frame, index: message.frame_index });
    if (this.samples.length > 90) this.samples.shift();
  }

  sample(now = performance.now() / 1000): Frame | null {
    if (!this.samples.length) return null;
    const latest = this.samples.at(-1)!.frame;
    if (this.paused) return latest;
    // One shared display clock, 100 ms behind the source. Never extrapolate
    // through a network stall and never restart easing on individual packets.
    const desired = this.epochT + (now - this.epochWall - .1) * this.rate;
    const time = Math.min(latest.t, Math.max(this.renderedTime, this.samples[0].frame.t, desired));
    this.renderedTime = time;
    let i = this.samples.findIndex((sample) => sample.frame.t > time);
    if (i < 0) return latest;
    if (i === 0) return this.samples[0].frame;
    const left = this.samples[i - 1].frame, right = this.samples[i].frame;
    const previous = this.samples[Math.max(0, i - 2)].frame;
    const next = this.samples[Math.min(this.samples.length - 1, i + 1)].frame;
    const u = (time - left.t) / (right.t - left.t);
    const drivers: Record<string, DriverState> = {};
    for (const [code, b] of Object.entries(left.drivers)) {
      const c = right.drivers[code];
      if (!c) { drivers[code] = b; continue; }
      const interval = right.t - left.t;
      const chord = Math.hypot(c.x - b.x, c.y - b.y);
      // Plausibility first: an interval longer than half a second, or one that
      // implies travel the reported speed cannot produce, is not interpolated at
      // all. Holding and flagging is the honest response; the gap is also where
      // the buffer treats the stream as discontinuous. Both checks therefore
      // bound what any reconstruction below is allowed to bridge.
      const maxTravel = Math.max(0, b.speed, c.speed) / 3.6 * interval * 2 + 10;
      if (interval > .5 || chord > maxTravel) {
        drivers[code] = { ...b, motion_quality: "gap" };
        continue;
      }
      // Sparse but plausible: follow the track rather than cutting the corner.
      if (chord > ROUTE_MIN_CHORD_M) {
        const routed = arcRoute(this.path, b, c, u);
        if (routed) {
          drivers[code] = { ...b, x: routed.x, y: routed.y,
            heading: routed.heading,
            speed: b.speed + (c.speed - b.speed) * u,
            fraction: b.fraction + (c.fraction - b.fraction) * u,
            motion_quality: "reconstructed" };
          continue;
        }
      }
      const earlier = previous.drivers[code] ?? b;
      const later = next.drivers[code] ?? c;
      const x = cubic(earlier.x, b.x, c.x, later.x, previous.t, left.t, right.t, next.t, time);
      const y = cubic(earlier.y, b.y, c.y, later.y, previous.t, left.t, right.t, next.t, time);
      let heading = b.heading;
      if (Number.isFinite(b.heading) && Number.isFinite(c.heading)) {
        const angle = c.heading! - b.heading!;
        heading = b.heading! + Math.atan2(Math.sin(angle), Math.cos(angle)) * u;
      } else if (Math.hypot(x.velocity, y.velocity) > .05) heading = Math.atan2(x.velocity, y.velocity);
      drivers[code] = { ...b, x: x.value, y: y.value, heading,
        speed: b.speed + (c.speed - b.speed) * u,
        fraction: b.fraction + (c.fraction - b.fraction) * u, motion_quality: "sampled" };
    }
    const a = left.safety_car, b = right.safety_car;
    const safety_car = a && b ? { ...a, x: a.x + (b.x-a.x)*u, y: a.y + (b.y-a.y)*u } : a;
    return { ...left, t: time, drivers, safety_car };
  }
}

export const playback = new PlaybackBuffer();
