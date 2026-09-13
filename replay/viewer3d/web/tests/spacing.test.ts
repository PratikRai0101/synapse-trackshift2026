import { beforeEach, expect, test } from "bun:test";
import { simulateActors } from "../src/scene/actors";
import { fitCarScales } from "../src/scene/spacing";
const origin = { x: 0, y: 0 };
beforeEach(() => { simulateActors([], origin, 0); });

test("enlarged cars fit a close train without moving telemetry coordinates", () => {
  const actors = simulateActors(Array.from({ length: 20 }, (_, i) => ({
    key: String(i), x: 0, y: i * 7, scale: 1, heading: 0,
  })), origin, 0);
  const scales = fitCarScales(actors, 5);
  for (let i = 1; i < actors.length; i++) {
    expect(3 * (scales[i - 1] + scales[i])).toBeLessThan(7);
    expect(actors[i].position.z).toBe(i * 7);
  }
});

test("parallel side-by-side cars use width, not a car-length collision radius", () => {
  const actors = simulateActors([
    { key: "A", x: 0, y: 0, scale: 1, heading: 0 },
    { key: "B", x: 2.5, y: 0, scale: 1, heading: 0 },
  ], origin, 0);
  expect(fitCarScales(actors, 1)).toEqual([1, 1]);
});

test("identical telemetry coordinates cannot produce intersecting models", () => {
  const actors = simulateActors([
    { key: "A", x: 0, y: 0, scale: 1 },
    { key: "B", x: 0, y: 0, scale: 1 },
  ], origin, 0);
  expect(fitCarScales(actors, 1)).toEqual([0, 0]);
});

test("rotated packs remain separated regardless of input order", () => {
  const actors = simulateActors(Array.from({ length: 20 }, (_, i) => ({
    key: String(i), x: (i % 5) * 2, y: Math.floor(i / 5) * 4,
    scale: i === 0 ? 1.18 : 1, heading: i * .19,
  })), origin, 0);
  const scales = fitCarScales(actors, 3);
  expect(fitCarScales([...actors].reverse(), 3).reverse()).toEqual(scales);
  for (let i = 0; i < actors.length; i++) {
    for (let j = i + 1; j < actors.length; j++) {
      const axes = [actors[i], actors[j]].flatMap((a) => [
        [Math.sin(a.heading), Math.cos(a.heading)],
        [Math.cos(a.heading), -Math.sin(a.heading)],
      ]);
      const separated = axes.some(([x, z]) => {
        const extent = (k: number) => scales[k] * (
          3 * Math.abs(x * Math.sin(actors[k].heading) + z * Math.cos(actors[k].heading)) +
          1.15 * Math.abs(x * Math.cos(actors[k].heading) - z * Math.sin(actors[k].heading))
        );
        const distance = Math.abs(x * (actors[i].position.x - actors[j].position.x) + z * (actors[i].position.z - actors[j].position.z));
        return distance >= extent(i) + extent(j);
      });
      expect(separated).toBe(true);
    }
  }
});
