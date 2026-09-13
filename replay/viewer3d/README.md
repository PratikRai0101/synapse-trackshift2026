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
| `SIZE` | Car scale: 1x, 1.5x, 2x, 3x, 5x (explicit magnification only) |
| `LABELS` | Driver tags; follow mode limits them to the focus car and two cars either side |

### Scale and units

FastF1 stores `X`/`Y` in **decimetres** while `Distance` is metres. The viewer
normalizes coordinates once at the wire boundary (`net/coordinates.ts`) and
then works in metres, so car size, track width and gap math share one unit.
A payload that does not declare `coordinate_units` is left untouched and the
HUD reports `UNNORMALIZED`. This conversion is why cars no longer disagree with
the ribbon they drive on.

Cars render at real size by default. A real car is ~5.6 m long and the circuit
ribbon is a stylised ~20 m wide centreline offset, so from the overview camera a
true-scale car is sub-pixel. `SIZE` is explicit user magnification, the 3D
equivalent of the 2D replay's 6 px circles.

### Overlapping samples are shown, not hidden

The viewer **does not shrink cars to avoid overlap**. When recorded positions
intersect, the overlap is real input, so it is displayed and reported:

- both cars keep full size, because silently shrinking them was a visual
  workaround that made ordered telemetry look like a physical collision;
- the HUD shows `AMBIGUOUS` with the affected codes;
- their labels gain a `?` and an amber tint;
- no lateral offset, collision force or position is invented.

A simulator, not the viewer, owns collision. When a `replay_ai` branch is
streamed, its contact decision arrives in `simulation.contact` and is displayed
as `CONTACT MODELLED`.

Labels are sized from camera distance every frame, so they stay a constant
number of screen pixels at any zoom. Recorded pit status (`in_pit`) tints a
label slate and adds `PIT` to the cue strip; the viewer does not infer a pit
lane.

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

## Why the leaderboard can differ from the 2D app

The payload carries **two different orderings** of the same field, and they drift
apart over a stint:

| Source | How it is derived |
|---|---|
| `position` (payload) | FastF1 `Distance` per lap, integrated |
| `fraction` (payload) | projection of the car's `x`/`y` onto the reference line |

Measured on the cached Italian GP race at the same frame: both sources advance at
exactly the reported speed (ratios 1.001-1.004 against `speed`), so neither is
jumping or glitched. They simply disagree by a roughly constant offset that
accumulates over the race. At lap 9 the two orderings reverse GAS and VER, with
about 110 m of accumulated drift between the two derivations.

Everything drawn is placed from `x`/`y`, so the viewer orders by `fraction`
(`trackProgress` in `scene/cues.ts`). Ordering by `position` instead would let the
leaderboard and the AHEAD/BEHIND cue contradict the cars actually rendered, which
is the reversal this replaced.

**Tradeoff, stated plainly:** the 2D leaderboard re-sorts by `(lap, dist)`
(`LeaderboardComponent.draw`), so in a drift case the 3D rank can differ from the
2D rank by one place. The 3D view is self-consistent — list, cue and cars agree —
but it does not reproduce the 2D numbers exactly. Single-sourcing the order in the
backend would make both agree; that changes 2D leaderboard behaviour, so it is a
deliberate decision rather than a rendering fix.

## Trajectory reconstruction

Between two observations the racing line is unknown. Interpolating a straight
chord across a corner is the one case where that ignorance is *visible*, because
the car leaves the track. Measured on the cached Italian GP race, a chord between
samples 0.33 s apart (sparse source, ~300 km/h) deviates by up to **5.05 m** from
the line at the first chicane — a quarter of the 20 m ribbon.

The buffer therefore reconstructs sparse intervals along the **centreline**
(`net/trackPath.ts`): it locates both samples on the arc-length table, follows the
track between those two positions, and carries the recorded lateral offset across,
so the car stays on the side of the track it was recorded on. It never invents a
racing line — it follows known geometry.

Engagement is deliberately narrow, and all three guards are real-data checked:

| Guard | Value | Effect on real Monza |
|---|---|---|
| Minimum chord | 6 m | Normal 30 Hz playback is ~2.8 m at 300 km/h, so no work is done at all |
| Arc must exceed chord by | 2 % | Engages on 3.5 % of spans (chicanes, corners); straights measure 1.0000 |
| Sample must be within | half the declared width | A car in the pit lane or off track is left on the chord |

