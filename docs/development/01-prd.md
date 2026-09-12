# Product requirements document

Status: proposed specification · Local review draft · Intended triage role after approval: ready-for-agent

## Problem Statement

A race engineer must decide whether spending finite electrical energy now improves the eventual race result. Visible rival speed may reflect conservation, power restriction, tyre condition, traffic, weather or car performance; the same observation can support different explanations. An unsuccessful attack can consume resources needed later. A confident but unsupported rival-state estimate can therefore be more damaging than an explicitly uncertain one.

The Trackshift theme asks for energy-deployment and overtake risk–reward decision support. Our demonstrator must show decisions affecting simulated outcomes, not merely classify prewritten scenarios or animate historical traces. Its intended customer conversation is with a professional strategy/performance group such as Haas; that is a proposed audience, not an endorsement.

## Solution

Provide a reproducible simulation workbench and decision engine that compares feasible attack, defend, defer and reference plans. It carries uncertain rival explanations forward, includes remaining-race resource value, and exposes recommendation reasons, alternatives, limiting constraints and evidence quality. Engineers remain responsible for decisions. No car actuation is in scope.

### Success definition

Delivery succeeds when another developer can reproduce a complete episode and benchmark from a frozen configuration, verify the observation restrictions, inspect resource accounting and explain why the selected strategy differs from the baseline. Competitive superiority is a research question, not a delivery prerequisite: unfavorable results must remain visible.

## User Stories

1. As a race engineer, I want an attack recommendation with its energy cost and later consequences, so that immediate speed is not mistaken for race value.
2. As a race engineer, I want plausible rival responses, so that I can understand what could invalidate a recommendation.
3. As a race engineer, I want the reference strategy shown beside the proposed change, so that the comparison has a clear meaning.
4. As a race engineer, I want abstention when evidence is insufficient, so that uncertainty is not hidden behind a command.
5. As a race engineer, I want the reason for abstention, so that uncertainty, physical limitation and solver failure are distinguishable.
6. As a race engineer, I want current energy, temperature and power limits separated, so that I can identify the binding constraint.
7. As a race engineer, I want compound and tyre-set context, so that thermal grip recovery is not confused with wear reversal.
8. As a race engineer, I want defensive value included, so that holding position is not automatically called wasted energy.
9. As a race engineer, I want a verified event-rules profile, so that mode eligibility is not inferred from gap alone.
10. As a race engineer, I want observation freshness and source labels, so that simulated, inferred and measured quantities cannot be confused.
11. As an analyst, I want a replay mode, so that observable forecasts can be compared with recorded telemetry.
12. As an analyst, I want a distinct simulation mode, so that action-dependent counterfactuals are not presented as historical outcomes.
13. As an analyst, I want driver priors conditioned on context, so that car performance is not reduced to a personality score.
14. As an analyst, I want sparse-history fallback, so that a new driver/session does not produce unwarranted confidence.
15. As an analyst, I want tyre changes and component changes recorded separately, so that persistent memory respects physical identity.
16. As an analyst, I want environmental perturbations, so that the strategy can be challenged under plausible model mismatch.
17. As an analyst, I want a delayed or unresponsive rival policy, so that a feint is allowed to fail.
18. As a researcher, I want identical observation contracts for competing controllers, so that comparisons are fair.
19. As a researcher, I want a privileged comparator labelled explicitly, so that it is not mistaken for a deployable policy.
20. As a researcher, I want held-out opponent families and physical parameters, so that the inference model is not evaluating its own assumptions.
21. As a researcher, I want complete outcome distributions, so that selected successful runs do not determine the claim.
22. As a researcher, I want component ablations, so that added complexity must demonstrate value.
23. As a researcher, I want attempted-attack and missed-opportunity definitions fixed before testing, so that metrics cannot be adjusted to flatter a method.
24. As a developer, I want deterministic seeded episodes, so that failures can be reproduced.
25. As a developer, I want bounded planner execution and a current-state fallback, so that a slow solve cannot stall the experiment.
26. As a developer, I want versioned contracts and parameter provenance, so that model changes remain traceable.
27. As a presenter, I want the interface to read actual decision records, so that every chart and headline can be traced to an experiment.
28. As a presenter, I want borrowed methods and proposed novelty separated, so that the pitch remains defensible.

## Implementation Decisions

### Scope and requirements

