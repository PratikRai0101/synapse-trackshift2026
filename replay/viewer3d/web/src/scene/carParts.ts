import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

/** Procedural generic open-wheel car: +Z forward, +Y up. No licensed assets. */
export interface CarPart {
  geometry: THREE.BufferGeometry;
  material: THREE.Material;
  matrix: THREE.Matrix4;
  colored?: boolean;
}

/** Elliptical body sections [z, half-width, centre-height, half-height]. */
function bodywork(sections: number[][]): THREE.BufferGeometry {
  const vertices: number[] = [];
  const indices: number[] = [];
  const sides = 16;
  for (const [z, width, y, height] of sections) {
    for (let i = 0; i < sides; i++) {
      const angle = i / sides * Math.PI * 2;
      vertices.push(Math.cos(angle) * width, y + Math.sin(angle) * height, z);
    }
  }
  for (let s = 0; s < sections.length - 1; s++) {
    for (let i = 0; i < sides; i++) {
      const a = s * sides + i;
      const b = s * sides + (i + 1) % sides;
      indices.push(a, b, a + sides, b, b + sides, a + sides);
    }
  }
  for (let i = 1; i < sides - 1; i++) {
    indices.push(0, i + 1, i);
    const end = (sections.length - 1) * sides;
    indices.push(end, end + i, end + i + 1);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();
  return geometry;
}

export function buildCarParts(): CarPart[] {
  const paint = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, metalness: 0.35, roughness: 0.3,
    clearcoat: 1, clearcoatRoughness: 0.22,
  });
  const carbon = new THREE.MeshStandardMaterial({ color: 0x151b23, roughness: 0.58, metalness: 0.25 });
  const rubber = new THREE.MeshStandardMaterial({ color: 0x191b20, roughness: 0.94 });
  const metal = new THREE.MeshStandardMaterial({ color: 0x707886, metalness: 0.85, roughness: 0.28 });
  const visor = new THREE.MeshStandardMaterial({ color: 0x142b42, metalness: 0.75, roughness: 0.12 });
  const stripe = new THREE.MeshStandardMaterial({ color: 0xe8dcbc, roughness: 0.65 });
  const light = new THREE.MeshStandardMaterial({ color: 0xff2020, emissive: 0xff0808, emissiveIntensity: 2 });
  const parts: CarPart[] = [];
  type Point = [number, number, number];
  const add = (geometry: THREE.BufferGeometry, material: THREE.Material, position: Point = [0, 0, 0], rotation: Point = [0, 0, 0]) => {
    parts.push({ geometry, material, colored: material === paint, matrix: new THREE.Matrix4().compose(
      new THREE.Vector3(...position),
      new THREE.Quaternion().setFromEuler(new THREE.Euler(...rotation)),
      new THREE.Vector3(1, 1, 1),
    ) });
  };
  const box = (size: Point, material: THREE.Material, position: Point, rotation?: Point) => add(new THREE.BoxGeometry(...size), material, position, rotation);
  const rod = (from: Point, to: Point, radius = 0.025, material: THREE.Material = carbon) => {
    const a = new THREE.Vector3(...from), b = new THREE.Vector3(...to);
    const direction = b.clone().sub(a);
    const geometry = new THREE.CylinderGeometry(radius, radius, direction.length(), 8);
    geometry.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize()));
    add(geometry, material, a.add(b).multiplyScalar(0.5).toArray() as Point);
  };

  add(bodywork([[-2.15, .14, .43, .15], [-1.3, .34, .52, .24], [0, .42, .56, .25], [.8, .34, .55, .22], [1.6, .16, .43, .13], [2.65, .09, .31, .08]]), paint);
  add(bodywork([[-1.9, .08, .65, .08], [-.85, .27, .72, .29], [-.32, .22, .92, .38], [-.12, .17, .91, .29]]), paint);
  box([.22, .14, .025], carbon, [0, 1.12, -.105]); // air intake
  box([1.65, .065, 2.7], carbon, [0, .16, -.6]);
  for (const side of [-1, 1]) {
    add(bodywork([[-1.65, .13, .36, .12], [-.7, .34, .46, .2], [.35, .35, .49, .23], [.6, .24, .5, .17]]), paint, [side * .56, 0, 0]);
    box([.36, .16, .025], carbon, [side * .6, .52, .61]);
    box([.055, .13, 2.4], carbon, [side * .84, .22, -.65]);
    rod([side * .28, .64, .7], [side * .64, .72, .82], .018);
    box([.17, .085, .16], paint, [side * .65, .73, .82]);
    // Twin wishbones at both axles.
    for (const z of [1.55, -1.72]) {
      for (const y of [.26, .48]) {
        rod([side * .3, y, z - .35], [side * .89, .35, z]);
        rod([side * .3, y, z + .3], [side * .89, .35, z]);
      }
    }
  }
  // Multi-element aero surfaces, endplates and rear diffuser strakes.
  for (let i = 0; i < 3; i++) {
    box([1.87, .035, .18], i === 0 ? carbon : paint, [0, .22 + i * .06, 2.7 - i * .15], [-.12, 0, 0]);
    box([1.03, .045, .17], i === 0 ? carbon : paint, [0, .87 + i * .1, -2.25 - i * .1], [.15, 0, 0]);
  }
  for (const side of [-1, 1]) {
    box([.045, .24, .57], paint, [side * .94, .31, 2.56]);
    box([.045, .46, .56], paint, [side * .53, .9, -2.35]);
    rod([side * .2, .35, -1.95], [side * .2, .94, -2.28], .028);
  }
  for (const x of [-.6, -.3, 0, .3, .6]) box([.025, .15, .48], carbon, [x, .21, -1.95], [-.18, 0, 0]);
  box([.12, .1, .05], light, [0, .38, -2.2]);

  // Recessed cockpit, driver helmet, visor and supported halo.
  const opening = new THREE.SphereGeometry(.29, 20, 12);
  opening.scale(1, .22, 1.55);
  add(opening, carbon, [0, .79, .25]);
  add(new THREE.SphereGeometry(.16, 20, 14), paint, [0, .87, .18]);
  const glass = new THREE.SphereGeometry(.164, 20, 8, 0, Math.PI * 2, Math.PI * .36, Math.PI * .25);
  add(glass, visor, [0, .87, .18]);
  const haloCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-.3, .94, -.05), new THREE.Vector3(-.34, 1, .45),
    new THREE.Vector3(0, 1.01, .79), new THREE.Vector3(.34, 1, .45), new THREE.Vector3(.3, .94, -.05),
  ]);
  add(new THREE.TubeGeometry(haloCurve, 24, .032, 8, false), carbon);
  rod([0, .64, .83], [0, 1.01, .79], .028);

  // Rounded slick tyres with inset wheel covers, hubs and sidewall rings.
  for (const z of [1.55, -1.72]) {
    for (const side of [-1, 1]) {
      const width = z < 0 ? .4 : .33;
      const x = side * .91;
      const tyre = new THREE.CylinderGeometry(.35, .35, width, 32);
      add(tyre, rubber, [x, .35, z], [0, 0, Math.PI / 2]);
      for (const face of [-1, 1]) {
        const faceX = x + face * (width / 2 + .002);
        add(new THREE.CylinderGeometry(.23, .23, .012, 24), carbon, [faceX, .35, z], [0, 0, Math.PI / 2]);
        add(new THREE.CylinderGeometry(.075, .075, .018, 12), metal, [faceX + face * .012, .35, z], [0, 0, Math.PI / 2]);
        add(new THREE.TorusGeometry(.287, .007, 6, 32), stripe, [faceX, .35, z], [0, Math.PI / 2, 0]);
        add(new THREE.TorusGeometry(.31, .04, 8, 32), rubber, [x + face * (width / 2 - .035), .35, z], [0, Math.PI / 2, 0]);
      }
    }
  }
  // Bake static details into one instanced batch per material, rather than
  // paying a draw call for every suspension rod, wheel ring and aero element.
  const batches: CarPart[] = [];
  for (const material of [paint, carbon, rubber, metal, visor, stripe, light]) {
    const geometries = parts.filter((part) => part.material === material).map((part) => {
      part.geometry.applyMatrix4(part.matrix);
      part.geometry.deleteAttribute("uv");
      return part.geometry;
    });
    const geometry = mergeGeometries(geometries);
    if (!geometry) throw new Error("Unable to batch car geometry");
    batches.push({ geometry, material, matrix: new THREE.Matrix4(), colored: material === paint });
    for (const source of geometries) source.dispose();
  }
  return batches;
}

export const SAFETY_CAR_COLOR = new THREE.Color("#ffb020");
