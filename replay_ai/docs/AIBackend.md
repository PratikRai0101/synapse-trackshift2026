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
.venv/bin/python -m pytest -q      # 201 passed
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

The report keeps events, not rows, in separate partitions. The checked-in
100-event synthetic run contains 67 train, 21 validation and 12 test events.
Its overall ERS-mode accuracy is 0.528 / 0.417 / 0.533, while the tactically
critical harvest-vs-derate accuracy is 0.997 / 0.997 / 1.000. These are
synthetic-generator results, not real-race validation.

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
MAE. It now includes a track baseline feature so different circuit lengths do
not get conflated. Simulator-labelled training data is generated separately
with explicit battery/fuel truth; public FastF1 samples still use explicit
pedal-derived energy proxies.

## Measured behaviour

On synthetic labelled data, and on **held-out** data drawn from the same
generator:

| held-out synthetic test metric | result |
|---|---:|
| four-way ERS-mode accuracy | 0.533 |
| harvest-vs-derate accuracy | 1.000 |
| test events / observations | 12 / 720 |

The tactically critical metric separates `Lharvest` from `Lderate`; confusing
those modes can trigger an attack against a rival deliberately saving energy.
The result only shows that the inference machinery recovers signatures created
by its synthetic generator. It does not establish the same separation on an
unlabelled real car. The modest four-way score also means `H` versus `M` must be
shown as uncertainty, not presented as a reliable classification.

## Latency budget

Measure every architecture block independently:

```sh
.venv/bin/python scripts/benchmark_latency.py \
  --iterations 200 --output artifacts/latency.json
```

Reference measurement on an Apple Silicon arm64 host, CPython 3.14.6, pure
Python with NumPy/SciPy LP (no JIT, no native solver):

| block | design budget | p50 | p95 | p99 |
|---|---:|---:|---:|---:|
| telemetry feature deltas | per frame | 0.003 ms | 0.004 ms | 0.004 ms |
| 40-state HMM update | per observation | 0.20 ms | 0.21 ms | 0.21 ms |
| Level 4 season DP | per weekend | 0.014 ms | 0.015 ms | 0.075 ms |
| Level 3 lap DP | per lap | 3.64 ms | 3.68 ms | 3.68 ms |
| Level 2 full (heuristic + POMCP + SOCP) | < 1000 ms | 3.26 ms | 3.51 ms | 10.86 ms |
| — Level 2 heuristic only | | 0.018 ms | 0.019 ms | 0.020 ms |
| — particle POMCP search | | 3.60 ms | 3.73 ms | 4.02 ms |
| — spatial SOCP profile | | 0.022 ms | 0.023 ms | 0.028 ms |
| Level 1 actuator MPC | 10 ms tick | 0.74 ms | 0.85 ms | 1.01 ms |
| vehicle plant step (10 ms) | per tick | 0.003 ms | 0.003 ms | 0.003 ms |
| end-to-end observation | | 4.12 ms | 4.22 ms | 4.29 ms |
| closed-loop control step | | 4.95 ms | 5.47 ms | 6.04 ms |
| counterfactual fork (C) | interactive | 218 ms | 221 ms | 221 ms |

Particle search dominates tactical latency. The SOCP projection and the
heuristic scorer are effectively free by comparison. Cost scales close to
linearly with the simulation budget:

| simulations | particles | p50 |
|---:|---:|---:|
| 64 | 32 | 0.56 ms |
| 128 | 64 | 1.26 ms |
| 256 | 128 | 3.25 ms |
| 512 | 256 | 6.99 ms |

### Consequences to keep in mind

- **Level 1 meets its 10 ms tick** with ~7% utilisation; the whole closed-loop
  step uses about half the tick.
- **Level 2 is roughly 300x under its 1 s sector budget**, so search fidelity can
  be raised substantially before latency matters.
- **The counterfactual fork is synchronous.** 218 ms of main-thread work is a
  perceptible hitch. It belongs in a worker thread before this is shown live.
