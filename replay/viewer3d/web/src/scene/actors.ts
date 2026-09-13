import * as THREE from "three";
import type { WorldOrigin } from "../state/store";
import { sceneX, sceneZ } from "./world";

/** Render interpolation only: this replay does not simulate vehicle forces. */
export interface Actor {
  key: string;
  position: THREE.Vector3;
  start: THREE.Vector3;
  target: THREE.Vector3;
  heading: number;
  targetHeading: number;
  elapsed: number;
  duration: number;
  lastX: number;
  lastY: number;
  scale: number;
  discontinuity: boolean;
}
export interface ActorEntry {
  key: string;
  x: number;
  y: number;
  scale: number;
  /** Initial orientation only; movement determines heading thereafter. */
  heading?: number | null;
}
export interface PlaybackStep {
  /** Measured wall-clock interval between source samples, not simulation time. */
  sampleInterval?: number;
  paused?: boolean;
  reset?: boolean;
}
const actors = new Map<string, Actor>();
export function getActor(key: string): Actor | undefined { return actors.get(key); }
export function shortestAngle(from: number, to: number): number {
  return Math.atan2(Math.sin(to - from), Math.cos(to - from));
}

export function simulateActors(entries: ActorEntry[], origin: WorldOrigin, dt: number, playback: PlaybackStep = {}): Actor[] {
  const ordered: Actor[] = [];
  const seen = new Set<string>();
  const step = Math.max(0, Math.min(dt, .1));
  for (const entry of entries) {
    if (!Number.isFinite(entry.x) || !Number.isFinite(entry.y)) continue;
    seen.add(entry.key);
    const x = sceneX(entry.x, origin), z = sceneZ(entry.y, origin);
    let actor = actors.get(entry.key);
    const initialHeading = Number.isFinite(entry.heading) ? entry.heading! : 0;
    if (!actor) {
      actor = {
        key: entry.key, position: new THREE.Vector3(x, 0, z),
        start: new THREE.Vector3(x, 0, z), target: new THREE.Vector3(x, 0, z),
        heading: initialHeading, targetHeading: initialHeading,
        elapsed: 0, duration: 1 / 30, lastX: entry.x, lastY: entry.y, scale: entry.scale, discontinuity: true,
      };
      actors.set(entry.key, actor);
    }
    const dx = entry.x - actor.lastX, dy = entry.y - actor.lastY;
    const moved = Math.hypot(dx, dy);
    const reset = playback.reset || Math.hypot(x - actor.target.x, z - actor.target.z) > 250;
    actor.discontinuity = Boolean(reset);
    if (reset) {
      actor.position.set(x, 0, z);
      actor.start.copy(actor.position);
      actor.target.copy(actor.position);
      actor.heading = actor.targetHeading = initialHeading;
      actor.elapsed = actor.duration;
    } else if (moved > 0) {
      actor.start.copy(actor.position);
      actor.target.set(x, 0, z);
      actor.elapsed = 0;
      actor.duration = Math.max(1 / 120, Math.min(playback.sampleInterval ?? 1 / 30, .1));
      // Ignore sub-centimetre positional noise when estimating orientation.
      // In pit lanes/overtakes the centreline tangent need not match this path.
      if (moved > .01) actor.targetHeading = Math.atan2(dx, dy);
    }
    actor.lastX = entry.x;
    actor.lastY = entry.y;
    actor.scale = entry.scale;
    if (playback.paused) {
      actor.position.copy(actor.target);
      actor.elapsed = actor.duration;
    } else {
      actor.elapsed = Math.min(actor.duration, actor.elapsed + step);
      actor.position.lerpVectors(actor.start, actor.target, actor.elapsed / actor.duration);
      actor.heading += shortestAngle(actor.heading, actor.targetHeading) * (1 - Math.exp(-18 * step));
    }
    ordered.push(actor);
  }
  for (const key of actors.keys()) if (!seen.has(key)) actors.delete(key);
  return ordered;
}

if (import.meta.env.DEV) {
  (globalThis as unknown as Record<string, unknown>).__actors = actors;
}
