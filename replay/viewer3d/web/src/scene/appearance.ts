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
