/**
 * Synthetic source for developing the 3D viewer without running a race.
 *
 * Binds the same TCP port as the real `TelemetryStreamServer` and emits the
 * same newline-delimited JSON shape, driving 20 cars around a stadium-style
 * oval and shipping `track_geometry` every 120 frames.
 *
 *     bun run bridge/mock.ts      # then start the bridge + viewer as normal
 *
 * Useful for tuning camera, lighting and materials without waiting for a
 * 500 MB session pickle to load.
 */

const PORT = Number(process.env.TELEMETRY_PORT ?? 9999);
const FPS = 60;
const CAR_COUNT = 20;
const POINTS = 600;

// Stadium oval, metres. Half-straights joined by semicircles.
const STRAIGHT = 900;
const RADIUS = 400;

function ovalPoint(u: number): { x: number; y: number } {
  // u in [0, 1) around the loop
  const angle = u * Math.PI * 2;
  const straightHalf = STRAIGHT / 2;
  const perimeter = 2 * STRAIGHT + 2 * Math.PI * RADIUS;
  let d = u * perimeter;

  if (d < STRAIGHT) return { x: -straightHalf + d, y: -RADIUS };
  d -= STRAIGHT;
  if (d < Math.PI * RADIUS) {
    const a = d / RADIUS - Math.PI / 2;
    return { x: straightHalf + Math.cos(a) * RADIUS, y: Math.sin(a) * RADIUS };
  }
  d -= Math.PI * RADIUS;
  if (d < STRAIGHT) return { x: straightHalf - d, y: RADIUS };
  d -= STRAIGHT;
  const a = d / RADIUS + Math.PI / 2;
  return { x: -straightHalf + Math.cos(a) * RADIUS, y: Math.sin(a) * RADIUS };
}

function buildGeometry() {
  const x: number[] = [];
  const y: number[] = [];
  const xInner: number[] = [];
  const yInner: number[] = [];
  const xOuter: number[] = [];
  const yOuter: number[] = [];
  const halfWidth = 100;

  for (let i = 0; i < POINTS; i += 1) {
    const u = i / POINTS;
    const p = ovalPoint(u);
    const q = ovalPoint((i + 1) / POINTS);
    const tx = q.x - p.x;
    const ty = q.y - p.y;
    const len = Math.hypot(tx, ty) || 1;
    const nx = -ty / len;
    const ny = tx / len;

    x.push(p.x);
    y.push(p.y);
    xInner.push(p.x - nx * halfWidth);
    yInner.push(p.y - ny * halfWidth);
    xOuter.push(p.x + nx * halfWidth);
    yOuter.push(p.y + ny * halfWidth);
  }

  return {
    x,
    y,
    x_inner: xInner,
    y_inner: yInner,
    x_outer: xOuter,
    y_outer: yOuter,
    rotation_deg: 0,
  };
}

const GEOMETRY = buildGeometry();
const PERIMETER =
  2 * STRAIGHT + 2 * Math.PI * RADIUS;

const TEAMS = [
  "#3671C6", "#FF8000", "#E8002D", "#27F4D2", "#229971",
  "#FF87BC", "#64C4FF", "#6692FF", "#B6BABD", "#52E252",
];
const CODES = [
  "VER", "NOR", "LEC", "PIA", "RUS", "HAM", "SAI", "ALO", "TSU", "STR",
  "GAS", "OCO", "ALB", "HUL", "RIC", "BOT", "MAG", "ZHO", "SAR", "DEV",
];

const driverColors: Record<string, string> = {};
CODES.forEach((code, i) => {
  driverColors[code] = TEAMS[i % TEAMS.length];
});

let frameIndex = 0;
let t = 0;
type Conn = { write(data: string): number };
const clients = new Set<Conn>();

function makeFrame() {
  const drivers: Record<string, unknown> = {};
  const leaderFrac = (t * 55) / PERIMETER;

  CODES.forEach((code, i) => {
    const offset = i * 0.0016;
    const u = (leaderFrac - offset + 1) % 1;
    const p = ovalPoint(u);
    const ahead = ovalPoint((u + 0.002) % 1);
    const vx = ahead.x - p.x;
    const vy = ahead.y - p.y;
    const speed = 240 + Math.sin(t * 0.5 + i) * 40;

    drivers[code] = {
      x: p.x,
      y: p.y,
      speed,
      gear: 7,
      drs: i % 4 === 0 ? 12 : 0,
      throttle: 100,
      brake: 0,
      tyre: 3,
      lap: 1 + Math.floor(leaderFrac),
      rel_dist: u,
      position: i + 1,
      fraction: u,
      // Not part of the real payload, but handy for the mock renderer.
      _vx: vx,
      _vy: vy,
    };
  });

  t += 1 / FPS;
  frameIndex += 1;

  return {
    frame_index: frameIndex,
    frame: {
      drivers,
      safety_car: null,
      lap: 1 + Math.floor(leaderFrac),
      t,
      weather: {
        air_temp: 19,
        track_temp: 27,
        humidity: 55,
        wind_speed: 1.2,
        wind_direction: 180,
        rain_state: "DRY",
      },
    },
    track_status: "1",
    playback_speed: 1,
    is_paused: false,
    total_frames: 100000,
    circuit_length_m: PERIMETER,
    driver_colors: driverColors,
    has_rc_data: false,
    race_control_events: [],
    session_data: {
      time: "00:00:00",
      time_s: t,
      lap: 1 + Math.floor(leaderFrac),
      leader: "VER",
      total_laps: 57,
    },
    selected_drivers: [],
    ...(frameIndex % 120 === 1 ? { track_geometry: GEOMETRY } : {}),
  };
}

Bun.listen({
  hostname: "127.0.0.1",
  port: PORT,
  socket: {
    open(socket) {
      clients.add(socket as unknown as Conn);
      console.log(`[mock] client connected (${clients.size})`);
    },
    close(socket) {
      clients.delete(socket as unknown as Conn);
    },
    data() {},
  },
});

console.log(`[mock] synthetic telemetry on tcp://127.0.0.1:${PORT} (${FPS} fps)`);

setInterval(() => {
  if (clients.size === 0) return;
  const line = `${JSON.stringify(makeFrame())}\n`;
  for (const client of clients) {
    try {
      client.write(line);
    } catch {
      clients.delete(client);
    }
  }
}, 1000 / FPS);
