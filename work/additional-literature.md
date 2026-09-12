# Trackshift: additional literature and defensible novelty

Verified 11 September 2026. Eight priority papers plus one supporting sim-to-real reference. The six supplied foundation papers were not reread; their limitations and deferred extensions below are attributed to the main agent's audit. This is a bounded literature assessment, not a systematic review or a claim of priority. Author code is linked only where its connection to the paper was verified; repositories were not executed. Unverified publication, arXiv, and code details below remain unresolved; no further search is pending.

The strongest candidate contribution is an **independent physical identifiability benchmark coupled to decision regret and calibrated abstention**. “Opponent-aware energy RL,” “RL plus constrained MPC,” “adaptive opponents,” and “uncertainty-aware racing” already have close precedents. The research question should be whether useful, defensible energy decisions remain possible when several physical explanations fit the same public observations.

## Eight priority papers

### 1. Learning-based Multi-agent Race Strategies in Formula 1

**Giona Fieni, Joschua Wüthrich, Marc-Philippe Neumann, Christopher H. Onder. 2026. Preprint; no peer-reviewed venue verified.** First submitted 26 February; latest verified **arXiv:2602.23056v2, 2 July 2026**. [Versioned record](https://arxiv.org/abs/2602.23056v2), [full text](https://arxiv.org/html/2602.23056v2). Author code not verified.

This is the closest additional competitor to the overall product concept. It combines energy allocation, tire degradation, aerodynamic interaction, pit stops, an interaction correction to a frozen single-agent policy, and self-play. Crucially, its opponent observation deliberately excludes battery level and allocation strategy; the formulation uses available quantities such as tire age, pit decisions, and gap. See §§II-B–II-E of the [paper](https://arxiv.org/html/2602.23056v2).

Its lap-by-lap reactive strategy is a necessary baseline. Trackshift cannot claim novelty merely from acting against competitors with hidden batteries or adapting energy to their responses. The narrower opportunity is to measure when physically distinct hidden explanations remain observationally indistinguishable, and whether explicitly retaining that ambiguity changes decisions. Publicly available *inputs* do not establish public ground truth for hidden states.

### 2. Bridging RL and MPC for mixed-integer optimal control with application to Formula 1 race strategies

**Joschua Wüthrich, Romir Damle, Giona Fieni, Melanie N. Zeilinger, Christopher H. Onder, Andrea Carron. 2026. Preprint, submitted to IEEE; acceptance not verified.** **arXiv:2604.00826v1, 1 April 2026**. [Record](https://arxiv.org/abs/2604.00826v1), [full text](https://arxiv.org/html/2604.00826v1). Author code not verified.

The actor learns the full hybrid action space, supplies discrete decisions and a continuous warm start over the planning horizon, and its critic supplies MPC's terminal cost. The paper establishes recursive feasibility under structural assumptions and evaluates F1 strategy against an offline mixed-integer optimization benchmark, including adaptations to unseen disturbances without retraining. A critical restriction is that discrete inputs affect dynamics and cost but not constraint feasibility. See §§II–IV of the [paper](https://arxiv.org/html/2604.00826v1).

Consequently, “learning long-term value while MPC enforces constraints” is occupied territory. Its feasibility result cannot simply be inherited by opponent-dependent constraints or regulatory mode switches. A Trackshift contribution would need a separate argument connecting ambiguity-set validity, action-value error, and decision regret.

### 3. Towards Learning-Based Formula 1 Race Strategies

**Giona Fieni, Joschua Wüthrich, Marc-Philippe Neumann, Mohammad M. Moradi, Christopher H. Onder. 2025. Verified as a preprint.** **arXiv:2512.21570v1, 25 December 2025**. [Record](https://arxiv.org/abs/2512.21570v1), [manuscript](https://arxiv.org/html/2512.21570v1). Metadata discrepancy: the manuscript lists **Mohammad H. Moradi**, whereas the arXiv author record lists **Mohammad M. Moradi**. The manuscript header names *Transportation Engineering*, but that alone does not verify acceptance. Author code not verified.

It develops both mixed-integer nonlinear optimization and RL for coupled energy allocation, tire wear, and pit-stop timing. Both use the same race scenario, with nominal and unexpected-disturbance comparisons. This supplies an important control-quality benchmark and a route to quantify the price of imperfect energy allocation. See §§2–5 of the [manuscript](https://arxiv.org/html/2512.21570v1).

The opportunity is not introducing energy-aware race RL or an optimizer reference. It is evaluating inference and decisions against a separate physical generator whose latent mechanisms and observation errors were not defined by the estimator being tested. Agreement inside a shared model is useful algorithmic validation, but does not resolve physical model misspecification.

### 4. Keynesian Beauty Contests on the Pit Wall: Game-Theoretic Energy Strategy in 2026 Formula 1

**Kalliopi Kleisarchaki. 2026. Author-uploaded preprint; no peer-reviewed venue verified.** Accessible **v1.1, post-Melbourne**, uploaded 10 March 2026; the document records v1 on 5 March and says it was submitted to arXiv on 8 March. [Author full text](https://www.researchgate.net/publication/401730959_Keynesian_Beauty_Contests_on_the_Pit_Wall_Game-Theoretic_Energy_Strategy_in_2026_Formula_1), DOI **10.13140/RG.2.2.27003.17448**. Exact-title arXiv searches found no separate record; direct arXiv author search failed. Submission is not evidence of an arXiv posting. No code release verified.

The accessible version discusses a partially observable stochastic game, strategically manipulated rival beliefs, and the harvest/derate distinction. It is direct prior art against claiming strategic adaptation or deceptive harvesting as new. The main agent additionally reports that HMM v3 explicitly defers correlated emissions, geometry-conditioned transitions, adaptive opponents, and bounded-rationality POMCP here. Text searches of accessible v1.1 did not locate Gaussian, geometry, or POMCP details: distinguish a promised extension from a verified implementation. Neither establishes novelty for simply adding those features. [Source](https://www.researchgate.net/publication/401730959_Keynesian_Beauty_Contests_on_the_Pit_Wall_Game-Theoretic_Energy_Strategy_in_2026_Formula_1).

### 5. Kernel-Based Metrics Learning for Uncertain Opponent Vehicle Trajectory Prediction in Autonomous Racing

**Hojin Lee, Youngim Nam, Sanghun Lee, Cheolhyeon Kwon. 2024. Peer-reviewed, IEEE Robotics and Automation Letters 9(12), 11050–11057.** Publisher version, published 24 October; current-version date 31 October 2024. [DOI:10.1109/LRA.2024.3486178](https://doi.org/10.1109/LRA.2024.3486178), [author-hosted published PDF](https://amilearning.github.io/assets/pdf/ral2024.pdf), [verified author code](https://github.com/HMCL-UNIST/OpponentPredictionWithKMDKL). No arXiv version verified.

KM-DKL learns opponent-policy representations from interaction histories, predicts trajectory distributions, and incorporates them into MPC obstacle constraints. It includes physical 1/10-scale racing and an unseen cooperative-policy experiment assessed with negative log-likelihood (NLL). See especially §V-D of the [PDF](https://amilearning.github.io/assets/pdf/ral2024.pdf).

This is the strongest selected precedent for calibrated opponent prediction under policy shift. Trackshift should compare against a behavioral predictor of this kind, not only a basic HMM. Lower NLL does not alone establish nominal coverage, latent-state identifiability, or calibrated action selection. A defensible extension must test those distinct properties and the usefulness of abstention, rather than claim uncertainty calibration itself as new.

### 6. Interactive Multi-Modal Motion Planning With Branch Model Predictive Control

**Yuxiao Chen, Ugo Rosolia, Wyatt Ubellacker, Noel Csomay-Shanklin, Aaron D. Ames. 2022. Peer-reviewed, IEEE Robotics and Automation Letters 7(2), 5365–5372.** [DOI:10.1109/LRA.2022.3156648](https://doi.org/10.1109/LRA.2022.3156648), [Caltech record](https://authors.library.caltech.edu/records/g0rss-pzw90), **[arXiv:2109.05128v2](https://arxiv.org/abs/2109.05128v2), 18 September 2021**, [verified paper-linked code](https://github.com/chenyx09/belief-planning).

Branch MPC constructs scenarios from possible opponent feedback policies and optimizes a corresponding branching ego policy. CVaR adjusts the performance–robustness tradeoff. Evaluation includes vehicle overtaking/merging simulation and physical quadruped interaction. [Paper](https://arxiv.org/abs/2109.05128v2).

This is a close competitor to choosing actions robustly across harvest, derate, or traffic explanations. Branching, contingent plans, and risk-sensitive optimization are established ingredients. Trackshift's distinction would be how *observational ambiguity* defines and validates the candidate models, and how action disagreement or regret controls commitment. CVaR under an assumed probability model and worst-case regret across plausible models are different objectives; compare both explicitly.

### 7. Identifiability in inverse reinforcement learning

**Haoyang Cao, Samuel N. Cohen, Łukasz Szpruch. 2021. Peer-reviewed, NeurIPS 34.** [Official proceedings](https://proceedings.neurips.cc/paper_files/paper/2021/hash/671f0311e2754fcdd37f70a8550379bc-Abstract.html), **[arXiv:2106.03498v3](https://arxiv.org/abs/2106.03498v3), 8 November 2021**. Author code not verified.

The paper characterizes reward ambiguity under entropy-regularized decision models and conditions under which differing environments or discount factors identify rewards up to a constant. Observing behavior accurately does not automatically recover its underlying objective. [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2021/hash/671f0311e2754fcdd37f70a8550379bc-Abstract.html).

Use it to motivate observational equivalence and the value of varied conditions. Its theorems concern reward recovery, not F1 battery-state observability: do not present them as proving that SOC cannot be inferred. Trackshift must establish its own equivalence classes for physical state, power restrictions, policy, and traffic, under a specified sensor model and observation horizon. Structural non-identifiability and merely insufficient noisy data require different claims.

### 8. Safe Planning in Dynamic Environments Using Conformal Prediction

**Lars Lindemann, Matthew Cleaveland, Gihyun Shim, George J. Pappas. 2023. Peer-reviewed, IEEE Robotics and Automation Letters 8(8), 5116–5123.** [DOI:10.1109/LRA.2023.3292071](https://doi.org/10.1109/LRA.2023.3292071), **[arXiv:2210.10254v2](https://arxiv.org/abs/2210.10254v2), 8 June 2023**, [published author PDF](https://www.georgejpappas.org/wp-content/uploads/2023/08/Safe_Planning_in_Dynamic_Environments_Using_Conformal_Prediction.pdf). Author code not verified.

It combines trajectory forecasts, conformal prediction regions, and constrained MPC. Important qualifications are explicit: Assumption 1 excludes ego actions changing the other agents' trajectory distribution; Assumption 2 requires independently sampled trajectories from that distribution. The safety statements also have feasibility conditions. See §§II–IV of the [PDF](https://www.georgejpappas.org/wp-content/uploads/2023/08/Safe_Planning_in_Dynamic_Environments_Using_Conformal_Prediction.pdf).

Reactive racing directly challenges the first assumption. Thus “add conformal intervals and obtain safe overtaking” is not justified without a new analysis. Calibrate observable forecasts under the deployed interaction policy and evaluate intervention-induced shifts. Coverage of an observable trajectory does not automatically establish coverage of hidden energy state or correctness of an energy recommendation.

## Supporting sim-to-real reference: Dynamic Multi-Team Racing

Full title: **Dynamic Multi-Team Racing: Competitive Driving on 1/10-th Scale Vehicles via Learning in Simulation**.

**Peter Werner, Tim Seyde, Paul Drews, Thomas Matrai Balch, Igor Gilitschenski, Wilko Schwarting, Guy Rosman, Sertac Karaman, Daniela Rus. 2023. Peer-reviewed, CoRL; PMLR 229, 1667–1685.** [Official proceedings/version of record](https://proceedings.mlr.press/v229/werner23a.html), [author project](https://sites.google.com/view/dynmutr/home). Separate DOI/arXiv and author code not verified. The proceedings PDF exceeded the web reader's size limit and OpenReview required browser verification; this assessment uses the official abstract and project material.

The work combines model-based methods, parallel simulation, and self-play RL, with zero-shot transfer to physical multi-agent racing. [Proceedings](https://proceedings.mlr.press/v229/werner23a.html).

It sets an appropriate evidentiary reference for claims about racing transfer: a simulator result alone is insufficient. Its scale-car evidence is not F1 hybrid-powertrain validation. Trackshift can instead make a bounded claim of robustness across independently specified simulators, observation conditions, and opponent families, with any physical transfer left unclaimed. The comparison should concern evaluation discipline, not incompatible lap-time numbers.

## What the proposal can credibly claim

The following are proposed investigations, not established results or verified global firsts.

**1. Establish decision-relevant physical ambiguity.** Define the observation stream precisely: sampling, timestamp error, available speed/gap channels, geometry, and missingness. Construct matched histories from an independent longitudinal/energy generator in which intentional conservation, SOC-limited deployment, thermal/power restrictions, and traffic produce observations within the same noise tolerance. Some mechanisms can coexist; avoid forcing “harvest / derate / traffic” into mutually exclusive labels unless the benchmark explicitly imposes that simplification.

Vary observation horizon and instrumentation to measure when ambiguity disappears. Use controlled interventions on latent causes rather than different HMM emission means to manufacture distinguishability. A useful result may be negative: certain labels are unrecoverable from the proposed public channels. The important follow-up is whether those unresolved states recommend the same energy action or opposing actions.

**2. Evaluate action value across the unresolved explanations.** Let C(h) contain plausible physical states, opponent policies, and uncertain model parameters given history h. For each action, evaluate its opportunity loss relative to the best feasible action under each member of C(h). Compare posterior expected value, MAP-state control, CVaR, and minimax regret using a common action space, constraints, and computational allowance. Branch planning already provides the relevant conceptual baseline; novelty must rest on the physical ambiguity construction and its validated consequences. [Branch MPC](https://arxiv.org/abs/2109.05128v2).

A policy need not abstain merely because state entropy is high: all plausible explanations might favor the same action. Conversely, a concentrated but misspecified posterior can still produce expensive mistakes. A useful commitment rule requires a favorable lower bound on improvement over a defined fallback across plausible explanations, including action-value estimation error. A regret guarantee would need both true-model inclusion and reliable value bounds; finite-sample Monte Carlo error bounds do not cover omitted physics.

**3. Calibrate what can actually be observed.** Without trusted rival latent labels, public data can assess future speed, gap, timing, and prediction-region coverage, but cannot independently certify harvest/derate classification. Reserve latent calibration claims for separately labeled simulator or instrumented data. Specify which evidence supports each claim. Predictive coverage, latent-state coverage, and selective decision risk are different quantities. The assumptions in the conformal MPC precedent make this distinction particularly consequential in reactive competition. [Lindemann et al.](https://arxiv.org/abs/2210.10254v2).

Fit thresholds on held-out episodes and freeze them before testing. Report coverage versus abstention, risk among accepted recommendations, fallback cost, and foregone profitable opportunities. Condition empirical diagnostics on traffic, braking/straight geometry, power limitation, and unseen opponent family; do not mistake aggregate coverage for guaranteed coverage within every subgroup. An always-abstaining method can appear reliable while being operationally useless.

## Minimum empirical package

Use an evaluator whose physical equations, parameter sampling, and latent labels are independent of the estimator's emission/transition implementation. A different random seed in the same self-generator is not independence. Keep estimator training, calibration episodes, policy selection, and final testing separate. Hold out whole tracks, races, opponent families, and physical parameter regimes; adjacent telemetry rows should not cross split boundaries.

The main agent's suspected circular validation and absent public latent labels should be written as audit questions until substantiated. Even a sound independent simulator establishes validity inside its tested model class, not validity for real rival SOC. Publish matched ambiguous examples, observation transformations, latent definitions, seeds, and failure cases so that the benchmark can be challenged.

Prioritize comparisons against: a no-opponent fallback; the supplied HMM-belief/DQN baseline; a strengthened HMM with the already-proposed correlation/context/adaptation extensions; a KM-DKL-style behavioral predictor using the same downstream decision rule; reactive multi-agent race RL; and Branch/CVaR control. Use an oracle with privileged simulator state to quantify the information gap. The optimizer and RL–MPC papers supply complementary references for control suboptimality. [Multi-agent F1](https://arxiv.org/abs/2602.23056v2), [RL–MPC](https://arxiv.org/abs/2604.00826v1), [optimization/RL benchmark](https://arxiv.org/abs/2512.21570v1).

Report paired decision regret, race-time or position outcomes, energy/constraint violations, accepted-decision risk, calibration error, and runtime with uncertainty across complete episodes. Ablate the generator mismatch, ambiguity retention, calibration, and fallback separately. In counterfactual rollouts, allow the opponent to respond to the changed ego action; replaying its recorded future unchanged answers a different question. Tune baselines comparably and report paired confidence intervals rather than only an average win rate.

**Recommended proposal wording:** “We investigate the identifiability of rival energy behavior from limited race observations and evaluate whether decisions robust across physically plausible explanations reduce regret. An independently specified physical benchmark separates inference-model fit from decision quality, while calibrated abstention measures when recommendations remain useful under ambiguity.” This remains contingent on results. Neither assembling existing components nor promising correlated emissions, adaptive opponents, or an MPC fallback is sufficient by itself for a publication claim.
