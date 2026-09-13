import { expect, test } from "bun:test";
import { PlaybackBuffer } from "../src/net/playback";
import { TrackPath, trackPath } from "../src/net/trackPath";
import type { DriverState, TelemetryMessage, TrackGeometry } from "../src/net/protocol";

/**
 * A closed rectangular centreline, 400 m x 400 m, so the arc-length table has a
 * genuine perimeter and a genuine 90-degree corner:
 *
 *   (0,400) -------- (400,400)      s = 400..800 along the top
 *      |                  |
 *      |                  |         s = 800..1200 down the right
 *   (0,0) --------- (400,0)         s = 1200..1600 along the bottom
 *
 * The top-left corner sits at s = 400, which is what a straight chord between
 * two samples either side of it cuts across.
 */
const SIDE = 400;
const PERIMETER = 1600;

function loopGeometry(): TrackGeometry {
  const x: number[] = [];
  const y: number[] = [];
  for (let i = 0; i < 100; i++) { x.push(0); y.push(i * 4); }              // left, up
  for (let i = 0; i < 100; i++) { x.push(i * 4); y.push(SIDE); }           // top, right
  for (let i = 0; i < 100; i++) { x.push(SIDE); y.push(SIDE - i * 4); }    // right, down
  for (let i = 0; i < 100; i++) { x.push(SIDE - i * 4); y.push(0); }       // bottom, left
  const half = 3;
  return {
    x, y,
    x_inner: x, y_inner: y, x_outer: x, y_outer: y,
    rotation_deg: 0, track_width: half * 2,
    track_width_kind: "schematic_constant_offset",
  };
}

/** A long thin loop, so a car on one side never projects onto the other. */
function straightGeometry(): TrackGeometry {
  const x: number[] = [];
  const y: number[] = [];
  for (let i = 0; i <= 100; i++) { x.push(i * 4); y.push(0); }
  for (let i = 100; i >= 0; i--) { x.push(i * 4); y.push(40); }
  return {
    x, y, x_inner: x, y_inner: y, x_outer: x, y_outer: y,
    rotation_deg: 0, track_width: 6,
  };
}

const driver = (over: Partial<DriverState>): DriverState => ({
  x: 0, y: 0, speed: 200, gear: 7, drs: 0, throttle: 100, brake: 0,
  tyre: 2, lap: 1, rel_dist: 0, position: 1, fraction: 0, ...over,
});

function packet(t: number, drivers: Record<string, DriverState>, geometry: TrackGeometry): TelemetryMessage {
  return {
    frame_index: Math.round(t * 30), frame: { t, lap: 1, drivers, safety_car: null },
    track_status: "1", playback_speed: 1, is_paused: false, total_frames: 9999,
    circuit_length_m: PERIMETER, driver_colors: {}, has_rc_data: false,
    race_control_events: [], selected_drivers: [],
    session_data: { time: "", time_s: t, lap: 1, leader: "A", total_laps: 3 },
    track_geometry: geometry, coordinate_units: "m", source_id: "test",
  } as TelemetryMessage;
}

test("a straight chord across a corner is replaced by the centreline path", () => {
  const geometry = loopGeometry();
  const path = trackPath(geometry)!;
  const buffer = new PlaybackBuffer();
  buffer.setTrack(geometry);

  // Two samples 0.2 s apart straddling the top-left corner, at 180 km/h so the
  // separation is consistent with the reported speed.
  buffer.push(packet(0, { A: driver({ x: 0, y: 395, speed: 180, fraction: 395 / PERIMETER }) }, geometry), 0);
  buffer.push(packet(0.2, { A: driver({ x: 5, y: 400, speed: 180, fraction: 405 / PERIMETER }) }, geometry), 0.2);

  const car = buffer.sample(0.2)!.drivers.A;

  // The fixture really does cut the corner: the chord's midpoint misses the line.
  const chordMid = path.locate(2.5, 397.5)!;
  expect(chordMid.offCentre).toBeGreaterThan(2);

  // The reconstructed position stays on the track and between the samples.
  const projection = path.locate(car.x, car.y)!;
  expect(projection.offCentre).toBeLessThan(0.2);
  expect(projection.s).toBeGreaterThan(395);
  expect(projection.s).toBeLessThan(405);
  expect(car.motion_quality).toBe("reconstructed");
});

test("dense samples are untouched and do no projection work", () => {
  const geometry = straightGeometry();
  const buffer = new PlaybackBuffer();
  buffer.setTrack(geometry);
  // 4 m apart, well below the routing threshold: a chord cannot cut anything.
  buffer.push(packet(0, { A: driver({ x: 100, y: 0, fraction: 0.1 }) }, geometry), 0);
  buffer.push(packet(1 / 30, { A: driver({ x: 104, y: 0, fraction: 0.11 }) }, geometry), 1 / 30);

  const car = buffer.sample(1 / 60 + 0.1)!.drivers.A;
  expect(car.motion_quality).toBe("sampled");
  expect(car.x).toBeGreaterThanOrEqual(100);
  expect(car.x).toBeLessThanOrEqual(104);
});

test("sparse samples on a straight stay on the chord, not rerouted", () => {
  const geometry = straightGeometry();
  const buffer = new PlaybackBuffer();
  buffer.setTrack(geometry);
  buffer.push(packet(0, { A: driver({ x: 100, y: 0, speed: 900, fraction: 0.1 }) }, geometry), 0);
  buffer.push(packet(0.4, { A: driver({ x: 200, y: 0, speed: 900, fraction: 0.2 }) }, geometry), 0.4);

  // Arc length equals chord length on a straight, so the ratio test declines.
  const car = buffer.sample(0.3)!.drivers.A;
  expect(car.motion_quality).toBe("sampled");
  expect(car.y).toBeCloseTo(0, 6);
});

