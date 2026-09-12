# F1 Replay — 3D Companion Viewer

A real-time 3D companion to the existing replay window. It renders the same
session in three dimensions (circuit, kerbs, 20 cars, safety car) and runs
entirely beside the current app.

> **This folder is additive.** Nothing in `src/`, `main.py` or `requirements.txt`
> was changed to support it. Delete `viewer3d/` and the Python application is
> byte-identical to before.

## How it connects

```
arcade replay process            bridge                  browser
TelemetryStreamServer  ──TCP──▶  TCP client  ──WS──▶     Three.js viewer
localhost:9999                   localhost:9998           localhost:5173
```

The Python app already broadcasts JSON telemetry on `localhost:9999` whenever
the replay runs with telemetry enabled (`main.py` passes
`enable_telemetry=True` for race sessions). The bridge translates that raw TCP
stream into a WebSocket because browsers cannot open TCP sockets.

The bridge is a pure pass-through with two jobs:

- **Coalescing** — the source emits ~60 messages/sec; the bridge keeps only the
  newest and flushes at `FLUSH_HZ` (default 30).
- **Retention** — `track_geometry` is only sent every ~120 frames. The bridge
  keeps the last copy and re-injects it, so a coalesced packet can't lose the
  circuit mesh.

It also strips `lap_times` and `status_laps`, which the live server repeats on
every tick and this viewer never reads.

## Running

Requires [Bun](https://bun.sh). Install once:

```bash
cd viewer3d
bun install
```

**Option A — real race.** Start the existing app as usual, then:

```bash
cd viewer3d && bun run dev
```

Open <http://localhost:5173>. The replay must already be running so the server
on `:9999` is live; the bridge retries every 2s until it is.

**Option B — no race needed.** A synthetic source drives 20 cars around a
stadium oval so you can develop without loading a 500 MB session pickle:

```bash
# terminal 1
cd viewer3d && bun run mock

# terminal 2
cd viewer3d && bun run dev
```

| Command | Purpose |
|---|---|
| `bun run dev` | Bridge + Vite dev server together |
| `bun run mock` | Synthetic telemetry on `:9999` |
| `bun run shot` | Headless screenshot of orbit + follow views into `.shots/` |
| `bun run build` | Production bundle in `web/dist` |
| `bun run typecheck` | Typecheck bridge, tools and web |

Environment overrides: `TELEMETRY_PORT` (9999), `WS_PORT` (9998),
`FLUSH_HZ` (30), `VITE_BRIDGE_URL` for the viewer.

## Controls

| Control | Effect |
|---|---|
| `CAM` | Toggle `ORBIT` (free orbit over the circuit) / `FOLLOW` (chase camera) |
| `FOLLOW` | Show the chase target; click it to return to the live leader |
| Leaderboard row | Follow that driver immediately |
| `SIZE` | Car scale: 1x, 1.5x, 2x, 3x, 5x |
| `LABELS` | Driver code tags above each car |

### Why cars are scaled up

A real car is ~5.6 m long; the circuit data here is a stylised ~200 m wide
ribbon spanning several kilometres, so a true-scale car is sub-pixel from the
default camera. The magnifier is the 3D equivalent of the 2D replay drawing
6 px circles. Drop it to 1x for a literal view, raise it for detail.

Labels are sized from camera distance every frame, so they stay a constant
number of screen pixels at any zoom.

## Dev tooling

`bun run shot` drives the viewer in headless Chromium and writes orbit and
follow captures to `.shots/`. It uses a locally installed Chromium-family
browser; override with `BROWSER_PATH=/path/to/browser bun run shot`. This is how
the scene was tuned — screenshots beat guessing when the feedback loop is a
renderer.

## Camera

The **CAM** button in the HUD toggles between:

- `ORBIT` — free orbit over the whole circuit (drag / scroll).
- `FOLLOW` — chases the selected driver from behind and above. Click any
  leaderboard row to select a car, or click **FOLLOW** to return to the live
  race leader.

## Swapping in a real car model

The default car is a generic open-wheel model built from primitives, tinted per
team from `driver_colors` in the telemetry payload. Real F1 geometry and liveries
are trademarked, so team colour is applied to a neutral shape.

To use a GLTF instead, drop it at `web/public/models/car.glb`. See
[`web/public/models/README.md`](web/public/models/README.md) for sourcing and
licensing notes, and `web/src/scene/carParts.ts` for the current definition.

## Data the viewer depends on

The JSON payload from `_broadcast_telemetry_state()` is the only contract:

- `frame.drivers[CODE]` — `x`, `y`, `speed`, `gear`, `drs`, `throttle`,
  `brake`, `tyre`, `lap`, `position`, `fraction`
- `frame.safety_car` — `x`, `y`, `phase`, `alpha`
- `driver_colors` — `CODE -> "#RRGGBB"`
- `track_geometry` — centreline plus `inner`/`outer` edges
- `session_data`, `track_status`, `playback_speed`, `is_paused`

## Known limits

- **No elevation.** FastF1 telemetry carries no reliable height, so the circuit
  is flat.
- **Heading uses the track tangent** when lap fraction and geometry are
  available, with a smoothed position-delta fallback for incomplete telemetry.
- **High playback speeds** (64x+) make cars jump large distances per tick; jumps
  beyond 250 m are applied instantly rather than interpolated.
- **Race sessions only.** `run_qualifying_replay` never starts the telemetry
  server, so there is nothing to consume for qualifying.
- **Bunched packs can overlap at enlarged car scales**, since those models are
  intentionally larger than real racing gaps. The default 1x scale preserves
  physical spacing.

## Troubleshooting the renderer

Two failures that look like "cars are off the track" and are not:

**The track is invisible, so cars look like they float.** The asphalt colour has
to contrast with the ground plane. If you retune colours, check both views with
`bun run shot` — a colour that reads on the follow camera can vanish on the
overview and vice versa.

**`logarithmicDepthBuffer` is required.** The circuit spans kilometres while the
track surface sits only ~1 m above the ground plane. With a linear depth buffer
and a large `far` plane the ground punches through the track, which presents as
the circuit partially disappearing at orbit distance. Do not remove it from the
Canvas `gl` props, and keep `near` well above 1.

**Chase-camera heading comes from the track, not the car.** The follow camera
takes its direction of travel from the centreline tangent at the followed car's
`fraction` (`trackHeading()` in `scene/world.ts`), falling back to the car's own
smoothed yaw only when `fraction` is unavailable.

Do not reintroduce a heading derived from a single position delta. Position
deltas are dominated by floating-point noise, especially at low speed, and the
follow camera sits tens of metres behind the car — a few degrees of heading
noise becomes metres of lateral camera movement per frame. Measured heading
"jerk" (mean absolute second difference, sampled in headless Chromium at ~9 fps):

| Source | Jerk |
|---|---|
| Raw single-frame delta (original behaviour) | 0.296° |
| Smoothed velocity vector | 0.024° |
| **Track tangent (current camera)** | **0.027°** |

Roughly an 11x reduction against the original. `tools/screenshot.ts` captures
stills, but wobble needs the metric above, not a screenshot.
