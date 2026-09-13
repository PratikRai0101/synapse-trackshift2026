import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { buildCarParts, SAFETY_CAR_COLOR } from "./carParts";
import { getActor, simulateActors, type ActorEntry } from "./actors";
import { playback } from "../net/playback";
import { useViewerStore } from "../state/store";
import { trackHeading } from "./world";
import { detectOverlaps, fitCarScales } from "./spacing";
import { drsOpening, tyreColour } from "./appearance";
import { battleSet, orderCodes } from "./cues";

/**
 * All cars in one set of `InstancedMesh`es, one mesh per car part, plus a
 * screen-constant driver label per car.
 *
 * 20 cars x ~20 parts would be ~400 draw calls as separate objects; instead
 * every part is drawn once with 20 instances. Team colour rides on
 * `instanceColor`, which is free.
 *
 * Two deliberately unphysical tricks make this readable, mirroring what the 2D
 * arcade replay does with its 6 px circles:
 *
 *  - Cars are scaled by `carScale`. At true scale a 5.6 m car is sub-pixel from
 *    the overview camera.
 *  - Labels are sized each frame from camera distance so they stay a constant
 *    number of screen pixels, whatever the zoom.
 *
 * Position and heading come from `simulateActors`, which the follow camera also
 * reads, so the camera frames exactly the transform that is drawn.
 */

const MAX_ACTORS = 24;
const SAFETY_CAR_SCALE = 1.18;
const LABEL_SCREEN_FRACTION = 0.013;
const LABEL_ASPECT = 2; // canvas is 2:1

const colorCache = new Map<string, THREE.Color>();

function cachedColor(hex: string): THREE.Color {
  let color = colorCache.get(hex);
  if (!color) {
    color = new THREE.Color(hex);
    colorCache.set(hex, color);
  }
  return color;
}

const labelTextures = new Map<string, THREE.CanvasTexture>();

