# Four-horizon architecture: review and 24-hour build plan

12 September 2026 · Proposed design, not implemented results

This reviews the user's expanded approach and the pasted feedback. The pasted feedback is not an authoritative source: several of its formulas, guarantees, and descriptions of the literature need correction. The original [proposal](proposed-solution.md) and [literature review](research-evidence.md) remain background; this note considers the new scope without claiming it has been approved or built.

## 1. Recommendation

Retain the convex performance envelope, add explicit thermal/tyre state and persistent opponent context, and use a four-horizon hierarchy. Implement MPC where continuous feedback control benefits from it; use coarse strategic optimization at race and season scales. Test tactical energy feints against reactive opponents, including opponents that do not fall for them.

The core scientific question remains decision quality under uncertain rival capability. Adding many poorly identifiable states is not automatically an improvement. Every added model should change a feasible action, a prediction, or the future value of a resource, and earn its place through an ablation.

## 2. Corrections that affect the implementation

| Proposed idea / claim | Assessment |
|---|---|
| Convex envelope “maximizes grip” | Keep it as a model of available combined acceleration/braking/cornering capability. The objective is race performance within that capability, not maximum grip utilization everywhere. |
| Four levels are necessarily four MPCs | Four horizons are sensible. Solver choice, update rate, and exchanged quantities should differ by horizon. |
| Battery health declines with demanding operation | Plausible, but quantitative capacity/resistance loss needs cell-specific evidence. Do not infer a real pack's percentage health from lap counts. |
| Tyre degradation is just age | Age is incomplete. Separate irreversible wear, reversible thermal effects, compound, and context. |
| The HMM tyre model is literally linear | The supplied version has five discrete wear states and nonuniform pace penalties, not simply a linear age curve. Its coarse/unconditioned structure is the more accurate criticism. |
| The HMM repeatedly starts without context | Section 5.1 propagates the previous belief. Clearing DQN replay during retraining is a different operation. |
| Super-clipping means draining the battery | It is a recovery mechanism at full throttle, not another name for depletion. A public speed/throttle signature alone does not uniquely identify it. |
| A penalty implies a damaged rival battery | A penalty may concern a different component or a new replacement. Record the reason and evidence; do not substitute it for battery health. |
| Monte Carlo tree search makes the problem linear | It samples future trajectories; it does not turn nonlinear dynamics or a stochastic game into an LP. |
| We can eliminate draws and losses by pruning | No. Finite computation can be enforced; guaranteed competitive victory generally cannot. Holding a position may be valuable. |

