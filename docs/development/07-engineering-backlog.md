# Proposed development backlog

Status: draft for granularity/dependency review; not published to an external tracker and not claimed as approved. Source: [PRD](01-prd.md). Work the frontier: a slice becomes available when its listed blockers are complete. Each slice must expose a verifiable end-to-end behavior through an episode, record or report; visual UI is not required for every slice.

## T01 — Reproduce one action-responsive episode

**What to build:** a developer starts a declared scenario with a reference controller and obtains a deterministic episode trace and manifest.

**Blocked by:** None — can start immediately.

**Owner:** A with B on record contract. **Requirements:** R01, R02 foundations.

- [ ] Configuration, units, initial bounds and provenance are validated.
- [ ] Changing ego action changes future state; rival truth is not passed to the controller.
- [ ] Fixed-work seeded reruns reproduce the trace within declared tolerances.
- [ ] Final report includes completion/failure and raw time/resource outcomes.

## T02 — Replay public observations without invented state

**What to build:** an analyst loads a cached permitted telemetry fixture and obtains a causal, provenance-labelled observation stream.

**Blocked by:** None — can start immediately against the proposed contract.

**Owner:** B. **Requirements:** R02, R12.

- [ ] Native cadence, throttle units, missingness and timestamps are audited.
- [ ] Features use only available past data; future-data mutation test passes.
- [ ] Missing energy/health/aero channels remain unknown or explicitly inferred.
- [ ] Output is marked replay and cannot claim action-dependent historical results.

## T03 — Execute within battery, grip and event limits

**What to build:** an episode shows how a requested deployment is accepted, saturated or rejected, with correct energy/thermal accounting and rule explanations.

**Blocked by:** T01 — Reproduce one action-responsive episode.

**Owner:** A. **Requirements:** R03, R04, R09 battery foundation, R11.

- [ ] Battery sign/root/conservation and cooling tests pass.
- [ ] Current, voltage, energy and combined-grip constraints affect executed controls.
- [ ] Unknown restricted-mode authorization is rejected.
- [ ] Saturation and invalid conditions are visible in records; no silent state clipping.

## T04 — Preserve tyre and contextual memory across events

**What to build:** a scenario with tyre/environment changes produces distinct grip/wear trajectories and correctly scoped memory resets.

**Blocked by:** T01 — Reproduce one action-responsive episode.

**Owner:** B. **Requirements:** R09 tyres, R10.

- [ ] Compound-specific thermal/wear model changes capability.
- [ ] Cooling does not reverse wear; tyre replacement resets only relevant states.
- [ ] Component identity can be unknown; penalties do not imply health loss.
- [ ] Reports distinguish stress proxies from measured deterioration.

## T05 — Compare reference and constrained deployment

**What to build:** the same scenario runs through a conditional convex planner and a reference controller, returning executed profiles and comparable outcomes.

**Blocked by:** T03 — Execute within battery, grip and event limits.

**Owner:** A. **Requirements:** R05, R11, R14 foundation.

- [ ] DCP/solver capability, residuals and trust-region checks pass.
- [ ] Nonlinear execution rejects or reports prediction infeasibility.
- [ ] Timeout/infeasible-target path rechecks the reference rather than blindly reusing a plan.
- [ ] Both controllers receive equal initial resources and constraints.

## T06 — Decide from persistent uncertain rival evidence

**What to build:** a noisy simulated observation sequence updates a rival-capability belief and produces a record showing how uncertainty changes over time.

**Blocked by:** T01 — Reproduce one action-responsive episode. T02 is an integration dependency only for public replay, not simulated inference.

**Owner:** B. **Requirements:** R02, R06.

- [ ] Missing/late observations propagate uncertainty; repeated evidence is not double-counted.
- [ ] Immediate hidden-state mutation cannot change the action under identical permitted input.
- [ ] Hypotheses separate capability from intent; no exact public SOC claim.
- [ ] New-session and sparse-history behavior is tested.

## T07 — Value energy beyond the next attack

**What to build:** otherwise similar attack windows receive different energy targets when remaining-race opportunities or reserves differ.

**Blocked by:** T05 — Compare reference and constrained deployment; T04 — Preserve tyre and contextual memory across events.

**Owner:** A. **Requirements:** R08, R09 integration, R10 lifecycle interface.

- [ ] Reachable lap-map/value queries are versioned and use compatible units.
- [ ] Terminal resource cost is counted once and matched across baselines.
- [ ] Out-of-domain/unreachable targets are rejected or conservatively handled.
- [ ] Configured lifecycle price is labelled season-informed.

