import type { WorldOrigin } from "../state/store";
import type { TrackGeometry } from "../net/protocol";
import { trackPath } from "../net/trackPath";

/**
 * Replay world space (FastF1 metres, y-up on the 2D plane) mapped into the 3D
 * scene: scene X = world x, scene Z = world y, scene Y = up.
 *
 * Centring happens through `origin` so the camera can live near the origin
 * regardless of circuit.
 */
export function sceneX(worldX: number, origin: WorldOrigin): number {
  return worldX - origin.x;
}

export function sceneZ(worldY: number, origin: WorldOrigin): number {
  return worldY - origin.y;
}

export interface TrackBounds {
  radius: number;
  width: number;
  depth: number;
}

export function computeBounds(geometry: TrackGeometry): TrackBounds {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const value of geometry.x) {
    if (value < minX) minX = value;
    if (value > maxX) maxX = value;
  }
  for (const value of geometry.y) {
    if (value < minY) minY = value;
    if (value > maxY) maxY = value;
  }

  const width = maxX - minX;
  const depth = maxY - minY;
  return {
    width,
    depth,
    radius: Math.max(width, depth) / 2,
  };
}

/**
 * Heading of the track itself at a fractional position along the lap.
 *
 * The centreline is a smooth, noise-free curve, whereas a per-frame position
 * delta is dominated by floating-point noise at low speed. A chase camera wants
 * the direction of travel along the track, so this is a far more stable source
 * than the car's own yaw. Fractions are resolved by cumulative segment length,
 * not point index, because real centreline samples are not uniformly spaced.
 */
export function trackHeading(
  fraction: number,
  geometry: TrackGeometry,
): number | null {
  if (geometry.x.length < 3 || !Number.isFinite(fraction)) return null;
  // `fraction` is distance around the lap, resolved by cumulative segment
  // length rather than point index, because real centreline samples are not
  // uniformly spaced. TrackPath owns that table and the tangent lookup.
  const path = trackPath(geometry);
  if (!path) return null;
  const wrapped = ((fraction % 1) + 1) % 1;
  return path.headingAt(wrapped * path.total);
}

/**
 * Triangle strip between two polylines of equal length, laid flat on the
 * ground plane. Closed by default; pass `closed=false` for partial markings.
 *
 * `colors` optionally supplies a per-station RGB triple, used for the
 * alternating red/white kerbs.
 */
export function buildStripGeometry(
  innerX: number[],
  innerY: number[],
  outerX: number[],
  outerY: number[],
  origin: WorldOrigin,
  height = 0,
  colors?: (station: number) => [number, number, number],
  closed = true,
): {
  positions: Float32Array;
  indices: Uint32Array;
  colors?: Float32Array;
} {
  const count = Math.min(
    innerX.length,
    innerY.length,
    outerX.length,
    outerY.length,
  );

  const positions = new Float32Array(count * 2 * 3);
  const segments = count < 2 ? 0 : count - 1 + (closed ? 1 : 0);
  const indices = new Uint32Array(segments * 6);
  const vertexColors = colors ? new Float32Array(count * 2 * 3) : undefined;

  for (let i = 0; i < count; i += 1) {
    const base = i * 6;
    positions[base + 0] = sceneX(innerX[i], origin);
    positions[base + 1] = height;
    positions[base + 2] = sceneZ(innerY[i], origin);
    positions[base + 3] = sceneX(outerX[i], origin);
    positions[base + 4] = height;
    positions[base + 5] = sceneZ(outerY[i], origin);

    if (vertexColors && colors) {
      const [r, g, b] = colors(i);
      vertexColors[base + 0] = r;
      vertexColors[base + 1] = g;
      vertexColors[base + 2] = b;
      vertexColors[base + 3] = r;
      vertexColors[base + 4] = g;
      vertexColors[base + 5] = b;
    }
  }

  let cursor = 0;
  const triangle = (a: number, b: number, c: number) => {
    const ax = positions[a * 3], az = positions[a * 3 + 2];
    const normalY = (positions[b * 3 + 2] - az) * (positions[c * 3] - ax) -
      (positions[b * 3] - ax) * (positions[c * 3 + 2] - az);
    indices[cursor++] = a;
    indices[cursor++] = normalY >= 0 ? b : c;
    indices[cursor++] = normalY >= 0 ? c : b;
  };
  const quad = (a: number, b: number, c: number, d: number) => {
    triangle(a, b, c);
    triangle(c, b, d);
  };

  // Winding is chosen to face up (+Y).
  for (let i = 0; i < count - 1; i += 1) {
    const a = i * 2;
    quad(a, a + 1, a + 2, a + 3);
  }
  if (closed && count > 1) {
    quad((count - 1) * 2, (count - 1) * 2 + 1, 0, 1);
  }

  return { positions, indices, colors: vertexColors };
}
