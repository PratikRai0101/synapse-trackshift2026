import { useViewerStore } from "../state/store";
import { focusCue } from "../scene/cues";

const TYRE_LABEL: Record<number, string> = {
  1: "S",
  2: "M",
  3: "H",
  4: "I",
  5: "W",
};

const TYRE_COLOR: Record<number, string> = {
  1: "#e8453c",
  2: "#f0d33a",
  3: "#e8e8e8",
  4: "#3fbf5f",
  5: "#3f7fe0",
};

const STATUS_COLOR: Record<string, string> = {
  GREEN: "#3ddc84",
  YELLOW: "#ffd23f",
  "SAFETY CAR": "#ffa726",
  VSC: "#ffa726",
  "VSC ENDING": "#ffa726",
  RED: "#ff4d4d",
};

/**
 * DOM overlay. Deliberately plain: the 3D canvas owns the pixels, this owns
 * the text, so neither has to compromise.
 */
export function Hud() {
  const connected = useViewerStore((state) => state.connected);
  const session = useViewerStore((state) => state.session);
  const drivers = useViewerStore((state) => state.drivers);
  const driverColors = useViewerStore((state) => state.driverColors);
  const trackStatusLabel = useViewerStore((state) => state.trackStatusLabel);
  const frameIndex = useViewerStore((state) => state.frameIndex);
  const totalFrames = useViewerStore((state) => state.totalFrames);
  const speed = useViewerStore((state) => state.speed);
  const paused = useViewerStore((state) => state.paused);
  const cameraMode = useViewerStore((state) => state.cameraMode);
  const setCameraMode = useViewerStore((state) => state.setCameraMode);
  const followedDriver = useViewerStore((state) => state.followedDriver);
  const setFollowedDriver = useViewerStore((state) => state.setFollowedDriver);
  const chaseView = useViewerStore((state) => state.chaseView);
  const setChaseView = useViewerStore((state) => state.setChaseView);
  const showCues = useViewerStore((state) => state.showCues);
  const toggleCues = useViewerStore((state) => state.toggleCues);
  const circuitLengthM = useViewerStore((state) => state.circuitLengthM);

  const cue = drivers ? focusCue(drivers, followedDriver, circuitLengthM) : null;

  const gapText = (value: number | null) =>
    value == null ? "—" : `+${value.toFixed(1)}s`;
  const carScale = useViewerStore((state) => state.carScale);
  const setCarScale = useViewerStore((state) => state.setCarScale);
  const showLabels = useViewerStore((state) => state.showLabels);
  const toggleLabels = useViewerStore((state) => state.toggleLabels);

  const leaderboard = drivers
    ? Object.entries(drivers)
        .sort(([, a], [, b]) => a.position - b.position)
        .slice(0, 20)
    : [];

  return (
    <div className="hud">
      <header className="hud__bar">
        <span className={`dot ${connected ? "dot--on" : "dot--off"}`} />
        <span className="hud__title">
          {session ? `LAP ${session.lap}/${session.total_laps}` : "WAITING FOR TELEMETRY"}
        </span>
        <span className="hud__spacer" />
        <span
          className="hud__status"
          style={{ color: STATUS_COLOR[trackStatusLabel] ?? "#c8d0dc" }}
        >
          {trackStatusLabel}
        </span>
        <span className="hud__meta">
          {paused ? "PAUSED" : `${speed}x`}
        </span>
        <span className="hud__meta">
          {totalFrames > 0
            ? `${((frameIndex / totalFrames) * 100).toFixed(1)}%`
            : "—"}
        </span>
        <button
          className="hud__button"
          type="button"
          onClick={() => setCameraMode(cameraMode === "orbit" ? "follow" : "orbit")}
        >
          CAM: {cameraMode.toUpperCase()}
        </button>
        <button
          className={`hud__button ${followedDriver ? "hud__button--on" : ""}`}
          type="button"
          title="Return the follow camera to the live race leader"
          onClick={() => setFollowedDriver(null)}
        >
          FOLLOW: {followedDriver ?? "LEADER"}
        </button>
        <label className="hud__view">
          VIEW
          <select aria-label="Follow camera view" className="hud__button"
            value={chaseView}
            onChange={(event) => setChaseView(event.target.value as typeof chaseView)}>
            <option value="chase">CHASE</option>
            <option value="broadcast">BROADCAST</option>
            <option value="overhead">OVERHEAD</option>
          </select>
        </label>
        <button
          className="hud__button"
          type="button"
          onClick={() => {
            const steps = [1, 1.5, 2, 3, 5];
            const next = steps[(steps.indexOf(carScale) + 1) % steps.length];
            setCarScale(next ?? 1);
          }}
        >
          SIZE: ≤{carScale}x
        </button>
        <button
          className={`hud__button ${showCues ? "hud__button--on" : ""}`}
          type="button"
          title="DRS zones, focus ring and gap tether"
          onClick={toggleCues}
        >
          CUES
        </button>
        <button
          className={`hud__button ${showLabels ? "hud__button--on" : ""}`}
          type="button"
          onClick={toggleLabels}
        >
          LABELS
        </button>
      </header>

      {showCues && cue && (
        <div className="cues">
          <span className="cues__code">{cue.code}</span>
          <span className="cues__item">P{cue.position}</span>
          <span className="cues__item" title="Gap to the car ahead">
            AHEAD {gapText(cue.gapAheadS)}
          </span>
          <span className="cues__item" title="Gap to the car behind">
            BEHIND {gapText(cue.gapBehindS)}
          </span>
          {cue.drs && <span className="cues__flag">DRS</span>}
        </div>
      )}

      {leaderboard.length > 0 && (
        <aside className="hud__board">
          {leaderboard.map(([code, driver]) => (
            <button
              className={`row ${followedDriver === code ? "row--selected" : ""}`}
              key={code}
              type="button"
              title={`Follow ${code}`}
              onClick={() => setFollowedDriver(code)}
            >
              <span className="row__pos">{driver.position}</span>
              <span
                className="row__chip"
                style={{ background: driverColors[code] ?? "#6b7280" }}
              />
              <span className="row__code">{code}</span>
              <span className="row__gap" />
              <span className="row__speed">{Math.round(driver.speed)}</span>
              <span
                className="row__tyre"
                style={{ color: TYRE_COLOR[Math.round(driver.tyre)] ?? "#c8d0dc" }}
              >
                {TYRE_LABEL[Math.round(driver.tyre)] ?? "?"}
              </span>
            </button>
          ))}
        </aside>
      )}
    </div>
  );
}
