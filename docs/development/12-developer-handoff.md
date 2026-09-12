# Developer handoff and readiness checklist

## What exists now

A corrected PRD, architecture, mathematical model specification, data contracts, test protocol, two-person schedule, proposed backlog, glossary and source-linked pitch/research notes. The workspace also contains earlier research and an illustrative HTML interface. No verified simulator, controller, benchmark result, dependency lockfile or runnable development CLI exists yet.

Start at [the package index](README.md). Treat [the PRD](01-prd.md) as intended behavior and [the contracts](04-data-and-contracts.md) as the proposed engineering interface. Use [the backlog](07-engineering-backlog.md) to choose one complete slice. Do not begin by replacing the interface or training a DQN.

## First implementation session

1. Confirm organizer/reuse requirements and choose the reference scenario; use relative event time until the actual deadline is verified.
2. Resolve a small parameter set with explicit provenance. Synthetic is acceptable for a demonstrator when labelled; unknown is not silently treated as calibrated.
3. Establish a fresh implementation environment and lock dependencies after testing imports and installed solver capabilities.
4. Implement T01 and T02 in parallel, sharing the observation/record contract.
5. Complete a deterministic action-responsive episode and baseline report before adding sophisticated inference.
6. Add numerical and leakage tests immediately; do not postpone all validation until the presentation window.

## Parameter readiness ledger

| Parameter family | Must be resolved before its feature executes | Acceptable initial source |
|---|---|---|
| Track | Length, curvature, grade, width, coordinate frame, passing-window geometry | Verified geometry or explicitly synthetic closed track |
| Vehicle | Mass/inertia simplifications, footprint, wheelbase, force/torque/speed limits | Declared reference model with sensitivity range |
| Aero | Drag/downforce maps, wind convention, wake map and validity | Declared synthetic/reference coefficients; no private-team attribution |
| Engine | Mechanical force/power and fuel-use approximation | Declared generic map; not inferred as exact from throttle |
| Battery | Capacity, OCV, positive resistance map, current/voltage/SOC limits, thermal constants | Reference-cell/pack abstraction or synthetic sensitivity family |
| Health | Capacity/resistance multipliers and reference conditions | Scenario priors; no claimed measured rival SOH |
| Tyres | Compound IDs, temperature/grip/wear maps, heat/stress model | Declared surrogate families; no invented Pirelli calibration |
| Sensors | Cadence, units, delay, noise, missingness and availability times | Audited public sample or explicit simulation settings |
| Rivals | Policy families, reaction times and private memory | Scripted reactive policies with declared limits, not scripted outcomes |
| Rules | Edition/event, permissions, cap curves and accounting definitions | Verified source plus event profile; disable unresolved restricted modes |
| Cost | Episode objective, terminal conditions, stress conversion and reference | Explicit project choice; tune only on allowed splits |
| Numerics | Step size, solver tolerances, scenario counts and cutoff policy | Measured convergence/runtime selection |

The [manifest template](templates/run-manifest.example.json) intentionally contains nulls. It is a contract example, not an executable F1 configuration. Do not populate all unknowns with values copied from different papers without reconciling units, operating regime and vehicle assumptions.

## Suggested first validation commands

During implementation, create commands for config validation, one seeded episode, paired controller comparison, batch evaluation and record replay. The proposed names in the build plan are targets, not commands available now. Record the exact successful commands in the implementation README once they exist.

The development documentation itself was checked for local-link integrity, reference IDs, JSON syntax, table shape and backlog consistency. Those checks are not simulator tests and must never appear as evidence that the algorithm works.

## Session completion note

Every implementation handoff should state: slice completed; files changed; commands/tests actually run; measured results; known failures; unresolved assumptions; next unblocked slice. Mark a requirement complete only when its acceptance evidence exists. Preserve all negative results and do not silently weaken the information contract.

## Explicit unknowns

Organizer rubric/reuse rules; final event geometry and permissions; real battery/tyre/aero calibration; selected hardware and dependency versions; observed method performance; exact bounded-runtime behavior; external validation and publication novelty. These are not reasons to invent values. They are readiness checks, configurable assumptions, or future evidence tasks.
