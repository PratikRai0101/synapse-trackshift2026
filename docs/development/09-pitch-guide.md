# Pitch guide: what we do, why it matters, what is ours

This is pitch content and a citation map, not a completed slide deck. Replace every results placeholder with measured evidence from the frozen implementation. Do not imply Haas sponsorship of our project or use team branding as endorsement.

## 1. Positioning

**Working product name:** GRID//OPS.

**One-line proposition:** An auditable energy-strategy adviser that compares attack, defend and conserve decisions against plausible rival responses and their later race consequences.

**Haas-facing hypothesis:** a complementary analysis/review tool for strategy and performance engineers, not a replacement for existing team simulation or an assertion that Haas lacks such tools. Haas's public Mphasis partnership names analytics, predictive modeling and performance optimization as relevant areas [D05]. The Ferrari power-unit relationship means real integration would require the appropriate authorized team/supplier model interfaces, not public guesses about pack parameters [D06].

## 2. A sixty-second explanation

“A slower rival is not automatically an easy overtake. They may have energy in reserve, be temporarily power-limited, or simply be responding to traffic. If we commit energy to the wrong explanation, we can lose the opportunity that matters later.

GRID//OPS keeps several plausible explanations alive and tests our alternatives in an action-responsive race simulation. A constrained planner checks what our car can achieve; the strategy layer includes remaining-race value; and the system explains whether an attack remains worthwhile across the uncertainty.

Our research question is whether this reduces costly commitments without becoming too conservative. We test it against budget-aware and optimization-based strategies using identical information and resources. The demonstration uses simulated battery truth, clearly separated from public observations. A team deployment would require identified vehicle models and authorized validation.”

Only after measurement append: “In [N] held-out episodes under [conditions], we observed [paired result and uncertainty], with [failure/latency figures].”

## 3. Eight-slide narrative

| Slide | Claim / content | Visual evidence | References |
|---|---|---|---|
| 1 — The decision | Spending energy now can hurt the later race; rival capability is uncertain | One attack window and a later opportunity | P03, P06 |
| 2 — Why visible slowdown is ambiguous | Several hidden mechanisms can explain similar observations | Matched observation traces with separately revealed simulated truth | P06; D01–D02; our benchmark |
| 3 — How the system works | Evidence → beliefs → feasible candidates → reactive futures → recommendation | Architecture diagram with evaluator truth kept separate | P01–P05, P14 |
| 4 — What we model | Charge, power, heat, grip, tyres and event permissions are distinct | One trace showing an actual binding constraint | P16–P19; D03 |
| 5 — Proposed contribution | Decision-relevant ambiguity, not just more hidden-state labels | Same candidate set under mean versus ambiguity-aware selection | P20–P22; our algorithm |
| 6 — Live/replayed experiment | Show recommendation, alternative and subsequent outcome | Recorded action-responsive scenario, plus a failure/abstention case | Our manifest and logs |
| 7 — Results and limits | Measured benefit/trade-off, sample count, violations and latency | Paired benchmark plot/table; visible limitations | Our frozen evaluation |
| 8 — Team integration and ask | An auditable module that can be evaluated with better models/data | Public demonstrator → authorized offline evaluation → engineer review | D05–D06 |

Keep full references in notes/appendix; use short author/year citations on slides. Do not crowd the main narrative with every paper. If the presentation format is shorter, combine slides 3–4 and 6–7 after confirming organizer requirements.

## 4. Demo script

1. Show the run ID, synthetic/observed labels, initial resources and baseline.
2. Pause before a decision. Reveal only the evidence the controller currently has.
3. Show rival-capability hypotheses and the costs of at least two feasible alternatives.
4. Advance the simulation with the selected action; demonstrate the rival's response.
5. Continue beyond the immediate straight so reserve and re-pass consequences are visible.
6. Compare the paired baseline run under matched initial conditions and exogenous events.
7. Show an ambiguous or failed case and explain the limitation without changing the scoring rule.

A recording is an honest replay of a logged simulation, not “live telemetry.” If the solver is running interactively, distinguish computation latency from observation delay and screen-refresh rate.

## 5. Judge questions and defensible answers

**Is this real simulation?** It integrates declared vehicle, battery and tyre states under actions, with a reacting opponent. It is a reduced-order model, not CFD or a calibrated Haas digital twin. Show conservation and integration-refinement tests.

**Do you know the rival's SOC?** No. The controller carries hypotheses and forecasts response capability. Hidden truth exists only in our simulator for evaluation; public-data replay cannot validate actual battery-state accuracy.

**What is new?** The candidate contribution is the benchmark and decision treatment of physically plausible ambiguity, measured through costly energy commitments. Convex MPC, HMMs, lifecycle planning, tyre models and game theory are existing foundations. Novelty remains subject to closest-work comparison and results.

**Why not just RL?** A learned policy is an important comparator, but it still needs a valid environment, observations and constraint handling. The first engine uses explicit models and bounded evaluation so its assumptions and failures can be inspected. RL can later select candidates or estimate continuation value if it improves measured performance.

**Why four horizons?** Fast feasibility, lap deployment, race allocation and component lifecycle operate at different timescales. They exchange resource values and reachable targets. We state which horizons are actually optimized and which are configured context; four horizons do not imply four real-time MPCs.

**How do you avoid wasted attacks or stalemates?** By pricing later consequences and comparing with a reference, not by deleting every zero-position-gain outcome. Defending position can be valuable; no algorithm guarantees victory against every rival.

**How is the convex paper used?** As a foundation for a combined-performance envelope and tractable conditional deployment optimization. It constrains modeled available grip; it does not increase grip or make the whole interacting game convex.

**Is it FIA compliant?** It checks the modeled rules in an identified configuration. Complete legality requires current event instructions and operational review; no car actuation or certification is claimed.

**How do you know the result is not scripted?** Show the action-responsive simulator, randomized held-out scenarios, identical-information baselines, failure records and reproducible manifest. Two carefully chosen threshold examples would not be enough.

**What would you ask Haas for?** First, engineer feedback on the decision/uncertainty interface and a scoped offline evaluation protocol. Later, authorized own-car energy/thermal signals, validated vehicle constraints and event-rule configuration under suitable access controls. Do not demand rival private telemetry or promise an internship outcome.

## 6. Claims to remove from the pitch

- “Production-grade,” “guaranteed win,” “global optimum of the whole race game.”
- “We read the rival's mind/battery” or “super-clipping proves depletion.”
- “10 Hz public telemetry,” unless the selected source actually supports that native rate.
- “Four-level MPC implemented,” when execution is projection or lifecycle is a configured price.
- “Improved battery life by X%,” based on an uncalibrated stress proxy.
- “First RL/game-theoretic/thermal/season-aware racing strategy.”
- Any borrowed paper's timing or lap gain presented as our result.

## 7. Evidence checklist before presenting

Have a source for every borrowed method, a manifest for every chart, a test for every feasibility claim, a count for every reported success rate, and a clear label for every inferred/synthetic quantity. Leave unsupported numerical claims out rather than put an invented number in a placeholder.
