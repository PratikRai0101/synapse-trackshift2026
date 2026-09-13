import { expect, test } from "bun:test";
import {
  battleSet,
  drsZoneRanges,
  focusCue,
  gapBetween,
  isDrsActive,
  orderCodes,
  shouldDrawConnector,
} from "../src/scene/cues";
import type { DriverState, TrackGeometry } from "../src/net/protocol";

const LAP = 5000;
const driver = (over: Partial<DriverState>): DriverState => ({
  x: 0, y: 0, speed: 200, gear: 7, drs: 0, throttle: 100, brake: 0,
  tyre: 2, lap: 1, rel_dist: 0, position: 1, fraction: 0, ...over,
});

test("gap math matches the replay's distance / 55.56 m/s reference", () => {
  const { distanceM, timeS } = gapBetween(0.2, 0.1, LAP);
  expect(distanceM).toBeCloseTo(500);
  expect(timeS).toBeCloseTo(500 / 55.56);
});

test("a lapped car adjacent in track order is not tethered", () => {
  expect(shouldDrawConnector(0.4)).toBe(true);
  expect(shouldDrawConnector(3.0001)).toBe(false);
  expect(shouldDrawConnector(null)).toBe(false);
});

test("order and battle set mirror the replay focus mode", () => {
  const drivers = Object.fromEntries(
    ["VER", "NOR", "LEC", "PIA", "RUS"].map((code, index) => [
      code, driver({ position: index + 1, fraction: 1 - index * 0.01 }),
    ]),
  );
  const ordered = orderCodes(drivers);
  expect(ordered).toEqual(["VER", "NOR", "LEC", "PIA", "RUS"]);
  expect([...battleSet(ordered, "LEC")]).toEqual(["VER", "NOR", "LEC", "PIA", "RUS"]);
  expect([...battleSet(ordered, "VER")]).toEqual(["VER", "NOR", "LEC"]);
  expect([...battleSet(ordered, null)]).toEqual([]);
});

test("focus cue falls back to the leader and reports both gaps", () => {
  const drivers = {
    VER: driver({ position: 1, fraction: 0.5 }),
    NOR: driver({ position: 2, fraction: 0.49, drs: 12 }),
  };
  const cue = focusCue(drivers, null, LAP)!;
  expect(cue.code).toBe("VER");
  expect(cue.aheadCode).toBeNull();
  expect(cue.behindCode).toBe("NOR");
  expect(cue.gapBehindS).toBeCloseTo(50 / 55.56);
  expect(focusCue(drivers, "NOR", LAP)!.drs).toBe(true);
  expect(isDrsActive(4)).toBe(false);
});

test("DRS zone ranges are sanitized before they reach geometry", () => {
  const geometry = {
    x: [], y: [], x_inner: [], y_inner: [],
    x_outer: Array(100).fill(0), y_outer: Array(100).fill(0), rotation_deg: 0,
    drs_zones: [
      { start: 10, end: 40 },
      { start: 60, end: 55 },
      { start: -1, end: 10 },
      { start: 95, end: 200 },
    ],
  } as unknown as TrackGeometry;
  expect(drsZoneRanges(geometry)).toEqual([
    { start: 10, end: 40 },
    { start: 95, end: 200 },
  ]);
  expect(drsZoneRanges(null)).toEqual([]);
});