/** White-on-dark or black-on-light, whichever the team colour needs. */
function labelTexture(code: string, hex: string): THREE.CanvasTexture {
  const key = `${code}|${hex}`;
  const cached = labelTextures.get(key);
  if (cached) return cached;

  const width = 256;
  const height = 128;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");

  if (ctx) {
    const pad = 12;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = hex;
    ctx.beginPath();
    ctx.roundRect(pad, pad, width - pad * 2, height - pad * 2, 28);
    ctx.fill();
    ctx.lineWidth = 5;
    ctx.strokeStyle = "rgba(255,255,255,0.55)";
    ctx.stroke();

    const base = new THREE.Color(hex);
    const luminance = 0.2126 * base.r + 0.7152 * base.g + 0.0722 * base.b;
    ctx.fillStyle = luminance > 0.55 ? "#0b0e13" : "#ffffff";
    ctx.font = "bold 62px ui-monospace, Menlo, Consolas, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(code, width / 2, height / 2 + 3);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  labelTextures.set(key, texture);
  return texture;
}

export function CarFleet() {
  const parts = useMemo(() => buildCarParts(), []);
  const revision = useRef(-1);
  const drsStates = useRef(new Map<string, number>());
  const carScale = useViewerStore((state) => state.carScale);
  const showLabels = useViewerStore((state) => state.showLabels);

  const coloredIndices = useMemo(
    () =>
      parts
        .map((part, index) => (part.colored ? index : -1))
        .filter((index) => index >= 0),
    [parts],
  );

  const { group, meshes } = useMemo(() => {
    const root = new THREE.Group();
    const instances = parts.map((part) => {
      const mesh = new THREE.InstancedMesh(
        part.geometry,
        part.material,
        MAX_ACTORS,
      );
      mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.frustumCulled = false;
      mesh.count = 0;
      root.add(mesh);
      return mesh;
    });
    return { group: root, meshes: instances };
  }, [parts]);

  const labels = useMemo(() => new Map<string, THREE.Sprite>(), []);
  useEffect(() => () => {
    for (const mesh of meshes) mesh.dispose();
    for (const part of parts) part.geometry.dispose();
    for (const material of new Set(parts.map((part) => part.material))) material.dispose();
    for (const sprite of labels.values()) sprite.material.dispose();
    for (const texture of labelTextures.values()) texture.dispose();
    labelTextures.clear();
  }, [meshes, parts, labels]);
  const colorSignature = useMemo(() => ({ value: "" }), []);

  const scratch = useMemo(
    () => ({
      car: new THREE.Matrix4(),
      part: new THREE.Matrix4(),
      local: new THREE.Matrix4(),
      flap: new THREE.Matrix4(),
      quaternion: new THREE.Quaternion(),
      euler: new THREE.Euler(),
      scale: new THREE.Vector3(1, 1, 1),
      world: new THREE.Vector3(),
    }),
    [],
  );

  useFrame((state, delta) => {
    const store = useViewerStore.getState();
    const { origin } = store;
    const frame = playback.sample();
    const drivers = frame?.drivers;
    group.visible = Boolean(origin && drivers);
    if (!origin || !drivers) return;

    const dt = Math.min(delta, 0.1);

    // Stable order so instance indices line up between colours and matrices.
    const codes = Object.keys(drivers).sort(
      (a, b) => (drivers[a].position ?? 99) - (drivers[b].position ?? 99),
    );

    const entries: (ActorEntry & { color: THREE.Color })[] = [];

    for (const code of codes) {
      const driver = drivers[code];
      if (!Number.isFinite(driver.x) || !Number.isFinite(driver.y)) continue;
      entries.push({
        key: code,
        x: driver.x,
        y: driver.y,
        scale: 1,
        heading: driver.heading ?? (!getActor(code) && store.geometry
          ? trackHeading(driver.fraction, store.geometry) : null),
        color: cachedColor(store.driverColors[code] ?? "#9aa4b2"),
      });
    }

    const sc = frame?.safety_car;
    if (sc && Number.isFinite(sc.x) && Number.isFinite(sc.y) && sc.alpha > 0.02) {
      entries.push({
        key: "__SC",
        x: sc.x,
        y: sc.y,
        scale: SAFETY_CAR_SCALE,
        color: SAFETY_CAR_COLOR,
      });
    }

    // Shared with CameraRig. Returned in the same order as `entries`.
    entries.splice(MAX_ACTORS);
    const reset = revision.current !== playback.revision;
    revision.current = playback.revision;
    const simulated = simulateActors(entries, origin, dt, { paused: store.paused, reset, direct: true });
    const fittedScales = fitCarScales(simulated, carScale);
    const overlaps = detectOverlaps(simulated, carScale);
    store.setRenderWarnings([...overlaps].sort(), Object.keys(drivers).filter((code) => drivers[code].motion_quality === "gap").sort());
    const activeKeys = new Set(simulated.map((actor) => actor.key));
    for (const key of drsStates.current.keys()) {
      if (!activeKeys.has(key)) drsStates.current.delete(key);
    }
    for (const [key, sprite] of labels) {
      if (activeKeys.has(key)) continue;
      group.remove(sprite);
      sprite.material.dispose();
      labels.delete(key);
    }
    const focus = store.followedDriver && drivers[store.followedDriver]
      ? store.followedDriver : codes[0] ?? null;
    const visibleCodes = store.cameraMode === "follow" ? battleSet(orderCodes(drivers), focus) : null;

    const camera = state.camera as THREE.PerspectiveCamera;
    const tanHalfFov = Math.tan((camera.fov * Math.PI) / 360);
    const activeLabels = new Set<string>();

    for (let index = 0; index < simulated.length; index += 1) {
      const actor = simulated[index];
      const worldScale = fittedScales[index];

      scratch.euler.set(0, actor.heading, 0);
      scratch.quaternion.setFromEuler(scratch.euler);
      scratch.scale.setScalar(worldScale);
      scratch.car.compose(actor.position, scratch.quaternion, scratch.scale);

      const previousDrs = drsStates.current.get(actor.key);
      const opening = drsOpening(previousDrs ?? 0, drivers[actor.key]?.drs, dt,
        reset || store.paused || previousDrs === undefined);
      drsStates.current.set(actor.key, opening);
      for (let i = 0; i < meshes.length; i += 1) {
        scratch.local.copy(parts[i].matrix);
        if (parts[i].animation === "drs") {
          scratch.flap.makeRotationX(-.6 * opening);
          scratch.local.multiply(scratch.flap);
        }
        scratch.part.multiplyMatrices(scratch.car, scratch.local);
        meshes[i].setMatrixAt(index, scratch.part);
        if (parts[i].tyreColored) {
          meshes[i].setColorAt(index, cachedColor(tyreColour(drivers[actor.key]?.tyre)));
        }
      }

      // Follow mode labels only the immediate battle, not all twenty cars.
      if (!showLabels || (visibleCodes && !visibleCodes.has(actor.key) && actor.key !== "__SC")) continue;
      activeLabels.add(actor.key);

      let sprite = labels.get(actor.key);
      if (!sprite) {
        sprite = new THREE.Sprite(
          new THREE.SpriteMaterial({
            transparent: true,
            depthTest: false,
            depthWrite: false,
          }),
        );
        sprite.renderOrder = 20;
        group.add(sprite);
        labels.set(actor.key, sprite);
      }
      const uncertain = overlaps.has(actor.key) || drivers[actor.key]?.motion_quality === "gap";
      // Recorded pit status, not an inferred pit lane. Pit cars are tinted
      // slate so they are distinguishable from cars on a flying lap.
      const inPit = drivers[actor.key]?.in_pit === true;
      const texture = labelTexture(uncertain ? `${actor.key}?` : inPit ? `${actor.key}·` : actor.key,
        uncertain ? "#d69326" : inPit ? "#6b7280"
          : store.driverColors[actor.key] ?? (actor.key === "__SC" ? "#ffb020" : "#9aa4b2"));
      if (sprite.material.map !== texture) {
        sprite.material.map = texture;
        sprite.material.needsUpdate = true;
      }

      scratch.world
        .copy(actor.position)
        .setY(Math.max(1.5, 2.6 * worldScale));
      sprite.position.copy(scratch.world);

      const distance = camera.position.distanceTo(scratch.world);
      const height = 2 * distance * tanHalfFov * LABEL_SCREEN_FRACTION;
      sprite.scale.set(height * LABEL_ASPECT, height, 1);
    }

    for (const mesh of meshes) {
      mesh.count = simulated.length;
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
    }

    for (const [key, sprite] of labels) {
      sprite.visible = showLabels && activeLabels.has(key);
    }

    // Recolour only when the field or the team palette actually changes.
    const signature = entries
      .map((entry) => `${entry.key}:${entry.color.getHexString()}`)
      .join("|");

    if (signature !== colorSignature.value) {
      colorSignature.value = signature;

      for (const partIndex of coloredIndices) {
        const mesh = meshes[partIndex];
        for (let index = 0; index < entries.length; index += 1) {
          mesh.setColorAt(index, entries[index].color);
        }
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      }

    }
  }, -2);

  return <primitive object={group} />;
}
