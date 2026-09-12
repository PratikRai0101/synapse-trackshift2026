# Data, interfaces and development contracts

This document defines proposed contracts, not existing endpoints. Field names and CLI examples are development targets. The PRD intentionally avoids implementation paths; this engineering document may specify them.

## 1. Data authority and source inventory

| Quantity | Public evidence | Demonstrator source | Permitted interpretation |
|---|---|---|---|
| Speed, throttle, brake status, RPM/gear | Library/API channels, subject to sampling audit | Sampled/noisy simulation or labelled replay | Observations, not electrical power |
| Timing, stint, compound, weather, race-control messages | Endpoint/session dependent | Versioned event data or synthetic scenario | Context with timestamps and missingness |
| Own battery SOC/current/temperature | Not established in inspected public schemas | Simulated own-car sensors | Simulated measurements, not live Haas telemetry |
| Rival energy/temperature/SOH | No direct public channel established | Hidden plant state | Evaluator truth; controller hypotheses only |
| Fuel, exact grip, wake and component health maps | Not identified from inspected public data | Declared model parameters | Synthetic or externally calibrated, never assumed measured |
| Precise passing lanes/footprints | Public position is insufficient by itself | Explicit track and geometric plant | Simulated geometric feasibility only |
| Active aero / Overtake eligibility | Requires verified event-specific evidence | Rules/event ledger or unknown | Not automatically a legacy DRS-field mapping |

Public adapters preserve native timestamps. FastF1 source documents throttle as 0–100 and typical car samples 240 ms apart [D01]; OpenF1 documents different approximate endpoint cadences and limitations [D02]. Audit the chosen session rather than imposing a supposed 10 Hz source. A timestamp-aligned grid is an analysis convenience, not an extra measurement.

## 2. Common record header

Every externally exchanged record contains `schema_version`, `run_id`, `record_id`, monotonic simulation/session time, source identity and provenance. Observation records additionally carry `sampled_at`, `available_at`, validity/missingness masks, original channel units and transformation version.

Provenance vocabulary: `public_observation`, `derived_observation`, `simulated_measurement`, `model_estimate`, `synthetic_parameter`, `verified_rule`, `unknown`. A value can be derived from multiple sources; preserve their identifiers. Null means unknown/unavailable, not zero. Times are seconds relative to a recorded UTC origin; weather temperatures use kelvin internally with explicit display conversion.

## 3. Main interfaces

| Interface | Input | Output | Invariants / error modes |
|---|---|---|---|
| `run_episode(spec, controller)` | Validated scenario and controller adapter | Episode report and append-only records | Seeded reproducibility; controller never receives plant object |
| `decide(input, controller_state, budget)` | Permitted decision input, prior internal state, deadline | Recommendation and new controller state | No IO lookup of hidden truth; bounded work; declared fallback |
| `observe(history, available_time)` | Authorized raw events up to availability time | Observation frame | No future samples or duplicate assimilation |
| `race_value(query)` | Reachable resource/context state and remaining laps | Cost, targets, valid domain and provenance | Units in seconds for required build; unknown outside domain |
| `advance(actions, dt)` | Feasible/attempted controls and integration interval | New plant state plus events | Plant-owned truth; energy and geometry checks |
| `evaluate(manifest)` | Frozen controller/configuration/seed sets | Metrics and failures | Same information and initial resources; no silent exclusions |

`advance` is private to the simulation/evaluator process context. Tests can inspect it, but the deployable decision adapter cannot. Use serialized immutable decision inputs so accidental object references cannot expose private fields.

## 4. Decision input

Required fields:

- `decision_time_s`, `last_observation_available_at_s`, `run_mode` and clock origin.
- `ego`: progress/speed; estimated SOC/temperature and uncertainties; current constraints; tyre-set context; provenance for each state; previously applied controls and measured/reported saturation, distinct from earlier requested controls.
- `opponents`: public identity/context and observation frames only. Controller-owned belief state is passed separately, not substituted for observed truth.
- `track_context`: relevant path samples, curvature, width, candidate windows and track-condition confidence.
- `event_context`: lap, laps remaining, race-control state and verified/unknown mode permissions.
- `resource_targets`: reachable reserve band, lap budget, race-value version and lifecycle-price provenance.
- `versions`: vehicle prediction model, ruleset, feature transform, candidate library and trained artifact identifiers.

Fields specifically prohibited: true rival SOC/current/temperature, policy-family label, future telemetry, random generator state revealing opponent futures, test labels and privileged-counterfactual outcomes.

## 5. Recommendation contract

