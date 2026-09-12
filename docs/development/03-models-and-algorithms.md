# Models and algorithms: implementable mathematical specification

All equations below specify our proposed reduced models unless explicitly attributed. They are not identified Haas/Ferrari/Pirelli models. Internal units are SI; reference parameters, valid ranges and numerical tolerances must be resolved before execution. References are indexed in the [bibliography](10-references.md).

## 1. State, control and exogenous inputs

The time-domain plant retains, for each car, track progress, speed, lateral state when enabled, fuel mass, battery SOC and temperature, tyre temperature/wear by axle, component identity and rule counters. Capacity and resistance-health multipliers are fixed within the initial race simulation. The rival additionally has private policy parameters and memory; the controller cannot read them.

The initial energy decision is requested MGU-K DC power, positive for deployment and negative for recovery, plus a candidate path and speed reference. An ordinary simulated driver/tracker supplies engine, braking and steering behavior consistent with that plan. Both cars use the same physical constraints. Environmental inputs include ambient/coolant conditions, track condition, air density and wind. These enter specific physical mechanisms, not a universal weather multiplier.

## 2. Longitudinal plant

For a fixed-path starter model:

\[
\dot s=v,\qquad m\dot v=F_{ICE}+F_K-F_{fric}-F_{drag}-F_{roll}-mg\sin\theta.
\]

`F_fric >= 0` denotes friction-braking magnitude. `F_K` is signed. Tyre longitudinal force is `F_x = F_ICE + F_K - F_fric`; aerodynamic drag and grade are not mistakenly added to tyre-contact demand. Fuel use reduces vehicle mass according to a declared engine fuel map or an explicitly synthetic nonnegative rate. Starting fuel is a scenario parameter, not assumed equal across real drivers.

For adequate speed, `P_K,mech = eta_m P_K,dc` in deployment and `P_K,mech = P_K,dc / eta_m` in recovery; then `F_K = P_K,mech / v`. These are simplified conversion relationships at a declared accounting location. At low speed, use torque/force limits rather than dividing by a small arbitrary epsilon. Include auxiliary DC demand separately at the battery terminal.

Model drag with relative air velocity and fixed/configured aerodynamic maps. Wake can reduce drag and downforce differently. Smooth bounded wake maps are scenario assumptions; do not fit exact F1 wakes from approximate public XY coordinates. Sensitivity tests must include no-wake and stronger/weaker-wake cases.

### Grip

A starting combined-force envelope is

\[
\left\|[F_x/r_x,\;F_y/r_y]\right\|_2\leq \mu(T_{tyre},w,c,\text{surface})F_z.
\]

Use positive fixed shape factors and a declared load model. This is a reduced combined-grip model inspired by the performance-envelope literature [P01], not an exact reproduction of its fitted coefficients. Do not claim available grip is increased by the optimizer. Temperature, wear, load and downforce can change the available envelope; optimization chooses how to use it.

The first longitudinal tests can use `F_y = m v² kappa(s)`. Before reporting completed overtakes, add a dynamically checked lateral/path model and footprints. Merely integrating progress until the ordering flips establishes catch-up only.

## 3. Passing geometry and execution

Required passing-claim model: a kinematic bicycle tracker with longitudinal acceleration and a known wheelbase, driven along a selected smooth offset path. Track-coordinate conversion must be consistent with world coordinates; path curvature and lateral acceleration must satisfy the grip check. A kinematic model does not reproduce all high-speed tyre transients, and that limitation belongs in results.

Use oriented rectangular vehicle footprints for overlap/track containment, interpolating motion or refining integration near potential contact. Define completion as the ego rear clearing the rival front along the appropriate local path by a configured margin, with no modeled contact or track exit, and maintaining the new order for a configured persistence interval. Store these definitions in the run manifest. A post-pass re-pass remains possible and is scored in the race outcome.

Candidate offset paths are enumerated, not continuously optimized inside a purportedly convex game. Reject paths whose curvature, track width or opponent predictions make them inadmissible. For inadequate geometric evidence in public replay, do not infer collision-free lane placement.

## 4. Battery: one-resistance electrothermal model first

Let discharge-positive current be `I`, usable charge capacity `Q_C` in coulombs, charge SOC `z`, and terminal voltage `V`. For the first model:

\[
\dot z=-I/Q_C,\quad V=U_{oc}(z)-IR(z,T,h_R),\quad
P_{term}=VI=P_{K,dc}+P_{aux,dc}.
\]

`Q_C = 3600 Q_ref,Ah h_Q`; `h_Q` is capacity retention. `h_R` is a resistance-growth parameter, not the same percentage. The initial model uses a reference-temperature OCV curve and ignores reversible/entropic heat; temperature affects resistance and limits. More complete circuit/thermal models are extensions [P17–P19].

For `R > 0`, choose the physically admissible low-current root of `R I² - U_oc I + P_term = 0`, subject to current, voltage, SOC, thermal and power limits. Check the discriminant. An inadmissible request is saturated/rejected and recorded; it is not converted into imaginary current or clipped SOC after integration. Handle the zero-resistance limiting case explicitly.

