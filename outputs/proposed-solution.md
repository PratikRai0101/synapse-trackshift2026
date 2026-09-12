# GRID//OPS: opponent-aware energy decisions under uncertainty

Research and architecture proposal · 12 September 2026 · Draft for discussion

## Recommendation

Build an engineer-facing energy strategy system that answers: **Should we spend electrical energy attacking or defending now, or preserve it for a better opportunity—and does that answer survive uncertainty about the rival?**

The competition deliverable should be a working physics simulation, an opponent-belief estimator, a constrained deployment planner, and a reproducible comparison against simpler strategies. A later interface should expose that evidence. It must not substitute for it.

The research hypothesis is narrower than the product: **preserving physically plausible explanations of an opponent's behavior, and committing only when their decision consequences justify it, can reduce costly energy mistakes under sparse telemetry and model mismatch.** This is a candidate contribution, not a proven result or a verified global first.

Team/resources: two people, CPU/GPU access, public data only. The user specified a 24-hour hackathon starting at 12:30 PM on the following day when answering on 11 September; the schedule below uses relative time to avoid depending on an unverified organizer calendar. Confirm the official start/end, submission rules, and permission to reuse pre-event code. This turn produces research and planning only.

## 1. Where the papers leave us

The supplied papers already cover most of the obvious component combinations. We should use them, cite them, and avoid presenting their contribution as ours.

