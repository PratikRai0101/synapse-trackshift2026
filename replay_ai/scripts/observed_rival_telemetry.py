"""
Phase C (revised) - generate_rival_observed_evidence.py

Exports raw RivalTelemetry-shaped fields per decision tick - NOT pre-computed
features. FeatureExtractor in hierarchical.py builds dv_baseline / dgap /
throttle_clip / etc. itself from these raw fields; duplicating that logic
here would risk drifting from the real implementation.

Output: rival_observed_evidence.csv
    Columns: time_s, speed_kmh, throttle_pct, brake, gap_s, active_aero,
             sector, lap, tyre_life

IMPORTANT: gap_s is currently a constant placeholder (see WARNING below).
Do not trust Phase D/E results until you replace it with a real gap trace -
dgap is one of only four features that feeds the HMM's emission likelihood.
"""
import fastf1
import pandas as pd
import numpy as np
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "fastf1_cache"
fastf1.Cache.enable_cache(str(CACHE_DIR))

# --- Configure the rival lap to extract -------------------------------------
YEAR, TRACK, SESSION_TYPE, RIVAL_ID = 2026, 'Monza', 'R', 'HAM'
DECISION_TICK_S = 1.0

# NOTE: this must be the SAME (year, track, session, driver, lap) you use to
# generate rival_ground_truth.csv in Phase A/Simscape, or Phase E's merge
# will be comparing two different laps.

session = fastf1.get_session(YEAR, TRACK, SESSION_TYPE)
session.load()

rival_laps = session.laps.pick_drivers(RIVAL_ID)
lap = rival_laps.pick_fastest()
if lap is None:
    raise ValueError(f"No valid timed lap for {RIVAL_ID}. "
                      f"Drivers in this session: {sorted(session.laps['Driver'].unique())}")

tel = lap.get_car_data().add_distance().reset_index(drop=True)
t_raw = tel['Time'].dt.total_seconds().to_numpy()
speed_kmh = tel['Speed'].to_numpy()
throttle = np.clip(tel['Throttle'].to_numpy().astype(float), 0, 100)
brake = tel['Brake'].to_numpy().astype(float)
drs = tel['DRS'].to_numpy()

t_ticks = np.arange(t_raw[0], t_raw[-1], DECISION_TICK_S)
speed_i = np.interp(t_ticks, t_raw, speed_kmh)
throttle_i = np.interp(t_ticks, t_raw, throttle)
brake_i = (np.interp(t_ticks, t_raw, brake) > 0.5).astype(float)
drs_i = np.round(np.interp(t_ticks, t_raw, drs)).astype(int)
active_aero_i = np.isin(drs_i, [8, 10, 12, 14]).astype(float)  # matches race_replay.py's own check

# gap_s: no rival-ahead in a single-lap extract - approximate with a constant
# placeholder and FLAG this loudly. If you have a real gap trace (e.g. from
# a session-wide comparison against the car ahead of RIVAL_ID), substitute
# it here instead of this placeholder.
gap_s_i = np.full_like(t_ticks, 1.0)
print("WARNING: gap_s is a constant placeholder (1.0s) - substitute real "
      "gap-to-car-ahead data before trusting any downstream result. dgap is "
      "one of only four features that actually enters the HMM's emission "
      "likelihood (dgap, throttle_clip, brake_delta, tyre_life).")

lap_distance_total = tel['Distance'].max()
distance_i = np.interp(t_ticks, t_raw, tel['Distance'].to_numpy())
sector1_frac = lap['Sector1Time'] / lap['LapTime'] if pd.notna(lap['Sector1Time']) else 1 / 3
sector2_frac = ((lap['Sector1Time'] + lap['Sector2Time']) / lap['LapTime']
                 if pd.notna(lap['Sector1Time']) and pd.notna(lap['Sector2Time'])
                 else 2 / 3)  # cumulative boundary, matching the distance-based np.select checks below
sector_i = np.select(
    [distance_i <= lap_distance_total * sector1_frac,
     distance_i <= lap_distance_total * sector2_frac],
    [0, 1], default=2)  # 0-indexed to match int(rival.get("sector", 0)) in race_replay.py

evidence = pd.DataFrame({
    'time_s': t_ticks,
    'speed_kmh': speed_i,
    'throttle_pct': throttle_i,
    'brake': brake_i,
    'gap_s': gap_s_i,
    'active_aero': active_aero_i,
    'sector': sector_i,
    'lap': int(lap['LapNumber']),
    'tyre_life': lap['TyreLife'] if pd.notna(lap['TyreLife']) else 0.0,
})

out_path = f'rival_observed_evidence_{RIVAL_ID}.csv'
evidence.to_csv(out_path, index=False)
print(f"Saved {len(evidence)} rows to {out_path}")
print(evidence.head())