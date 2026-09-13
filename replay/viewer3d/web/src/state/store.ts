import { create } from "zustand";
import { toMetres } from "../net/coordinates";
import { playback } from "../net/playback";
import type { ChaseView } from "../scene/chase";
import type {
  DriverState,
  SafetyCarState,
  SessionData,
  TelemetryMessage,
  TrackGeometry,
} from "../net/protocol";

export interface WorldOrigin {
  x: number;
  y: number;
}

export type CameraMode = "orbit" | "follow";

const TRACK_STATUS_LABEL: Record<string, string> = {
  "1": "GREEN",
  "2": "YELLOW",
  "4": "SAFETY CAR",
  "5": "RED",
  "6": "VSC",
  "7": "VSC ENDING",
};

/**
 * Centre of the track's bounding box. Replay world coordinates are absolute
 * FastF1 metres, which are large and off-origin; every scene object is placed
 * relative to this so the camera can sit near (0, 0, 0).
 */
function computeOrigin(geometry: TrackGeometry): WorldOrigin {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (let i = 0; i < geometry.x.length; i += 1) {
    if (geometry.x[i] < minX) minX = geometry.x[i];
    if (geometry.x[i] > maxX) maxX = geometry.x[i];
    if (geometry.y[i] < minY) minY = geometry.y[i];
    if (geometry.y[i] > maxY) maxY = geometry.y[i];
  }

  return { x: (minX + maxX) / 2, y: (minY + maxY) / 2 };
}

interface ViewerState {
  connected: boolean;
  sourceId: string | null;
  coordinateUnits: "m" | "dm" | null;
  runMode: "recorded" | "simulated" | "synthetic" | "unknown";
  geometryProvenance: string;
  motionProvenance: string;
  simulation: TelemetryMessage["simulation"] | null;
  overlapCodes: string[];
  gapCodes: string[];
  /** Cars whose path this frame was reconstructed along the centreline. */
  reconstructedCodes: string[];
  setRenderWarnings: (overlaps: string[], gaps: string[], reconstructed: string[]) => void;
  hasData: boolean;
  geometry: TrackGeometry | null;
  origin: WorldOrigin | null;
  drivers: Record<string, DriverState> | null;
  driverColors: Record<string, string>;
  safetyCar: SafetyCarState | null;
  trackStatus: string;
  trackStatusLabel: string;
  session: SessionData | null;
  frameIndex: number;
  totalFrames: number;
  paused: boolean;
  speed: number;
  cameraMode: CameraMode;
  /** Strategy cues: DRS zones, focus ring, gap tether, focus strip. */
  showCues: boolean;
  /** Metres per lap; needed to turn lap fractions into gap distances. */
  circuitLengthM: number;
  toggleCues: () => void;
  /** Null keeps the chase camera on the live race leader. */
  followedDriver: string | null;
  chaseView: ChaseView;
  setChaseView: (view: ChaseView) => void;
  /**
   * Car size multiplier. A real car is ~5.6 m against a ~4 km circuit, i.e.
   * sub-pixel from the overview camera. Exaggerating the model is the 3D
   * equivalent of the 2D replay drawing 6 px circles.
   */
  carScale: number;
  showLabels: boolean;
  setConnected: (connected: boolean) => void;
  setCameraMode: (mode: CameraMode) => void;
  setFollowedDriver: (code: string | null) => void;
  setCarScale: (scale: number) => void;
  toggleLabels: () => void;
  apply: (message: TelemetryMessage) => void;
}

export const useViewerStore = create<ViewerState>((set) => ({
  connected: false,
  sourceId: null,
  coordinateUnits: null,
  runMode: "unknown",
  geometryProvenance: "Unspecified track geometry",
  motionProvenance: "Unspecified motion source",
  simulation: null,
  overlapCodes: [],
  gapCodes: [],
  reconstructedCodes: [],
  setRenderWarnings: (overlapCodes, gapCodes, reconstructedCodes) => set((state) =>
    state.overlapCodes.join() === overlapCodes.join() &&
    state.gapCodes.join() === gapCodes.join() &&
    state.reconstructedCodes.join() === reconstructedCodes.join()
      ? state : { overlapCodes, gapCodes, reconstructedCodes }),
  hasData: false,
  geometry: null,
  origin: null,
  drivers: null,
  driverColors: {},
  safetyCar: null,
  trackStatus: "1",
  trackStatusLabel: "GREEN",
  session: null,
  frameIndex: 0,
  totalFrames: 0,
  paused: false,
  speed: 1,
  cameraMode: "orbit",
  showCues: true,
  circuitLengthM: 0,
  toggleCues: () => set((state) => ({ showCues: !state.showCues })),
  followedDriver: null,
  chaseView: "chase",
  setChaseView: (chaseView) => set({ chaseView, cameraMode: "follow" }),
  // Keep cars at physical scale by default. Enlarged cars overlap at normal
  // racing gaps and look as if they are colliding.
  carScale: 1,
  showLabels: true,

  setConnected: (connected) => set({ connected }),
  setCameraMode: (cameraMode) => set({ cameraMode }),
  setFollowedDriver: (followedDriver) =>
    set({ followedDriver, cameraMode: "follow" }),
  setCarScale: (carScale) => set({ carScale }),
  toggleLabels: () => set((state) => ({ showLabels: !state.showLabels })),

  apply: (raw) =>
    set((state) => {
      const sourceId = raw.source_id ?? "legacy";
      const coordinateUnits = raw.coordinate_units ?? null;
      const changed = sourceId !== state.sourceId || coordinateUnits !== state.coordinateUnits;
      const message = toMetres({ ...raw,
        track_geometry: changed || !state.geometry ? raw.track_geometry : undefined });
      playback.push(message);
      const next: Partial<ViewerState> = {
        sourceId, coordinateUnits,
        runMode: message.run_mode ?? "unknown",
        geometryProvenance: message.geometry_provenance ?? "Unspecified track geometry",
        motionProvenance: message.motion_provenance ?? "Unspecified motion source",
        simulation: message.simulation ?? null,
        ...(changed ? { geometry: null, origin: null, overlapCodes: [], gapCodes: [], reconstructedCodes: [], driverColors: {} } : {}),
        hasData: true,
        drivers: message.frame?.drivers ?? null,
        safetyCar: message.frame?.safety_car ?? null,
        trackStatus: message.track_status,
        trackStatusLabel:
          TRACK_STATUS_LABEL[message.track_status] ?? message.track_status,
        session: message.session_data,
        frameIndex: message.frame_index,
        totalFrames: message.total_frames,
        circuitLengthM: message.circuit_length_m || (changed ? 0 : state.circuitLengthM),
        paused: message.is_paused,
        speed: message.playback_speed,
      };

      if (
        message.driver_colors &&
        Object.keys(message.driver_colors).length > 0
      ) {
        next.driverColors = message.driver_colors;
      }

      // Geometry is retained by the bridge and arrives once; capture the origin
      // at the same moment so track and cars share one coordinate frame.
      if (message.track_geometry && (changed || !state.geometry)) {
        next.geometry = message.track_geometry;
        next.origin = computeOrigin(message.track_geometry);
        // The playback buffer reconstructs sparse-sample paths along this line.
        playback.setTrack(message.track_geometry);
      }

      return next;
    }),
}));

// Dev affordance: lets tooling (and the console) inspect live state.
if (import.meta.env.DEV) {
  (globalThis as unknown as Record<string, unknown>).__viewer = useViewerStore;
}
