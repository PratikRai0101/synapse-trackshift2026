import { expect, test } from "bun:test";
import * as THREE from "three";
import { ChaseCamera, CHASE_VIEWS } from "../src/scene/chase";
import { buildCarParts } from "../src/scene/carParts";

test("chase framing is invariant under acceleration, pause and translation", () => {
  const rig = new ChaseCamera();
  const anchor = new THREE.Vector3();
  rig.update(anchor, .4, 1, "chase", 1 / 60, true);
  const offset = rig.position.clone();
  const direction = rig.look.clone().sub(rig.position).normalize();
  for (const z of [1, 3, 7, 7, 7, 20, 1000]) {
    anchor.set(z * .4, 0, z);
    rig.update(anchor, .4, 1, "chase", 1 / 60);
    expect(rig.position.clone().sub(anchor).distanceTo(offset)).toBeLessThan(1e-10);
    expect(rig.look.clone().sub(rig.position).normalize().distanceTo(direction)).toBeLessThan(1e-10);
  }
});

test("camera presets keep the camera outside enlarged cars", () => {
  for (const view of Object.keys(CHASE_VIEWS) as (keyof typeof CHASE_VIEWS)[]) {
    const rig = new ChaseCamera();
    rig.update(new THREE.Vector3(), 0, 5, view, 1 / 60, true);
    expect(rig.position.y).toBeGreaterThan(10);
    expect(rig.position.distanceTo(rig.look)).toBeGreaterThan(25);
  }
});

test("heading wrap uses short rotation and reset immediately reframes", () => {
  const rig = new ChaseCamera();
  rig.update(new THREE.Vector3(), Math.PI - .01, 1, "chase", 1 / 60, true);
  rig.update(new THREE.Vector3(), -Math.PI + .01, 1, "chase", 1 / 60);
  expect(Math.abs(rig.heading - Math.PI)).toBeLessThan(.02);
  rig.update(new THREE.Vector3(500, 0, 500), 0, 1, "chase", 1 / 60, true);
  expect(rig.position.toArray()).toEqual([500, 5, 489]);
});

test("model batches keep wheels and the DRS flap independently animatable", () => {
  const parts = buildCarParts();
  const wheels = parts.filter((part) => part.wheel);
  const drs = parts.filter((part) => part.animation === "drs");
  expect(drs.length).toBe(1);
  // Four wheels, and every wheel batch is fully tagged so the renderer can spin
  // and steer it without touching the merged bodywork.
  expect(wheels.length).toBe(16);
  expect([...new Set(wheels.map((part) => part.wheel!.index))].sort()).toEqual([0, 1, 2, 3]);
  expect(wheels.filter((part) => part.wheel!.axle === "front").length).toBe(8);
  expect(parts.filter((part) => !part.wheel && !part.animation).length).toBe(4);
  // One tyre-compound batch per wheel, so compound colour follows the tyres.
  expect(parts.filter((part) => part.tyreColored).length).toBe(4);
  for (const part of parts) {
    part.geometry.dispose();
    part.material.dispose();
  }
});

test("detailed model stays within a real car envelope", () => {
  const parts = buildCarParts();
  const bounds = new THREE.Box3();
  for (const part of parts) {
    part.geometry.computeBoundingBox();
    bounds.union(part.geometry.boundingBox!.clone().applyMatrix4(part.matrix));
    expect(Array.from(part.geometry.getAttribute("position").array).every(Number.isFinite)).toBe(true);
    part.geometry.dispose();
    part.material.dispose();
  }
  const size = bounds.getSize(new THREE.Vector3());
  expect(size.x).toBeLessThan(2.3);
  expect(size.z).toBeLessThan(5.7);
  expect(size.y).toBeLessThan(1.5);
});