\[
C_{th}\dot T=I^2R-H(T-T_{coolant}).
\]

Define chemical stored energy for the frozen-capacity, reference-OCV model as

\[
E_{chem}(z)=Q_C\int_{z_{min}}^z U_{oc}(q)\,dq.
\]

Then `dE_chem/dt = -U_oc I`, and `U_oc I = P_term + I²R`. This supplies an explicit conservation test. Do not integrate terminal power as chemical energy while also applying internal resistance losses again. MGU-K DC counters, battery-terminal energy and chemical energy have different accounting roles.

Recovery during positive engine demand is permitted where the modeled mechanical architecture and rules allow it; engine work then supplies electrical recovery and reduces net wheel power. This captures the possibility of full-throttle recovery without equating full throttle to maximum net propulsion. No unrestricted charging or free energy is introduced.

### Health and environment

Accumulate charge throughput `integral |I| dt` in coulombs and declared temperature/current exposure summaries. They are stress proxies. Do not convert them to percent capacity loss or remaining life without a calibrated ageing model. High-temperature degradation and cold/high-rate charging degradation are not interchangeable mechanisms [P18–P19].

Vary `h_Q`, `h_R`, cooling effectiveness and initial temperature across scenarios. Within-race SOH is frozen in the first build; this is a scope decision, not a claim that real ageing stops. An optional synthetic lifecycle map may update health between events, labelled as synthetic. SOC is reinitialized at a new event rather than inherited from an old race without evidence.

## 5. Tyres: compound-dependent thermal state and irreversible wear

Required model: one effective temperature `T_a` and wear proxy `w_a` per axle, with a compound/event-specific parameter set. Optional extension: separate surface and bulk thermal nodes. The physical precedent for coupling temperature, grip and wear is established [P16]; our numeric maps remain assumptions until calibrated.

If slip is actually modeled, use dissipated sliding power

\[
P_{slip}\approx |F_xv_{slip,x}|+|F_yv_{slip,y}|,\qquad E_{slip}=\int P_{slip}\,dt.
\]

If the initial plant lacks slip, define a dimensionless utilization stress `u_a` from normalized longitudinal/lateral force demand, and an explicitly synthetic heat input `P_heat = P_ref,c f_c(u_a,v)`. It is a force-utilization surrogate, not measured contact-patch work. Do not use `integral force × vehicle speed × distance` as energy.

\[
C_{a,c}\dot T_a=\chi_c P_{heat,a}-H_{a,c}(T_a-T_{environment,a}),
\quad \dot w_a=k_c f_c(u_a)g_c(T_a)\geq0.
\]

Define `k_c` in inverse seconds when `w` and the functions are dimensionless. Use a bounded positive grip map with a thermal optimum and a monotone wear penalty. Coefficients, hot/cold behavior and any cliff are scenario assumptions; do not claim measured Pirelli operating windows. Cooling may restore thermal grip but cannot decrease accumulated wear.

Hard/Medium/Soft are event-relative labels; store actual compound identity separately where verified [D04]. A pit stop changes tyre-set identity and temperature/wear priors, not the driver prior or battery health. Driver behavior affects loads through the simulated controls; avoid multiplying in an aggression factor that counts the same stress twice.

## 6. Conditional convex deployment planner

Use a spatial grid and fixed candidate path. Let kinetic energy `e_k = m v_k²/2` be the speed state. Decision variables include kinetic energy, signed MGU-K power in a preselected regime, friction braking and the declared engine-force decision or reference. Mass, path, regime, efficiencies and local linearization maps are fixed for each solve.

An implementable first subproblem uses:

\[
e_{k+1}=e_k+\Delta s_k(F_{ICE,k}+F_{K,k}-F_{fric,k}-\widehat F_{res,k}),
\]

with affine frozen/local drag representation. For a fixed reference speed `v_ref,k`, map `P_K,dc` to `F_K` using the appropriate fixed deployment/recovery efficiency. Constrain the power sign by the enumerated operating regime; do not permit independent simultaneous charge/discharge variables to create artificial benefit.

Use `F_y,k = 2 kappa_k e_k`, an affine expression, and a positive frozen or affine downforce approximation in a second-order-cone grip constraint. Fix tyre/thermal/wake coefficients during the solve. Bound deviations from the reference-speed trajectory. A nonlinear power-versus-speed rule is represented by a conservative envelope over that trust interval, not a cap evaluated at an unrelated speed.

The chemical-energy prediction may use a frozen local conversion ratio `alpha_k = U_oc,ref/V_term,ref`:

\[
E_{k+1}=E_k-\frac{\Delta s_k}{v_{ref,k}}\alpha_k(P_{K,dc,k}+P_{aux,dc,k}).
\]

This is an affine approximation, not the nonlinear battery model. Separate deployment/recovery regimes require appropriate reference ratios; validate both against the plant and tighten the trust interval when mismatched. Power, current and thermal prediction limits are conservative local approximations. Keep their residuals visible.

Minimize a convex elapsed-time surrogate plus a compatible convex terminal resource cost:

\[
\sum_k\Delta s_k\sqrt{m/2}\,e_k^{-1/2}+\widehat V_{terminal}(E_N)+\text{regularization},\quad e_k>0.
\]

