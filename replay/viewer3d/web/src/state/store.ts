import { create } from "zustand";
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
  /** Null keeps the chase camera on the live race leader. */
  followedDriver: string | null;
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
  followedDriver: null,
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

  apply: (message) =>
    set((state) => {
      const next: Partial<ViewerState> = {
        hasData: true,
        drivers: message.frame?.drivers ?? null,
        safetyCar: message.frame?.safety_car ?? null,
        trackStatus: message.track_status,
        trackStatusLabel:
          TRACK_STATUS_LABEL[message.track_status] ?? message.track_status,
        session: message.session_data,
        frameIndex: message.frame_index,
        totalFrames: message.total_frames,
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
      if (message.track_geometry && !state.geometry) {
        next.geometry = message.track_geometry;
        next.origin = computeOrigin(message.track_geometry);
      }

      return next;
    }),
}));

// Dev affordance: lets tooling (and the console) inspect live state.
if (import.meta.env.DEV) {
  (globalThis as unknown as Record<string, unknown>).__viewer = useViewerStore;
}
