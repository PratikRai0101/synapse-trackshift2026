"""
Phase C (rewrite) - generate_rival_observed_evidence.py

CHANGE FROM PREVIOUS VERSION: gap_s is no longer a constant placeholder.
It is now computed by reproducing the replay's own progress-based gap
logic (race_replay.py: build_track_from_example_lap / _project_to_reference /
_compute_driver_progress / gap_between), confirmed against source by a
full-repo audit:

    1. A reference polyline is built from an "example lap" (production uses
       the fastest QUALIFYING lap, independent of focus driver - see
       ASSUMPTION below), resampled to N_REF_POINTS points along arc length.
    2. Each car's raw (X, Y) telemetry is projected onto the nearest
       reference-polyline segment via KD-tree nearest-point lookup, giving
       a projected along-track distance for that instant.
    3. progress = (lap_number - 1) * ref_total_length + projected_distance
       - i.e. cumulative distance including completed laps.
    4. gap_s between two cars = |progress_a - progress_b| / 55.56 (a fixed
       divisor used everywhere in the replay - NOT either car's actual
       speed).

WHO IS "AHEAD" IS NOT A FIXED IDENTITY FOR THIS LAP. Official classification
has HAM at P4 with VER (P3) ahead and PIA (P5) behind at both the lap-23 and
lap-24 boundaries, BUT contemporaneous race reporting describes a Hamilton/
Piastri position swap that occurred and reverted within lap 23 without
showing up in either lap-boundary classification. Since the replay's own
`ordered_codes` is resorted by projected progress every frame - not by
official Position - a script that hardcodes "VER is ahead of HAM for the
whole lap" would silently produce a wrong (or discontinuous) gap trace
during that transient. Instead, this script pulls THREE drivers (HAM, VER,
PIA), computes all three progress traces, and picks whichever of {VER, PIA}
is immediately ahead of HAM at each individual tick - reproducing what the
replay would actually do, including capturing the swap if it happened.

ASSUMPTION (flagged per this project's convention of documenting deviations
explicitly): production's build_track_from_example_lap() normally uses the
fastest lap of QUALIFYING as the reference polyline, regardless of focus
driver. This cache has no qualifying session data, so this script falls
back to the fastest lap of THIS race session instead (same fallback order
main.py itself uses when qualifying is unavailable). This should produce
a very similar polyline since it's still a clean, representative lap of
the same track, but is not byte-for-byte identical to what production
would use if qualifying data were present - flag this if a future
comparison against a real replay session shows a discrepancy.

TIME BASIS CHANGE: the previous version force-zeroed each lap's telemetry
time to 0 and concatenated laps with an artificial running offset, purely
so HAM's own row timeline looked monotonic. That approach cannot support
real gap computation, which requires genuine wall-clock alignment across
different drivers' telemetry. This version uses each driver's SessionTime
(FastF1's absolute session-relative clock) as the common clock for all
three drivers, and reports that same absolute time in the exported
time_s column. This is a deliberate, necessary behavior change, not an
oversight - Phase D re-baselines time_s to start at 0 for the target lap
regardless, so downstream compatibility is unaffected.

CONFIRMED BUG FIXES (from a targeted audit against the real cached Monza
2026 R data, HAM lap 23):
  1. get_car_data()'s 'Time' and get_telemetry()'s 'Time' are NOT the same
     clock (different sampling/endpoints, both lap-relative in different
     ways). 'SessionTime' IS consistent between the two APIs (max ~0.24s
     nearest-sample diff) and is what this script now uses everywhere.
  2. Raw X/Y telemetry is in DECIMETERS, not meters, in this cache: the
     raw X/Y path length for HAM lap 23 was ~57,581 vs. Distance.max() of
     ~5,751.55 (matching Monza's real ~5.8km lap) - almost exactly a 10x
     mismatch. X/Y are now divided by 10 before any projection/distance
     math so gap_s comes out in physically correct meters/seconds.
  A separate KD-tree seam/chicane-jump hypothesis was checked and ruled
  out for HAM lap 23 (nearest-index sequence advances smoothly, no large
  or negative jumps) - the two fixes above were sufficient.

Output: rival_observed_evidence_<RIVAL_ID>.csv
    Columns: time_s, speed_kmh, throttle_pct, brake, gap_s, active_aero,
             sector, lap, tyre_life
    Rows are tagged by 'lap' - Phase D feeds ALL rows through the model in
    order (to build up history) but only scores/exports belief for rows
    where lap == TARGET_LAP.
"""
import fastf1
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from pathlib import Path

