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
| `VIEW` | Chase, broadcast or overhead follow framing |
| `CUES` | DRS zones, focus ring and gap tether (on by default) |
| `SIZE` | Maximum car scale: 1x, 1.5x, 2x, 3x, 5x; auto-fitted to available space |
| `LABELS` | Driver code tags above each car |

### Why cars are scaled up

A real car is ~5.6 m long; the circuit data here is a stylised ~200 m wide
ribbon spanning several kilometres, so a true-scale car is sub-pixel from the
default camera. The magnifier is the 3D equivalent of the 2D replay drawing
6 px circles. The default maximum is 1x; raise it for detail.

Oriented car bounds automatically limit each model's size when cars get close,
including side-by-side cars. Size is restored gradually as space opens up.
This is a presentation adjustment, **not collision physics**: telemetry positions,
order and gaps are never changed. When telemetry supplies identical coordinates,
there is no room for either mesh; both reduce to zero size, with driver labels
still available when LABELS is enabled. Small models can therefore indicate
crowded or ambiguous telemetry, not actual smaller vehicles.

Labels are sized from camera distance every frame, so they stay a constant
number of screen pixels at any zoom.

## Dev tooling

`bun run shot` drives the viewer in headless Chromium and writes orbit and
follow captures to `.shots/`. It uses a locally installed Chromium-family
browser; override with `BROWSER_PATH=/path/to/browser bun run shot`. This is how
the scene was tuned — screenshots beat guessing when the feedback loop is a
renderer.

## Strategy cues

The viewer does not re-implement strategy. Cues are derived from the same public
telemetry the 2D replay uses, with the replay's own rules copied deliberately so
the two cannot disagree:

| Cue | Source |
|---|---|
| DRS zone markings on track | `drs_zones` index ranges, computed by the 2D replay |
| Focus ring under the followed car | selection; green when that car's DRS is open |
| Gap tether to the car ahead | `gap_between` math, drawn only within the connector window |
| `AHEAD` / `BEHIND` strip | focus-driver gaps, position and DRS |

Rules mirrored from `replay/src/interfaces/race_replay.py`: `gap_between`
(distance / 55.56 m/s), `_battle_set` (focus car +- `focus_radius` = 2) and
`MAX_CONNECTOR_SECONDS` = 3. `isDrsActive` mirrors the `8/10/12/14` overlay
codes.

All of it is a **rendering of public evidence**, not battery state. The replay's
energy and overtake outputs are belief estimates; show those on the focus strip
only from a real backend payload rather than recomputing them here.

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
- `track_geometry` — centreline plus `inner`/`outer` edges, and `drs_zones`
  (`{start, end}` index ranges into the outer edge, reused from the 2D replay)
- `session_data`, `track_status`, `playback_speed`, `is_paused`

## Known limits

- **No elevation.** FastF1 telemetry carries no reliable height, so the circuit
  is flat.
- **Heading follows observed motion**, with time-based angular smoothing and a
  small noise threshold. The track tangent initializes stationary/new cars.
- **Playback is interpolation, not a physics simulation.** Cars reach their
  latest sample in a bounded interval, stop exactly when paused, and reset on
  detected seeks rather than accelerating or driving backwards to old positions.
- **High playback speeds** (64x+) make cars jump large distances per tick; jumps
  beyond 250 m are applied instantly rather than interpolated.
- **Race sessions only.** `run_qualifying_replay` never starts the telemetry
  server, so there is nothing to consume for qualifying.
- **Sparse telemetry** can still draw straight segments across a corner. The
  viewer does not invent missing racing lines or treat recorded overlaps as
  evidence of a real collision.

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

**The chase camera reads the rendered actor.** Fleet updates run before the
camera. Both eye and look target share the actor's translation; heading and
view offsets are smoothed in car-relative space, avoiding independent world-space
lags. This also allows pit-lane motion to differ from the circuit centreline.

Run `bun run test` for motion, pause/seek, frame-rate, spacing, model bounds and
camera-framing regressions. These are numerical checks, not visual validation.
