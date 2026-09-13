import { expect, test } from "bun:test";
import { buildStripGeometry } from "../src/scene/world";

test("partial track markings do not close across the circuit", () => {
  const data = buildStripGeometry([0, 0, 1], [0, 1, 2], [1, 1, 2], [0, 1, 2], { x: 0, y: 0 }, .03, undefined, false);
  expect(data.indices.length).toBe(12);
});

test("surface triangles face upward regardless of edge order", () => {
  for (const reverse of [false, true]) {
    const a = reverse ? [1, 1] : [0, 0];
    const b = reverse ? [0, 0] : [1, 1];
    const data = buildStripGeometry(a, [0, 2], b, [0, 2], { x: 0, y: 0 }, 0, undefined, false);
    const [i, j, k] = Array.from(data.indices).map((index) => index * 3);
    const p = data.positions;
    const normalY = (p[j + 2] - p[i + 2]) * (p[k] - p[i]) - (p[j] - p[i]) * (p[k + 2] - p[i + 2]);
    expect(normalY).toBeGreaterThan(0);
  }
});

test("empty and one-station strips contain no invalid faces", () => {
  for (const values of [[], [0]]) {
    const data = buildStripGeometry(values, values, values, values, { x: 0, y: 0 });
    expect(data.indices.length).toBe(0);
  }
});
