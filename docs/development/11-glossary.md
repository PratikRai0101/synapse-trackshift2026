# Technical glossary and notation

The canonical racing/domain definitions are in [CONTEXT.md](../../CONTEXT.md). This companion explains mathematical and engineering terms for development and the pitch. Domain definitions take precedence if informal wording elsewhere differs.

## 1. Control and optimization

| Term | Plain-language meaning | Important distinction |
|---|---|---|
| MPC — model predictive control | Repeatedly predict a horizon, optimize controls, execute the first part and replan | A controller is not MPC merely because it has a forecast |
| Receding horizon | A moving future window recomputed as observations arrive | A remaining-race horizon may also shrink toward the finish |
| Hierarchical control | Different decision timescales exchange targets and feedback | Not four unrelated objectives |
| Convex optimization | A problem with mathematical structure allowing global solutions under suitable feasibility/numerical conditions | A convex subproblem does not make the coupled system globally convex |
| QP — quadratic program | Quadratic objective with linear constraints in the intended convex case | Does not directly include arbitrary norm/conic constraints |
| SOCP — second-order-cone program | Convex optimization including norm inequalities of an appropriate affine form | Not a stochastic-game solver |
| DCP — disciplined convex programming | Rules used to verify/express convex structure | A necessary implementation check, not physical validation |
| NLP — nonlinear program | Optimization with nonlinear objectives or constraints | May be nonconvex and have local solutions |
| KKT conditions | First-order constrained-optimization conditions under assumptions | Generally not sufficient for a global nonconvex follower optimum |
| MPCC | Mathematical program with complementarity constraints | Numerically difficult; relaxation introduces its own checks |
| PMP — Pontryagin's minimum principle | Necessary optimal-control conditions using a Hamiltonian and costates | A switching law depends on the exact model and cost conventions |
| Costate / shadow price | Marginal value associated with a state or constraint in an optimization model | Not automatically a transferable physical constant |
| Trust region | A limit on departure from the local approximation's reference | Helps control model mismatch; does not eliminate it |
| Warm start | Reuse of a previous solution as a solver initial condition | Does not prove the old solution remains feasible |
| Feasibility residual | Numerical measure of constraint satisfaction | Must be checked in appropriate units/scales |
| Dynamic programming | Solve a finite-horizon decision problem through value recursion | State-space size can grow rapidly |
| Terminal cost | Value assigned to the state at the end of a planning horizon | Should not double-count the same future energy value |

## 2. Inference, games and learning

| Term | Meaning | Limit in our setting |
|---|---|---|
| HMM — hidden Markov model | Hidden-state transition model with observations and sequential belief updates | Already carries history through its posterior |
| Belief state | Distribution or set summarizing uncertainty given evidence | Not measured ground truth |
| POMDP | Sequential decision model with partially observed state | Commonly treats transition dynamics as given rather than solving arbitrary adapting games |
| POSG | Partially observable stochastic game with multiple decision makers | Exact solution can be substantially harder than a single-agent POMDP |
| POMCP | Partially Observable Monte-Carlo Planning using a generative model and history search | Not linearization; simple scenario enumeration is not POMCP |
| MCTS | Monte Carlo tree search over sampled future decisions | Search budget is finite and its result is model-dependent |
| RL — reinforcement learning | Learn a policy/value from reward and interaction or a specified dataset | Updating a Bayesian filter is not RL |
| DQN | Deep Q-network estimating action values | Values require a defined reward, training process and observation contract |
| MARL | Multi-agent reinforcement learning | Self-play does not guarantee robustness to unseen human opponents |
| IRL | Infer an objective from observed behavior | Multiple objectives can explain similar behavior |
| Nash equilibrium | Strategy profile where no player benefits from a unilateral change under the game model | Not a guarantee that our car wins |
| Stackelberg game | A leader anticipates a follower's response under a specified commitment model | Strategic leader does not necessarily mean car physically ahead |
| Non-anticipativity | Decisions must agree while the information available to them is indistinguishable | Prevents using future scenario labels to choose controls |
| Posterior mean decision | Optimize expected cost under a specified belief | Can be sensitive to misspecified probabilities |
| CVaR | Average cost in a specified adverse tail under a distribution | Not identical to worst-case optimization |
| Minimax regret | Minimize worst excess cost relative to a specified scenario comparator | Different from maximizing worst improvement over a reference |
| Calibration | Agreement between forecast probabilities/intervals and frequencies under stated conditions | Not the same as classification accuracy or causal identification |
| Identifiability | Whether available evidence can uniquely determine the modeled unknown | A narrow posterior alone does not establish it |
| Ablation | Remove or replace one feature while controlling the comparison | Changing the physical plant at the same time confounds attribution |
| Model mismatch | Difference between prediction assumptions and the evaluated/real system | More Monte Carlo samples do not remove omitted physics |