## T08 — Compare commitments against reactive rivals

**What to build:** the decision engine ranks reference/attack/defer/defend alternatives against rival responses and can rationally retain the reference.

**Blocked by:** T05 — Compare reference and constrained deployment; T06 — Decide from persistent uncertain rival evidence; T07 — Value energy beyond the next attack.

**Owner:** B with A on profile integration. **Requirements:** R07, R08, R11.

- [ ] Rival future changes in response to ego action; unresponsive and strong-rival cases exist.
- [ ] Shared initial actions enforce non-anticipativity across indistinguishable futures.
- [ ] Posterior-mean and ambiguity-aware methods use matched candidates/compute.
- [ ] Runtime cutoff, error allowance and rejection explanations are recorded.

## T09 — Count only geometrically checked passes

**What to build:** simulated passing attempts can succeed, abort or be re-passed, with footprints, track containment and persistence determining the label.

**Blocked by:** T03 — Execute within battery, grip and event limits.

**Owner:** A. **Requirements:** R13.

- [ ] Candidate path tracking respects the configured acceleration envelope.
- [ ] Collision/track exit cannot be labelled a successful pass.
- [ ] Integration refinement stabilizes classification near close interactions.
- [ ] Without this capability, every output remains catch-up/opportunity only.

## T10 — Freeze and evaluate the scientific comparison

**What to build:** one batch produces complete paired outcomes for B0/B1/B2/M across held-out conditions, including failures and ablations.

**Blocked by:** T08 — Compare commitments against reactive rivals; T04 — Preserve tyre and contextual memory across events. T09 additionally blocks any completed-pass claim.

**Owner:** B with A on failures. **Requirements:** R14, R02 final gate, R09 final gate.

- [ ] Test splits/settings are frozen; no test-set tuning is used in the reported batch.
- [ ] Failure/timeout episodes remain accounted for.
- [ ] Raw time/energy/position and model-dependent metrics are distinguished.
- [ ] Numerical, leakage, reset and latency results accompany performance results.

## T11 — Present recorded decisions and reproduce the demo

**What to build:** an engineer opens a recorded run, inspects the recommendation and alternatives, and can trace every displayed metric to the frozen experiment.

**Blocked by:** T10 — Freeze and evaluate the scientific comparison. The presentation adapter can be drafted earlier against fixtures, but completion requires real records.

**Owner:** B; A packages reproduction. **Requirements:** R12, R15.

- [ ] Simulated/inferred/public data and unavailable states are visually distinct.
- [ ] The demo includes ambiguous, later-value and failure/limitation cases.
- [ ] Reproduction instructions, dependencies and permitted fixtures are packaged.
- [ ] Pitch claims match implemented requirements and measured outcomes.

## T12 — Test a strategic energy feint

**What to build:** an optional probe/defer policy is compared against opponents that respond, adapt or ignore it, with later race consequences scored.

**Blocked by:** T08 — Compare commitments against reactive rivals; T09 — Count only geometrically checked passes if the claim involves passing.

**Owner:** whichever lane clears first. **Requirements:** R16. **Priority:** optional; do not delay T10.

- [ ] No scripted depletion, illegal maneuver or guaranteed-success label.
- [ ] Its own resource/time cost is included.
- [ ] Failure and successful response families are both reported.

## T13 — Solve an explicitly synthetic lifecycle example

**What to build:** a small finite event/inventory model changes its marginal stress value when future events or replacement options change.

**Blocked by:** T07 — Value energy beyond the next attack.

**Owner:** A after required gates. **Requirements:** R17. **Priority:** optional.

- [ ] Known-answer dynamic-program test and explicit payoff/wear maps.
- [ ] Component identity and replacement transitions are correct.
- [ ] No calibrated battery-life or entire real championship claim.

## T14 — Research-grade extension campaign

**What to build:** a follow-up study compares stronger learned/risk-aware baselines, independent plant assumptions and a bounded novelty hypothesis.

**Blocked by:** T10 — Freeze and evaluate the scientific comparison.

**Requirements:** R18 and publication evidence. **Priority:** after the event.

- [ ] Closest-work full-text/code review and exact reproduction/adaptation labels.
- [ ] RL/value training has no deployable-policy truth leakage and declared compute.
- [ ] Expanded held-out scenario design, statistical analysis and reproducible artifacts.
- [ ] Negative results and remaining external-validity limits are reported.
