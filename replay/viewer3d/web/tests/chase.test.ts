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

test("detailed model stays within a real car envelope and uses eight batches", () => {
  const parts = buildCarParts();
  expect(parts.length).toBe(8);
  expect(parts.filter((part) => part.animation === "drs").length).toBe(1);
  expect(parts.filter((part) => part.tyreColored).length).toBe(1);
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