A reconstructed frame is labelled `motion_quality: "reconstructed"` and counted
in the HUD (`RECONSTRUCTED · n`), so a followed path is never mistaken for a
measured one. Intervals that fail the plausibility checks are held and marked
`gap` instead, and the buffer treats anything over 0.5 s as discontinuous rather
than interpolating across it.

## Camera

The **CAM** button in the HUD toggles between:

- `ORBIT` — free orbit over the whole circuit (drag / scroll).
- `FOLLOW` — chases the selected driver from behind and above. Click any
  leaderboard row to select a car, or click **FOLLOW** to return to the live
  race leader.

## Visual presentation

- Procedural asphalt grain and grass textures, generated locally with mipmaps
  and anisotropic filtering; texture size is tied to world coordinates.
- Distance-based red/white kerb blocks, with an explicit lap seam. Partial DRS
  markings stay open rather than bridging their endpoints across the track.
- Neutral daylight sky and atmospheric haze, plus SMAA edge antialiasing. These
  are presentation choices, **not reconstructed event weather**.
- Tyre sidewall colours follow reported compound IDs; unknown values use grey.
- The top rear-wing flap follows the replay's existing DRS flag convention. It
  animates visually but does not change drag, authorize DRS or predict a pass.
- Batching: 4 merged body materials, 16 per-wheel batches so wheels can spin
  and steer independently, and one DRS flap.

This pass does not reconstruct surveyed track widths or add elevation.

These are the **remaining** realism gaps, tracked so they are not mistaken for
done:

- no surveyed track width, runoff, barriers or elevation;
- no brake glow or suspension travel;
- no camera distance/height control beyond the three presets.

## Scale agreement

The three things that must agree, and how each is held to the others:

| Quantity | Value | Enforced by |
|---|---|---|
| Units | metres after normalization | `net/coordinates.ts`, `realism.test.ts` |
| Car envelope | 5.5 m x 2.0 m | `CAR_DIMENSIONS`, asserted against the built mesh |
| Engine contact envelope | `CarPose(5.5, 2.0)` | `replay_ai/tests/test_race_physics.py` |

The pair of tests is deliberate: the engine decides contact from 5.5 m x 2.0 m,
so a mesh wider than that would let the viewer draw a touch the simulator does
not model. The mesh is 1.99 m x 5.48 m, just inside the envelope, and
`spacing.ts` uses the same extents so an `AMBIGUOUS` warning and a simulated
contact decision cannot disagree.

**Track width is declared, not assumed.** The ribbon is a constant normal
offset from the centreline, so its width is a property of the data rather than a
surveyed circuit. The payload states it (`track_geometry.track_width`) and says
it is schematic (`track_width_kind`). Kerb, edge-line and DRS-marking sizes are
derived from that declared width (`scene/surfaceSizes.ts`) instead of a
duplicated metre constant, and the HUD shows `TRACK 20.0m SCHEMATIC`. Real
circuits are ~12-15 m; the fallback when nothing is declared is 14 m.

Animated details are driven by observed motion, never by invented state:

- **DRS flap** follows the replay's existing flag convention. It does not change
  drag, authorize DRS or predict a pass.
- **Wheel spin** converts reported speed into rotation using the rendered radius.
  It is a display of distance already travelled.
- **Steering** uses the kinematic relation `tan(delta) = wheelbase * yawRate / speed`
  from the actor's own heading change, clamped to 0.55 rad and smoothed. At rest
  the ratio is unstable, so speed is floored rather than dividing by zero. It
  never feeds back into motion.
- **Tyre sidewalls** follow reported compound IDs; unknown values stay grey.

Wheels are baked around their own axle and batched per wheel, so `CarFleet` can
compose placement, steer and spin per frame without rebuilding geometry. That
costs 16 instanced draws instead of 4 merged ones; the whole field is 21 batches.

## Simulation mode

The viewer renders a `replay_ai` branch without knowing what a branch is. It
only reads the wire contract, so the same scene code draws a recorded race and
an evaluated counterfactual:

```
replay_ai closed-loop plant                       (owns motion + decision)
        ↓  scripts/simulate_stream.py             (same JSON schema)
bridge (:9999 TCP -> :9998 WS)                    (unchanged)
        ↓
viewer3d                                          (owns presentation only)
```

