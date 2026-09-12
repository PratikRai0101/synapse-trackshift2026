# Degradation model review

12 September 2026. Scope: a 24-hour build by two capable people using public data and available CPU/GPU. Six primary sources; architecture recommendations only. No numerical F1 health predictions or transplanted coefficient values.

## Corrections to carry into the architecture

**Battery charge, temperature, and health are different quantities.** SOC tracks remaining charge relative to a defined capacity; temperature is a thermal state. Capacity SOH can be defined as `Q_aged/Q_fresh`, while resistance growth is separately `R_aged/R_fresh`. Compare health measurements under the same reference temperature, SOC, rate and pulse duration: an operating-temperature resistance change is not automatically irreversible ageing. Schmalstieg et al. measure capacity and resistance separately and couple calendar/cycle ageing to an electrical–thermal model. [S2]

**Replace arbitrary quadratic resistance-versus-temperature growth.** Use positive, calibrated maps `R_j(SOC,T)` and an independently specified ageing dependence. Neither the existence of heating nor accelerated hot ageing establishes `R ∝ T²`. Temperature-dependent electrical behaviour and time-dependent resistance degradation must remain separate. A polynomial could interpolate measured data locally; it is not a universal physical law. The source models support an equivalent-circuit/thermal architecture, not coefficients for an F1 pack. [S1][S2]

**Correct “high temperature causes lithium plating.”** Kucinskis et al. experimentally distinguish a high-temperature branch dominated by solid-electrolyte-interphase growth from a low-temperature branch dominated by lithium deposition. Higher charging rates can shift the crossover; cell design and ageing state also matter. Cold/high-rate *charging*, including regenerative charging in an analogous model, is the relevant plating concern. Do not apply this mechanism indiscriminately to high discharge rates. There is no universal crossover temperature or globally valid quadratic ageing curve. An Arrhenius factor `exp(-E_a/(R_g T))`, with absolute temperature and molar activation energy, is defensible only within an identified mechanism/regime. [S3]

**Correct tyre frictional work.** With traction `τ` acting on tread and local tread–road relative velocity `v_slip`, dissipated sliding power is

`P_slip = -∫contact τ · v_slip dA ≥ 0`.

This is a mechanical/dimensional derivation. A lumped approximation uses force times the corresponding **slip velocity**. Vehicle speed alone is insufficient: the ideal no-slip limit gives no sliding heat, while deformation losses can remain. West–Limebeer Eq. (1) contains forward speed *multiplied by slip ratio/slip-angle terms*; its speed factor is not justification for deleting those terms. [S4]

Energy is `E_slip = ∫P_slip dt` in joules. Along distance `s`, it is `∫P_slip/(ds/dt) ds`; `∫P_slip ds` has units W·m, not energy. Use time integration at stops. Define explicitly what fraction heats the tyre; total contact dissipation is not all retained in the rubber.

## Reduced models worth retaining

**Battery:** a Thevenin circuit with SOC, one polarization-voltage state and a lumped temperature is a sensible small model. PyBaMM documents OCV, series resistance, RC branches and coupled lumped thermal models. A suitable proposed structure, for discharge-positive current and frozen reference capacity, is:

`dz/dt = -I/(3600 Q_ref SOH_Q)`; `dv_p/dt = -v_p/(R_1 C_1) + I/C_1`;

`V = U_oc(z,T) - I R_0(z,T) - v_p`;

`C_th dT/dt = Q_irr + Q_rev - H(T-T_cool)`.

Here capacity is in Ah; charge efficiency is idealized. Heat terms must be consistent with the chosen circuit and entropy convention. A second thermal node is optional when a justified thermal lag matters. These are proposed reductions, not an identified F1 pack. [S1]

**Tyres:** West–Limebeer uses tread and carcass temperatures, cumulative wear, a nonlinear friction-power wear law, and a grip surface depending on temperature and wear. Its temperature window must change with compound; a single shared linear degradation slope loses this structure. Its cold/hot wear terms are empirical assumptions, not measured universal graining/blistering laws. [S4] Farroni et al. additionally couple tread removal to thermal behaviour and adhesive/hysteretic friction, supporting feedback between wear, temperature and grip. [S5]

A compact proposed surrogate is `x_tyre=(T_surface,T_bulk,w)` per axle initially, with `dw/dt=g_c(P_slip,T_surface,w)≥0` and `μ=μ_c(T_surface,w)`. Use bounded nonlinear maps indexed by compound `c`; give all rates and maps explicit provenance. Cooling may restore a reversible temperature effect but cannot undo accumulated wear. [S4][S5]

