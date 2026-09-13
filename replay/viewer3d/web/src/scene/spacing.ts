import type { Actor } from "./actors";

/** Explicit user magnification only. Never hide overlap by shrinking a car. */
export function fitCarScales(actors: readonly Actor[], requestedScale: number): number[] {
  return actors.map((actor) => requestedScale * actor.scale);
}

/** Report oriented model intersections as uncertainty/contact, not a collision
 * response. The simulator owns physical motion; recorded observations remain intact. */
export function detectOverlaps(actors: readonly Actor[], requestedScale = 1): Set<string> {
  // Conservative oriented bounds enclose the complete car, including wings.
  const halfWidth = 1.15, halfLength = 3;
  const overlaps = new Set<string>();
  const axes = actors.map((actor) => {
    const sin = Math.sin(actor.heading), cos = Math.cos(actor.heading);
    return [[sin, cos], [cos, -sin]];
  });
  const extent = (index: number, axis: number[]) => {
    const [forward, right] = axes[index];
    return (halfLength * Math.abs(forward[0] * axis[0] + forward[1] * axis[1]) +
      halfWidth * Math.abs(right[0] * axis[0] + right[1] * axis[1])) * requestedScale * actors[index].scale;
  };
  for (let i = 0; i < actors.length; i++) {
    for (let j = i + 1; j < actors.length; j++) {
      const dx = actors[j].position.x - actors[i].position.x;
      const dz = actors[j].position.z - actors[i].position.z;
      // Separating axis theorem: the first separating axis determines the
      // maximum common scale that fits this pair without touching.
      let ratio = 0;
      for (const axis of [...axes[i], ...axes[j]]) {
        const sum = extent(i, axis) + extent(j, axis);
        if (sum > 0) ratio = Math.max(ratio, Math.abs(dx * axis[0] + dz * axis[1]) / sum);
      }
      if (ratio < 1) {
        overlaps.add(actors[i].key);
        overlaps.add(actors[j].key);
      }
    }
  }
  return overlaps;
}