```bash
# terminal 1: a simulated branch (forced action, or omit for the reference)
cd replay_ai && .venv/bin/python scripts/simulate_stream.py --action BURN
# terminal 2: bridge + viewer
cd replay/viewer3d && bun run dev
```

Either the Python stream server or a dependency-free fallback socket serves the
payload, so this works headless.

What the viewer does with it:

- `run_mode` drives a colour-coded banner: `RECORDED REPLAY`, `SIMULATED
  BRANCH` or `SYNTHETIC SOURCE`. A simulated branch must never look like the
  recorded race.
- `simulation.command`, `gap_s`, `ego_energy` and `contact` are shown, using the
  simulator's own numbers rather than recomputed ones.
- `motion_provenance` and `geometry_provenance` are attached to the
  `PROVENANCE` tooltip so a synthetic display loop cannot be mistaken for a
  surveyed circuit.
- the hidden rival mode used for evaluation is never published.

## Swapping in a real car model

The default car is a generic open-wheel model built from primitives, tinted per
team from `driver_colors` in the telemetry payload. Real F1 geometry and liveries
are trademarked, so team colour is applied to a neutral shape.

The current renderer uses `web/src/scene/carParts.ts`; it does not automatically
load a GLTF dropped into `public/models`. A future asset loader must preserve
team/tyre tinting, the DRS hinge and instancing. See
[`web/public/models/README.md`](web/public/models/README.md) for sourcing notes.

## Data the viewer depends on

The JSON payload from `_broadcast_telemetry_state()` is the only contract.
Optional fields are all provenance or mode markers; a payload without them
still renders, just without the banner.

- `frame.drivers[CODE]` — `x`, `y` (decimetres), `speed`, `gear`, `drs`,
  `throttle`, `brake`, `tyre`, `lap`, `position`, `fraction`, and optional
  `heading`, `in_pit`, `motion_quality`
- `frame.safety_car` — `x`, `y`, `phase`, `alpha`
- `driver_colors` — `CODE -> "#RRGGBB"`
- `track_geometry` — centreline plus `inner`/`outer` edges, and `drs_zones`
  (`{start, end}` index ranges into the outer edge, reused from the 2D replay)
- `source_id`, `coordinate_units`, `run_mode` — mode and unit markers, so a new
  source resets retained state instead of splicing two sessions together
- `geometry_provenance`, `motion_provenance`, `simulation` — shown in the banner
- `session_data`, `track_status`, `playback_speed`, `is_paused`

## Known limits

- **No elevation.** FastF1 telemetry carries no reliable height, so the circuit
  is flat.
- **Heading follows observed motion**, with time-based angular smoothing and a
  small noise threshold. The track tangent initializes stationary/new cars.
- **Playback is a shared clock, not a physics simulation.** One display clock
  (100 ms behind the source, rate-limit corrected) samples recorded positions
  with monotone cubic interpolation, so motion no longer depends on packet
  arrival timing. Gaps longer than 0.5 s or faster than the reported speed
  allows are marked `motion_quality: "gap"` rather than bridged with an
  invented trajectory.
- **No steering model.** The viewer never invents lateral motion; recorded cars
  follow recorded positions and headings only.
- **`replay_ai`'s drag constant is uncalibrated.** `PlantConfig.drag_accel` is a
  placeholder, so simulated cars coast unrealistically slowly. It is left
  unchanged on purpose: retuning a physical constant invalidates frozen
  benchmark numbers, so it must be a separate, explicit change.
- **Streamed branches are longitudinal only.** `simulate_stream.py` projects
  plant distance onto a synthetic display loop. It does not model steering,
  a racing line or a pit lane.
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
track surface sits only 0.08 world units above the ground plane. With a linear depth buffer
and a large `far` plane the ground punches through the track, which presents as
the circuit partially disappearing at orbit distance. Do not remove it from the
Canvas `gl` props, and keep `near` well above 1.

**The chase camera reads the rendered actor.** Fleet updates run before the
camera. Both eye and look target share the actor's translation; heading and
view offsets are smoothed in car-relative space, avoiding independent world-space
lags. This also allows pit-lane motion to differ from the circuit centreline.

Run `bun run test` for motion, pause/seek, frame-rate, spacing, model bounds and
camera-framing regressions. These are numerical checks, not visual validation.