Compound identity must include season and event nomination. Pirelli's May 2026 announcement maps C3/C4/C5 to Hard/Medium/Soft at Monaco, but C2/C3/C4 at Barcelona. Thus “Medium” is not a fixed compound identifier. [S6]

## What the 24-hour prototype should evolve or freeze

| Evolve within a simulation | Freeze as latent scenario parameters |
|---|---|
| Battery SOC, polarization voltage, temperature | Reference capacity/resistance SOH; OCV/RC maps; thermal mass, cooling and entropy parameters |
| Charge throughput and separate hot/cold charging exposure summaries | Ageing kinetics, activation energies, plating thresholds and exposure-to-damage conversion |
| Tyre surface/bulk temperature and nondecreasing wear proxy | Compound-specific grip/wear curves, heat capacities, conductances, heat partition and initial-condition assumptions |

This is an engineering recommendation. Frozen SOH is a scope choice, not evidence that physical ageing vanishes during a race. Exposure summaries are not capacity loss or plated-lithium estimates. Persist tyre states through a stint; replacement sets need their own initial conditions.

Public data support **proxies**, not identification of the hidden physics. No source here supplies an actual F1 pack's electrothermal/ageing coefficients. This bounded search does not prove none exist anywhere. Missing evidence includes pack current/voltage/temperature histories and reference health tests, plus tyre slip, contact forces, internal temperature, measured tread loss and compound calibration. Therefore public pace/compound/stint observations cannot uniquely separate thermal effects, physical wear and driving conditions. Label synthetic thermal/health trajectories accordingly.

For this team, prioritize a CPU-sized surrogate, dimensional checks and sensitivity comparisons across explicitly documented assumptions. GPU capacity does not resolve missing measurements. Do not fit a large latent physical model or report numerical real-F1 health improvements.

## Six primary sources and their limits

1. **S1 — [PyBaMM Thevenin model documentation, v22.11](https://docs.pybamm.org/en/v22.11/source/models/equivalent_circuit/thevenin.html).** Official implementation documentation; establishes model structure, not F1 validation or a current-version API recommendation.
2. **S2 — [Schmalstieg et al., “From Accelerated Aging Tests to a Lifetime Prediction Model,” EVS27, 2013](https://www.citelec.org/EVS27/download.php?f=papers/EVS27-2870281.pdf).** Public original conference paper; reference-condition health tests and coupled ageing model. Commercial high-energy NMC/graphite cells, not racing packs; coefficients do not transfer.
3. **S3 — [Kucinskis et al., “Arrhenius plots for Li-ion battery ageing…,” Journal of Power Sources, 2022](https://dspace.lu.lv/server/api/core/bitstreams/3fb0395b-6985-425c-a50f-2ba7ffa0a906/content).** University-hosted original paper, DOI 10.1016/j.jpowsour.2022.232129. Commercial/laboratory cells; mechanism crossover depends on tested cells and charging conditions.
4. **S4 — [West and Limebeer, “Optimal Tyre Management of a Formula One Car,” IFAC 2020](https://ifatwww.et.uni-magdeburg.de/ifac2020/media/pdfs/0335.pdf).** Original congress preprint, thermal/wear Sections 2.1–2.3 only. Tread telemetry fitting; carcass temperature was unmeasured. Illustrative compound curves are not current Pirelli calibration.
5. **S5 — [Farroni, Sakhnevych and Timpone, “Physical modelling of tire wear…,” 2017](https://journals.sagepub.com/doi/abs/10.1177/1464420716666107).** Peer-reviewed motorsport-relevant journal paper. Public abstract inspected; full text restricted. Supports coupling claims, not verified equations or coefficients here.
6. **S6 — [Pirelli, “The tyre compound selections for Monte Carlo and Barcelona,” 19 May 2026](https://press.pirelli.com/the-tyre-compound-selections-for-monte-carlo-and-barcelona/).** Official event nominations; establishes label semantics, not thermal properties or wear coefficients.

[S1]: https://docs.pybamm.org/en/v22.11/source/models/equivalent_circuit/thevenin.html
[S2]: https://www.citelec.org/EVS27/download.php?f=papers/EVS27-2870281.pdf
[S3]: https://dspace.lu.lv/server/api/core/bitstreams/3fb0395b-6985-425c-a50f-2ba7ffa0a906/content
[S4]: https://ifatwww.et.uni-magdeburg.de/ifac2020/media/pdfs/0335.pdf
[S5]: https://journals.sagepub.com/doi/abs/10.1177/1464420716666107
[S6]: https://press.pirelli.com/the-tyre-compound-selections-for-monte-carlo-and-barcelona/
