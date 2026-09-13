import * as THREE from "three";
import { buildStripGeometry } from "./world";
import type { WorldOrigin } from "../state/store";

/** Seeded, seamless tiling material detail. No downloads or browser canvas. */
export function surfaceTexture(kind: "asphalt" | "grass"): THREE.DataTexture {
  const size = 128;
  const data = new Uint8Array(size * size * 4);
  let seed = 7391;
  for (let i = 0; i < size * size; i++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    const noise = (seed >>> 24) / 255;
    const shade = .78 + noise * .22;
    const base = kind === "asphalt" ? [115, 117, 119] : [91, 111, 68];
    for (let channel = 0; channel < 3; channel++) data[i * 4 + channel] = base[channel] * shade;
    data[i * 4 + 3] = 255;
  }
  const texture = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.LinearFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}

export function kerbTexture(): THREE.DataTexture {
  const texture = new THREE.DataTexture(new Uint8Array([
    185, 42, 38, 255, 224, 221, 210, 255,
  ]), 2, 1, THREE.RGBAFormat);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.magFilter = THREE.NearestFilter;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}

/** World-space UVs keep asphalt grain the same size on wide/narrow ribbons. */
export function planarUVs(geometry: THREE.BufferGeometry, tileSize = 4): void {
  const positions = geometry.getAttribute("position");
  const uv = new Float32Array(positions.count * 2);
  for (let i = 0; i < positions.count; i++) {
    uv[i * 2] = positions.getX(i) / tileSize;
    uv[i * 2 + 1] = positions.getZ(i) / tileSize;
  }
  geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
}

/** Explicit seam vertices prevent UVs wrapping backwards over the last segment.
 * Each red/white block is two world units, regardless of sample spacing. */
export function kerbGeometry(
  edgeX: number[], edgeY: number[], nearX: number[], nearY: number[], origin: WorldOrigin,
): THREE.BufferGeometry {
  const close = (values: number[]) => values.length ? [...values, values[0]] : [];
  const x = close(edgeX), y = close(edgeY);
  const data = buildStripGeometry(x, y, close(nearX), close(nearY), origin, .02, undefined, false);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(data.positions, 3));
  geometry.setIndex(new THREE.BufferAttribute(data.indices, 1));
  const count = data.positions.length / 6;
  const uv = new Float32Array(count * 4);
  let distance = 0;
  for (let i = 0; i < count; i++) {
    if (i > 0) distance += Math.hypot(x[i] - x[i - 1], y[i] - y[i - 1]);
    uv.set([distance / 4, 0, distance / 4, 1], i * 4);
  }
  geometry.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
  geometry.computeVertexNormals();
  return geometry;
}
