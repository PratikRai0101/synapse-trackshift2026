/** Inset an edge toward the centreline by a fixed world-space distance.
 * Never consume more than a quarter of the available half-track width. */
export function insetEdge(
  edgeX: number[], edgeY: number[], centreX: number[], centreY: number[], width: number,
): { x: number[]; y: number[] } {
  const x: number[] = [], y: number[] = [];
  const count = Math.min(edgeX.length, edgeY.length, centreX.length, centreY.length);
  for (let i = 0; i < count; i++) {
    const dx = centreX[i] - edgeX[i], dy = centreY[i] - edgeY[i];
    const distance = Math.hypot(dx, dy);
    const blend = distance > 0 ? Math.min(.25, Math.max(0, width) / distance) : 0;
    x.push(edgeX[i] + dx * blend);
    y.push(edgeY[i] + dy * blend);
  }
  return { x, y };
}
