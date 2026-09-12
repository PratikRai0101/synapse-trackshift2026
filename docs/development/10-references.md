# Paper references and source ledger

Bounded review as of 12 September 2026. IDs below are used throughout the package. Existing full-text notes are in [the evidence review](../../outputs/research-evidence.md), [degradation review](../../work/degradation-model-review.md) and [development reference audit](../../work/development-reference-audit.md). This is not a systematic literature review; no external implementation was reproduced.

Version/status statements refer to the inspected records, not guaranteed latest publisher editions. Keep exact compared versions in experiment manifests. Resolve final publisher metadata before formal manuscript submission.

## A. Eight supplied foundations

**P01 — Duhr et al. (2022). _Convex Performance Envelope for Minimum Lap Time Energy Management of Race Cars._ IEEE Transactions on Vehicular Technology.** [DOI: 10.1109/TVT.2022.3172473](https://doi.org/10.1109/TVT.2022.3172473). Use: combined performance-envelope modeling and convex energy planning. Earlier local file no longer available at its supplied Downloads path; modeling was cross-checked in [Duhr's author thesis, Chapter 7](https://www.research-collection.ethz.ch/server/api/core/bitstreams/a40125ce-dcac-4ffd-870d-19881e8820a8/content). No claim to reproduce private fitted maps.

**P02 — Salazar, Balerna, Elbert, Grando, Onder (2017). _Real-Time Control Algorithms for a Hybrid Electric Race Car Using a Two-Level Model Predictive Control Scheme._ IEEE TVT 66(12), 10911–10922.** [DOI: 10.1109/TVT.2017.2729623](https://doi.org/10.1109/TVT.2017.2729623); [institutional record](https://research.tue.nl/en/publications/real-time-control-algorithms-for-a-hybrid-electric-race-car-using/). Use: planner/execution decomposition. Bibliography and abstract verified; its runtime and historical regulations do not transfer to our system.

**P03 — van Kampen, Moriggi, Braghin, Salazar (2024). _Model Predictive Control Strategies for Electric Endurance Race Cars Accounting for Competitors' Interactions._** [arXiv:2403.06885v1](https://arxiv.org/abs/2403.06885v1). Supplied full text reviewed. Use: interaction value beyond the immediate maneuver. Electric-endurance charging and recorded nonreacting competitors differ from our F1-inspired reactive scenario.

**P04 — Fieni, Neumann, Zanardi, Cerofolini, Onder (2025 version). _Game-theoretic Energy Management Strategies With Interacting Agents in Formula 1._** [arXiv:2405.11032v3](https://arxiv.org/abs/2405.11032v3); [IEEE TVT DOI](https://doi.org/10.1109/TVT.2025.3601890). Supplied full text reviewed. Use: drag-coupled interaction and energy optimization. Local-solution and runtime limitations prohibit importing a real-time/global-equilibrium guarantee.

**P05 — Fieni et al. (2026 version). _Game Theory in Formula 1: From Physical to Strategic Interactions._** [arXiv:2503.05421v5](https://arxiv.org/abs/2503.05421v5); [European Journal of Control DOI](https://doi.org/10.1016/j.ejcon.2026.101554). Supplied full text reviewed. Use: trajectory/aerodynamic interaction and distinctions between game formulations. A strategic leader is not necessarily the car ahead.

**P06 — Kleisarchaki (2026). _Opponent State Inference Under Partial Observability: An HMM–POMDP Framework for 2026 Formula 1 Energy Strategy._** [arXiv:2603.01290v3](https://arxiv.org/abs/2603.01290v3). Preprint; supplied full text reviewed. Use: belief-state baseline. Synthetic validation, correlated emissions and stationary-opponent assumptions limit empirical interpretation; regulatory statements require independent checking.

**P07 — van den Eshof, de Vries, Salazar (2026). _A Computationally Efficient and Human Implementable Minimum-lap-time Control Policy for Energy-limited Race Cars._** [arXiv:2603.02339v1](https://arxiv.org/abs/2603.02339v1). Record states submitted to ITSC 2026; supplied full text reviewed. Use: interpretable control structure under its specific fixed-path/loss assumptions, not portable costate thresholds for our coupled model.

**P08 — de Vries, van den Eshof, van Kampen, Salazar (2026). _Competitor-aware Race Management for Electric Endurance Racing._** [arXiv:2603.28286v2](https://arxiv.org/abs/2603.28286v2). Record reports ITSC 2026 acceptance; supplied full text reviewed. Use: game-model/race-policy coupling and opponent pools. Its charging-race results are not F1 gains.

## B. Closest architecture and novelty comparisons

**P09 — Fieni, Wüthrich, Neumann, Onder (2026). _Learning-based Multi-agent Race Strategies in Formula 1._** [arXiv:2602.23056v2](https://arxiv.org/abs/2602.23056v2). Preprint; method review. Direct comparator for multi-agent energy/tyre/pit strategy with hidden rival energy. Author implementation not verified.

**P10 — Wüthrich, Damle, Fieni, Zeilinger, Onder, Carron (2026). _Bridging RL and MPC for Mixed-Integer Optimal Control with Application to Formula 1 Race Strategies._** [arXiv:2604.00826v1](https://arxiv.org/abs/2604.00826v1). Submitted manuscript; method/assumptions reviewed. Use: learned discrete choices, warm starts and terminal value; feasibility conditions cannot be inherited unchanged.

**P11 — Fieni et al. (2025). _Towards Learning-Based Formula 1 Race Strategies._** [arXiv:2512.21570v1](https://arxiv.org/abs/2512.21570v1). Preprint; method review. Use: joint energy/tyre/pit optimization baseline. Final author metadata should be normalized against the version actually cited.

**P12 — Neumann, Habermacher, Fieni, Cerofolini, Zardini, Onder. _Hierarchical Co-Design for Multi-Race Strategy Optimization in Formula 1._** 2025 working paper; authors list ITSC 2026 in press. [MIT author bibliography](https://zardini.mit.edu/publications/); [ETH project record](https://idsc.ethz.ch/research-guzzella-onder/research-projects/Formula1.html); [author manuscript link](https://www.research-collection.ethz.ch/server/api/core/bitstreams/7e6b5a19-6bec-4544-b403-04262777d6cc/content). Abstract/metadata only; full retrieval failed, revision not verified. Direct prior art for season performance/wear/replacement planning.

**P13 — Kleisarchaki (2026). _Keynesian Beauty Contests on the Pit Wall: Game-Theoretic Energy Strategy in 2026 Formula 1._** [Author-uploaded preprint](https://www.researchgate.net/publication/401730959_Keynesian_Beauty_Contests_on_the_Pit_Wall_Game-Theoretic_Energy_Strategy_in_2026_Formula_1), DOI 10.13140/RG.2.2.27003.17448. Accessible v1.1 partially reviewed; no peer-reviewed venue verified. Prior art for strategic belief manipulation; not every promised extension was verified as implemented.

**P14 — Chen, Rosolia, Ubellacker, Csomay-Shanklin, Ames (2022). _Interactive Multi-Modal Motion Planning With Branch Model Predictive Control._** IEEE RA-L. [arXiv:2109.05128v2](https://arxiv.org/abs/2109.05128v2); [author-linked code](https://github.com/chenyx09/belief-planning). Method review; code found, not run. Use: reactive-policy scenarios, branching and risk sensitivity. These methods are prior art.

**P15 — Silver and Veness (2010). _Monte-Carlo Planning in Large POMDPs._** NeurIPS. [Original paper](https://papers.nips.cc/paper_files/paper/2010/file/edfbe1afcf9246bb0d40eb4d8027d90f-Paper.pdf). Algorithm reviewed. Use: belief/history search and bounded planning; does not turn physics into an LP or guarantee victory.

## C. Physical-model references

**P16 — West and Limebeer (2020). _Optimal Tyre Management of a Formula One Car._** IFAC World Congress. [Original congress manuscript](https://ifatwww.et.uni-magdeburg.de/ifac2020/media/pdfs/0335.pdf). Thermal/wear sections reviewed. Use: coupled temperature, wear and grip; example parameters are not current Pirelli calibration.

**P17 — PyBaMM, Thevenin equivalent-circuit model documentation.** [Versioned structural reference, v22.11](https://docs.pybamm.org/en/v22.11/source/models/equivalent_circuit/thevenin.html). Official documentation; not a paper or current installation recommendation. Use: equivalent-circuit and thermal architecture, not F1 coefficients.

**P18 — Schmalstieg et al. (2013). _From Accelerated Aging Tests to a Lifetime Prediction Model._** EVS27. [Original paper](https://www.citelec.org/EVS27/download.php?f=papers/EVS27-2870281.pdf). Use: separate capacity/resistance health and coupled ageing models. Tested cells differ from F1 packs; coefficients do not transfer automatically.

**P19 — Kucinskis et al. (2022). _Arrhenius plots for Li-ion battery ageing as a function of temperature, C-rate, and ageing state—An experimental study._** Journal of Power Sources, 232129. [University-hosted paper](https://dspace.lu.lv/server/api/core/bitstreams/3fb0395b-6985-425c-a50f-2ba7ffa0a906/content); [DOI](https://doi.org/10.1016/j.jpowsour.2022.232129). Use: regime-dependent temperature/charging effects; no universal plating threshold or F1 lifetime estimate.

## D. Research-method and evaluation references

**P20 — Zhao, Kim, Sahoo, Ma, Ermon (2021). _Calibrating Predictions to Decisions: A Novel Approach to Multi-Class Calibration._** NeurIPS. [Official proceedings](https://papers.nips.cc/paper/2021/hash/bbc92a647199b832ec90d7cf57074e9e-Abstract.html). Main-result screening. Prior art for decision-oriented calibration; not automatically a sequential racing guarantee.

**P21 — Kiyani, Hassani, Pappas, Roth (2025 preprint). _Robust Decision Making with Partially Calibrated Forecasts._** [arXiv:2510.23471v1](https://arxiv.org/abs/2510.23471v1). Abstract/main-result screening; final venue not asserted. Close predecessor for robust decisions under imperfect calibration.

**P22 — Nakao, Jiang, Shen (2021). _Distributionally Robust Partially Observable Markov Decision Process with Moment-based Ambiguity._** SIAM Journal on Optimization. [arXiv:1906.05988v3](https://arxiv.org/abs/1906.05988v3); [DOI](https://doi.org/10.1137/19M1268410). Abstract/repository screening. Prior art for ambiguity sets in partially observed planning; not an implementation we have reproduced.

**P23 — Lee, Nam, Lee, Kwon (2024). _Kernel-Based Metrics Learning for Uncertain Opponent Vehicle Trajectory Prediction in Autonomous Racing._** IEEE RA-L. [Published author PDF](https://amilearning.github.io/assets/pdf/ral2024.pdf); [DOI](https://doi.org/10.1109/LRA.2024.3486178). Method/evaluation review. Stronger contextual opponent-prediction comparator; physical small-scale racing is not F1 battery validation.

**P24 — Cao, Cohen, Szpruch (2021). _Identifiability in Inverse Reinforcement Learning._** NeurIPS. [arXiv:2106.03498v3](https://arxiv.org/abs/2106.03498v3). Formal-results screening. Limits on identifying objectives from behavior; not a theorem about our battery observability.

**P25 — Lindemann, Cleaveland, Shim, Pappas (2023). _Safe Planning in Dynamic Environments Using Conformal Prediction._** IEEE RA-L. [arXiv:2210.10254v2](https://arxiv.org/abs/2210.10254v2). Assumptions reviewed. Useful calibration discipline; action-dependent reactive opponents challenge assumptions of fixed external trajectory distributions.

## E. Data, rules and pitch evidence

**D01 — FastF1 official source.** [Car-data parser and embedded channel documentation](https://raw.githubusercontent.com/theOehrly/Fast-F1/master/fastf1/_api.py). Used for units, cadence and provenance; public library access is not private team telemetry entitlement.

**D02 — OpenF1 project documentation.** [Endpoint reference](https://openf1.org/docs/). Used for channel availability, approximate cadence and positional limitations. Access and redistribution terms require checking for the selected use.

**D03 — FIA 2026 regulations, reviewed editions.** [Technical Section C, Issue 20](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_20_-_2026-08-05.pdf), [Sporting Section B, Issue 08](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_b_sporting_-_iss_08_-_2026-08-05_7.pdf), 5 August 2026. Event supplements and certain tracked-change details remain unresolved; no blanket compliance claim.

**D04 — Pirelli (19 May 2026).** [Compound selections for Monte Carlo and Barcelona](https://press.pirelli.com/the-tyre-compound-selections-for-monte-carlo-and-barcelona/). Supports event-relative compound labels, not tyre thermal coefficients.

**D05 — Haas (21 November 2024).** [Mphasis digital-partner announcement](https://www.haasf1team.com/news/moneygram-haas-f1-team-welcomes-mphasis-partnership). Supports analytics/predictive-modeling relevance, not endorsement or evidence of an internal capability gap.

**D06 — Haas (16 July 2024).** [Ferrari power-unit partnership extension](https://www.haasf1team.com/news/partnership-extended-between-moneygram-haas-f1-team-and-scuderia-ferrari). Supports supplier context; confers no access to models or telemetry.

## F. Development documentation

**S01 — CVXPY:** [DCP rules](https://www.cvxpy.org/tutorial/dcp/index.html), [solver selection](https://www.cvxpy.org/tutorial/solvers/index.html). Verify formulation and installed solver support; no runtime guarantee.

**S02 — Clarabel:** [overview](https://clarabel.org/stable/), [supported cones](https://clarabel.org/stable/api_cone_types/). Conic formulation support; package version and platform must be pinned during development.

**S03 — OSQP:** [official problem definition](https://osqp.org/docs/). Convex QP with linear constraints; not direct general-SOCP support.

## Citation practice for slides and a future paper

Cite the specific borrowed method on the slide where it appears. Keep our equations labelled as proposed adaptations unless faithfully reproduced. Use publisher DOI metadata when verified and pin arXiv/manuscript versions for comparisons. Distinguish full-text review from abstract screening, available code from executed reproduction, and peer review from preprint status. No citation authorizes a claim beyond the evidence in that source.
