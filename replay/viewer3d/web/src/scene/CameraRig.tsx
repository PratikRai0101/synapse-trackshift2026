import { useEffect, useMemo, useRef } from "react";
import type { ComponentRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { useViewerStore } from "../state/store";
import { getActor, shortestAngle } from "./actors";
import { computeBounds, trackHeading } from "./world";

/**
 * Two cameras in one component.
 *
 * `orbit` is the overview: framed to the whole circuit once geometry arrives.
 * `follow` chases the selected driver, or the race leader in automatic mode.
 *
 * The follow camera reads position and heading from the shared actor state that
 * also drives the car meshes, so it frames exactly the transform being drawn.
 * Deriving heading here from a raw position delta was what made it wobble —
 * a few degrees of heading noise is tens of metres of lateral camera movement
 * at this follow distance.
 *
 * OrbitControls is only mounted in orbit mode so the two can never fight over
 * the camera.
 */

const FOLLOW_BACK = 22;
const FOLLOW_UP = 8;
const FOLLOW_LOOKAHEAD = 10;
const CAMERA_LAG = 8;
const LOOK_LAG = 10;
/** Time constant for aligning the chase camera with the track direction. */
const HEADING_LAG = 6;

/**
 * Follow distance scales with the car size multiplier so the camera does not
 * end up inside an exaggerated car.
 */
function followOffset(carScale: number): { back: number; up: number } {
  const factor = Math.max(1, carScale * 0.75);
  return { back: FOLLOW_BACK * factor, up: FOLLOW_UP * factor };
}

export function CameraRig() {
  const geometry = useViewerStore((state) => state.geometry);
  const mode = useViewerStore((state) => state.cameraMode);
  const camera = useThree((state) => state.camera);
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const framed = useRef(false);
  const lastTarget = useRef<string | null>(null);
  const cameraHeading = useRef(0);
  const cameraLook = useRef(new THREE.Vector3());

  const scratch = useMemo(
    () => ({
      desired: new THREE.Vector3(),
      look: new THREE.Vector3(),
      forward: new THREE.Vector3(),
    }),
    [],
  );

  // Dev affordance: lets tooling measure camera stability.
  useEffect(() => {
    if (import.meta.env.DEV) {
      (globalThis as unknown as Record<string, unknown>).__camera = camera;
    }
  }, [camera]);

  const frameCircuit = useMemo(
    () => (radius: number) => {
      camera.position.set(radius * 0.15, radius * 1.25, radius * 1.45);
      camera.lookAt(0, 0, 0);
      controls.current?.target.set(0, 0, 0);
      controls.current?.update();
    },
    [camera],
  );

  useEffect(() => {
    if (!geometry || framed.current) return;
    frameCircuit(computeBounds(geometry).radius);
    framed.current = true;
  }, [geometry, frameCircuit]);

  // Returning to orbit after a chase leaves the camera pointing at the leader;
  // re-frame so the controls have a sane target again.
  useEffect(() => {
    if (mode !== "orbit" || !geometry) return;
    frameCircuit(computeBounds(geometry).radius);
  }, [mode, geometry, frameCircuit]);

  useFrame((_, delta) => {
    if (mode !== "follow") return;

    const {
      drivers,
      origin,
      carScale,
      geometry: trackGeometry,
      followedDriver,
    } = useViewerStore.getState();
    if (!drivers || !origin) return;

    let code = followedDriver && drivers[followedDriver] ? followedDriver : null;
    if (!code) {
      code =
        Object.entries(drivers).find(([, driver]) => driver.position === 1)?.[0] ??
        null;
    }
    if (!code) return;

    const driver = drivers[code];
    const actor = getActor(code);
    if (!actor) return;

    // Prefer the track's own direction of travel. The car's yaw comes from a
    // noisy position delta that will never be completely stable; the centreline
    // is smooth by construction. Falling back to the car keeps the safety car
    // (which has no `fraction`) working.
    const tangent =
      trackGeometry && trackHeading(driver.fraction, trackGeometry);
    const targetHeading = tangent ?? actor.heading;

    const dt = Math.min(delta, 0.1);
    const isNewTarget = lastTarget.current !== code;
    if (isNewTarget) {
      cameraHeading.current = targetHeading;
      lastTarget.current = code;
    } else {
      const headingAlpha = 1 - Math.exp(-dt * HEADING_LAG);
      cameraHeading.current +=
        shortestAngle(cameraHeading.current, targetHeading) * headingAlpha;
    }

    const heading = cameraHeading.current;
    const px = actor.position.x;
    const pz = actor.position.z;
    const { back, up } = followOffset(carScale);

    // Car forward is +Z locally, so world forward is (sin h, 0, cos h).
    scratch.forward.set(Math.sin(heading), 0, Math.cos(heading));
    scratch.desired.set(px, up, pz).addScaledVector(scratch.forward, -back);
    scratch.look
      .set(px, 1.4, pz)
      .addScaledVector(scratch.forward, FOLLOW_LOOKAHEAD);

    if (isNewTarget) {
      // The target changed: snap rather than sweeping across the circuit.
      camera.position.copy(scratch.desired);
      cameraLook.current.copy(scratch.look);
    } else {
      const positionAlpha = 1 - Math.exp(-dt * CAMERA_LAG);
      const lookAlpha = 1 - Math.exp(-dt * LOOK_LAG);
      camera.position.lerp(scratch.desired, positionAlpha);
      cameraLook.current.lerp(scratch.look, lookAlpha);
    }

    // Smoothing the look target as well as camera position prevents telemetry
    // ticks from becoming tiny but visible orientation kicks.
    camera.lookAt(cameraLook.current);
  });

  if (mode !== "orbit") return null;

  return (
    <OrbitControls
      ref={controls}
      makeDefault
      enableDamping
      dampingFactor={0.08}
      maxPolarAngle={Math.PI * 0.49}
      minDistance={20}
      maxDistance={20000}
    />
  );
}
