import * as THREE from "three";
import { shortestAngle } from "./actors";

export const CHASE_VIEWS = {
  chase: { back: 11, up: 5, side: 0, ahead: 3, fov: 48 },
  broadcast: { back: 15, up: 8, side: 10, ahead: 2, fov: 42 },
  overhead: { back: 5, up: 25, side: 0, ahead: 3, fov: 48 },
} as const;
export type ChaseView = keyof typeof CHASE_VIEWS;

/** All smoothing happens in car-relative space. Translation is shared by the
 * eye and look target, so accelerating or pausing cannot change the framing. */
export class ChaseCamera {
  heading = 0;
  offset = new THREE.Vector3();
  lookOffset = new THREE.Vector3();
  position = new THREE.Vector3();
  look = new THREE.Vector3();
  private desired = new THREE.Vector3();
  private desiredLook = new THREE.Vector3();

  update(anchor: THREE.Vector3, heading: number, scale: number, view: ChaseView, delta: number, reset = false) {
    const dt = Math.min(Math.max(delta, 0), .1);
    this.heading = reset ? heading : this.heading + shortestAngle(this.heading, heading) * (1 - Math.exp(-5 * dt));
    const preset = CHASE_VIEWS[view];
    const sin = Math.sin(this.heading), cos = Math.cos(this.heading);
    this.desired.set((cos * preset.side - sin * preset.back) * scale, preset.up * scale, (-sin * preset.side - cos * preset.back) * scale);
    this.desiredLook.set(sin * preset.ahead * scale, .65 * scale, cos * preset.ahead * scale);
    const alpha = 1 - Math.exp(-8 * dt);
    if (reset) {
      this.offset.copy(this.desired);
      this.lookOffset.copy(this.desiredLook);
    } else {
      this.offset.lerp(this.desired, alpha);
      this.lookOffset.lerp(this.desiredLook, alpha);
    }
    this.position.copy(anchor).add(this.offset);
    this.look.copy(anchor).add(this.lookOffset);
  }
}
