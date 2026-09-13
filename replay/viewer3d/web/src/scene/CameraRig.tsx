import { useEffect, useMemo, useRef } from "react";
import type { ComponentRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import * as THREE from "three";
import { useViewerStore } from "../state/store";
import { getActor } from "./actors";
import { orderCodes } from "./cues";
import { computeBounds } from "./world";
import { ChaseCamera, CHASE_VIEWS } from "./chase";

export function CameraRig() {
  const geometry = useViewerStore((state) => state.geometry);
  const mode = useViewerStore((state) => state.cameraMode);
  const camera = useThree((state) => state.camera);
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const lastTarget = useRef<string | null>(null);
  const lastPosition = useRef(new THREE.Vector3());
  const chase = useMemo(() => new ChaseCamera(), []);

  useEffect(() => {
    if (import.meta.env.DEV) {
      (globalThis as unknown as Record<string, unknown>).__camera = camera;
    }
  }, [camera]);

  useEffect(() => {
    lastTarget.current = null;
    if (mode !== "orbit" || !geometry) return;
    const radius = computeBounds(geometry).radius;
    camera.position.set(radius * .15, radius * 1.25, radius * 1.45);
    camera.lookAt(0, 0, 0);
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.fov = 45;
      camera.updateProjectionMatrix();
    }
    controls.current?.target.set(0, 0, 0);
    controls.current?.update();
  }, [mode, geometry, camera]);

  useFrame((_, delta) => {
    if (mode !== "follow") return;
    const { drivers, carScale, followedDriver, chaseView } = useViewerStore.getState();
    if (!drivers) return;
    const code = followedDriver && drivers[followedDriver]
      ? followedDriver
      : orderCodes(drivers)[0];
    if (!code) return;
    const actor = getActor(code);
    if (!actor) return;

    const reset = lastTarget.current !== code || actor.discontinuity || actor.position.distanceTo(lastPosition.current) > 250;
    // Use the rendered car's heading and position, never a newer telemetry tick.
    chase.update(actor.position, actor.heading, carScale, chaseView, delta, reset);
    camera.position.copy(chase.position);
    camera.lookAt(chase.look);
    if (camera instanceof THREE.PerspectiveCamera) {
      const targetFov = CHASE_VIEWS[chaseView].fov;
      camera.fov += (targetFov - camera.fov) * (reset ? 1 : 1 - Math.exp(-8 * Math.min(delta, .1)));
      camera.updateProjectionMatrix();
    }
    lastTarget.current = code;
    lastPosition.current.copy(actor.position);
  }, -1);

  if (mode !== "orbit") return null;
  return <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={.08}
    maxPolarAngle={Math.PI * .49} minDistance={20} maxDistance={20000} />;
}