test("off-track samples are never snapped onto the racing line", () => {
  const geometry = loopGeometry();
  const buffer = new PlaybackBuffer();
  buffer.setTrack(geometry);
  // 30 m off the line: pit lane or off track, so the arc position is unusable.
  buffer.push(packet(0, { A: driver({ x: -30, y: 380, speed: 180, fraction: 0.23 }) }, geometry), 0);
  buffer.push(packet(0.2, { A: driver({ x: -28, y: 400, speed: 180, fraction: 0.25 }) }, geometry), 0.2);

  const car = buffer.sample(0.2)!.drivers.A;
  expect(car.motion_quality).toBe("sampled");
  expect(car.x).toBeLessThan(0);
});

test("a gap the buffer treats as discontinuous is never bridged", () => {
  const geometry = loopGeometry();
  const buffer = new PlaybackBuffer();
  buffer.setTrack(geometry);
  // 3 s apart: beyond the interpolation window, so the buffer restarts instead
  // of inventing a path across it.
  buffer.push(packet(0, { A: driver({ x: 0, y: 395, speed: 180, fraction: 395 / PERIMETER }) }, geometry), 0);
  buffer.push(packet(3, { A: driver({ x: 5, y: 400, speed: 180, fraction: 405 / PERIMETER }) }, geometry), 3);

  for (const now of [1.1, 2.1, 3.0]) {
    const car = buffer.sample(now)!.drivers.A;
    expect(car.motion_quality).not.toBe("reconstructed");
    expect(car.y).toBe(400);
  }
});

test("an interval implying impossible travel is held rather than reconstructed", () => {
  const geometry = loopGeometry();
  const buffer = new PlaybackBuffer();
  buffer.setTrack(geometry);
  // 0.4 s apart but 100 m apart on track: 900 km/h implied at 180 km/h reported.
  buffer.push(packet(0, { A: driver({ x: 0, y: 395, speed: 180, fraction: 395 / PERIMETER }) }, geometry), 0);
  buffer.push(packet(0.4, { A: driver({ x: 300, y: 400, speed: 180, fraction: 700 / PERIMETER }) }, geometry), 0.4);

  const car = buffer.sample(0.3)!.drivers.A;
  expect(car.motion_quality).toBe("gap");
  expect(car.y).toBe(395);
});

test("reconstruction carries the recorded lateral offset through the corner", () => {
  const geometry = loopGeometry();
  const path = trackPath(geometry)!;
  const buffer = new PlaybackBuffer();
  buffer.setTrack(geometry);
  // Both samples are 1.5 m inside the line, which must survive the corner.
  buffer.push(packet(0, { A: driver({ x: 1.5, y: 395, speed: 180, fraction: 395 / PERIMETER }) }, geometry), 0);
  buffer.push(packet(0.2, { A: driver({ x: 6.5, y: 400, speed: 180, fraction: 405 / PERIMETER }) }, geometry), 0.2);

  const car = buffer.sample(0.2)!.drivers.A;
  const projection = path.locate(car.x, car.y)!;
  expect(projection.offCentre).toBeGreaterThan(0.5);
  expect(projection.offCentre).toBeLessThan(3);
});

test("track path resolves arc length, tangents and lateral sign consistently", () => {
  const path = new TrackPath(loopGeometry());
  expect(path.usable).toBe(true);
  expect(path.total).toBeCloseTo(PERIMETER, 6);
  expect(path.halfWidth).toBe(3);

  expect(path.headingAt(200)).toBeCloseTo(0, 6);           // up the left side
  expect(path.headingAt(600)).toBeCloseTo(Math.PI / 2, 6); // right along the top
  expect(path.headingAt(1000)).toBeCloseTo(Math.PI, 6);    // down the right side

  const onLine = path.locate(0, 200)!;
  expect(onLine.s).toBeCloseTo(200, 6);
  expect(onLine.offCentre).toBeCloseTo(0, 6);

  // Signed lateral offset must round-trip through pointAt.
  const point = path.pointAt(200, 2);
  const back = path.locate(point.x, point.y)!;
  expect(back.s).toBeCloseTo(200, 6);
  expect(back.lateral).toBeCloseTo(2, 6);
  expect(back.offCentre).toBeCloseTo(2, 6);
});

test("arc length wraps around the closing segment", () => {
  const path = new TrackPath(loopGeometry());
  const start = path.pointAt(0);
  const end = path.pointAt(path.total);
  expect(end.x).toBeCloseTo(start.x, 6);
  expect(end.y).toBeCloseTo(start.y, 6);
  const nearLine = path.pointAt(1599);
  expect(path.locate(nearLine.x, nearLine.y)!.s).toBeCloseTo(1599, 6);
});

test("a degenerate centreline is reported as unusable instead of throwing", () => {
  const empty = {
    x: [0], y: [0], x_inner: [], y_inner: [], x_outer: [], y_outer: [], rotation_deg: 0,
  } as TrackGeometry;
  expect(trackPath(empty)).toBeNull();
  expect(trackPath(null)).toBeNull();
  expect(new TrackPath(empty).usable).toBe(false);
});