- **High playback rates are the real constraint.** The replay computes
  intelligence once per distinct `frame_index`, so cost per rendered frame
  scales with playback speed: about 25% of a 60 FPS budget at 1x, 50% at 2x and
  ~99% at 4x. The 4x setting will drop frames with the full stack enabled.
- These numbers are this host, this Python, and these reference solvers. A
  trained neural lap map or a compiled SOCP backend would change them.

## Paired benchmark matrix

Run the multi-seed comparison with identical initial conditions:

```sh
.venv/bin/python scripts/benchmark_matrix.py \
  --seeds 10 --steps 100 --output artifacts/paired-benchmark.json
```

The matrix compares the full stack against these one-factor ablations over
all hidden rival modes and three plant conditions: nominal, energy stress and
thermal stress. Stress conditions are deliberately used to expose controller
components that are dormant in the nominal plant.

- `no_mpc`
- `no_search`
- `no_soh`
- `no_spatial`

It reports mean, sample standard deviation, 95% confidence intervals, energy
use, gap and completion rate. Rows are paired by seed and rival mode; failures
remain in the report rather than being dropped. The plant also applies
temperature-dependent battery resistance and thermal SOH fade, so longer
multi-lap runs can exercise lifecycle-aware ablations.

Generate a model-mismatch report with:

```sh
.venv/bin/python scripts/model_mismatch.py \
  --seeds 10 --steps 300 --output artifacts/model-mismatch.json
```

This reports speed-target error, decision alignment against hidden simulator
truth, physical-versus-lifecycle resistance mismatch, and explicit limitations.
The rival-mode alignment is diagnostic only; it is not a public-telemetry
validation result.

For circuit-level generalization, provide JSONL rows containing a `circuit`
field and run:

```sh
.venv/bin/python scripts/evaluate_circuit_holdout.py data/laps \
  --output artifacts/circuit-holdout.json
```

This performs leave-one-circuit-out evaluation and refuses to mix held-out
circuit rows into training.

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
2. **Transition calibration depends on labelled sequences.** The runtime can
   load a fitted ERS transition matrix, but public-only races still lack the
   hidden labels needed to estimate it.
3. **Emission model is diagonal and Gaussian.** Real `dgap` is autocorrelated and
   heteroscedastic; a diagonal Gaussian with one pooled scale per feature cannot
   represent that.
4. **`_expected()` means are priors, partly hand-set.** Only the ERS-derived
   entries are currently fitted; the override contribution is still a constant.
5. **SOH integration is currently a reference degradation model.** Battery
   SOH now scales usable Level 3 energy, adds resistance/wear cost, and fades
   under closed-loop throughput. The constants are not yet fitted to cell or
   race battery data.
6. **Level 2 has explicit spatial state and bounded belief-tree search,
   but not a production SOCP.** `socp_envelope.py` projects requested
   speed/longitudinal acceleration onto the tyre cone and reports primal
   residuals. `spatial_planner.py` evaluates the upcoming curvature profile and
   produces a distance-indexed speed/costate reference. `scenario_search.py`
   samples hidden ERS modes from belief and prices continuation energy over
   bounded rollouts. Safety gates still prevent weak evidence from triggering
   BURN/HARVEST. Level 1 now has a linear
   zone-MPC LP (`zone_mpc.py`) with speed-zone and reserve constraints; it still
   requires actuator and plant validation before production use.
7. **The season SOH model is a reference degradation model.** It is a real
   finite-horizon retain/replace DP with indicative time-equivalent constants,
   not a validated cell model or championship-points optimizer.
8. **The closed loop is a development simulator.** It is action-responsive,
   now includes curvature-aware combined grip, tyre wear/temperature, battery
   temperature/resistance, fuel mass, slipstream, dirty-air loss, pit events,
   geometric pass/contact checks and reactive defence. It still requires
   calibration against real vehicle data and richer multi-car strategy.
