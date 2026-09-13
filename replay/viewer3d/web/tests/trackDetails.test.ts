import { expect, test } from "bun:test";
import { insetEdge } from "../src/scene/trackDetails";

test("kerb width stays fixed on wide and normal tracks", () => {
  const result = insetEdge([0, 0], [0, 0], [100, 7], [0, 0], .9);
  expect(result.x[0]).toBeCloseTo(.9);
  expect(result.x[1]).toBeCloseTo(.9);
});

test("insets do not cross a narrow centreline or produce NaN at a collapsed edge", () => {
  const result = insetEdge([0, 0], [0, 0], [.1, 0], [0, 0], .9);
  expect(result.x).toEqual([.025, 0]);
  expect(result.y).toEqual([0, 0]);
});

test("insets respect diagonal geometry", () => {
  const result = insetEdge([1], [2], [4], [6], 1);
  expect(Math.hypot(result.x[0] - 1, result.y[0] - 2)).toBeCloseTo(1);
});
