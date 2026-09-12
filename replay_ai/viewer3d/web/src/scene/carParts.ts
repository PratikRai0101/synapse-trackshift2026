import * as THREE from "three";

/**
 * A generic open-wheel car built from primitives.
 *
 * This is the fallback so the viewer runs with no external asset. Drop a GLTF
 * at `public/models/car.glb` and `useCarDefinition` will prefer it (see
 * `CarModel.ts`). Real team geometry/liveries are trademarked; the body is
 * tinted per team at runtime from `driver_colors` in the telemetry payload,
 * which is the same compromise the whole viewer is built around.
 *
 * Local axes: +Z is forward, +Y is up, origin sits on the ground between the
 * wheels so a car can be placed directly at a track coordinate.
 */

export interface CarPart {
  geometry: THREE.BufferGeometry;
  material: THREE.Material;
  /** Local offset from the car origin. */
  matrix: THREE.Matrix4;
  /** When true the part picks up the per-instance team colour. */
  colored?: boolean;
}

function compose(
  position: [number, number, number],
  rotation: [number, number, number] = [0, 0, 0],
): THREE.Matrix4 {
  return new THREE.Matrix4().compose(
    new THREE.Vector3(...position),
    new THREE.Quaternion().setFromEuler(new THREE.Euler(...rotation)),
    new THREE.Vector3(1, 1, 1),
  );
}

function buildMaterials() {
  return {
    body: new THREE.MeshStandardMaterial({
      color: 0xffffff,
      metalness: 0.28,
      roughness: 0.34,
      envMapIntensity: 1.5,
    }),
    carbon: new THREE.MeshStandardMaterial({
      color: 0x1b1f26,
      metalness: 0.45,
      roughness: 0.5,
      envMapIntensity: 1.2,
    }),
    tyre: new THREE.MeshStandardMaterial({
      color: 0x17181b,
      metalness: 0.0,
      roughness: 0.92,
    }),
    detail: new THREE.MeshStandardMaterial({
      color: 0x3d444f,
      metalness: 0.7,
      roughness: 0.3,
      envMapIntensity: 1.4,
    }),
  };
}

export function buildCarParts(): CarPart[] {
  const materials = buildMaterials();
  const parts: CarPart[] = [];

  const add = (
    geometry: THREE.BufferGeometry,
    material: THREE.Material,
    position: [number, number, number],
    rotation: [number, number, number] = [0, 0, 0],
    colored = false,
  ) => {
    parts.push({ geometry, material, matrix: compose(position, rotation), colored });
  };

  const body = materials.body;
  const carbon = materials.carbon;
  const detail = materials.detail;
  const tyre = materials.tyre;

  // Monocoque
  add(new THREE.BoxGeometry(0.78, 0.42, 3.4), body, [0, 0.52, 0.1], [0, 0, 0], true);
  // Nose cone
  add(new THREE.BoxGeometry(0.42, 0.26, 1.5), body, [0, 0.46, 2.05], [0, 0, 0], true);
  // Engine cover + airbox
  add(new THREE.BoxGeometry(0.5, 0.44, 1.5), body, [0, 0.74, -0.85], [0, 0, 0], true);
  add(new THREE.BoxGeometry(0.34, 0.34, 0.5), body, [0, 1.02, -0.15], [0, 0, 0], true);
  // Sidepods
  add(new THREE.BoxGeometry(0.52, 0.4, 1.7), body, [0.72, 0.5, -0.35], [0, 0, 0], true);
  add(new THREE.BoxGeometry(0.52, 0.4, 1.7), body, [-0.72, 0.5, -0.35], [0, 0, 0], true);
  // Floor
  add(new THREE.BoxGeometry(1.6, 0.07, 2.2), carbon, [0, 0.2, -0.9]);

  // Front wing + endplates
  add(new THREE.BoxGeometry(1.85, 0.06, 0.55), body, [0, 0.26, 2.78], [0, 0, 0], true);
  add(new THREE.BoxGeometry(0.06, 0.3, 0.6), body, [0.9, 0.38, 2.78], [0, 0, 0], true);
  add(new THREE.BoxGeometry(0.06, 0.3, 0.6), body, [-0.9, 0.38, 2.78], [0, 0, 0], true);

  // Rear wing + endplates + support
  add(new THREE.BoxGeometry(1.02, 0.07, 0.44), body, [0, 0.98, -2.42], [0, 0, 0], true);
  add(new THREE.BoxGeometry(0.06, 0.52, 0.52), body, [0.51, 0.78, -2.42], [0, 0, 0], true);
  add(new THREE.BoxGeometry(0.06, 0.52, 0.52), body, [-0.51, 0.78, -2.42], [0, 0, 0], true);
  add(new THREE.BoxGeometry(0.14, 0.5, 0.14), carbon, [0, 0.72, -2.42]);
  // Beam wing
  add(new THREE.BoxGeometry(0.9, 0.05, 0.24), carbon, [0, 0.42, -2.62]);

  // Cockpit opening + halo
  add(new THREE.BoxGeometry(0.48, 0.16, 0.8), carbon, [0, 0.72, 0.42]);
  const halo = new THREE.TorusGeometry(0.36, 0.05, 6, 18, Math.PI);
  halo.rotateX(-Math.PI / 2);
  add(halo, detail, [0, 0.84, 0.45]);
  add(new THREE.BoxGeometry(0.08, 0.22, 0.08), detail, [0, 0.78, 0.92], [0.5, 0, 0]);

  // Wheels — cylinder axis rotated onto X.
  const wheelGeometry = new THREE.CylinderGeometry(0.34, 0.34, 0.34, 24);
  wheelGeometry.rotateZ(Math.PI / 2);
  const wheelPositions: [number, number, number][] = [
    [0.92, 0.34, 1.62],
    [-0.92, 0.34, 1.62],
    [0.96, 0.36, -1.85],
    [-0.96, 0.36, -1.85],
  ];
  for (const position of wheelPositions) {
    add(wheelGeometry, tyre, position);
  }

  return parts;
}

/** Amber safety car: same silhouette, distinct scale handled by the caller. */
export const SAFETY_CAR_COLOR = new THREE.Color("#ffb020");
