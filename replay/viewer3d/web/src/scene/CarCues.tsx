import { useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useViewerStore } from "../state/store";
import { getActor } from "./actors";
import { battleSet, focusCue, isDrsActive, orderCodes, shouldDrawConnector, gapBetween } from "./cues";

/**
 * Strategy cues drawn in world space, on top of the cars.
 *
 * Deliberately sparse. The 2D replay uses focus mode to make one battle legible
 * among twenty cars; in 3D the equivalent is a single ring under the followed
 * car and one tether to the car it is fighting. Everything else stays in the
 * HUD, so the circuit itself is not covered in overlays.
 *
 * A tether is only drawn inside the replay's connector window, so lapped traffic
 * adjacent in track order cannot produce a streak across the circuit.
 */

const RING_INNER = 2.6;
const RING_OUTER = 3.1;
const RING_HEIGHT = 0.06;

export function CarCues() {
  const objects = useMemo(() => {
    const group = new THREE.Group();
    const ringGeometry = new THREE.RingGeometry(RING_INNER, RING_OUTER, 48);
    ringGeometry.rotateX(-Math.PI / 2);
    const ring = new THREE.Mesh(
      ringGeometry,
      new THREE.MeshBasicMaterial({
        color: "#7fb4ff",
        transparent: true,
        opacity: 0.75,
        depthWrite: false,
        side: THREE.DoubleSide,
      }),
    );
    ring.renderOrder = 15;
    ring.visible = false;

    const tetherGeometry = new THREE.BufferGeometry();
    tetherGeometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(6), 3));
    const tether = new THREE.Line(
      tetherGeometry,
      new THREE.LineBasicMaterial({ color: "#ffc447", transparent: true, opacity: 0.8, depthWrite: false }),
    );
    tether.renderOrder = 15;
    tether.visible = false;
    tether.frustumCulled = false;

    group.add(ring, tether);
    return { group, ring, tether, tetherAttribute: tetherGeometry.getAttribute("position") as THREE.BufferAttribute };
  }, []);

  useFrame(() => {
    const store = useViewerStore.getState();
    const { showCues, drivers, followedDriver, circuitLengthM, carScale } = store;
    const active = showCues && Boolean(drivers);
    objects.ring.visible = false;
    objects.tether.visible = false;
    if (!active || !drivers) return;

    const cue = focusCue(drivers, followedDriver, circuitLengthM);
    if (!cue) return;
    const self = getActor(cue.code);
    if (!self) return;

    // Highlight the followed car. Green when its own DRS is open, so the ring
    // doubles as an attack-available cue instead of adding another badge.
    const drs = isDrsActive(drivers[cue.code]?.drs);
    const material = objects.ring.material as THREE.MeshBasicMaterial;
    material.color.set(drs ? "#4ade80" : "#7fb4ff");
    objects.ring.position.set(self.position.x, RING_HEIGHT, self.position.z);
    objects.ring.scale.setScalar(Math.max(1, carScale));
    objects.ring.visible = true;

    // Tether to the car ahead only within the replay's connector window.
    if (!cue.aheadCode) return;
    const ahead = getActor(cue.aheadCode);
    if (!ahead) return;
    const { timeS } = gapBetween(
      drivers[cue.code].fraction,
      drivers[cue.aheadCode].fraction,
      circuitLengthM,
    );
    if (!shouldDrawConnector(timeS)) return;

    // Mark only genuinely adjacent cars as a battle, matching focus mode.
    const battling = battleSet(orderCodes(drivers), cue.code).has(cue.aheadCode);
    const tetherMaterial = objects.tether.material as THREE.LineBasicMaterial;
    tetherMaterial.opacity = battling ? 0.85 : 0.35;

    const attribute = objects.tetherAttribute;
    const array = attribute.array as Float32Array;
    array[0] = self.position.x;
    array[1] = 1.6 * Math.max(1, carScale);
    array[2] = self.position.z;
    array[3] = ahead.position.x;
    array[4] = 1.6 * Math.max(1, carScale);
    array[5] = ahead.position.z;
    attribute.needsUpdate = true;
    objects.tether.visible = true;
  }, -1.5);

  return <primitive object={objects.group} />;
}