If the full race-value lookup is nonconvex, enumerate terminal-energy targets externally or use a documented convex local approximation. Do not insert an arbitrary learned value function into a convex program and retain the convexity claim. The outer scenario evaluator can use the original nonconvex continuation map.

Verify DCP and solver compatibility. A conic-capable solver is needed when SOC constraints remain; OSQP alone handles quadratic programs with linear constraints, not general SOCPs [S01–S03]. Compile parameterized problems once when supported; record cold and warm runtimes. Return primal residuals and status. A limited sequential refinement may update reference trajectories, but global optimality of the coupled problem is not established.

PMP switching laws from [P07] may be reproduced as a separate simplified-model baseline. Do not paste their costate thresholds into this hybrid model and call them its exact optimum.

## 7. Opponent beliefs and context

Use a compact weighted hypothesis ensemble initially: physical reserve/capability, temperature/wear hypotheses, uncertain car parameters and a small set of response-policy families. A four-mode HMM is a lightweight baseline; a faithful forty-state reproduction of [P06] is a separate, optional reproduction task.

For an elapsed-time transition model and only newly available evidence:

\[
b^-_t(x')=\int p(x'\mid x,a^{ego}_{t-1},\Delta t,context)b_{t-1}(x)dx,
\quad b_t(x')\propto p(o_t\mid x',context)b^-_t(x').
\]

The transition marginalizes the rival's unknown action through its response policy. Our action is not incorrectly treated as the rival's burn/harvest command. Normalize in a stable domain; preserve a low-confidence recovery path when every hypothesis has poor likelihood.

Use jointly modeled residuals or a carefully selected subset of signals. Do not multiply speed, sector time and a speed-derived aero proxy as independent evidence. Condition baselines on track position, past-only stint context, weather and traffic. Process sector statistics only after their availability time; overlapping windows must not be counted repeatedly as independent measurements.

Driver priors describe conditional observable behavior and shrink toward a pooled prior when history is sparse. Across sessions, persist parameters with evidence counts and forgetting, not current SOC. A component ledger records verified replacements and uncertainty about identity. Report forecasts of response capability with an interval/hypothesis spread, not a precise rival battery gauge.

## 8. Bounded tactical planning and commitment

Generate at most a small configured number of candidate profiles; start with five action families and approximately 16–32 hypothesis rollouts per family, then profile. Counts are engineering starting points, not statistical guarantees. Include multiple opponent response families, reaction delays and an unresponsive policy. Apply common first controls across indistinguishable scenarios; follow-up actions depend only on observations actually generated in each rollout.

For lower-is-better cost `J_H` and current-state-feasible reference `a0`, estimate paired improvement:

\[
\widehat G(a,\theta)=\widehat J_H(a_0,\theta)-\widehat J_H(a,\theta),
\quad L(a)=\min_{\theta\in\Theta(h)}\widehat G(a,\theta)-\epsilon_a.
\]

Choose the feasible candidate with greatest `L` only if it exceeds a configured positive commitment margin. Otherwise retain the reference. `epsilon_a` is a declared validation-derived or conservative heuristic model-error allowance; without a proven bound it is **not** a confidence certificate. Track scenario coverage, probability mass excluded and sensitivity to set construction. Rare but plausible adverse responses cannot be silently dropped to improve results.

Compare this rule with posterior-mean selection, CVaR of cost and minimax regret using the same candidates and rollouts. Those objectives are different. Worst-case improvement can be overly conservative; measure missed opportunities and the performance–risk curve. A probe/feint is valuable only if later outcomes improve after its own energy, time and tyre costs; an opponent can ignore it.

Use fixed horizon, rollout cap, wall-clock deadline and cancellation. Sampling does not linearize physics. Without history-tree search this is not POMCP [P15]. No formulation guarantees that a stronger rival loses or that every tie should be eliminated.

## 9. Remaining-race and lifecycle value

For a restricted strategy set, generate lap transition maps over reachable resource states. A finite-horizon recursion can be

\[
V_\ell(q)=\min_{u\in U_\ell(q)}\{t_{lap}(q,u)+\lambda_{stress}\Delta A(q,u)+V_{\ell+1}(f_{lap}(q,u))\}.
\]

`q` contains a deliberately small energy/thermal/tyre context; hold or enumerate pit plans rather than exhaustively branching over the grid. The initial primary cost is elapsed/remaining finish time in seconds, with explicit feasibility constraints. Stress cost is time-equivalent, with its conversion declared. Report finishing order separately. Full expected-points optimization requires a richer race-order model and is not implied by two-car time minimization.

Terminal reserve is valued once: if `V` already prices remaining energy, do not add an unrelated duplicate energy penalty. Full-race terminal values and constraints are fixed for all controllers. Unreachable map queries are flagged, not freely extrapolated.

The optional season dynamic program uses synthetic event payoff/wear maps, component inventory and replacement choices. It can output a local marginal resource price. Existing multi-race co-design is prior art [P12]. A configured price is sufficient for the season-informed interface but cannot be advertised as an optimized season result.