The HMM corrections follow PDF pp. 7 and 9, including equation (15) and the alternating training schedule. [Kleisarchaki, v3](https://arxiv.org/abs/2603.01290v3). Super-clipping is described as recovery at full throttle in the [FIA-hosted 2026 media kit](https://www.fia.com/sites/default/files/final_2026_media_kit.pdf).

## 3. Four horizons, with coherent interfaces

| Horizon | Appropriate first method | What goes downward | What comes back upward |
|---|---|---|---|
| Season / component lifecycle | Offline scenario analysis or small finite-horizon dynamic program | Marginal value of component wear, replacement constraints, risk preferences | Race-level performance-versus-wear outcomes and revised component evidence |
| Remaining race | Receding/shrinking-horizon allocation using lap maps; initially fixed or enumerated pit plans | Lap energy targets, reserve requirements, tyre-use targets, continuation value | Achievable pace, energy/thermal feasibility, actual wear and interaction outcomes |
| Lap / tactical windows | Conditional convex energy planner plus bounded scenario comparison | Speed/power references and candidate attack/defend/follow plans | Tracking cost, revised opponent beliefs, new thermal/grip limits |
| Fast execution | Small tracking MPC/LP where its formulation is valid; simulation feasibility supervisor | Applied simulated power/brake commands | Actual state, constraint residuals and feasibility failures |

These are not four independent optimizers with conflicting objectives. A lower layer must be able to reject an infeasible energy target. Upper layers pass compatible continuation values and constraints, not four unrelated weighted scores. Convert costs into a consistent utility basis before combining race time, expected points, and degradation.

The season layer values the health of identifiable components and remaining replacement options. It does not carry one battery's end-of-race SOC blindly into the next event or assume the same pack is always installed. Exact rival component continuity can be unknown.

Important new prior art: Neumann, Habermacher, Fieni, Cerofolini, Zardini and Onder's *Hierarchical Co-Design for Multi-Race Strategy Optimization in Formula 1* already links performance, energy, component wear and replacement across a season. ETH lists the 2025 working paper; the authors' MIT page lists ITSC 2026 in-press status. We verified the abstract and author records, but direct full-PDF retrieval failed. [ETH author record](https://idsc.ethz.ch/the-institute/people/person-detail.MTg4NDAy.TGlzdC82MjMsMjA4ODk3NDEzOQ%3D%3D.html), [MIT publication list](https://zardini.mit.edu/publications/). Do not claim the season-layer idea itself as new.

## 4. Preserve the convex paper correctly

Use Duhr's speed-dependent combined-acceleration envelope for a specified racing path. Tyre condition and environmental estimates can change the envelope supplied to the optimizer. The paper's fit and mathematical relaxation do not certify true grip in every condition. The original local Downloads file is no longer at its supplied path; this review cross-checked the author's thesis, Chapter 7. [Duhr thesis](https://www.research-collection.ethz.ch/server/api/core/bitstreams/a40125ce-dcac-4ffd-870d-19881e8820a8/content)

For the hackathon, freeze predicted thermal/wear/compound parameters during each conditional convex solve, then check its trajectory in the nonlinear plant. Update between solves. A sequence of convex subproblems is not a proof that the fully coupled problem is convex or globally optimal.

Keep the roles separate: the nonlinear plant produces wear and temperature; the estimator produces uncertain state; a conservative fitted envelope limits the planner. Multiplying an optimized tyre-temperature or wear variable by another decision variable can destroy convexity. Fixed candidate passing paths can be enumerated outside the continuous solve, with each trajectory checked for track containment and vehicle separation. Call longitudinal crossing alone catch-up, not a completed safe pass.

## 5. Battery state: what should actually be modeled

Use current charge, thermal state, and long-term health as different quantities:

- SOC or stored energy: fast resource state. Specify whether it is charge-based or energy-based and how it maps to terminal voltage.
- Battery temperature: dynamic thermal state, with cooling and losses.
- Usable capacity and resistance/power capability: separate health-related parameters; initially fixed within a short tactical episode, but varied across scenarios and updated at slower scales.
- Accumulated aging stress: an accounting quantity that can inform strategic cost. Until calibrated, label it a stress proxy, not percentage capacity loss or remaining life.

A minimal equivalent-circuit plant could use, for discharge-positive current,

\[
\dot z=-I/Q_{\mathrm{usable}},\qquad
V_{\mathrm{term}}=V_{\mathrm{oc}}(z,T)-I R(z,T,h_R),\qquad
P_{\mathrm{term}}=V_{\mathrm{term}}I.
\]

Here capacity is in coulombs; if stored in ampere-hours, include the factor 3600. At this fidelity, freeze capacity over the integration interval. A corresponding lumped thermal balance is:

\[
C_{\mathrm{th}}\dot T=I^2R+Q_{\mathrm{other}}-G_{\mathrm{cool}}(T-T_{\mathrm{coolant}}).
\]

Do not subtract conversion losses twice when coupling this model to the motor and DC energy counters. Current, voltage, SOC and thermal bounds all restrict available power. When no physically admissible current realizes a requested power, report saturation/infeasibility.

The pasted arbitrary quadratic temperature/SOH resistance formula is not a verified cell model. Nor is ordinary resistive heating itself a thermal-runaway model. High-temperature aging and lithium plating have different dependencies; neither is captured by a generic “hot means plating” assertion. Experiments distinguish high-temperature SEI-dominated aging from low-temperature lithium-deposition regimes, with crossover depending on charging conditions and cell state. Numerical coefficients still require a declared reference cell or sensitivity ranges. [Kucinskis et al., 2022](https://dspace.lu.lv/server/api/core/bitstreams/3fb0395b-6985-425c-a50f-2ba7ffa0a906/content)

For model structure, see [PyBaMM's Thevenin documentation](https://docs.pybamm.org/en/v22.11/source/models/equivalent_circuit/thevenin.html) and [Schmalstieg et al.'s electrical–thermal lifetime model](https://www.citelec.org/EVS27/download.php?f=papers/EVS27-2870281.pdf). The linked software documentation is a versioned structural reference, not a recommendation to install that old version. A polarization state can be added if transient voltage behavior matters; omit it explicitly in the first resistive model.

Environmental factors enter through mechanisms: ambient/coolant conditions and cooling effectiveness for the pack; track surface, weather, and temperature for tyres; wind/air density for aerodynamic load. Track temperature is not battery temperature. Do not add all weather fields as independent health multipliers.

## 6. Tyres: nonlinear without fabricated observability

Maintain a tyre-set state with compound identity, irreversible wear and thermal condition. A useful first model has one effective thermal state and one wear state per axle, with different compound parameter sets. This is a reduced-order model, not a detailed tyre construction model.

The intended dependencies are:

\[
\dot D=f_c(T_{\mathrm{tyre}},F_z,P_{\mathrm{slip}},\text{surface}),\qquad
\mu=g_c(T_{\mathrm{tyre}},D,F_z,\text{surface}).
\]

The pasted work integral is dimensionally wrong: force times vehicle speed integrated over distance has units of power times distance, not energy. Frictional work uses slip-relative velocity and integration over time. A lumped approximation is:

\[
W_{\mathrm{slip}}=\int\left(|F_xv_{\mathrm{slip},x}|+|F_yv_{\mathrm{slip},y}|\right)dt.
\]

If the simulator does not model slip, use a named, normalized load/utilization stress proxy instead. Do not describe that proxy as measured contact-patch work. Avoid multiplying a driver-aggression factor into stress that already encodes their harder inputs without checking for double counting.

For a rival, observations support beliefs over wear and temperature, not exact friction utilization. Condition on reported compound, tyre-set age, circuit segment, traffic, and observed pace residuals. Account for uncertainty in fuel, aero and car performance. Use the actual event's compound nomination where available; a relative Soft/Medium/Hard label is not a universal compound identity.

A pit event resets the appropriate tyre-set state and its temperature prior. It does not reset driver behavior or battery health. Conversely, heat-related grip can recover even though accumulated wear does not.

Relevant prior art is [West and Limebeer, *Optimal Tyre Management of a Formula One Car*, IFAC 2020](https://ifatwww.et.uni-magdeburg.de/ifac2020/media/pdfs/0335.pdf), which couples tread/carcass temperature, wear and grip. Nonlinear thermal/compound-aware tyres are therefore an existing modeling foundation, not an original contribution by themselves. Its example parameters are not current Pirelli calibration. The event-specific nature of compound labels is illustrated by [Pirelli's 2026 Monaco and Barcelona nominations](https://press.pirelli.com/the-tyre-compound-selections-for-monte-carlo-and-barcelona/).

## 7. Persistent memory without stale-state errors

The useful extension is hierarchical, event-aware persistence, not “giving an HMM memory.”

| Memory | Preserve | Reinitialize or revise when |
|---|---|---|
| Fast race belief | Current energy/capability, temperatures, wear hypotheses and uncertainty | Sensor gaps require prediction and wider uncertainty; tyre changes reset only relevant state |
| Driver/car context | Conditional response tendencies with evidence counts and forgetting | Circuit, car specification, weather, or behavior changes invalidate old tendencies |
| Component/event record | Confirmed replacements, usage reports, penalties and source timestamps | Component identity changes or is unknown; penalty reason differs from inferred health |

Carry the posterior between observations. Between sessions, reuse learned parameters/context where appropriate but initialize unobserved fast states from fresh priors. Never persist yesterday's estimated SOC as today's measurement. Bayesian parameter updates, shrinkage toward population priors and change detection are more defensible than permanent fixed aggression scores.

The 2026 sporting rules explicitly include component allocation and replacement penalties, making lifecycle planning a legitimate concern. They do not provide battery-SOH measurements. [FIA Section B, B8.2](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_b_sporting_-_iss_08_-_2026-08-05_7.pdf)

## 8. Feints, stalemates, and finite search

Add strategic energy feints as candidate policies, not scripted successes. Simulate rivals that attack apparent weakness, conserve, adapt, or ignore the signal. Count a feint's benefit only after its position/energy/tyre/thermal consequences have played out. Inducing a rival to spend energy is not valuable if it lets them pass and win.

Do not assume rivals run our inference algorithm or mistake a specific throttle percentage for a particular mode. No unnecessary brake-checking, erratic driving, contact, or illegal blocking belongs in the model. Feasible deployment and permissions must be enforced for both cars; a leading car does not automatically possess the trailing car's Overtake eligibility.

Separate three concepts: tied local progress; a game-theoretic equilibrium/role-selection issue; and a solver that does not terminate. They are not the same failure. Equal progress can protect a position, open a gap to a third car, or set up a later move. A season objective can rationally accept a local loss for a larger later gain.

Use a finish/continuation utility and marginal resource values, plus a chosen downside-risk criterion. Do not prune every branch with zero immediate position gain. Prune modeled illegality/infeasibility and provable dominance; heuristic pruning must be reported as such. Strict zero-loss requirements can make the action set empty when the rival is simply stronger.

POMCP means Partially Observable Monte-Carlo Planning. It combines belief sampling and search using a generative simulator; it does not linearize dynamics. The original algorithm explicitly has a search timeout and bounded/discounted rollout depth. It does not guarantee victory against an arbitrary adapting opponent. [Silver and Veness, 2010](https://papers.nips.cc/paper_files/paper/2010/file/edfbe1afcf9246bb0d40eb4d8027d90f-Paper.pdf)

For 24 hours, begin with bounded scenario rollouts over a small tactical action set. If we do not implement belief/history tree search, call it scenario planning, not POMCP. Apply a fixed horizon, rollout/iteration cap, wall-clock deadline and validated fallback. Monte Carlo error is not a bound on omitted physics or unknown opponent policies.

## 9. Build sequence for two people

Proposed implementation shape: one simulation/experiment process, small typed data contracts and replayable decision records. Avoid distributed-service work during the event. Separate plant truth from policy observations at the API boundary. Optimize continuous trajectories on CPU; optional GPU policy training stays outside the critical path.

| Hours from start | Person A | Person B | Required output |
|---|---|---|---|
| 0–2 | State, sign and unit contracts; baseline dynamics | Public-data schema audit, scenario/configuration definitions | One deterministic observation/action loop and agreed metric |
| 2–6 | Plant, combined-grip constraints, battery SOC/thermal behavior | Compound-aware wear/thermal model, rivals and filtered observations | Complete physically checked episodes; no UI dependency |
| 6–10 | Conditional convex trajectory planner and fast executor | Persistent belief updates, fixed-budget opponent-response rollouts | Attack/follow/defend decisions with feasible power/energy traces |
| 10–13 | Remaining-race allocation/continuation maps | Feint policies, non-reacting/adaptive rivals, no-memory comparison | Multi-lap consequences and adversarial failure cases |
| 13–15 | Small synthetic season DP if core gates pass; otherwise explicit external wear price | Held-out calibration and baseline comparison | Clear distinction between optimized season result and configured season assumptions |
| 15–19 | Integration, latency and physical-failure testing | Paired batches, uncertainty, ablations and record-backed visualization | Frozen methods and reproducible evidence |
| 19–24 | Demo reliability, packaging and bug fixes | Pitch, rehearsals, backup recording and submission | Working artifact with measured claims and submission buffer |

The small season demonstration can enumerate declared event payoff/wear maps, component-health bins and replacement choices. It illustrates the interface and solves that simplified problem. It is not a calibrated entire-2026-championship optimizer. If it is not implemented, call the result “season-informed,” not “four fully implemented MPCs.”

Do not launch a fresh convex lap optimization inside every tree rollout. Precompute candidate profiles and coarse continuation maps, simulate their consequences cheaply, and refine the selected plan. Cache keys must include relevant state/parameter/rules versions. Limit replans and handle invalid cache coverage explicitly.

Do not add full RL training, a new solver, detailed electrochemistry and a full-grid game simultaneously. A functioning lower-level loop is the dependency for every later claim. Check official competition rules before reusing pre-existing code.

## 10. Evidence that each addition matters

Required comparisons: base two-level planner; plus battery thermal limits; plus compound/thermal/wear tyres; plus persistent context; plus interactive tactics; plus season-informed wear value. Also test the full method against strong shared-model baselines so order-dependent incremental gains are not mistaken for independent contributions.

Use common initial resources, observations and seed sets. Report race/episode outcomes, reserve, energy/thermal violations, failed-attack cost, missed opportunities, fallback rate and decision latency. For persistence, hold out sessions/conditions and test component changes; warm-starting on test outcomes is leakage. For feints, report win rate against multiple response families, including failure.

Test numerical convergence, signed charge/discharge accounting, saturation, wear monotonicity, tyre-change resets, thermal recovery, missing observations, wrong health priors, and the absence of future/privileged-state leakage. Public replay can validate observable forecasts; health/energy truth in this demonstrator is simulated and labeled accordingly.

Proposed research framing: **health- and context-aware opponent energy strategy, with persistent uncertainty and independently tested tactical response**. The contribution must survive comparison with existing seasonal co-design, thermal/tyre models, and opponent-aware planning. The number of hierarchy levels is not the scientific result.