| Field | Meaning |
|---|---|
| `status` | `RECOMMEND`, `RETAIN_REFERENCE`, `FALLBACK` or `UNAVAILABLE` |
| `action_family` | Reference / attack now / defer / defend / conserve / optional probe |
| `plan` | Timestamped speed, power and optional path references, with validity interval |
| `reference_id` | Exact baseline plan used for comparison |
| `alternatives` | Candidate IDs, modeled mean/downside cost, paired gain and rejection reason |
| `belief_summary` | Capability forecasts, hypothesis spread and evidence freshness; no claimed observed SOC |
| `resource_forecast` | Own modeled energy/thermal/tyre consequences, units and uncertainty |
| `constraint_report` | Physical/rule residuals, limiting constraints, prediction-model validity |
| `reason_codes` | Machine-readable cause; presentation maps to plain-language explanation |
| `runtime` | Estimation, compilation, solve, rollout, verification and total wall times |
| `trace` | Input IDs, versions, scenario-set ID, score criterion and error-margin provenance |

Suggested reasons: `GAIN_SURVIVES_SCENARIOS`, `AMBIGUOUS_CAPABILITY`, `INSUFFICIENT_RESERVE`, `THERMAL_LIMIT`, `GRIP_LIMIT`, `ELIGIBILITY_UNKNOWN`, `INPUT_STALE`, `SOLVER_TIMEOUT`, `NO_FEASIBLE_REFERENCE`, `MODEL_OUT_OF_DOMAIN`. Multiple reasons may apply; do not collapse all into “trap.”

## 6. Ruleset contract

Store edition, document URL/hash, article, event supplement identity, reviewer and verification status. Distinguish:

1. MGU-K DC power and torque limits.
2. Speed-dependent deployment envelope and any event/sector/low-grip modification.
3. ES usable/swing accounting and separately measured recharge counters.
4. Detection/activation lines, authorization notifications and mode expiry/disable events.
5. Pit-lane lap-accounting transitions and relevant restrictions.

The reviewed baseline is FIA Technical Issue 20 and Sporting Issue 08, dated 5 August 2026; event completeness remains unverified [D03]. Do not copy a general 350 kW cap into every operating regime or treat a permitted 4 MJ energy swing as battery capacity. Unverified ruleset fields remain null and affected modes disabled. The example ruleset is intentionally non-executable until completed; it is not certification.

Put detailed speed curves in validated configuration tables and test breakpoints/units. Do not duplicate them in UI code. A public one-second gap observation is not a mode authorization event.

## 7. Experiment and parameter manifest

Every run records:

- Code revision or source-tree hash, dependency lock hash and platform/hardware.
- Master seed and separate plant, sensor, opponent and controller seed derivations.
- Scenario, track, ruleset, plant, controller and observation versions/hashes.
- Initial resources, component identities, health assumptions and exogenous event schedule.
- Candidate/scenario/iteration caps, wall-clock budget and fallback configuration.
- Objective units, terminal conditions, commitment margin and its tuning split.
- Native observation cadence, latency/noise/missingness model and data origin.
- Pass definition, numerical tolerances, metric definitions and invalid-run policy.

Each parameter entry needs value, unit, source, calibration status, valid range and uncertainty/sensitivity range. Parameters without evidence can be synthetic, but must not inherit the prestige of a nearby paper citation. The example manifest has null values for measurements and unresolved identifiers; run validation must reject incomplete execution manifests.

## 8. Storage and proposed project layout

Use local files first: immutable JSON Lines for decision/events, columnar/tabular episode outputs where useful, JSON configuration/manifests and a compact summary report. No database server, message queue, cloud deployment or live data subscription is required for the closed-loop build.

```text
gridops/
  contracts/            versioned records and validation
  simulation/           physical plant, rivals and sensors
  decision/             belief, candidates, planning and supervisor
  race_value/           reference maps and strategic allocation
  evaluation/           baselines, batches, metrics and reports
  adapters/             public replay and record-driven presentation
configs/                approved scenarios and rulesets
tests/                  contracts, mechanisms, episodes, leakage
artifacts/              immutable manifests, traces and results
```

This layout is proposed; these implementation directories are not created by the specification task. Keep controller artifacts and evaluator-only truth separate in storage and access paths. Public-data credentials, if later needed, never enter manifests or committed files.

## 9. Interface requirements for the later UI

The interface must show run mode, clock/freshness, primary recommendation, reference alternative, uncertainty and binding constraints. Use energy/power/temperature traces and a visible experiment comparison. A track view is optional until the geometry is verified; a rival “mind gauge” is not appropriate language.

Scenario interventions create a new run/branch and are logged. Pause/play is playback control, not an invisible physical-state change. Replayed decision records must display exactly their recorded recommendations rather than recompute with newer models. UI refresh can be independent of sensor and planner rates.

## 10. Development stack and dependency policy

Proposed CPU stack: Python, NumPy/SciPy, typed record validation, CVXPY with Clarabel for conic subproblems, pytest and a lightweight plotting/presentation adapter. FastF1 or OpenF1 is an optional public replay adapter. A frontend framework can be chosen after the record interface exists; the old synthetic HTML is not an experiment engine.

Check official solver documentation [S01–S03], installed solver availability and platform support, then pin exact versions in a lockfile during implementation. OSQP is an option only for a QP-compatible formulation. CasADi/IPOPT and GPU training are optional research dependencies, not required imports. No packages are installed or pinned by this documentation task.
