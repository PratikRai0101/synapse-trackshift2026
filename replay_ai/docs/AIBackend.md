# AI backend — environment, pipeline and measured behaviour

This document covers only the intelligence layer added on top of the replay app.
The replay itself is unchanged and still runs as described in the main README.

## Environment

The replay app requires **Python 3.11+** (it uses `match` statements). This
working copy is set up on **Python 3.14.6**:

```sh
uv venv --python /opt/homebrew/bin/python3.14 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
```

`requirements.txt` lists `pyside6`, which is a ~420 MB download. The app only
imports `PySide6.QtCore` and `PySide6.QtWidgets`, which live in
`pyside6-essentials` (~105 MB), so installing that alone is enough:

```sh
uv pip install --python .venv/bin/python pyside6-essentials
```

On a slow connection this download can outlive a foreground shell command. Run
it detached and poll the log rather than assuming it failed:

```sh
nohup uv pip install --python .venv/bin/python pyside6-essentials \
  > /tmp/pyside_install.log 2>&1 &
```

Verify:

```sh
.venv/bin/python -m pytest -q      # 141 passed
```

## What the model actually knows

FastF1 publishes speed, throttle, brake, gear, DRS, tyre life and lap timing. It
does **not** publish battery state of charge, MGU-K deployment, or energy store
limits. Every SOC/ERS number this backend produces is therefore a **belief over
public evidence**, not a measurement. The HUD labels it `EST` and the code never
presents `soc_probabilities` as telemetry.

The hidden state space is `ERS × override × tyre = 4 × 2 × 5 = 40`:

| factor | values |
|---|---|
| ERS | `H`, `M`, `Lharvest`, `Lderate` |
| override | `available`, `spent` |
| tyre | `new`, `light`, `moderate`, `heavy`, `cliff` |

`Lharvest` (deliberately hoarding energy) and `Lderate` (physically maxed out)
look identical on a timing screen. Separating them is the point of the filter:
the first means *do not attack*, the second means *attack now*.

## Runtime artifact loading

The replay loads the calibrated HMM artifact from
`artifacts/hmm-emissions.json` and the fitted Level 3 map from
`artifacts/lap-time-map.json` by default. Override either without changing code:

```sh
HMM_EMISSIONS_ARTIFACT=artifacts/hmm-emissions.json \
LAP_TIME_MAP_ARTIFACT=artifacts/lap-time-map.json \
  .venv/bin/python main.py
```

A missing or invalid artifact falls back to the default reference HMM so the
replay still starts. The active sources are exposed as `hmm_source` and the lap planner is
re-evaluated once at each observed lap boundary. The first planned lap's
battery target is shown in the replay HUD.

Compare runtime behaviour explicitly:

```sh
.venv/bin/python scripts/benchmark_closed_loop.py --steps 100
.venv/bin/python scripts/benchmark_closed_loop.py --steps 100 \
  --artifact artifacts/hmm-emissions.json
```

## Pipeline

Run from inside this directory.

```sh
# 1. Labelled development data (synthetic rival; not race evidence)
.venv/bin/python scripts/generate_synthetic_training.py \
  --events 10 --samples-per-event 60 --output data/synthetic-labelled.jsonl

# 2. Fit emission means and per-feature scales
.venv/bin/python scripts/fit_hmm_emissions.py \
  data/synthetic-labelled.jsonl --output artifacts/hmm-emissions.json

# 3. Score held-out labelled data
.venv/bin/python scripts/evaluate_hmm.py \
  data/synthetic-labelled.jsonl --artifact artifacts/hmm-emissions.json
```

Held-out event evaluation (fit only on train events):

```sh
.venv/bin/python scripts/evaluate_hmm_splits.py \
  data/synthetic-labelled.jsonl --output artifacts/hmm-split-report.json
```

The report keeps events, not rows, in separate partitions. On a 100-event
synthetic mixture, the current reference run produced 67 train, 21 validation
and 12 test events with overall accuracy 0.821 / 0.802 / 0.771. These are
synthetic results, not real-race validation.

