# Validation, experiments and claim gates

Status: prospective protocol. No results are reported here. Freeze method settings and metric definitions before the final test batch.

## 1. Evidence ladder

1. **Implementation correctness:** unit/sign, numerical and contract tests.
2. **Model validity within its assumptions:** conservation, limiting cases, geometry and convergence.
3. **Closed-loop decision value:** matched controllers in reactive simulation.
4. **Robustness:** different plant parameters, sensor conditions and opponent policies.
5. **Observable-data relevance:** causal forecasting on held-out public telemetry.
6. **External validity:** independent/identified plant and authorized team evidence; future work.

Passing one level does not imply the next. A posterior matching synthetic labels is not a measurement of real opponent SOC. Simulator performance is not a real-race lap-time gain.

## 2. Primary test seam

Run a complete episode through the decision interface with the same observation adapter, initial resources and event schedule. Inspect decision records and outcome reports. Keep focused numerical tests for the battery, grip, geometry and time integration because aggregate performance can conceal compensating errors.

No UI is needed to pass scientific acceptance. The later UI must reproduce the accepted records rather than invent additional conclusions.

## 3. Mechanism and invariant tests

| Test family | Required checks | Failure meaning |
|---|---|---|
| Accounting | Units; deployment decreases charge; recovery increases charge within headroom; internal loss counted once; separate DC counters | Invalid physics, not merely poor strategy |
| Battery | Known resistance-free limit; valid current root; current/voltage saturation; cooling with no heat; frozen-health semantics | Unsupported power/temperature forecast |
| Tyres | Wear never decreases; heat can recover; compound parameters change behavior; tyre-set reset preserves battery/driver context | Wrong causal state model |
| Grip | Straight/corner trade-off; braking and deployment bounds; low-grip perturbation; plant rejects infeasible candidate | Feasibility claim unsupported |
| Geometry | No contact/track exit counted as pass; sustained separation; re-pass possible; refine near collision | Overtake result unsupported |
| Events/rules | Unknown authorization disables restricted mode; exact line/event timing; lap/pit counters; breakpoint units | Modeled rules invalid |
| Memory | Posterior propagation; elapsed-time changes; missing evidence; new session/tyre/component reset scope | Persistence leaks or preserves wrong state |
| Planner | DCP, solver compatibility, trust region, primal residuals, incompatible target feedback | Candidate cannot be treated as feasible |
| Failure paths | Stale input, timeout, exhausted scenario budget, invalid cache, infeasible reference | Required fallback/unavailable behavior absent |

Choose and record tolerances with scale: initial targets may be relative battery-energy residual <= 0.1% over a test episode and <= 0.2% episode-time change when halving the integration step. They are engineering starting tolerances, not physical validation thresholds. Investigate systematic bias even when it falls below tolerance. Near geometry events, refine enough that the pass classification stabilizes; report unstable cases.

## 4. Information-leakage tests

- Hold the permitted input fixed and mutate hidden rival SOC/policy/temperature. The immediate recommendation must not change. Later recommendations may change only after permitted observations differ.
- Replace future telemetry, unannounced future events and evaluator labels after the current time. Current features and actions must remain unchanged. Already published schedules, verified track geometry and legitimately available forecasts are permitted context, not future truth.
- Ensure rolling baselines use prior completed data and no held-out session information.
- Ensure overlapping/resampled observations do not multiply evidence counts.
- Ensure hypothetical rollout controllers cannot read sampled latent state directly.
- Ensure preprocessing, calibration, learned priors, continuation maps and hyperparameter tuning use only their allowed splits.
- Verify cache keys include model/rules/context validity and never encode a hidden evaluation label.
- Separate privileged comparator records from deployable controller input and presentation during decision time.

This is a release gate, not an optional research refinement.

## 5. Required baselines

| ID | Controller | Purpose |
|---|---|---|
| B0 | Budget-aware heuristic: predefined eligible deployment windows and reserve | Practical minimum comparator; no future rival truth |
| B1 | Competitor-unaware conditional convex planner with the same plant constraints and race value | Measures value of interaction modeling |
| B2 | Posterior-mean scenario planner with identical beliefs, candidates, continuation and compute | Isolates ambiguity-aware commitment from better physics or more search |
| M | Proposed ambiguity-aware commitment rule | Main method under test |
| B3 | Optional CVaR/minimax-regret planner with matched resources | Tests whether an established risk criterion explains the benefit |
| O | Evaluator-only best feasible candidate with true latent state, within a specified candidate library | Privileged diagnostic reference; not a global optimum or deployable baseline |

The forty-state HMM/paper policy reproduction is a separate baseline only after its parameter availability and fidelity are audited. A four-state filter plus thresholds cannot be labelled an exact reproduction of the full paper.

## 6. Scenario families

**S1 — ambiguous opportunity.** Construct similar observable histories from different combinations of reserve, thermal capability, conservation and traffic. Then allow reactive defense. Include an explicit ambiguity metric over normalized observable histories; test multiple noise/cadence settings. Do not encode perfect separation into emission distributions and call it discovered.

**S2 — immediate versus later opportunity.** Keep the initial attack window similar while changing laps remaining, reserve or later overtaking opportunity. Demonstrate whether continuation value alters deployment. Score the full episode, not the first straight.

