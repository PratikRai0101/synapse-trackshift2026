# Race Energy Decision Support

A shared vocabulary for discussing energy deployment and competitor interaction. Definitions distinguish observable evidence from hidden state and simulated outcomes.

## Language

**Ego car**:
The car whose energy deployment the decision system advises.

**Opponent belief**:
A distribution or set of plausible opponent states conditional on the evidence available so far, not a measurement of the opponent's battery.
_Avoid_: Known opponent SOC, opponent telemetry ground truth

**Response capability**:
An opponent's physically feasible ability to counter an action over a specified upcoming track interval, conditional on an energy and vehicle-state hypothesis.

**Driver prior**:
A context-dependent initial model of a driver's observable behavior, distinct from their current intent and their car's physical capability.
_Avoid_: Fixed aggression score, personality diagnosis

**Deployment plan**:
A proposed allocation of electrical energy across track intervals, subject to the ego car's physical limits and an identified event ruleset.

**Energy reserve**:
Stored electrical energy retained for later use. This is distinct from a regulatory per-lap energy counter or an instantaneous electrical power limit.

**Attack window**:
A track interval where an attack can be evaluated, not an assertion that a pass will occur.

**Completed pass**:
A simulated or observed change in running order that satisfies the stated overlap, separation, and persistence criteria.
_Avoid_: Calling a longitudinal catch-up a completed overtake

**Model-feasible**:
Consistent with the physical constraints and rule predicates actually represented in the selected model; not a certification of real-world safety or full FIA compliance.

**Replay**:
Playback of recorded observations. An unobserved alternative strategy evaluated alongside a replay is a modeled counterfactual, not a historical result.

**Decision regret**:
The excess cost of a selected action relative to a specified comparator under the same evaluation conditions.

**Abstention**:
Withholding a proposed departure from the baseline strategy because the available evidence or model validity is insufficient.

**Battery state of charge (SOC)**:
The presently stored charge relative to a specified usable charge capacity. It is not a measure of permanent battery health, and it is not interchangeable with an electrical-energy counter in joules.

**Battery state of health (SOH)**:
Long-term battery condition relative to a defined reference, with capacity retention and resistance/power capability treated as distinct aspects.
_Avoid_: A universal health percentage that determines every battery property

**Battery thermal state**:
The battery's current temperature condition, distinct from its stored charge and accumulated irreversible degradation.

**Tyre thermal state**:
The current temperature condition affecting tyre performance; a temporary temperature-related grip change is not necessarily permanent wear.

**Tyre wear state**:
Accumulated deterioration of a particular tyre set, distinct from elapsed laps and reversible thermal performance changes.

**Component identity**:
The particular physical component to which age, usage, and health evidence belong; driver identity alone does not establish component continuity.

**Strategic energy feint**:
A tactical energy-use choice intended to influence a rival's response, whose benefit depends on that response and the later race outcome.
_Avoid_: Guaranteed trap, guaranteed opponent depletion

**Super-clipping**:
Energy recovery by the MGU-K while the driver remains at full throttle. Observing reduced speed at full throttle alone does not establish that this mechanism occurred.

### Decisions and outcomes

**Reference strategy**:
The explicitly identified, currently model-feasible strategy against which a proposed change is valued.
_Avoid_: An unspecified baseline, assuming yesterday's plan remains feasible

**Energy commitment**:
A decision to spend electrical resources on a particular tactical objective, with consequences extending beyond the current control interval.

**Decision-relevant ambiguity**:
Uncertainty between plausible hidden explanations whose differences can change the value or ranking of available actions.

**Commitment margin**:
The required modeled improvement over the reference before a proposed change is recommended.
_Avoid_: A guaranteed real-world advantage

**Continuation value**:
The modeled cost or utility of the race remaining after a planning interval, conditional on the resulting resource and race state.

**Strategic abstention**:
A deliberate decision to retain the reference because available alternatives do not justify a commitment under the chosen uncertainty criterion.
_Avoid_: Solver failure

**Technical fallback**:
Use of a currently checked reference policy because the requested planning process could not produce an accepted recommendation.
_Avoid_: A successful uncertainty-aware decision

**Catch-up**:
Reduction or reversal of longitudinal separation without, by itself, establishing a geometrically valid sustained pass.

**Modeled counterfactual**:
A simulated outcome under an alternative action, distinguished from an outcome actually observed in a historical race.

### Resources, context and evidence

**Chemical stored energy**:
The battery's internal energy under a specified electrochemical/reference model, distinct from terminal energy delivered after internal losses.

**DC energy counter**:
Accumulated electrical energy measured at a specified direct-current accounting location over a defined interval.
_Avoid_: Battery capacity, SOC

**Ageing stress proxy**:
A declared summary of operating exposure relevant to degradation, without an identified conversion into capacity loss or remaining life.

**Compound identity**:
The actual tyre specification associated with a season/event nomination, distinct from its relative Hard, Medium or Soft label.

**Tyre-set identity**:
The particular physical set to which usage and wear history belong.

**Season-informed strategy**:
A race strategy using explicit lifecycle assumptions or resource prices without necessarily solving a multi-event optimization problem.
_Avoid_: A fully optimized season MPC

**Observation availability time**:
The time at which a measurement or derived race statistic can actually be used for a decision, which may be later than its sampling time.

**Response policy**:
A context-dependent rule for a rival's actions as the interaction unfolds, distinct from that car's physical ability to execute those actions.

**Hypothesis set**:
The retained collection of plausible hidden rival states, model parameters and response policies consistent with the stated evidence procedure.
_Avoid_: A guaranteed confidence set without supporting assumptions

**Parameter provenance**:
The evidence, assumptions and validity conditions associated with a physical or strategic model parameter.

**Event authorization**:
Verified permission to use a restricted race mode under the applicable event conditions, distinct from an analyst's inferred proximity.
