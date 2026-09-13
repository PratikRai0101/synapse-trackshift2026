import { beforeEach, expect, test } from "bun:test";
import { simulateActors } from "../src/scene/actors";
import { detectOverlaps, fitCarScales } from "../src/scene/spacing";
const origin = { x: 0, y: 0 };
beforeEach(() => { simulateActors([], origin, 0); });

test("bunched cars keep their requested scale and expose ambiguity", () => {
  const actors = simulateActors([
    { key: "A", x: 0, y: 0, scale: 1 },
    { key: "B", x: 0, y: 0, scale: 1 },
  ], origin, 0);
  expect(fitCarScales(actors, 1)).toEqual([1, 1]);
  expect([...detectOverlaps(actors)]).toEqual(["A", "B"]);
  expect(actors.map((actor) => actor.position.toArray())).toEqual([[0,0,0], [0,0,0]]);
});

test("width-aware bounds allow normal side-by-side racing", () => {
  const actors = simulateActors([
    { key: "A", x: 0, y: 0, scale: 1 },
    { key: "B", x: 2.5, y: 0, scale: 1 },
  ], origin, 0);
  expect(detectOverlaps(actors).size).toBe(0);
  expect(fitCarScales(actors, 3)).toEqual([3, 3]);
  expect(detectOverlaps(actors, 3).size).toBe(2);
});

test("overlap warnings are independent of ordering and include rotated cars", () => {
  const actors = simulateActors([
    { key: "A", x: 0, y: 0, scale: 1, heading: Math.PI/2 },
    { key: "B", x: 1, y: 1, scale: 1 },
    { key: "C", x: 20, y: 20, scale: 1 },
  ], origin, 0);
  expect([...detectOverlaps(actors)].sort()).toEqual(["A", "B"]);
  expect([...detectOverlaps([...actors].reverse())].sort()).toEqual(["A", "B"]);
});
