import { isDrsActive } from "./cues";

/** Replay compound IDs. Unknown data stays neutral, not falsely 'hard'. */
export function tyreColour(compound: number | undefined): string {
  switch (compound) {
    case 1: return "#e8453c";
    case 2: return "#f0d33a";
    case 3: return "#e8e8e8";
    case 4: return "#3fbf5f";
    case 5: return "#3f7fe0";
    default: return "#626975";
  }
}

/** Visual actuator only. Follows the replay flag; does not authorize a mode,
 * infer a pass, change drag, or feed a synthetic control back into the engine. */
export function drsOpening(current: number, flag: unknown, dt: number, snap: boolean): number {
  const target = isDrsActive(flag) ? 1 : 0;
  if (snap) return target;
  return current + (target - current) * (1 - Math.exp(-14 * Math.min(.1, Math.max(0, dt))));
}

/**
 * Wheel spin, in radians, from the distance actually travelled.
 *
 * Rolling distance is observed telemetry, so no wheel speed sensor is invented:
 * this only converts metres into rotation using the rendered radius.
 */
export function wheelSpin(speedKmh: unknown, radiusM: number, dt: number,
                          current: number, snap = false): number {
  if (snap || !(radiusM > 0)) return current;
  const metresPerSecond = Math.max(0, Number(speedKmh) || 0) / 3.6;
  return current + (metresPerSecond / radiusM) * Math.min(.1, Math.max(0, dt));
}

/**
 * Front-wheel steering angle from the car's own observed yaw rate.
 *
 * Kinematic bicycle relation `tan(delta) = wheelbase * yawRate / speed`. At low
 * speed that ratio is unstable (a yaw rate from position noise divided by a
 * small speed), so the angle is clamped and the input is smoothed. Nothing here
 * feeds back into motion: it is a display of the path the car already took.
 */
export function steerAngle(previousHeading: number, heading: number,
                           speedKmh: unknown, wheelbaseM: number,
                           dt: number, current: number): number {
  const step = Math.min(.1, Math.max(0, dt));
  if (step <= 0) return current;
  const yawRate = Math.atan2(Math.sin(heading - previousHeading),
                             Math.cos(heading - previousHeading)) / step;
  const speed = Math.max(4, (Number(speedKmh) || 0) / 3.6); // avoid /0 at rest
  const target = Math.max(-0.55, Math.min(0.55,
    Math.atan((wheelbaseM * yawRate) / speed)));
  return current + (target - current) * (1 - Math.exp(-10 * step));
}
