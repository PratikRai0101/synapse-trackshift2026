import { beforeEach, describe, expect, test } from "bun:test";
import type { DriverState, TrackGeometry } from "../web/src/net/protocol";
import { useViewerStore } from "../web/src/state/store";
import { trackHeading } from "../web/src/scene/world";

const nonUniformTrack: TrackGeometry = {
  // Most samples are packed onto the first straight. Lap fraction is based on
  // distance, not point index; at 40% the car is on the northbound section.
  x: [0, 49, 50, 75, 100, 100, 0],
  y: [0, 0, 0, 0, 0, 100, 100],
  x_inner: [],
  y_inner: [],
  x_outer: [],
  y_outer: [],
  rotation_deg: 0,
};

const driver = (position: number): DriverState => ({
  x: 0,
  y: 0,
  speed: 200,
  gear: 7,
  drs: 0,
  throttle: 100,
  brake: 0,
  tyre: 2,
  lap: 1,
  rel_dist: 0,
  position,
  fraction: 0,
});

describe("viewer regressions", () => {
  beforeEach(() => {
    useViewerStore.setState({
      drivers: { VER: driver(1), NOR: driver(2) },
      cameraMode: "orbit",
    });
  });

  test("track heading follows arc length rather than non-uniform point indices", () => {
    const heading = trackHeading(0.4, nonUniformTrack);
    expect(heading).not.toBeNull();
    expect(Math.abs(heading!)).toBeLessThan(0.35);
  });

  test("a driver can be selected and remains the follow target", () => {
    const store = useViewerStore.getState() as ReturnType<typeof useViewerStore.getState> & {
      followedDriver?: string | null;
      setFollowedDriver?: (code: string) => void;
    };

    expect(typeof store.setFollowedDriver).toBe("function");
    store.setFollowedDriver!("NOR");
    expect((useViewerStore.getState() as typeof store).followedDriver).toBe("NOR");
    expect(useViewerStore.getState().cameraMode).toBe("follow");
  });
});