**S3 — physical capability shift.** Change battery cooling/resistance/capacity assumptions or tyre compound/thermal state. Test whether the planner reduces an infeasible commitment and whether the reduction improves eventual outcomes. Report these as synthetic health/thermal scenarios.

**S4 — response shift.** Evaluate aggressive defense, delayed defense, conservation, adapted response and an opponent ignoring a feint. Include an opponent stronger than the ego so “cannot win” is an allowed outcome.

**S5 — observation/event disruption.** Sensor loss, latency, a tyre change, unknown component replacement, mode authorization changes and wrong historical priors. Useful for reliability and persistence tests; not all need a polished demo scene.

Hackathon target: at least 10 paired seeds in each of four selected families, each evaluated by B0/B1/B2/M if runtime permits. This is a small diagnostic batch, not an adequately powered publication study. If reduced for time, disclose counts and incomplete comparisons rather than hide them. Use a separate showcase seed; it is not the statistical result.

## 7. Outcomes and definitions

Primary outcome for the required model: total episode/finish-time cost, with identical terminal conditions and separately reported finishing order. Compare paired differences per scenario/seed. Resource-aware planning uses a declared continuation cost, but the evaluator must also expose raw time, energy and position to prevent an arbitrary penalty from manufacturing improvement.

Secondary measures:

- **Attack expenditure:** gross positive MGU-K DC energy during a predeclared attack interval; report recovery separately. A failed attack does not imply every joule was useless.
- **Unsuccessful attack rate:** initiated attempts not meeting the sustained-pass definition within the stated horizon; separate aborts, re-passes and physical failures.
- **Missed opportunity:** retained reference where the specified hindsight feasible-candidate comparator would exceed the same benefit threshold. This is model- and candidate-library-dependent.
- **Decision regret:** selected cost minus comparator cost under matched evaluation; disclose comparator privilege and search limits.
- **Constraint violations:** count, maximum magnitude, duration and whether numerical, prediction or execution related.
- **Calibration:** future-observable forecast error/coverage; simulated hidden-capability calibration only where truth is available. Report support/sample count.
- **Reliability:** fallback/unavailable rate, completion rate, plan oscillation and latency tails.
- **Resource condition:** terminal reserve, maximum battery temperature, tyre wear proxy and stress exposure.

Do not define “wasted energy” solely as no immediate position change; defense and future setup can have value.

## 8. Splits, uncertainty and fairness

Separate development, calibration/selection and frozen test configurations. Public splits are chronological by session/event, not random adjacent telemetry rows. Simulation splits hold out opponent families/parameters and physical regimes; a new seed from the same generator is not independent model validation.

Use paired initial conditions and exogenous randomness. Isolate random streams so one controller's extra rollout does not change the physical opponent's random draws. Report per-family outcomes, median/mean paired differences and uncertainty intervals where sample size supports them. Bootstrap at the episode or event cluster level, not individual correlated telemetry samples. Small-batch intervals are descriptive and can be unstable.

Report failures for every method. Do not discard infeasible/timeout episodes from the winning method's average. Present completion rates alongside common-success comparisons and an explicit failure penalty or separate ranking; freeze that policy before tests. Do not declare statistical significance without a justified test and adequate sample design.

## 9. Ablations

Compare the complete method against versions without: retained ambiguity, contextual persistence, opponent reaction, thermal limits, compound/thermal/wear effects, remaining-race value, and optional feints. In each comparison preserve the same physical plant and data access. Changing the plant as well as the controller would hide the feature's cost.

Use one-factor removals from the full method plus a small staged build-up. The build-up alone is order-dependent. Measure compute and calibration effects, not only the favorable outcome metric. Lifecycle, RL and a richer battery model earn a claim only after their own ablation.

## 10. Runtime and numerical reproducibility

Initial advisory target: tactical replanning nominally once per second; warm total-decision p95 <= 300 ms with a 500 ms wall-clock cutoff, subject to measured hardware feasibility. These are goals, not achieved figures or actual-F1 operational requirements. HMM-only microbenchmarks do not establish total latency. Record cold compilation separately and also report its user-visible startup cost.

Native solvers may not honor Python-level cancellation. Use solver-supported limits plus an isolated worker that can be abandoned/terminated without blocking the execution loop; validate that behavior on the chosen platform. If the deadline cannot be enforced, do not claim bounded real-time operation.

For deterministic scientific runs, fix algorithmic rollout/iteration budgets. For wall-clock stress tests, record the exact cutoff and completed work; machine timing can make seeded runs differ. Reproducible playback uses recorded decisions, while numerical reruns use the frozen work-budget mode. Keep those guarantees separate.

## 11. Claim release gates

| Claim | Required evidence |
|---|---|
| Working simulation | Mechanism, accounting and episode tests |
| Completed simulated pass | Geometry, separation and persistence tests |
| Competitor-aware decisions | Action-responsive rival and shared-information baseline |
| Improved benchmark result | Frozen test batch with paired outcomes and failures |
| Persistent memory helps | Held-out-context and reset ablation |
| Real-time on stated hardware | Measured end-to-end tails, enforced cutoff and fallback |
| Public-data forecast relevance | Causal held-out observable forecasts |
| Battery-life improvement | Identified ageing model and external evidence; unavailable in core build |
| Haas race gain / FIA certification | Authorized operational validation; unavailable in core build |
| Publishable novelty | Closest-work comparison plus substantive reproducible contribution; unproven |
