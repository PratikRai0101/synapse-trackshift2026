import { expect, test } from "bun:test";
import { useViewerStore } from "../src/state/store";
import { simulateActors } from "../src/scene/actors";
import { fitCarScales } from "../src/scene/spacing";
import type { TelemetryMessage } from "../src/net/protocol";

export function packet(t = 0): TelemetryMessage {
  return {
    frame_index: Math.round(t * 60), frame: { t, lap: 1, drivers: {
      EGO: { x: 100, y: 200, speed: 72, gear: 4, drs: 0, throttle: 50,
        brake: 0, tyre: 2, lap: 1, rel_dist: 0, fraction: 0, position: 1 },
    }, safety_car: { x: 300, y: 400, phase: "on_track", alpha: 1 } },
    track_status: "1", playback_speed: 1, is_paused: false, total_frames: 100,
    circuit_length_m: 1000, driver_colors: {}, has_rc_data: false,
    race_control_events: [], selected_drivers: [],
    session_data: { time: "", time_s: t, lap: 1, leader: "EGO", total_laps: 3 },
    track_geometry: { x: [0, 1000, 1000, 0], y: [0, 0, 1000, 1000],
      x_inner: [100, 900, 900, 100], y_inner: [100, 100, 900, 900],
      x_outer: [-100, 1100, 1100, -100], y_outer: [-100, -100, 1100, 1100], rotation_deg: 0 },
    coordinate_units: "dm", source_id: "test-recording", run_mode: "recorded",
  } as TelemetryMessage;
}

test("FastF1 decimetres are converted once for cars, safety car and track", () => {
  useViewerStore.setState({ geometry: null, origin: null });
  const raw = packet();
  useViewerStore.getState().apply(raw);
  const state = useViewerStore.getState();
  expect(state.drivers!.EGO.x).toBe(10);
  expect(state.safetyCar!.y).toBe(40);
  expect(state.geometry!.x[1]).toBe(100);
  expect(raw.frame!.drivers.EGO.x).toBe(100);
});

test("physical car models never shrink or disappear at overlapping samples", () => {
  const actors = simulateActors([
    { key: "EGO", x: 0, y: 0, scale: 1 },
    { key: "RIV", x: 0, y: 0, scale: 1 },
  ], { x: 0, y: 0 }, 0);
  expect(fitCarScales(actors, 1)).toEqual([1, 1]);
});