Real telemetry export, and the leakage-safe event split:

```sh
.venv/bin/python scripts/export_training_data.py \
  computed_data/session_telemetry.pkl \
  --driver HAM --rival VER --track-length-m 5412 \
  --output data/ham-ver.jsonl

.venv/bin/python scripts/build_dataset.py \
  --input bahrain=cache/bahrain.pkl --input monaco=cache/monaco.pkl \
  --driver HAM --rival VER --output data/ham-ver
```

`build_dataset.py` splits by **event**, never by row, so adjacent sectors from
one race cannot leak across train/validation/test. Records carry
`timestamp_s` and `available_at_s`; the adapter refuses to emit a frame whose
`available_at_s` precedes its `timestamp_s`.

For Level 3 lap-time data, use the equivalent event-level pipeline:

```sh
.venv/bin/python scripts/build_lap_dataset.py \
  --input bahrain=cache/bahrain.pkl --input monaco=cache/monaco.pkl \
  --driver HAM --output data/ham-laps

.venv/bin/python scripts/evaluate_lap_map.py data/ham-laps
```

The lap map is fitted only on training-race laps and scored with held-out-race
MAE. Battery and fuel fields remain explicit pedal-derived proxies until they
are replaced with simulator-labelled energy states.

## Measured behaviour

On synthetic labelled data, and on **held-out** data drawn from the same
generator:

| configuration | overall accuracy | harvest-vs-derate accuracy |
|---|---|---|
| default emissions, `sigma=1.0` | 0.465 | — |
| fitted means + fitted per-feature scale | 0.650 | 0.989 |

The tactically critical metric is the second column: among samples whose true
mode is `Lharvest` or `Lderate`, how often the filter picked the *other* one.
That is the confusion that causes the controller to attack a car that is
deliberately saving energy. It is rare; the residual error sits on the
`H`/`M` boundary, which only misprices energy rather than inverting the decision.

### Why scale calibration was required

The first version fitted emission *means* but kept a hard-coded `sigma=1.0`. With
feature errors of order 0.01–0.3, every one of the 40 states scored within a few
percent of the others (`exp(-0.005) ≈ 0.995`), so the likelihood was effectively
flat and the filter decayed toward its prior. Accuracy was 0.465 — near chance.
Fitting a pooled within-mode standard deviation per feature
(`dgap ≈ 0.05`, `throttle_clip ≈ 0.24`, `brake_delta ≈ 0.21`) fixed it.
`test_fitted_scale_beats_uncalibrated_sigma` guards the regression.

## Honest limits

1. **Synthetic labels are not ground truth.** Accuracy above is measured against
   a generator, so it shows the *inference machinery* works, not that the
   inference is correct on real cars. No real ERS labels exist publicly.
2. **No fitted transition matrix.** `self_transition` is a configured constant,
   not estimated from data. Mode-switch timing is therefore not calibrated.
3. **Emission model is diagonal and Gaussian.** Real `dgap` is autocorrelated and
   heteroscedastic; a diagonal Gaussian with one pooled scale per feature cannot
   represent that.
4. **`_expected()` means are priors, partly hand-set.** Only the ERS-derived
   entries are currently fitted; the override contribution is still a constant.
5. **Levels 2 and 1 are transparent reference baselines, not production
   optimizers.** `lap_strategy.py` provides a fitted empirical lap-time map and
   finite-horizon battery allocation DP. `control_layers.py` provides a bounded
   grip envelope, three-action scenario planner, and pedal-aware execution
   cues. None is yet a validated SOCP/POMCP/MPC implementation, and Level 3 is
   not yet trained from a multi-race lap dataset or wired into the dashboard.
6. **The season SOH model is a reference stub.** It is a small finite-horizon DP
   with indicative constants, not a validated degradation model.
7. **No closed loop.** Rival actions do not react to ego actions; the model is
   still driven by replayed or synthetic observations.
