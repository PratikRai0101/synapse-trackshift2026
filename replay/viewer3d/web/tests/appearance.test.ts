import { expect, test } from "bun:test";
import { drsOpening, steerAngle, tyreColour, wheelSpin } from "../src/scene/appearance";
import { kerbGeometry, surfaceTexture } from "../src/scene/surfaces";
import { CAR_DIMENSIONS, buildCarParts } from "../src/scene/carParts";
import { FALLBACK_TRACK_WIDTH_M, surfaceSizes } from "../src/scene/surfaceSizes";
import * as THREE from "three";

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

test("rendered car fits the engine's declared contact envelope", () => {
  // replay_ai's CarPose defaults (5.5 m x 2.0 m) decide contact. A wider mesh
  // would let the viewer draw cars touching where the simulator sees clearance.
  const bounds = new THREE.Box3();
  for (const part of buildCarParts()) {
    part.geometry.computeBoundingBox();
    bounds.union(part.geometry.boundingBox!.clone().applyMatrix4(part.matrix));
    part.geometry.dispose();
    part.material.dispose();
  }
  const size = bounds.getSize(new THREE.Vector3());
  expect(size.x).toBeLessThanOrEqual(CAR_DIMENSIONS.width + 1e-6);
  expect(size.z).toBeLessThanOrEqual(CAR_DIMENSIONS.length + 1e-6);
  // And not accidentally tiny: the tyres must still set the width.
  expect(size.x).toBeGreaterThan(CAR_DIMENSIONS.width - 0.05);
  expect(size.z).toBeGreaterThan(CAR_DIMENSIONS.length - 0.2);
});

test("marker sizes follow the declared track width, not a hard-coded metre", () => {
  const declared = surfaceSizes({
    track_width: 20, track_width_kind: "schematic_constant_offset",
  } as never);
  expect(declared.declared).toBe(true);
  expect(declared.schematic).toBe(true);
  expect(declared.trackWidth).toBe(20);

  const missing = surfaceSizes({} as never);
  expect(missing.declared).toBe(false);
  expect(missing.trackWidth).toBe(FALLBACK_TRACK_WIDTH_M);
  expect(missing.schematic).toBe(false);
  expect(surfaceSizes(null).trackWidth).toBe(FALLBACK_TRACK_WIDTH_M);

  // Kerbs stay kerb-sized on an absurd ribbon instead of becoming metres wide.
  for (const width of [0.1, 8, 14, 20, 400]) {
    const sizes = surfaceSizes({ track_width: width } as never);
    expect(sizes.kerb).toBeGreaterThanOrEqual(0.6);
    expect(sizes.kerb).toBeLessThanOrEqual(1.1);
    expect(sizes.edgeLine).toBeLessThan(sizes.kerb);
    expect(sizes.trackWidth).toBe(width);
  }
});

test("wheel spin converts observed speed into rotation, never the reverse", () => {
  const radius = 0.35;
  // One second at 126 km/h (35 m/s) is 100 radians on a 0.35 m wheel.
  let spin = 0;
  for (let i = 0; i < 10; i++) spin = wheelSpin(126, radius, 0.1, spin);
  expect(spin).toBeCloseTo(100, 6);
  // Paused or seeked: the accumulator must not advance on its own.
  expect(wheelSpin(300, radius, 0.1, spin, true)).toBe(spin);
  expect(wheelSpin(0, radius, 0.1, spin)).toBeCloseTo(spin, 9);
  // A degenerate radius cannot produce NaN or Infinity.
  expect(Number.isFinite(wheelSpin(300, 0, 0.1, 0))).toBe(true);
});

test("steering comes from observed yaw rate and stays bounded", () => {
  const wheelbase = 3.27;
  // A left-hand turn at 200 km/h over a 0.1 s frame.
  const yaw = 0.02;
  let steer = 0;
  for (let i = 0; i < 40; i++) {
    steer = steerAngle(0, yaw * (i + 1), 200, wheelbase, 0.1, steer);
  }
  expect(steer).toBeGreaterThan(0);
  expect(steer).toBeLessThanOrEqual(0.55);
  // Straight line decays back toward zero.
  let settling = steer;
  for (let i = 0; i < 40; i++) settling = steerAngle(1, 1, 200, wheelbase, 0.1, settling);
  expect(Math.abs(settling)).toBeLessThan(0.02);
  // Absurd yaw rates cannot exceed the clamp, and zero dt is a no-op.
  expect(steerAngle(0, 5, 10, wheelbase, 0.1, 0)).toBeLessThanOrEqual(0.55);
  expect(steerAngle(0, 1, 200, wheelbase, 0, 0.3)).toBe(0.3);
});
