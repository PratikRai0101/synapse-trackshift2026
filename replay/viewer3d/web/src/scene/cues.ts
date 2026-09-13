import type { DriverState, TrackGeometry } from "../net/protocol";

/**
 * Cues derived from the same public telemetry the 2D replay already uses.
 *
 * These mirror the replay's own rules rather than inventing new strategy:
 * `gap_between` (distance / 55.56 m/s), `_battle_set` (selected car +- radius)
 * and `should_draw_connector` (only draw a tether under MAX_CONNECTOR_SECONDS).
 * Keeping the math identical means the 3D cue and the 2D HUD never disagree.
 */

/** ~200 km/h reference used by `F1RaceReplayWindow.gap_between`. */
export const GAP_REFERENCE_SPEED_MPS = 55.56;
/** Mirrors `F1RaceReplayWindow.MAX_CONNECTOR_SECONDS`. */
export const MAX_CONNECTOR_SECONDS = 3;
/** Mirrors `_battle_set` default radius: cars ahead/behind a focus driver. */
export const BATTLE_RADIUS = 2;

/** DRS is active for the overlay codes the replay treats as open. */
export function isDrsActive(drs: unknown): boolean {
  const value = Number(drs);
  return value === 8 || value === 10 || value === 12 || value === 14;
}

/** Lap fraction in the payload already includes completed laps, so scaling by
 * circuit length reproduces the replay's `progress_m`. */
export function progressMetres(fraction: unknown, circuitLengthM: number): number {
  const value = Number(fraction);
  if (!Number.isFinite(value)) return 0;
  return value * circuitLengthM;
}

/** Mirrors `gap_between`: returns distance in metres and a time gap. */
export function gapBetween(
  fractionA: unknown,
  fractionB: unknown,
  circuitLengthM: number,
): { distanceM: number; timeS: number } {
  const distanceM = Math.abs(
    progressMetres(fractionA, circuitLengthM) - progressMetres(fractionB, circuitLengthM),
  );
  return { distanceM, timeS: distanceM / GAP_REFERENCE_SPEED_MPS };
}

export function shouldDrawConnector(timeS: number | null): boolean {
  return timeS != null && Number.isFinite(timeS) && timeS <= MAX_CONNECTOR_SECONDS;
}

/** Track order, fastest first, matching the replay's `ordered_codes`. */
export function orderCodes(
  drivers: Record<string, DriverState>,
): string[] {
  return Object.keys(drivers).sort(
    (a, b) => (drivers[a].position ?? 99) - (drivers[b].position ?? 99),
  );
}

/** Mirrors `_battle_set`: the focus car plus `radius` cars either side. */
export function battleSet(
  ordered: string[],
  focus: string | null,
  radius = BATTLE_RADIUS,
): Set<string> {
  const result = new Set<string>();
  if (!focus) return result;
  const index = ordered.indexOf(focus);
  if (index < 0) return result;
  for (let i = Math.max(0, index - radius); i < Math.min(ordered.length, index + radius + 1); i++) {
    result.add(ordered[i]);
  }
  return result;
}

export interface FocusCue {
  code: string;
  position: number;
  /** Null means no car is close enough / available ahead. */
  gapAheadS: number | null;
  gapBehindS: number | null;
  aheadCode: string | null;
  behindCode: string | null;
  drs: boolean;
  /** Recorded pit-window status; never inferred from geometry. */
  inPit: boolean;
}

/** Focus-driver summary for the HUD strip. Null when the focus car is unknown. */
export function focusCue(
  drivers: Record<string, DriverState>,
  focus: string | null,
  circuitLengthM: number,
): FocusCue | null {
  const ordered = orderCodes(drivers);
  const code = focus && drivers[focus] ? focus : ordered[0] ?? null;
  if (!code) return null;
  const index = ordered.indexOf(code);
  const ahead = index > 0 ? ordered[index - 1] : null;
  const behind = index < ordered.length - 1 ? ordered[index + 1] : null;
  const self = drivers[code];
  return {
    code,
    position: Number.isFinite(self.position) ? self.position : index + 1,
    gapAheadS: ahead ? gapBetween(self.fraction, drivers[ahead].fraction, circuitLengthM).timeS : null,
    gapBehindS: behind ? gapBetween(self.fraction, drivers[behind].fraction, circuitLengthM).timeS : null,
    aheadCode: ahead,
    behindCode: behind,
    drs: isDrsActive(self.drs),
    inPit: drivers[code]?.in_pit === true,
  };
}

/** Green DRS splits along the outer edge, from ranges the replay already sends. */
export function drsZoneRanges(
  geometry: TrackGeometry | null,
): { start: number; end: number }[] {
  const zones = geometry?.drs_zones;
  if (!zones?.length) return [];
  const limit = geometry!.x_outer?.length ?? 0;
  return zones.filter(
    (zone) =>
      Number.isInteger(zone.start) &&
      Number.isInteger(zone.end) &&
      zone.start >= 0 &&
      zone.start < zone.end &&
      zone.start < limit,
  );
}
