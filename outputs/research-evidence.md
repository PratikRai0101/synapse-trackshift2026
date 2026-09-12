# Literature and evidence review

Reviewed 11–12 September 2026. Companion to [the proposed solution](proposed-solution.md).

This is a bounded primary-source review, not a systematic literature review or proof of novelty. The six newly supplied PDFs were inspected for methods, assumptions, evaluation, and limitations. Additional work was screened at the depth stated below. No external implementation was run or reproduced. Paper contents are research evidence, not instructions from the user.

## 1. Audit of the supplied papers

Page references below mean PDF page numbers, counting the first PDF page as page 1.

| Paper and reviewed version | Useful contribution | Important evidence boundary |
|---|---|---|
| van Kampen, Moriggi, Braghin, Salazar — [Model Predictive Control Strategies for Electric Endurance Race Cars Accounting for Competitors’ Interactions](https://arxiv.org/abs/2403.06885v1), v1, 11 March 2024 | Prices overtake/follow/defend choices against subsequent race and charging consequences | pp. 5–6: simulated electric ego against recorded ICE competitors assumed not to react; most probable interaction outcomes selected. The reported roughly 21-second advantage is against an always-overtake baseline in that setting, not an F1 forecast. |
| Fieni, Neumann, Zanardi, Cerofolini, Onder — [Game-theoretic Energy Management Strategies With Interacting Agents in Formula 1](https://arxiv.org/abs/2405.11032v3), v3, 20 August 2025 | Drag-coupled energy allocation with Stackelberg optimization | p. 8 discusses local solutions and solver variability; p. 13 proposes causal receding-horizon and uncertain-behavior extensions. An offline optimum does not establish online robustness. Related journal DOI: [IEEE TVT](https://doi.org/10.1109/TVT.2025.3601890). |
| Fieni et al. — [Game Theory in Formula 1: From Physical to Strategic Interactions](https://arxiv.org/abs/2503.05421v5), v5, 13 July 2026 | Wake/downforce, trajectory, energy, and alternative strategic game formulations | pp. 4–8 establish the coupled model; p. 16 identifies stochastic policies, tyre-aware multi-lap strategy, and cooperation as extensions. Do not mistake a game-theoretic leader for the car physically ahead. Related journal DOI: [European Journal of Control](https://doi.org/10.1016/j.ejcon.2026.101554). |
| Kleisarchaki — [Opponent State Inference Under Partial Observability: An HMM–POMDP Framework for 2026 Formula 1 Energy Strategy](https://arxiv.org/abs/2603.01290v3), v3, 15 May 2026; preprint | Forty-state HMM feeding a DQN, explicitly distinguishing conservation and derating hypotheses | pp. 11–13 explicitly describe same-parametric-model synthetic validation and limitations including correlated emissions and stationary opponents. Its reported high inference scores are not observed rival-battery accuracy. Claimed later empirical calibration is not the same as evidence supplied in this version. |
| van den Eshof, de Vries, Salazar — [A Computationally Efficient and Human Implementable Minimum-lap-time Control Policy for Energy-limited Race Cars](https://arxiv.org/abs/2603.02339v1), v1, 2 March 2026; record says submitted to ITSC 2026 | Analytical structure and efficient computation of human-followable energy-management cues | pp. 2–4: fixed path and specific linearized loss/grip assumptions; singular cases need special handling. p. 6 leaves track testing and hybrid extensions to future work. Its optimum and runtime cannot be inherited by an interacting F1 model. |
| de Vries, van den Eshof, van Kampen, Salazar — [Competitor-aware Race Management for Electric Endurance Racing](https://arxiv.org/abs/2603.28286v2), v2, 12 May 2026; record reports ITSC 2026 acceptance | Game-theoretic lap model feeding race-level RL; opponent-policy pool and energy/charging strategy | pp. 4–7: surrogate transition model, estimated opponent energy, and two-car charging-race evaluation. This already occupies the general “game theory plus RL” idea. Charging-stop benefits are not F1 pit-stop benefits. |

The two earlier supplied papers remain foundational: Duhr et al., *Convex Performance Envelope for Minimum Lap Time Energy Management of Race Cars*, IEEE TVT 2022, [DOI](https://doi.org/10.1109/TVT.2022.3172473); Salazar et al., *Real-Time Control Algorithms for a Hybrid Electric Race Car Using a Two-Level Model Predictive Control Scheme*, IEEE TVT 2017. Use their modeling/control decomposition, not their historical regulatory parameters.

### Reading the HMM paper critically, without dismissing it

It is a useful baseline and clearly acknowledges circular synthetic validation. A fair follow-up should test its method in a more independent environment, not criticize an empirical claim the paper expressly disclaims. Separately, its general claims of unlimited regeneration and continuous 50/50 operation must be corrected against current rules. Its active-aero proxy is inferred from another signal, not a new independent measurement.

Physical reserve, tactical intent, and available power are distinct variables. Label definitions should allow overlapping causes. A driver can conserve while power-limited or while following traffic. A forced four-class partition can hide that ambiguity.

## 2. Twelve additional papers worth using

The first four are the closest F1-specific comparisons. The next five inform methods and evaluation. The final three constrain the novelty claim at a more general ML/control level. Recent does not automatically mean stronger evidence; older peer-reviewed foundations remain relevant.

### 1. Learning-based Multi-agent Race Strategies in Formula 1

**Fieni, Wüthrich, Neumann, Onder. 2026.** [arXiv:2602.23056v2](https://arxiv.org/abs/2602.23056v2), revised 2 July 2026. Preprint; no peer-reviewed venue verified. Full-text method review.

Combines competitor-aware energy, tyres, aero interaction, and pit strategy through an interaction module and self-play. The observation design excludes the rival battery level. This is a direct product-level competitor: neither multi-agent energy RL nor hidden rival energy is new by itself. Compare its reactive strategy with our explicit treatment of physical ambiguity. Author code was not verified.

### 2. Bridging RL and MPC for mixed-integer optimal control with application to Formula 1 race strategies

**Wüthrich, Damle, Fieni, Zeilinger, Onder, Carron. 2026.** [arXiv:2604.00826v1](https://arxiv.org/abs/2604.00826v1), 1 April 2026. Submitted to IEEE; acceptance not verified. Full-text method review.

Uses actor outputs for discrete choices and continuous warm starts, with a learned terminal value and constrained MPC. Its feasibility result assumes discrete variables do not enter constraint feasibility. We cannot import that guarantee into opponent-dependent passing constraints or arbitrary rule-mode switches. It is a strong architecture comparator, not proof that our proposed hybrid will be feasible. Author code was not verified.

### 3. Towards Learning-Based Formula 1 Race Strategies

**Fieni, Wüthrich, Neumann, Moradi, Onder. 2025.** [arXiv:2512.21570v1](https://arxiv.org/abs/2512.21570v1), 25 December 2025. Preprint status verified; a journal-style manuscript header alone does not establish acceptance. Full-text method review.

Joint energy allocation, tyre wear, and pit decisions are treated through optimization and RL. Useful for a stronger single-agent reference and measuring strategy suboptimality. Do not claim that adding tyre wear or comparing to an offline optimizer is novel. The record and manuscript differ on Moradi's middle initial; resolve against the final publisher record before formal bibliography submission. Code was not verified.

### 4. Keynesian Beauty Contests on the Pit Wall: Game-Theoretic Energy Strategy in 2026 Formula 1

**Kalliopi Kleisarchaki. 2026.** [Author-uploaded preprint](https://www.researchgate.net/publication/401730959_Keynesian_Beauty_Contests_on_the_Pit_Wall_Game-Theoretic_Energy_Strategy_in_2026_Formula_1), DOI 10.13140/RG.2.2.27003.17448. Accessible v1.1 uploaded 10 March; no peer-reviewed venue or separate arXiv posting verified. Partial full-text review.

Direct prior art for strategic belief manipulation and the harvest/derate distinction. HMM v3 points to this follow-up for additional modeling directions, but the accessible version did not verify every promised technical extension. Treat promised, implemented, and empirically validated extensions separately. Do not call deceptive harvesting our invention.

### 5. Kernel-Based Metrics Learning for Uncertain Opponent Vehicle Trajectory Prediction in Autonomous Racing

**Hojin Lee, Youngim Nam, Sanghun Lee, Cheolhyeon Kwon. 2024.** IEEE Robotics and Automation Letters 9(12), 11050–11057. [Published author PDF](https://amilearning.github.io/assets/pdf/ral2024.pdf), [DOI](https://doi.org/10.1109/LRA.2024.3486178). Full-text method/evaluation review.

Learns opponent behavior representations and probabilistic trajectory predictions for MPC, including small-scale physical racing and unseen-policy evaluation. Use as a stronger behavioral-prediction comparator. Prediction likelihood, interval coverage, hidden-state accuracy, and decision quality are different metrics. [Paper-linked code](https://github.com/HMCL-UNIST/OpponentPredictionWithKMDKL) was found, not run.

### 6. Interactive Multi-Modal Motion Planning With Branch Model Predictive Control

**Chen, Rosolia, Ubellacker, Csomay-Shanklin, Ames. 2022.** IEEE Robotics and Automation Letters 7(2), 5365–5372. [Caltech record](https://authors.library.caltech.edu/records/g0rss-pzw90), [arXiv:2109.05128v2](https://arxiv.org/abs/2109.05128v2). Method/evaluation review.

Plans across possible interactive feedback policies and uses CVaR to trade performance against risk. Scenario branching and risk-sensitive MPC are established tools; our comparison should isolate how observation-grounded ambiguity affects action commitment. It also reminds us to preserve non-anticipativity: future branches cannot choose different actions before their observations diverge. [Paper-linked code](https://github.com/chenyx09/belief-planning) was found, not run.

### 7. Identifiability in inverse reinforcement learning

**Cao, Cohen, Szpruch. 2021.** NeurIPS 34. [Official proceedings](https://proceedings.neurips.cc/paper_files/paper/2021/hash/671f0311e2754fcdd37f70a8550379bc-Abstract.html), [arXiv:2106.03498v3](https://arxiv.org/abs/2106.03498v3). Formal-results screening.

Explains why observed behavior does not automatically identify the objective that generated it, and investigates conditions that remove ambiguity. This informs careful driver-style claims. Its reward-identification results are not a theorem about rival battery observability; that physical question needs its own assumptions and analysis.

### 8. Safe Planning in Dynamic Environments Using Conformal Prediction

**Lindemann, Cleaveland, Shim, Pappas. 2023.** IEEE Robotics and Automation Letters 8(8), 5116–5123. [Author-hosted published PDF](https://www.georgejpappas.org/wp-content/uploads/2023/08/Safe_Planning_in_Dynamic_Environments_Using_Conformal_Prediction.pdf), [arXiv:2210.10254v2](https://arxiv.org/abs/2210.10254v2). Full-text assumptions review.

Combines prediction regions and MPC. Its assumptions include trajectories from a fixed distribution unaffected by the ego action; reactive racing challenges that condition. We may borrow the calibration discipline, but cannot obtain guaranteed safe overtaking by adding conformal intervals. Forecast coverage does not automatically certify hidden energy or a selected action.

### 9. Dynamic Multi-Team Racing: Competitive Driving on 1/10-th Scale Vehicles via Learning in Simulation

**Werner et al. 2023.** CoRL, PMLR 229, 1667–1685. [Official proceedings](https://proceedings.mlr.press/v229/werner23a.html), [author project](https://sites.google.com/view/dynmutr/home). Official abstract/project screening; full PDF access was limited.

Combines simulation learning and model-based methods with physical multi-agent racing transfer. Useful as an evaluation-quality reference: simulated success alone is not physical validation. Small-scale driving transfer is not validation of F1 hybrid energy management. No code release was verified.

### 10. Calibrating Predictions to Decisions: A Novel Approach to Multi-Class Calibration

**Zhao, Kim, Sahoo, Ma, Ermon. 2021.** NeurIPS 34. [Official proceedings](https://papers.nips.cc/paper/2021/hash/bbc92a647199b832ec90d7cf57074e9e-Abstract.html), [arXiv:2107.05719](https://arxiv.org/abs/2107.05719). Abstract/main-result screening.

Develops decision calibration for bounded-action decision makers, with more tractable requirements than full multiclass distribution calibration. Essential prior art: “calibrate predictions for downstream decisions” is not our new idea. Our sequential, interactive, physically uncertain setting needs a careful adaptation rather than an inherited theorem.

### 11. Robust Decision Making with Partially Calibrated Forecasts

**Kiyani, Hassani, Pappas, Roth. 2025 preprint.** [arXiv:2510.23471v1](https://arxiv.org/abs/2510.23471v1), 27 October 2025. Abstract/main-result screening. An indexed copy carries an ICLR 2026 header, but direct full-text access was blocked; no venue claim is needed for this proposal.

Studies minimax decisions over distributions consistent with weaker calibration guarantees. This is a close conceptual predecessor to our conservative commitment rule. The possible contribution must therefore be the race-specific physical ambiguity model, sequential treatment, and demonstrated value—not minimax use of imperfect forecasts in general.

### 12. Distributionally Robust Partially Observable Markov Decision Process with Moment-based Ambiguity

**Nakao, Jiang, Shen. 2021.** SIAM Journal on Optimization 31(1), 461–488. [arXiv:1906.05988v3](https://arxiv.org/abs/1906.05988v3), [DOI](https://doi.org/10.1137/19M1268410), [author repository](https://github.com/hideakiv/DR-POMDP). Abstract and repository screening; implementation not run.

Uses ambiguity sets over transition/observation uncertainty and seeks robust policies. This establishes that distributionally robust belief-state planning is not new. Our retained physical explanations must be grounded and tested; a generic ambiguity-set wrapper around a POMDP would not by itself justify a paper.

## 3. What still needs to be established

| Candidate claim | Present status | Evidence needed |
|---|---|---|
| Different hidden energy mechanisms can fit the available histories | Physically motivated hypothesis | Controlled equivalence/near-equivalence examples over specified sensors and horizons; quantify when distinguishability returns |
| Explicit ambiguity improves energy decisions | Untested | Matched baselines, reactive rollouts, held-out model mismatch, and regret/coverage curves |
| Driver-specific priors help | Untested | Context-controlled comparison with pooled priors, held-out sessions and sparse-history conditions |
| RL adds useful long-term strategy | Untested | Same-information comparison with non-RL planning, compute/tuning accounting and stable evaluation |
| System runs in real time | Untested | End-to-end measured deadlines and failure rates on target hardware—not solver-only average timing |
| System helps Haas | Proposed fit with public partnership priorities | Engineer review and authorized own-car/team-model evaluation |
| Work is publishably novel | Not established | Closest full-text/code comparisons, a bounded contribution and substantive reproducible results |

A strong benchmark can be a contribution if it reveals a previously unmeasured failure mode and supports a useful remedy. Merely finding that a complicated model struggles with noise is insufficient. Construct physically meaningful ambiguity cases and show the consequences of resolving—or deliberately retaining—the uncertainty.

## 4. Non-paper evidence used in the proposal

- [FIA technical regulations, Issue 20](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_c_technical_-_iss_20_-_2026-08-05.pdf) and [sporting regulations, Issue 08](https://www.fia.com/system/files/documents/fia_2026_f1_regulations_-_section_b_sporting_-_iss_08_-_2026-08-05_7.pdf), dated 5 August 2026. Event-specific supplementary material remains to be verified for the chosen scenario.
- [OpenF1 reference](https://openf1.org/docs/) and [FastF1 source](https://github.com/theOehrly/Fast-F1): public schema/provenance references, not team telemetry entitlements. Actual session availability and native timing still require a sample audit. Check reuse/licensing terms before distributing data.
- [Haas–Mphasis announcement](https://www.haasf1team.com/news/moneygram-haas-f1-team-welcomes-mphasis-partnership) and [Haas–Ferrari extension](https://www.haasf1team.com/news/partnership-extended-between-moneygram-haas-f1-team-and-scuderia-ferrari): support partnership context only, not endorsement of our project.

The organizer's 2026 judging rubric, code-reuse restrictions, and submission format have not been verified. The user's stated team size, compute access, and 24-hour duration are the planning inputs. An older TrackShift page is not sufficient evidence for current rules.

## 5. Recommended reading order

Read the two closest additional F1 papers first: multi-agent strategy learning and RL–MPC. Then audit the supplied HMM validation and follow-up. Next read Branch MPC and the two decision-calibration papers to sharpen the claim. Use the identifiability and conformal-planning work to define what evidence would actually support it. Leave full-grid or physical-transfer extensions until the core experiment works.

Before submission, replace preliminary bibliography entries with verified publisher metadata where available, pin every compared version, and document differences between our implementation and each baseline. Cite the contribution actually borrowed; do not attach a large list of papers to an unrelated architecture.