fastf1.Cache.enable_cache(str(Path(__file__).parent / 'fastf1_cache'))

# --- Configure the rival lap to extract -------------------------------------
YEAR, TRACK, SESSION_TYPE, RIVAL_ID = 2026, 'Monza', 'R', 'HAM'
AHEAD_CANDIDATE_IDS = ['VER', 'PIA']  # confirmed neighbors of HAM at lap 23 (P3/P5); HAM was P4
DECISION_TICK_S = 1.0
WARMUP_LAPS = 5  # matches FeatureExtractor's deque(maxlen=5) per-sector history
N_REF_POINTS = 4000  # matches the replay's reference-polyline resolution

session = fastf1.get_session(YEAR, TRACK, SESSION_TYPE)
session.load()

rival_laps = session.laps.pick_drivers(RIVAL_ID)
target_lap_row = rival_laps.pick_fastest()
if target_lap_row is None:
    raise ValueError(f"No valid timed lap for {RIVAL_ID}. "
                      f"Drivers in this session: {sorted(session.laps['Driver'].unique())}")

TARGET_LAP = int(target_lap_row['LapNumber'])
lap_numbers_to_pull = list(range(max(1, TARGET_LAP - WARMUP_LAPS), TARGET_LAP + 1))
print(f"Target lap: {TARGET_LAP}. Pulling warm-up + target laps: {lap_numbers_to_pull}")


# --- Reference polyline (reproduces build_track_from_example_lap + the ---
# --- replay's KD-tree / cumulative-distance setup, race_replay.py:264-293) --
XY_SCALE = 10.0  # confirmed: raw X/Y telemetry in this cache is in decimeters, not meters


def build_reference_polyline(example_tel, n_points=N_REF_POINTS):
    x_raw = example_tel['X'].to_numpy(dtype=float) / XY_SCALE
    y_raw = example_tel['Y'].to_numpy(dtype=float) / XY_SCALE
    seg_raw = np.sqrt(np.diff(x_raw) ** 2 + np.diff(y_raw) ** 2)
    cumdist_raw = np.concatenate(([0.0], np.cumsum(seg_raw)))
    total_raw = cumdist_raw[-1]

    target_dist = np.linspace(0.0, total_raw, n_points)
    ref_xs = np.interp(target_dist, cumdist_raw, x_raw)
    ref_ys = np.interp(target_dist, cumdist_raw, y_raw)

    seg_len = np.sqrt(np.diff(ref_xs) ** 2 + np.diff(ref_ys) ** 2)
    ref_cumdist = np.concatenate(([0.0], np.cumsum(seg_len)))
    ref_total_length = float(ref_cumdist[-1])

    tree = cKDTree(np.column_stack([ref_xs, ref_ys]))
    return ref_xs, ref_ys, ref_cumdist, ref_total_length, tree


def project_to_reference(x, y, ref_xs, ref_ys, ref_cumdist, ref_total_length, tree):
    """Verbatim reproduction of race_replay.py:1258's _project_to_reference."""
    if ref_total_length == 0.0:
        return 0.0
    _, idx = tree.query([x, y])
    idx = int(idx)
    if idx < len(ref_xs) - 1:
        x1, y1 = ref_xs[idx], ref_ys[idx]
        x2, y2 = ref_xs[idx + 1], ref_ys[idx + 1]
        vx, vy = x2 - x1, y2 - y1
        seg_len2 = vx * vx + vy * vy
        if seg_len2 > 0:
            t = ((x - x1) * vx + (y - y1) * vy) / seg_len2
            t_clamped = max(0.0, min(1.0, t))
            proj_x = x1 + t_clamped * vx
            proj_y = y1 + t_clamped * vy
            seg_dist = np.sqrt((proj_x - x1) ** 2 + (proj_y - y1) ** 2)
            return float(ref_cumdist[idx] + seg_dist)
    return float(ref_cumdist[idx])


def gap_between(progress_a, progress_b):
    """Verbatim reproduction of race_replay.py:1308's gap_between."""
    dist_m = abs(float(progress_a) - float(progress_b))
    time_s = dist_m / 55.56
    return dist_m, time_s


# Production reference lap: fastest QUALIFYING lap. Fall back to fastest
# lap of this race session if no qualifying cache exists (see ASSUMPTION
# in the module docstring).
try:
    quali_session = fastf1.get_session(YEAR, TRACK, 'Q')
    quali_session.load()
    example_tel = quali_session.laps.pick_fastest().get_telemetry()
    print("Reference polyline built from fastest QUALIFYING lap (matches production).")