| ID | Requirement | Priority | Acceptance evidence |
|---|---|---|---|
| R01 | An action-responsive ego/rival simulation produces a complete episode | Required | Changing a feasible action changes future motion/resources; deterministic seed test |
| R02 | Controller receives only permitted observations and declared own-car state | Required | Privileged-state and future-data mutation tests |
| R03 | Deployment obeys signed energy accounting and modeled physical limits | Required | Conservation, saturation and integration-refinement tests |
| R04 | Event permissions are versioned and explicitly unknown when unverified | Required | Unknown eligibility prevents restricted mode; provenance audit |
| R05 | Candidate plans use a conditional convex formulation with explicit assumptions | Required | Convexity check, solver residuals and nonlinear rollout check |
| R06 | Beliefs persist causally and retain uncertainty about rival capability | Required | Sequential update, missing-data and ambiguity tests |
| R07 | Tactics include reactive opponent futures | Required | Action-dependent opponent responses; nonreactive comparator |
| R08 | Remaining-race value influences tactical energy use | Required | Matched immediate opportunity with different remaining-race context |
| R09 | Battery thermal behavior and tyre compound/thermal/wear state affect capability | Required | Controlled paired scenarios and mechanism tests |
| R10 | Health assumptions belong to identified or explicitly unknown components | Required | Replacement and uncertain-identity tests; no invented measured SOH |
| R11 | Planner can retain baseline, fall back or become unavailable | Required | Timeout, stale data, infeasible target and invalid-model tests |
| R12 | Replay and modeled counterfactuals are separated | Required | Mode-labelled records and interface |
| R13 | Completed passes require modeled geometry/separation/persistence | Required for passing claim | Geometric pass tests; otherwise report catch-up only |
| R14 | Experiments compare frozen methods on matched initial conditions | Required | Batch manifest, paired seeds and complete result table |
| R15 | Decision records drive all presentation outputs | Required | Record-to-display checks and traceable metric export |
| R16 | Explicit feint candidates are evaluated against several responses | Optional | Benefit and failure cases without scripted success |
| R17 | A small synthetic lifecycle optimization can produce wear values | Optional | Known-answer finite-horizon test and declared payoff maps |
| R18 | Learning can improve candidate selection or continuation estimates | Research follow-up | Same-information, matched-compute comparison with nonlearned planning |

### Architectural choices

- One local application with deep modules, not distributed services. Separate simulation truth from the decision interface from the beginning.
- A nonlinear plant evaluates a simpler conditional convex prediction model. Initial warm starts and candidate libraries keep expensive optimization outside the inner scenario loop.
- Four planning horizons exchange resource budgets, continuation values and feasibility feedback. They are not four independent weighted scores or necessarily four MPCs.
- Within-race health is a fixed uncertain parameter in the first release; stress exposure evolves. Quantitative life loss is not identified from public logs.
- Candidate selection uses bounded scenario evaluation. A probabilistic planner and an energy-budget heuristic are explicit baselines.
- All state transitions, information availability and source provenance are versioned. UI state cannot modify experimental truth outside an explicit scenario intervention.

## Testing Decisions

The primary acceptance seam is a complete episode through the decision module's interface. Tests assert observable behavior and invariant outcomes, not private solver iterations. Internal numerical tests are retained where a full episode would obscure a unit, sign or integration error. No verified existing simulator tests are present to reuse.

Test the simulator, observation adapter, decision module, event ledger and evaluator. Use paired actions, perturbed hidden truth, delayed observations and known physical limits. Include negative outcomes: impossible pass, useless feint, insufficient reserve, stale model and solver timeout. Numerical tolerances, dataset splits and compute limits are recorded before evaluating the frozen test set.

Performance targets are advisory-simulation targets on a declared machine, not actual-car real-time guarantees. The build plan specifies measured go/no-go gates and an anytime fallback; no solver runtime is assumed from a paper.

## Out of Scope

ECU/CAN actuation; autonomous safety certification; a calibrated Haas digital twin; full FIA compliance without event supplements; actual rival SOC/SOH measurement; full-grid equilibrium; CFD or detailed electrochemical simulation; exhaustive pit/season optimization in the required 24-hour build; guaranteed victory or publication; representing historical counterfactual gains as observed fact.

## Further Notes

This is a specification, not a declaration that requirements are implemented. The backlog is proposed pending review. Organizer rules and public-data redistribution permissions are kickoff prerequisites. The complete hierarchy and research roadmap are preserved even when optional delivery features are gated out. Scientific claims must state precisely which features and tests were actually completed.
