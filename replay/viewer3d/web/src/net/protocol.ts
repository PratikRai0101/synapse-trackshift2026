/**
 * Wire contract.
 *
 * This mirrors the JSON payload produced by `_broadcast_telemetry_state()` in
 * `src/interfaces/race_replay.py` and forwarded by the bridge. The viewer reads
 * only these fields and never imports from the Python app, so the replay can
 * evolve as long as the shape below holds.
 */

export interface DriverState {
  x: number;
  y: number;
  speed: number;
  gear: number;
  drs: number;
  throttle: number;
  brake: number;
  tyre: number;
  lap: number;
  rel_dist: number;
  position: number;
  fraction: number;
  /** Source orientation in scene convention: atan2(vx, vy), radians. */
  heading?: number;
  in_pit?: boolean;
  motion_quality?: "sampled" | "gap" | "reconstructed";
}

export interface WeatherState {
  air_temp: number;
  track_temp: number;
  humidity: number;
  wind_speed: number;
  wind_direction: number;
  rain_state: string;
}

export interface SafetyCarState {
  x: number;
  y: number;
  phase: "deploying" | "on_track" | "returning";
  alpha: number;
}

export interface Frame {
  drivers: Record<string, DriverState>;
  safety_car?: SafetyCarState | null;
  lap: number;
  t: number;
  weather?: WeatherState;
}

/**
 * Sent intermittently (every ~120 frames) and retained by the bridge, so the
 * viewer can rely on it arriving exactly once.
 */
export interface TrackGeometry {
  x: number[];
  y: number[];
  x_inner: number[];
  y_inner: number[];
  x_outer: number[];
  y_outer: number[];
  rotation_deg: number;
  /** Measured ribbon width in source units, so the viewer never hard-codes it. */
  track_width?: number;
  /** "schematic_constant_offset" when the ribbon is a constant normal offset. */
  track_width_kind?: string;
  /** Index ranges into the outer edge. Reused from the 2D replay's zones. */
  drs_zones?: { start: number; end: number }[];
}

export interface SessionData {
  time: string;
  time_s: number;
  lap: number;
  leader: string;
  total_laps: number;
}

export interface TelemetryMessage {
  coordinate_units?: "m" | "dm";
  source_id?: string;
  run_mode?: "recorded" | "simulated" | "synthetic";
  geometry_provenance?: string;
  motion_provenance?: string;
  simulation?: { command: string; ego_energy: number; gap_s: number; contact: boolean; model: string };
  frame_index: number;
  frame: Frame | null;
  track_status: string;
  playback_speed: number;
  is_paused: boolean;
  total_frames: number;
  circuit_length_m: number;
  driver_colors: Record<string, string>;
  has_rc_data: boolean;
  race_control_events: unknown[];
  session_data: SessionData;
  selected_drivers: string[];
  track_geometry?: TrackGeometry;
}
