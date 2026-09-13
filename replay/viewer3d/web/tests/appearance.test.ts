import { expect, test } from "bun:test";
import { drsOpening, tyreColour } from "../src/scene/appearance";
import { kerbGeometry, surfaceTexture } from "../src/scene/surfaces";

test("tyre sidewalls use reported compounds; unknown codes stay neutral", () => {
  expect(tyreColour(1)).toBe("#e8453c");
  expect(tyreColour(2)).toBe("#f0d33a");
  expect(tyreColour(3)).toBe("#e8e8e8");
  expect(tyreColour(4)).toBe("#3fbf5f");
  expect(tyreColour(5)).toBe("#3f7fe0");
  expect(tyreColour(undefined)).toBe(tyreColour(99));
});

test("DRS flap follows flag, stays bounded and snaps on pause/seek", () => {
  let opening = 0;
  for (let i = 0; i < 60; i++) opening = drsOpening(opening, 12, 1 / 60, false);
  expect(opening).toBeGreaterThan(.99);
  expect(opening).toBeLessThanOrEqual(1);
  expect(drsOpening(opening, 0, 1 / 60, true)).toBe(0);
  expect(drsOpening(0, 12, 0, true)).toBe(1);
  expect(drsOpening(.5, 12, 0, false)).toBe(.5);
});

test("kerb pattern is distance-based and remains continuous at the lap seam", () => {
  const geometry = kerbGeometry([0, 0, 4], [0, 8, 8], [1, 1, 3], [0, 7, 7], { x: 0, y: 0 });
  const uv = geometry.getAttribute("uv");
  expect(uv.count).toBe(8);
  expect(uv.getX(2)).toBe(2); // Eight world units = two red/white repeats.
  expect(uv.getX(4)).toBe(3);
  expect(uv.getX(6)).toBeGreaterThan(uv.getX(4));
  expect(geometry.index!.count).toBe(18);
  geometry.dispose();
});

test("surface textures are deterministic and need no external assets", () => {
  const a = surfaceTexture("asphalt"), b = surfaceTexture("asphalt");
  expect(a.image.data).toEqual(b.image.data);
  expect(a.image.width).toBe(128);
  expect(a.generateMipmaps).toBe(true);
  a.dispose(); b.dispose();
});