## 3. Vehicle and battery terminology

| Term | Meaning / unit |
|---|---|
| ICE | Internal-combustion engine |
| MGU-K | Motor-generator associated with kinetic energy recovery/deployment |
| DC power | Electrical energy transfer rate at an identified direct-current location, W |
| Mechanical power | Torque times angular velocity, or longitudinal force times speed, W |
| Energy | Integral of power over time, J; 1 MJ = 1,000,000 J |
| Charge capacity | Charge quantity, C or Ah; 1 Ah = 3,600 C |
| SOC | Stored charge relative to specified usable capacity; dimensionless |
| Capacity SOH | Reference-condition retained capacity relative to fresh capacity |
| Resistance growth | Reference-condition change in electrical resistance; not the same health ratio as capacity |
| OCV | Open-circuit voltage under a specified model/reference condition, V |
| Thevenin model | Equivalent circuit using voltage source, resistance and optional RC polarization branches |
| Polarization state | Transient voltage behavior beyond the simplest series-resistance model |
| Thermal capacity | Energy required per kelvin of temperature change, J/K |
| Thermal conductance | Heat-flow rate per temperature difference, W/K |
| Slip velocity | Local relative speed between tread and road; used in sliding work |
| Downforce | Aerodynamic force increasing tyre normal load |
| Wake / slipstream | Disturbed flow behind another car, affecting drag and potentially downforce |
| Active aero | Adjustable aerodynamic configuration governed by its applicable permissions |
| Overtake mode | A rules-defined energy/power mode requiring its own authorization; not identical to active aero |

## 4. Mathematical notation used in the specification

| Symbol | Meaning | Unit |
|---|---|---|
| `s, v, m` | Progress, speed, mass | m, m/s, kg |
| `kappa` | Path curvature | 1/m |
| `e` | Kinetic energy, `m v²/2` | J |
| `E_chem` | Model-defined internal stored battery energy | J |
| `z, h_Q, h_R` | Charge SOC, capacity multiplier, resistance-growth parameter | dimensionless |
| `I, V, U_oc, R` | Discharge-positive current, terminal voltage, OCV, resistance | A, V, V, ohm |
| `P_K,dc` | MGU-K DC deployment-positive power | W |
| `T, w` | Temperature, declared tyre wear proxy | K, dimensionless |
| `a, a0` | Candidate action/policy, reference action/policy | model-defined |
| `theta` | Retained hidden-state/model/response hypothesis | model-defined |
| `b` | Belief weights/distribution | dimensionless |
| `J, V_l` | Modeled cost, remaining-race value | seconds in required build |
| `G, L` | Paired modeled improvement, conservative commitment score | seconds in required build |
| `epsilon` | Declared action-value error allowance | same as cost |
| `Delta A` | Declared ageing-stress exposure increment | proxy-specific |
| `lambda_stress` | Time-equivalent price per stress unit | seconds / stress unit |

Never reuse `E` for both a battery energy and an HMM emission matrix without qualification. Likewise, a state labelled “low” must identify whether it means low charge, low observed deployment or low response capability.
