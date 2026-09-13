import { beforeEach, expect, test } from "bun:test";
import { simulateActors } from "../src/scene/actors";

const origin = { x: 0, y: 0 };
beforeEach(() => { simulateActors([], origin, 0); });

test("a car stops at its sample instead of sliding asymptotically", () => {
  simulateActors([{ key: "A", x: 0, y: 0, scale: 1 }], origin, 1 / 60);
  let actor;
  for (let i = 0; i < 6; i++) {
    [actor] = simulateActors([{ key: "A", x: 3, y: 0, scale: 1 }], origin, 1 / 60);
  }
  expect(actor!.position.x).toBeCloseTo(3, 6);
});

test("car faces its actual path, not an unrelated centreline tangent", () => {
  simulateActors([{ key: "A", x: 0, y: 0, heading: 0, scale: 1 }], origin, 1 / 60);
  let actor;
  for (let i = 1; i <= 60; i++) {
    [actor] = simulateActors([{ key: "A", x: i, y: 0, heading: 0, scale: 1 }], origin, 1 / 60);
  }
  expect(actor!.heading).toBeCloseTo(Math.PI / 2, 2);
});

test("paused replay stays exactly at its recorded position", () => {
  simulateActors([{ key: "A", x: 0, y: 0, scale: 1 }], origin, 1 / 60);
  for (let i = 0; i < 20; i++) {
    const [actor] = simulateActors([{ key: "A", x: 2, y: 3, scale: 1 }], origin, 1 / 60, { paused: true });
    expect(actor.position.toArray()).toEqual([2, 0, 3]);
  }
});

test("rewind resets orientation and position instead of driving backwards", () => {
  simulateActors([{ key: "A", x: 10, y: 10, heading: 1, scale: 1 }], origin, 1 / 60);
  const [actor] = simulateActors([{ key: "A", x: 8, y: 8, heading: .5, scale: 1 }], origin, 1 / 60, { reset: true });
  expect(actor.position.toArray()).toEqual([8, 0, 8]);
  expect(actor.heading).toBe(.5);
  expect(actor.discontinuity).toBe(true);
});

test("heading convergence is independent of render frame rate", () => {
  const run = (fps: number) => {
    simulateActors([], origin, 0);
    simulateActors([{ key: "A", x: 0, y: 0, heading: 0, scale: 1 }], origin, 0);
    let heading = 0;
    for (let i = 0; i < fps; i++) {
      const [actor] = simulateActors([{ key: "A", x: 2, y: 0, scale: 1 }], origin, 1 / fps);
      heading = actor.heading;
    }
    return heading;
  };
  expect(run(30)).toBeCloseTo(run(144), 10);
});