| Supplied foundation | Use in our design | Boundary we must retain |
|---|---|---|
| Convex performance envelope, Duhr et al. | Energy-aware grip/acceleration envelope; single-car optimization reference | Fitted vehicle models and convexity assumptions do not make a coupled racing game globally convex. |
| Two-level MPC, Salazar et al. | Separate energy planning from fast model-feasibility checks | Its older hybrid architecture and energy limits are not 2026 specifications. |
| [Competitor-interaction MPC, 2403.06885](https://arxiv.org/abs/2403.06885v1) | Price an attack against later energy consequences | Electric-endurance charging stops and non-reacting recorded rivals are not an F1 race model. |
| [Game-theoretic energy management, 2405.11032](https://arxiv.org/abs/2405.11032v3) | Interaction-dependent drag and energy allocation | Its offline game solutions are not a demonstrated fixed-deadline online controller. |
| [Physical-to-strategic interactions, 2503.05421](https://arxiv.org/abs/2503.05421v5) | Couple wake, downforce, trajectory, and energy | Do not copy perfect-information game roles as a model of actual human intent. |
| [HMM–POMDP, 2603.01290](https://arxiv.org/abs/2603.01290v3) | Belief-state inference and a useful comparison policy | Its synthetic validation uses the same parametric model for inference and generation; public rival-energy ground truth is absent. |
| [Human-implementable policy, 2603.02339](https://arxiv.org/abs/2603.02339v1) | Translate plans into a small number of meaningful cues | Optimality is conditional on the simplified single-car model; hybrid/interacting-car extensions need new analysis. |
| [Competitor-aware race management, 2603.28286](https://arxiv.org/abs/2603.28286v2) | Offline interaction models and race-level strategy learning | Already combines game theory and RL; its charging-dominated endurance setting cannot be transferred unchanged. |

The accompanying [evidence review](research-evidence.md) adds twelve relevant papers and distinguishes published work, preprints, and incompletely verified extensions. Most important: [multi-agent F1 strategy learning](https://arxiv.org/abs/2602.23056v2) and [RL–MPC for F1 strategy](https://arxiv.org/abs/2604.00826v1) directly overlap a generic “RL plus MPC plus opponents” pitch. Decision calibration and distributionally robust planning also have established foundations. Our contribution would need to be the specific observation/physics/decision problem, its solution, and evidence—not a new name for these ingredients.

## 2. The research question

Consider two hidden situations with similar visible speed and throttle histories:

- The rival has energy available but is choosing to conserve it.
- The rival is power-limited and cannot sustain a counterattack.

Traffic, tyre condition, wind, drag, gearing, fuel mass, and power restrictions can further confound that distinction. These causes can coexist. A small speed residual is not a direct measurement of one cause.

The useful question is not always “Which hidden label is correct?” It is “Would the best decision change between the remaining explanations?” High uncertainty can be harmless when all explanations recommend waiting. A confident but wrong estimate can be expensive when it triggers an attack.

### Proposed contribution package

1. **A physical ambiguity benchmark.** Generate matched observable histories from different latent energy/capability/policy conditions. Vary observation rate, delay, noise, and history length. Identify regions where hidden mechanisms remain difficult to distinguish, without manufacturing separation through hand-picked HMM emissions.
2. **An ambiguity-aware commitment rule.** Evaluate attack, defend, follow/conserve, and baseline plans across the plausible explanations. Use estimated improvement and downside relative to an explicit fallback, including uncertainty in predicted action values.
3. **An evidence-separated evaluation.** Train, calibrate, and test separately; challenge the controller with a plant and opponents not copied from its inference model. Report decision quality, missed opportunities, and calibration—not just latent classification accuracy.

This could support an applied controls/ML paper if the distinction survives a deeper closest-work comparison and produces meaningful results. A hackathon demo is an early experiment, not the completed publication.

### What would falsify the hypothesis?

The ambiguity-aware method may offer no benefit over a well-tuned probabilistic planner; it may become too conservative; its improvement may disappear under independent physics; or a better behavioral predictor may solve the problem without explicit latent energy inference. Those are real outcomes. Do not keep changing the metric until one favors us.

## 3. Proposed architecture

| Layer | Responsibility | Output / important boundary |
|---|---|---|
| Observation and provenance | Synchronize public timing/telemetry; preserve original samples, delay, missingness, and source | Timestamped evidence with explicit measured/inferred/simulated flags |
| Ego state and vehicle model | Maintain the controlled car's energy, speed, limits, and uncertainty | Simulation truth in the demonstrator; team telemetry would be required for real own-car energy state |
| Opponent inference | Update context-dependent driver priors and plausible physical states | A weighted scenario set and response-capability forecasts—not a displayed exact rival SOC |
| Race-horizon planner | Value energy remaining after the next interaction | A continuation cost and reserve target conditioned on laps remaining, traffic, and strategic context |
| Tactical planner | Compare feasible deployment profiles against reactive opponent scenarios | Ranked alternatives, energy cost, uncertainty, and likely failure mechanisms |
| Rule/feasibility supervisor | Check modeled constraints, stale inputs, solver status, and event permissions | Model-feasible recommendation, fallback, or unavailable status |
| Independent evaluator and recorder | Execute the actual simulated interaction; record outcomes and counterfactual comparisons | Reproducible episodes and measured metrics, with no privileged-state leak into the policy |

Data travels from observations to beliefs to planning to the supervisor. The simulator generates the next observation and closes the loop. The evaluator alone retains hidden ground truth for scoring. Log the exact information available when every recommendation was made.

### A. Physics plant: a genuine simulation

Use a reduced-order hybrid race-car model, not a hand-authored “overtake probability” score. The first implementation should include longitudinal motion on a curved track, fuel-dependent mass, aerodynamic drag/downforce, combined acceleration/braking grip, electrical deployment and recovery losses, friction braking, energy bounds, and opponent response.

At minimum, integrate:

\[
\dot{s}=v,\qquad
m\dot{v}=F_{\mathrm{ICE}}+F_{\mathrm{K}}-F_{\mathrm{brake}}-F_{\mathrm{drag}}-F_{\mathrm{roll}}-mg\sin\theta.
\]

With electrical powers defined at the chosen DC accounting point, an illustrative storage equation is:

\[
\dot E=-P_{\mathrm{deploy}}/\eta_d+\eta_c P_{\mathrm{recover}}-P_{\mathrm{aux}}.
\]

Keep DC power, mechanical wheel power, internal stored energy, and lap recharge counters separate. Express all internal quantities in SI units. Avoid applying an efficiency twice. Prevent simultaneous deployment/recovery in an abstraction that does not support it; cap recovery by braking/power limits and energy headroom.

Use a bicycle/lateral model or dynamically checked passing trajectories in the short interaction zone before claiming completed overtakes. A longitudinal model alone can establish catch-up and energy opportunity, not safe side-by-side execution. Specify vehicle footprints, track boundaries, overlap and separation criteria, and when the pass counts as sustained. A candidate that fails this check is a failed/aborted attack, not a success.

The planner may use a simpler spatial model and a coarser grid than the time-domain plant. Independent evaluation requires different modeling assumptions or parameter regimes, not merely a different random seed. For publication, use a second implementation or externally validated plant as an additional check.

This is the appropriate simulation problem for our question. CFD could later supply better drag/downforce/wake maps; it is not the strategy optimizer. We do not need a full aerodynamic design campaign before we can study energy decisions. We must call the first plant a parameterized race-car model, not a Haas digital twin.

### B. Observation and driver learning

OpenF1 documents approximately 3.7 Hz car data and approximate position, with no reliable left/right track placement. Its public schema does not list battery SOC, ERS electrical power, or battery temperatures. Brake is a pressed-status field, not hydraulic pressure. These are limits on our evidence, not reasons to invent channels. [OpenF1 documentation](https://openf1.org/docs/)

Audit a real session before committing to features. Keep raw timestamps; interpolation does not create sensor information. Do not assume a legacy `DRS` field identifies 2026 active-aero or Overtake status. Unknown mode eligibility must stay unknown unless another verified source provides it.

Use driver-specific learning for observable conditional behavior: braking onset relative to a contextual baseline, lift/coast patterns, exit acceleration, and responses to a nearby car. Condition on circuit section, car/session, tyre age, traffic, and weather; use population priors when a driver's history is sparse. Never conflate a slower car with a conservative driver or describe a learned prior as personality truth.

Start with a contextual HMM or compact particle/ensemble filter. Keep physical capability distinct from tactical intent. Avoid multiplying correlated speed/sector/aero-derived signals as independent evidence. For each rival, estimate possible future speed/gap and counterattack capability across retained states. The core estimator learns/predicts; it is not RL merely because it updates online.

For real public replay, even the ego car's true energy is unavailable. Any displayed ego energy must therefore be a declared simulation initialization/model estimate. Team use would replace this with authorized own-car measurements and uncertainty bounds.

### C. Tactical optimization and commitment

Use a small library of parameterized deployment plans rather than searching every throttle/steering action jointly. Examples: maintain the reference, deploy in the present straight, defer deployment to a later window, defend a specified interval, or follow and recover. Each candidate includes the energy profile and relevant passing trajectory—not just a text label.

For a finite scenario set \(\Theta(h)\) consistent with history \(h\), define a common cost \(J_H(a,\theta)\) for an action followed by a specified continuation policy. It includes elapsed-time/position consequences and the value of the terminal energy state. Lower is better. Use the same continuation and units for all alternatives.

An implementable starting rule is:

\[
G(a,\theta)=J_H(a_0,\theta)-J_H(a,\theta),\qquad
L(a)=\min_{\theta\in\Theta(h)}\widehat G(a,\theta)-\epsilon_a.
\]

Here \(a_0\) is the feasible reference strategy, and \(\epsilon_a\) accounts for estimated action-value error. Recommend the feasible candidate with largest \(L(a)\) only when it clears a chosen positive margin; otherwise retain the reference. This is a proposed model-conditioned rule, not a real-world safety certificate.

Benchmark this conservative version against posterior-mean planning, CVaR planning, and minimax regret under the same scenario/action budget. They optimize different objectives; do not call them interchangeable. Report how often the conservative rule misses a profitable attack. Broader ambiguity sets improve caution but can make it useless.

The opponent must react to each hypothetical ego action in rollouts. Reusing an unchanged recorded rival future does not evaluate strategic response. For multiple scenarios, plans must share actions until a differentiating observation could arrive; otherwise a branch planner is using future information.

Use a multi-lap continuation value or reference lap-time/energy map so that a fast first straight cannot be rewarded while bankrupting the next lap. Match energy budgets and terminal conditions across baselines. Evaluate ending ahead after several laps, not only crossing a car's longitudinal position once.

### D. Where RL earns its place

RL is optional for the first working engine and important as a comparison. After the simulator and baselines work, a GPU can train a belief-conditioned strategy policy against a pool of reactive opponents. Its actions can adjust the baseline energy allocation or choose tactical candidates; the constrained planner still evaluates feasibility.

Do not train an ego policy on true rival energy and then claim it works from public observations. Privileged information can be isolated in a training critic or evaluator, with that privilege declared and ablated. Keep the deployed actor's observation contract identical across comparisons.

Training interactively in a simulator before a race is not “offline RL” in the technical fixed-dataset sense. Public race logs alone do not reveal the outcomes of unchosen energy actions and are insufficient justification for unrestricted policy optimization.

The 24-hour RL go/no-go criterion: retain it only if it trains stably and improves a frozen validation metric within the measured compute budget. A slower or less robust RL variant belongs in the results, not in the critical demo path.

### E. 2026 rule and control boundary

The reviewed controlling documents are Technical Issue 20 and Sporting Issue 08, both dated 5 August 2026. Technical C5.2 specifies a 350 kW absolute ERS-K DC limit, speed-dependent deployment envelopes, a 4 MJ permitted ES energy swing, and conditional lap recharge limits. “Unlimited regeneration” and constant instantaneous “50/50 power” are unsuitable general assumptions. A 4 MJ swing is not a universal per-lap boost allowance. [FIA Section C](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_20_-_2026-08-05.pdf)

Overtake permissions depend on event detection/activation definitions and enablement, not simply the present gap. Active aero is governed separately. Model the relevant race-control state and use a versioned event configuration. [FIA Section B, B7.1–B7.2](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_b_sporting_-_iss_08_-_2026-08-05_7.pdf)

The product is an engineer-side adviser. No remote actuation or new cockpit integration is proposed. Those require separate review; human involvement alone does not establish compliance. C8.5 restricts team-to-car telemetry. F1 pit charging is also excluded; C5.2.20 prohibits an off-board ES charger in the pit lane. [FIA Section C](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_20_-_2026-08-05.pdf)

Unresolved before implementation: the exact chosen event's supplementary power/recharge settings, mode notifications, and any amended qualifying floor. Do not fill missing event values from an older paper. The supervisor certifies only the modeled predicates and must disclose omissions.

## 4. How we prove something useful

### Evidence levels

| Evidence | Legitimate claim | Claim it cannot support |
|---|---|---|
| Unit/invariant tests | Correct accounting and constraint implementation in the tested model | Realistic race performance |
| Held-out physical simulation | Comparative decision performance in specified conditions | Real Haas time/points gains |
| Historical public replay | Fit/calibration of observable future speed, gaps, and timing | True rival SOC accuracy or the actual result of an unchosen maneuver |
| Authorized instrumented/team study | Validation against those measured vehicle states and workflows | Generalization beyond the tested setting without further evidence |

### Baselines

For the hackathon: fixed energy schedule; greedy gap-triggered deployment; constrained single-car planner; the same opponent-aware planner using a single best state estimate; posterior-mean scenario planning; and our conservative scenario policy. Include a matched privileged-state planner as an information-gap diagnostic, not an automatically optimal upper bound.

For a paper, add a faithful HMM–DQN reproduction or clearly named adaptation, a strengthened contextual/correlated-emission baseline, behavioral-only prediction, Branch/CVaR MPC, and a multi-agent strategy learner. No claiming superiority to a paper based on an intentionally weak imitation of it. Publish divergences when source code or vehicle parameters are unavailable.

### Metrics and fairness

- Primary research metric: paired episode-level decision regret relative to a declared same-model action/continuation comparator. State the hindsight and optimization privilege of that comparator.
- Operational outcomes: sustained position advantage, episode/race time, energy spent on failed attacks, terminal reserve, and performance on the worst-decile scenarios. Choose a primary outcome before test results are visible.
- Uncertainty: future-observation interval coverage, Brier/log scores where labels exist, and decision risk versus recommendation coverage. Latent-state calibration is evaluated only where independent latent labels exist.
- Reliability: energy/rule violations, failed solves, fallback frequency, stale-data behavior, and end-to-end p50/p95/maximum latency on named hardware.
- Statistical discipline: paired scenario seeds; uncertainty across full episodes; train/calibration/test separation by whole runs, tracks, and opponent families. Do not split adjacent telemetry rows randomly.

Use the same initial conditions, energy limits, observation information, terminal treatment, and comparable tuning/compute allowances for all policies. Prespecify at least two unseen opponent families and several physical/noise shifts. For the hackathon, target 100 paired short episodes if runtime permits; that is an engineering target, not a power calculation or proof of significance. Measure first and report the actual count.

### Required physical and adversarial tests

Energy accounting residual; zero-power coast-down; braking-energy limit; full-storage recovery clipping; low-energy deployment clipping; time-step convergence; friction/grip limits; delayed/missing observation; wrong model parameters; a rival that changes behavior mid-episode; a failed attack followed by recovery; an unavailable Overtake permission; and a faster car approaching from behind as a stress case.

Do not train and evaluate with the same observation generator and call the result independent validation. Do not use pseudo-labeled inferred SOC as the truth that proves the inference accurate. A different plant is still a model, not real-race evidence.

## 5. What belongs in the 24 hours

This is a complete experimental slice, not a promise to reconstruct all of F1 overnight.

| Include in the core | Represent as context or uncertainty | Defer unless core evidence is complete |
|---|---|---|
| One traceable track configuration; two interacting cars; several-lap episodes | Fuel mass/burn and power-map uncertainty | Full-grid joint games and team cooperation |
| Energy-conserving hybrid plant and constrained plans | Tyre/grip degradation and surface variation | Full thermal/tyre identification and complete pit-strategy optimization |
| Noisy, delayed public-like observation stream | Wake/downforce sensitivity and wind | Bespoke CFD and a calibrated Haas digital twin |
| Multiple opponent hypotheses and reactive responses | Strategic value of a third car behind | Large-scale end-to-end racing RL |
| Physical passing checks and honest failure outcomes | Pit windows and race phase in continuation cost | New cockpit controls or real car integration |
| Reproducible baseline comparison and clear explanations | Unavailable event-specific rule parameters | Claims of regulatory certification |

A modest grey-box thermal cap can be a stress-test mechanism without claiming an identified electrothermal battery model. Similarly, a tyre-dependent grip/pace modifier can capture strategic sensitivity without pretending to model all degradation chemistry. These distinctions make the result auditable.

### Two-person schedule, relative to the 12:30 PM start

| Window | Person A: physics and planning | Person B: inference and evidence | Joint gate |
|---|---|---|---|
| T+0–2 h | Freeze state/action/units contracts; implement energy accounting | Audit one public session; define observation contract and scenario seeds | Confirm competition rules, one circuit, baseline and success metric |
| T+2–6 h | Working plant, reference controller, grip/passing checks | Opponent scenarios, observation corruption, baseline harness | A complete episode runs and passes physical invariants |
| T+6–10 h | Tactical candidates and multi-lap continuation cost | Belief updates, ambiguity cases, matched baselines | Closed-loop decisions alter later energy and position |
| T+10–14 h | Supervisor, failures, latency tuning | Calibration split, held-out runs; optional isolated RL training | Run initial comparison; reject misleading or unstable variants |
| T+14–18 h | Integration and record-backed visualization | Batch results, ablations, failure analysis | Freeze tested algorithm/configuration and preserve raw results |
| T+18–21 h | Demo reliability and offline operation | Pitch narrative, citations and limitations | Three rehearsed scenarios, one uncurated evaluation summary |
| T+21–24 h | Bug fixes and packaging only | Rehearsal, backup recording, submission checks | Submit with buffer; no last-minute scientific claims |

Do not allocate both people to modeling while nobody owns integration. Keep interfaces small and exchange a first complete episode early. Use GPU work in parallel only after a meaningful training environment exists. If physical passing validation slips, explicitly downgrade the claim to energy-aware attack-window prediction; never hide the omission with animation.

## 6. The demonstration that makes the argument

Show the same initial situation under the same energy budget and two hidden opponent conditions. Let the judge choose or change the hidden condition; keep it invisible to the policy.

1. A naive attack consumes reserve and is countered. The alternative policy preserves energy when its predicted benefit is fragile.
2. A superficially similar rival really is unable to sustain deployment. As evidence accumulates, the policy identifies an attack worth taking; it does not always abstain.
3. Observation loss or a permission change triggers a visible fallback with an explanation and logged timing.

Display actual simulated speed, power, energy and position traces; selected versus rejected plans; which assumptions changed the action; and the result several laps later. The exact outcomes must emerge from the simulator. If one episode does not support the narrative, do not alter physics to force it—select a labeled illustrative case and show the aggregate test results alongside it.

An example explanation format, with values filled only after computation: “Defer this attack: improvement is positive under the depleted-rival hypothesis but negative under the conserving-rival hypothesis. Retain the reference plan until the next informative segment. Reserve and eligibility constraints remain satisfied in the modeled scenarios.”

## 7. Positioning for Haas and Mphasis

Haas's Mphasis partnership explicitly names real-time analysis, predictive modeling, performance optimization, and operational efficiency. Our suggested fit is an auditable engineer-side scenario adviser supporting those aims—not a claim that Haas lacks strategy tools. [Haas partnership announcement, 21 November 2024](https://www.haasf1team.com/news/moneygram-haas-f1-team-welcomes-mphasis-partnership)

Haas has an announced Ferrari power-unit agreement through 2028. Do not imply Toyota branding supplies the 2026 engine or that we possess Ferrari calibration maps. [Haas supplier announcement, 16 July 2024](https://www.haasf1team.com/news/partnership-extended-between-moneygram-haas-f1-team-and-scuderia-ferrari)

### Proposed pitch

“An attack is an energy investment, and the rival's ability to respond is uncertain. GRID//OPS compares what happens if we attack, defend, or wait across physically plausible rival responses. It exposes when a recommendation is robust and when the evidence is too weak. We demonstrate the method in a constrained simulator against reproducible baselines, and propose team-data validation as the next step.”

Bring engineering evidence: time-to-decision, failed-attack energy, reserve consequences, provenance, and readable failure cases. Offer a bounded technical evaluation with anonymized own-car energy traces and an approved parameter interface. Do not ask for competitor secrets or upload team data to external services without authorization.

Potential later commercial value: pre-race scenario preparation, post-session decision review, and eventual live shadow-mode evaluation. These are proposed use cases, not verified Haas requirements. Keep private models separate from the public research artifact. Check public-data licensing before redistributing telemetry or proposing commercial deployment; access to an API does not grant every downstream right.

## 8. Publication path and immediate decisions

Working research title: **When Rival Energy Is Unobservable: Decision Regret in Competitor-Aware Race Energy Management**.

A paper would need a precise formal observation model, well-defined ambiguity tests, properly reproduced closest baselines, independent evaluation, multiple tracks/opponent regimes, uncertainty estimates, and a reproducible artifact with failure cases. A theoretical regret bound is a possible extension, not a promised contribution: it would require assumptions establishing model-set inclusion and action-value accuracy. Empirical calibration alone is not that proof.

After the hackathon, decide whether the strongest result is an algorithm, a benchmark/negative identifiability result, or an applied system study. Select a venue only after that choice. Keep dated experiment plans and accurate contribution records for both teammates; do not call an arXiv upload peer review.

Before building, settle the official rubric and reuse rules, choose the primary demonstrator circuit, approve the observation/energy boundary, and freeze the first comparison metric. The local Wayfinder map records these open decisions rather than treating this draft as approval.

Status: no solver, trained policy, physical benchmark, or measured performance gain has been produced in this turn. The pre-existing `index.html` remains an illustrative scoring mock-up; its displayed timing/confidence values are not research evidence. UI work should resume only after the engine's decision records exist.
