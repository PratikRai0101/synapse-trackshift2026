# AI Motorsport Intelligence — canonical architecture

This is the decided architecture for `replay_ai`. Research papers motivate the methods;
the repository's tests and frozen evaluations determine which implementation claims are
allowed.

## Information boundary

Public rival inputs are speed, throttle, brake, time/distance gap, DRS as an explicitly
labelled active-aero proxy, lap/sector and public tyre information. FastF1 does **not**
publish rival battery SOC, MGU-K deployment or override availability.

The 40-state HMM therefore estimates a categorical **ERS capability belief** over
`ERS mode × override mode × tyre condition`. It never measures battery percentage. Hidden
rival truth exists only in simulator evaluation and must not enter runtime decisions.

## Runtime cascade

1. **Block 0 — causal processing**
   - Deduplicate observations by replay frame/timestamp.
   - Build sector-aligned baselines from up to five completed prior laps.
   - Produce speed, gap, brake, variance, aero and full-throttle clipping-fraction features.
2. **Level 4 — lifecycle**
   - Run a finite-horizon retain/replace DP at event boundaries.
   - Pass effective SOH, resistance and a time-equivalent wear cost downward.
3. **Level 3 — race/lap strategy**
   - Replan at lap boundaries using a fitted lap-time map.
   - Allocate deployment subject to reserve, tyre, mass and lifecycle costs.
4. **Level 2 — tactical planning**
   - Update the 40-state HMM from newly available evidence.
   - Evaluate `BURN`, `HARVEST` and `PROACTIVE TRAP` with bounded particle POMCP.
   - Project the selected action into a coupled spatial grip/energy envelope.
   - Return tactical action, speed/kinetic-energy reference and sensitivity values.
5. **Level 1 — fast execution**
   - Preserve driver-requested thrust in grip-limited regions.
   - Run short-horizon zone MPC for power-limited execution in simulation.
   - Convert sensitivity ratios into simple driver guidance cues.
6. **Feedback**
   - Apply only the first control interval to the action-responsive two-car simulator.
   - Feed resulting public observations back to Block 0.

Replay mode is observational: it visualizes recommendations but cannot change an already
recorded race. Counterfactual actions must start a separately labelled simulation run.

## Update rates

The rates describe model time, not GUI render frequency:

| Layer | Trigger |
|---|---|
| Block 0 / HMM | one unique available observation |
| Level 4 | event boundary or confirmed component change |
| Level 3 | lap boundary or invalidated resource plan |
| Level 2 | sector/tactical update, target under 1 s after profiling |
| Level 1 | 10 ms model step in simulation, subject to measured solve latency |

## Required output provenance

Every dashboard recommendation should expose:

- model source (`calibrated artifact` or `default fallback`);
- observation timestamp and freshness;
- four marginalized ERS-mode probabilities;
- tactical action and alternatives;
- energy target and reserve;
- envelope feasibility/residual;
- POMCP rollout count and values;
- whether a displayed quantity is public, estimated, synthetic or simulator truth.

## Claim gates

The following are independent gates:

1. Unit and numerical tests pass.
2. A unique observation is consumed once and no future/hidden information leaks.
3. Closed-loop actions change physical state while respecting modeled constraints.
4. Each layer earns its place in paired ablation tests.
5. HMM and lap-map results hold on event-disjoint synthetic test data.
6. Observable forecasts hold on held-out public races.
7. Real SOC, battery-life, FIA-compliance or race-gain claims require authorized ground
   truth and are outside the current evidence.

## Current implementation boundary

The repository contains real HMM forward filtering, particle history-tree search, a
coupled cone-feasibility projection, finite-horizon lifecycle and lap allocation, a linear
zone MPC, an action-responsive simulator and replay integration. The checked-in model
artifacts are synthetic development defaults. Physical constants and tactical response
models still require calibration, and the spatial projection must not be represented as a
production conic solver until an actual solver formulation and dual validation replace it.