except Exception as e:
    print(f"WARNING: could not load qualifying session ({e}); falling back to "
          f"fastest lap of this race session for the reference polyline. This "
          f"matches main.py's own documented fallback order, but is a deviation "
          f"from production's normal (quali-based) reference lap - flag if a "
          f"real replay comparison later shows a mismatch.")
    example_tel = session.laps.pick_fastest().get_telemetry()

ref_xs, ref_ys, ref_cumdist, ref_total_length, track_tree = build_reference_polyline(example_tel)
print(f"Reference polyline: {N_REF_POINTS} points, total length {ref_total_length:.1f} m")


# --- Build a continuous (absolute session-time) progress trace for one ---
# --- driver across a set of laps -----------------------------------------
def build_progress_trace(driver_id, lap_numbers):
    """
    Returns a DataFrame with columns [time_s, progress], where time_s is
    absolute SessionTime (seconds since session start - confirmed the one
    clock that agrees between get_car_data() and get_telemetry(), unlike
    their respective 'Time' columns) and progress is
    (lap_number - 1) * ref_total_length + projected_distance, matching
    _compute_driver_progress.
    """
    driver_laps = session.laps.pick_drivers(driver_id)
    rows = []
    for lap_num in lap_numbers:
        candidates = driver_laps.pick_laps(lap_num)
        if len(candidates) == 0:
            print(f"  {driver_id} lap {lap_num}: no data, skipping")
            continue
        lap = candidates.iloc[0]
        tel = lap.get_telemetry()
        if tel.empty:
            print(f"  {driver_id} lap {lap_num}: empty telemetry, skipping")
            continue

        t_abs = tel['SessionTime'].dt.total_seconds().to_numpy()
        x = tel['X'].to_numpy(dtype=float) / XY_SCALE
        y = tel['Y'].to_numpy(dtype=float) / XY_SCALE

        projected_m = np.array([
            project_to_reference(xi, yi, ref_xs, ref_ys, ref_cumdist, ref_total_length, track_tree)
            for xi, yi in zip(x, y)
        ])
        progress = (max(lap_num, 1) - 1) * ref_total_length + projected_m

        rows.append(pd.DataFrame({'time_s': t_abs, 'progress': progress}))

    if not rows:
        raise RuntimeError(f"No usable laps found for {driver_id} in {lap_numbers}.")
    return pd.concat(rows, ignore_index=True).sort_values('time_s').reset_index(drop=True)


print(f"Building progress traces for HAM + ahead candidates {AHEAD_CANDIDATE_IDS}...")
ham_progress_trace = build_progress_trace(RIVAL_ID, lap_numbers_to_pull)
candidate_traces = {}
for cid in AHEAD_CANDIDATE_IDS:
    try:
        candidate_traces[cid] = build_progress_trace(cid, lap_numbers_to_pull)
    except RuntimeError as e:
        print(f"WARNING: {e} - {cid} will not be considered as a possible 'ahead' car.")

if not candidate_traces:
    raise RuntimeError(
        "None of the ahead-candidate drivers had usable telemetry - cannot compute a real gap_s. "
        "Check AHEAD_CANDIDATE_IDS against this session's actual driver list."
    )


def progress_at(trace_df, t_query):
    """Interpolate a driver's progress trace at arbitrary absolute time(s)."""
    return np.interp(t_query, trace_df['time_s'].to_numpy(), trace_df['progress'].to_numpy())


# --- Main per-lap extraction loop (speed/throttle/brake/sector/tyre_life ---
# --- logic unchanged from the previous version; gap_s is now real) --------
all_rows = []

