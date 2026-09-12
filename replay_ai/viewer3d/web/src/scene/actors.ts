import * as THREE from "three";
import type { WorldOrigin } from "../state/store";
import { sceneX, sceneZ } from "./world";

/**
 * Shared, smoothed car state.
 *
 * Both the car meshes and the follow camera read from here, so the camera is
 * attached to exactly the transform that is drawn. Previously each component
 * smoothed on its own, which meant the camera chased a slightly different
 * position and heading than the car it was framing.
 *
 * Heading comes from the track tangent when geometry is available, with an
 * exponentially smoothed velocity *vector* as fallback. A single position
 * delta is dominated by floating-point noise at low speed and swings wildly
 * between updates; because the follow camera sits `back` metres behind the car,
 * even a few degrees of heading noise becomes visible lateral movement.
 */

export interface Actor {
  key: string;
  position: THREE.Vector3;
  target: THREE.Vector3;
  heading: number;
  velocityX: number;
  velocityY: number;
  lastX: number;
  lastY: number;
  scale: number;
}

export interface ActorEntry {
  key: string;
  x: number;
  y: number;
  scale: number;
  /** Stable direction supplied by track geometry when available. */
  heading?: number | null;
}

/** A jump larger than this is a seek (rewind / high playback speed), not motion. */
const SNAP_DISTANCE = 250;
/** Below this squared per-sample delta (~1 cm) treat the car as stationary. */
const MOVEMENT_EPSILON = 1e-4;
/** Per-telemetry-sample blend factors. Samples arrive at roughly 30 Hz. */
const VELOCITY_ALPHA = 0.4;
const HEADING_ALPHA = 0.35;
/** Render-rate position smoothing time constant. */
const POSITION_SMOOTHING = 10;

const actors = new Map<string, Actor>();

export function getActor(key: string): Actor | undefined {
  return actors.get(key);
}

export function shortestAngle(from: number, to: number): number {
  const delta = to - from;
  return Math.atan2(Math.sin(delta), Math.cos(delta));
}

export function simulateActors(
  entries: ActorEntry[],
  origin: WorldOrigin,
  dt: number,
): Actor[] {
  const positionAlpha = 1 - Math.exp(-dt * POSITION_SMOOTHING);
  const ordered: Actor[] = [];
  const seen = new Set<string>();

  for (const entry of entries) {
    seen.add(entry.key);

    const targetX = sceneX(entry.x, origin);
    const targetZ = sceneZ(entry.y, origin);

    let actor = actors.get(entry.key);
    if (!actor) {
      actor = {
        key: entry.key,
        position: new THREE.Vector3(targetX, 0, targetZ),
        target: new THREE.Vector3(targetX, 0, targetZ),
        heading: entry.heading ?? 0,
        velocityX: 0,
        velocityY: 0,
        lastX: entry.x,
        lastY: entry.y,
        scale: entry.scale,
      };
      actors.set(entry.key, actor);
    }

    const dx = entry.x - actor.lastX;
    const dy = entry.y - actor.lastY;
    actor.lastX = entry.x;
    actor.lastY = entry.y;
    actor.target.set(targetX, 0, targetZ);
    actor.scale = entry.scale;

    const jumped = actor.position.distanceTo(actor.target) > SNAP_DISTANCE;

    if (entry.heading != null && Number.isFinite(entry.heading)) {
      actor.heading = jumped
        ? entry.heading
        : actor.heading +
          shortestAngle(actor.heading, entry.heading) * HEADING_ALPHA;
    } else if (dx * dx + dy * dy > MOVEMENT_EPSILON) {
      actor.velocityX += (dx - actor.velocityX) * VELOCITY_ALPHA;
      actor.velocityY += (dy - actor.velocityY) * VELOCITY_ALPHA;

      // World +y maps to scene +z, so heading is atan2(dx, dy).
      const targetHeading = Math.atan2(actor.velocityX, actor.velocityY);
      actor.heading = jumped
        ? targetHeading
        : actor.heading +
          shortestAngle(actor.heading, targetHeading) * HEADING_ALPHA;
    }

    if (jumped) {
      actor.position.copy(actor.target);
    } else {
      actor.position.lerp(actor.target, positionAlpha);
    }

    ordered.push(actor);
  }

  for (const key of [...actors.keys()]) {
    if (!seen.has(key)) actors.delete(key);
  }

  return ordered;
}

// Dev affordance: lets tooling measure heading stability.
if (import.meta.env.DEV) {
  (globalThis as unknown as Record<string, unknown>).__actors = actors;
}
