"""
Phase D (revised) - run_hmm_on_rival_evidence.py

SAVE THIS FILE IN replay_ai/scripts/, next to _bootstrap.py - that's the
repo's own convention for resolving `from src.intelligence...` imports
(confirmed: no pip install -e ., no pyproject; scripts rely on _bootstrap.py
inserting the replay_ai root into sys.path, and pytest.ini's `pythonpath = .`
does the equivalent for tests).

Feeds rival_observed_evidence_<RIVAL_ID>.csv (from Phase C - warm-up laps +
target lap) through the ACTUAL FortyStateHMM tick-by-tick, in order, so the
per-sector history deques fill with real data the same way a persistent
production model would. Only rows where lap == TARGET_LAP are written to the
belief output that Phase E will score against ground truth - warm-up rows
still update model state but aren't exported.

Construction mirrors evaluate_hmm.py's own pattern (the closest existing
in-repo evaluation harness):
    FortyStateHMM.from_artifact(str(artifact)) if artifact else FortyStateHMM()
Production replay (race_replay.py:165) supplies hmm-emissions.json by
default, so from_artifact is what you want here, not the bare constructor -
the bare constructor score are NOT scoring the model production actually
runs.

Output: rival_belief_output_<RIVAL_ID>.csv
    Columns: time_s, ers_H, ers_M, ers_Lharvest, ers_Lderate,
             most_likely_ers, most_likely_override, most_likely_tyre
"""
import _bootstrap  # noqa: F401  -- repo convention, inserts replay_ai root + scripts into sys.path

from pathlib import Path
import pandas as pd
from src.intelligence.hierarchical import FortyStateHMM, RivalTelemetry

RIVAL_ID = 'HAM'    # must match Phase C's RIVAL_ID
TARGET_LAP = 23   # set this to the TARGET_LAP printed by Phase C for this RIVAL_ID

if TARGET_LAP is None:
    raise ValueError(
        "Set TARGET_LAP to the value Phase C printed (the lap ground truth "
        "was generated for) before running this script."
    )

# Mirrors evaluate_hmm.py: from_artifact if the artifact exists, bare model otherwise.
# This script sits in replay_ai/scripts/, so artifacts/ is a sibling of scripts/.
ARTIFACT_PATH = Path(__file__).resolve().parent.parent / 'artifacts' / 'hmm-emissions.json'

if ARTIFACT_PATH.exists():
    model = FortyStateHMM.from_artifact(str(ARTIFACT_PATH))
    print(f"Constructed FortyStateHMM.from_artifact({ARTIFACT_PATH})")
else:
    model = FortyStateHMM()
    print(f"WARNING: artifact not found at {ARTIFACT_PATH} - falling back to bare "
          f"FortyStateHMM() with hard-coded defaults. This does NOT match what "
          f"race_replay.py runs in production. Fix ARTIFACT_PATH before trusting results.")

evidence = pd.read_csv(
    Path(__file__).parent / f'rival_observed_evidence_{RIVAL_ID}.csv'
).sort_values('time_s')

rows = []
for _, r in evidence.iterrows():
    obs = RivalTelemetry(
        speed_kmh=r['speed_kmh'],
        throttle_pct=r['throttle_pct'],
        brake=r['brake'],
        gap_s=r['gap_s'],
        active_aero=r['active_aero'],
        sector=int(r['sector']),
        lap=int(r['lap']),
        tyre_life=r['tyre_life'],
        time_s=r['time_s'],
    )
    result = model.observe(obs)  # always called, even for warm-up rows, to build up history/state

    if int(r['lap']) != TARGET_LAP:
        continue  # warm-up row: state updated above, but not scored/exported

    row = {
        'time_s': r['time_s'],
        **{f'ers_{k}': v for k, v in result.ers_probabilities.items()},
        'most_likely_ers': result.most_likely_state[0].value,
        'most_likely_override': result.most_likely_state[1].value,
        'most_likely_tyre': result.most_likely_state[2].value,
    }
    rows.append(row)

if not rows:
    raise RuntimeError(
        f"No rows with lap == {TARGET_LAP} found in the evidence file. "
        f"Check TARGET_LAP matches what Phase C printed."
    )

# Re-baseline time_s to start at 0 for the exported target lap. Phase C/D use a
# single global timeline across all warm-up + target laps (so the model sees a
# continuous sequence), but Simscape ground truth (Phase A) simulates just the
# target lap on its own clock starting near 0. Without this, Phase E's
# merge_asof would align against the wrong absolute times.
out_df = pd.DataFrame(rows)
t0 = out_df['time_s'].iloc[0]
out_df['time_s'] = out_df['time_s'] - t0
print(f"Re-baselined time_s: was {t0}-{t0 + out_df['time_s'].iloc[-1]:.1f}, "
      f"now 0-{out_df['time_s'].iloc[-1]:.1f}")

out_path = f'rival_belief_output_{RIVAL_ID}.csv'
out_df.to_csv(out_path, index=False)
print(f"Saved {len(out_df)} scored rows (target lap {TARGET_LAP}) to {out_path}")