for lap_num in lap_numbers_to_pull:
    lap_candidates = rival_laps.pick_laps(lap_num)
    if len(lap_candidates) == 0:
        print(f"  lap {lap_num}: no data, skipping (out-lap/in-lap/gap in session record)")
        continue
    lap = lap_candidates.iloc[0]

    tel = lap.get_car_data().add_distance().reset_index(drop=True)
    if tel.empty:
        print(f"  lap {lap_num}: empty telemetry, skipping")
        continue

    # Absolute SessionTime (see TIME BASIS CHANGE in module docstring) - confirmed
    # consistent with get_telemetry()'s SessionTime, unlike either API's 'Time' column,
    # so this is directly comparable to the progress traces above.
    t_abs = tel['SessionTime'].dt.total_seconds().to_numpy()
    speed_kmh = tel['Speed'].to_numpy()
    throttle = np.clip(tel['Throttle'].to_numpy().astype(float), 0, 100)
    brake = tel['Brake'].to_numpy().astype(float)
    drs = tel['DRS'].to_numpy()

    t_ticks = np.arange(t_abs[0], t_abs[-1], DECISION_TICK_S)
    if len(t_ticks) == 0:
        print(f"  lap {lap_num}: too short to tick, skipping")
        continue

    speed_i = np.interp(t_ticks, t_abs, speed_kmh)
    throttle_i = np.interp(t_ticks, t_abs, throttle)
    brake_i = (np.interp(t_ticks, t_abs, brake) > 0.5).astype(float)
    drs_i = np.round(np.interp(t_ticks, t_abs, drs)).astype(int)
    active_aero_i = np.isin(drs_i, [8, 10, 12, 14]).astype(float)  # matches race_replay.py's own check

    # --- Real gap_s: HAM's own progress at each tick vs. each candidate's ---
    # --- interpolated progress at that same absolute time; take whichever ---
    # --- candidate is immediately ahead (smallest positive progress delta). ---
    ham_progress_i = progress_at(ham_progress_trace, t_ticks)
    gap_s_i = np.empty_like(t_ticks)
    for i, t_q in enumerate(t_ticks):
        candidate_progress = {
            cid: progress_at(trace, t_q) for cid, trace in candidate_traces.items()
        }
        ahead = {cid: p for cid, p in candidate_progress.items() if p > ham_progress_i[i]}
        if ahead:
            ahead_id = min(ahead, key=ahead.get)  # closest-ahead = smallest progress that's still > HAM's
            ahead_progress = ahead[ahead_id]
        else:
            # No candidate is ahead at this instant (can happen briefly near a
            # transient swap or interpolation edge) - fall back to whichever
            # candidate has the largest progress and flag it, rather than
            # silently producing a physically backwards gap.
            ahead_id = max(candidate_progress, key=candidate_progress.get)
            ahead_progress = candidate_progress[ahead_id]
            print(f"  WARNING: at t={t_q:.1f}s (lap {lap_num}) no candidate was ahead of "
                  f"{RIVAL_ID} in projected progress - falling back to {ahead_id} anyway. "
                  f"Likely a transient swap or reference-lap edge effect; inspect if this "
                  f"repeats for many consecutive ticks.")
        _, gap_s_i[i] = gap_between(ahead_progress, ham_progress_i[i])

    lap_distance_total = tel['Distance'].max()
    distance_i = np.interp(t_ticks, t_abs, tel['Distance'].to_numpy())
    sector1_frac = lap['Sector1Time'] / lap['LapTime'] if pd.notna(lap['Sector1Time']) else 1 / 3
    sector2_frac = ((lap['Sector1Time'] + lap['Sector2Time']) / lap['LapTime']
                     if pd.notna(lap['Sector1Time']) and pd.notna(lap['Sector2Time'])
                     else 2 / 3)  # cumulative boundary, matches the distance-based np.select checks below
    sector_i = np.select(
        [distance_i <= lap_distance_total * sector1_frac,
         distance_i <= lap_distance_total * sector2_frac],
        [0, 1], default=2)  # 0-indexed to match int(rival.get("sector", 0)) in race_replay.py

    lap_df = pd.DataFrame({
        'time_s': t_ticks,
        'speed_kmh': speed_i,
        'throttle_pct': throttle_i,
        'brake': brake_i,
        'gap_s': gap_s_i,
        'active_aero': active_aero_i,
        'sector': sector_i,
        'lap': lap_num,
        'tyre_life': lap['TyreLife'] if pd.notna(lap['TyreLife']) else 0.0,
    })
    all_rows.append(lap_df)

if not all_rows:
    raise RuntimeError("No usable laps found in the warm-up + target range.")

evidence = pd.concat(all_rows, ignore_index=True)

n_warmup_rows = (evidence['lap'] != TARGET_LAP).sum()
n_target_rows = (evidence['lap'] == TARGET_LAP).sum()
print(f"Total rows: {len(evidence)} ({n_warmup_rows} warm-up, {n_target_rows} target-lap {TARGET_LAP})")
print(f"gap_s summary for target lap: min={evidence.loc[evidence['lap'] == TARGET_LAP, 'gap_s'].min():.2f}s, "
      f"max={evidence.loc[evidence['lap'] == TARGET_LAP, 'gap_s'].max():.2f}s - "
      f"sanity check this isn't constant (would indicate the projection fell back to a "
      f"single candidate for the whole lap).")

out_path = Path(__file__).parent / f'rival_observed_evidence_{RIVAL_ID}.csv'
evidence.to_csv(out_path, index=False)
print(f"Saved to {out_path}")
print(evidence.head())