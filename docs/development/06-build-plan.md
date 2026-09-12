# Two-person, 24-hour build and execution path

All times are relative to the official start. This is a dependency-aware plan, not a promise that every optional model fits. Both developers are assumed capable across the stack; ownership minimizes simultaneous changes to the same module.

## 1. Kickoff contract

Before reusing or submitting anything, verify organizer rules for pre-event code, external libraries, AI assistance, datasets, licenses and presentation format. Planning documents do not settle those rules. Select one circuit geometry, two-car scenarios, the evaluation horizon and a synthetic parameter provenance policy. Record machine, package versions and roles.

Use a single local process/application architecture with isolated planner execution where cancellation requires it. No Kubernetes, distributed microservices, cloud deployment or GPU job is on the critical path.

## 2. Parallel work lanes

| Window | Developer A — simulation/control | Developer B — evidence/evaluation | Integration gate |
|---|---|---|---|
| T+0–2 | State/control contracts, simple action-responsive plant | Run manifest, observation contract, deterministic runner, public sample audit | G0: both agree on units, hidden information and one complete scenario |
| T+2–6 | Battery/accounting, grip and baseline driver; numerical tests | Reactive rivals, sensor masks, tyre/context state, baseline reports | G1: full episode; different actions change outcome; no UI dependency |
| T+6–10 | Conditional convex deployment profiles and current-state supervisor | Persistent belief filter, causal features and leakage tests | G2: a decision record connects observations to a feasible executed profile |
| T+10–14 | Race continuation maps and checked passing paths | Bounded scenario evaluator, paired baselines and ambiguity cases | G3: attack/defer/defend choices change multi-lap outcomes; pass claims gated |
| T+14–18 | Thermal/tyre integration review, mismatch and latency fixes | Frozen method selection, held-out batches, optional feint only if stable | G4: all required mechanisms integrated; benchmark and failure table generated |
| T+18–21 | Reliability, worker cutoff, packaging and reproduction | Record-driven interface and pitch evidence | G5: replayable demo and reproducible result bundle |
| T+21–24 | Fix release blockers; submission support | Rehearsal, backup recording, citations and submission | Freeze with buffer; do not add a new algorithm |

Start thermal/tyre mechanisms before T+6, but permit the first tracer episode to use fixed capability. Their fully coupled behavior must pass tests before R09 is marked delivered. No major physical subsystem should first appear at T+16.

## 3. Gate actions when behind schedule

- **G0 fails:** stop adding scope. Resolve units, data availability and execution contracts. Use a declared synthetic reference circuit if real geometry cannot be verified.
- **G1 fails:** work jointly on the complete episode and accounting. Do not proceed to a complicated HMM or interface.
- **G2 fails:** retain the tested reference controller and reduce convex grid/candidate complexity. A heuristic fallback must be labelled; R05 remains incomplete until a valid constrained planner exists.
- **G3 geometry fails:** report catch-up/energy opportunity, not completed passes. This narrows the demonstration and must appear in the pitch.
- **G4 experiment budget fails:** drop optional RL, season DP, richer circuits and feints; preserve test integrity. Disclose smaller sample counts.
- **G5 timing fails:** demonstrate offline accelerated experiments with measured latency and no real-time claim. Never replace solver output with scripted recommendations.

Cutting features is an explicit delivery change, not permission to rename an incomplete system as the full architecture. Update the requirement matrix and pitch claims accordingly.

## 4. Required vertical milestones

1. Reproducible episode and manifest with a reference controller.
2. A resource-constrained action changes simulated speed, energy and subsequent ability to act.
3. The same episode runs with a convex deployment controller, showing residuals.
4. A persistent belief controller acts only on causal observations.
5. Candidate comparison includes a reacting opponent and multi-lap value.
6. Thermal/tyre changes alter feasible choices; geometric passing is checked where claimed.
7. Paired batch comparison exports all results and failures.
8. Interface and pitch read that frozen evidence.

Detailed acceptance criteria appear in the [proposed backlog](07-engineering-backlog.md). Work any unblocked slice; do not interpret the order as requiring a developer to wait on unrelated work.

## 5. Compute budget

Use CPU for the reduced plant and convex optimization. Precompute reusable lap/candidate maps and cache only inside declared state/rules validity ranges. Start small: five action families, a short tactical horizon, a coarse spatial grid and tens—not thousands—of opponent hypotheses. Profile before increasing any count.

Do not put a convex/NLP solve inside every rollout step. Generate candidate profiles once per valid state/query, cheaply simulate their consequences, then optionally refine the selected candidate. Benchmark process overhead and cold problem compilation, not just solve time.

GPU use is optional: later policy/value learning or parallel batch analysis. Available GPU memory does not solve missing physical calibration or small-data identifiability.

## 6. Development workflow

Agree on contract ownership at kickoff. Developer A owns dynamics and continuous planning; B owns evidence, policy comparison and evaluation; contract changes require a brief joint review and a schema-version update. Integration occurs at least at every gate, preferably after each complete slice.

Each slice finishes with a runnable episode or report, not a standalone notebook that nobody else can execute. Freeze dependencies during the first hours. Record unresolved assumptions in configuration, not in silent defaults. Preserve older research notes; do not treat the synthetic UI's existing numbers as baseline measurements.

Suggested future commands, to implement rather than assume present:

```text
gridops validate-config <scenario>
gridops run <scenario> --controller reference --seed 1
gridops run <scenario> --controller ambiguity-aware --seed 1
gridops evaluate <benchmark-manifest>
gridops report <run-or-batch-id>
gridops replay <recorded-run-id>
```

No claim in this package depends on these commands already existing.

## 7. Optional extensions and go/no-go

| Extension | Start only when | Stop/drop when |
|---|---|---|
| Energy feint | G3 works; multiple response families exist | Success depends on a scripted rival or harms main validation |
| Synthetic season DP | Required physical/decision gates pass; payoff maps are explicit | It becomes arbitrary lifetime claims or delays the batch |
| One-RC battery | Simple battery conservation already passes | Extra parameters cannot be justified or calibrated |
| Learned actor/value | Baselines, splits and stable simulator exist | Training/tuning consumes evaluation time or privileged input leaks |
| Full KKT game reproduction | Separate research phase with correct model/parameters | It becomes a required online dependency during the event |

## 8. Submission bundle

Include the implemented source and lockfile; allowed data-fetch instructions or redistributable fixtures; complete scenario/parameter/rules manifests; test instructions and output; result tables with failures; immutable demo traces; source-linked architecture and limitations; pitch file and backup recording. Never include credentials or redistribute restricted telemetry without permission.

The presentation headline must be generated from the actual batch. If no improvement is demonstrated, show the working mechanism and discovered limitations without fabricating a gain. A technically honest failure analysis is preferable to an unsupported quantitative claim.
