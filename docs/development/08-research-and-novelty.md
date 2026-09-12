# Research question, candidate novelties and publication path

## 1. What we are doing, and why

The product makes energy decisions under uncertain rival capability. The research focuses on a narrower issue: **when several physically plausible explanations fit the available telemetry, should the controller try harder to classify the hidden state, or make a decision that remains worthwhile across those explanations?**

Not every uncertainty matters equally. Two different latent states may recommend the same action; conversely, a small probability of strong defense may matter greatly when an attack is expensive. We propose measuring that distinction through action consequences rather than relying only on mode-classification accuracy.

This is a research hypothesis, not an established novelty claim. Combining many papers, adding four horizons, or using the word “AI” does not establish originality.

## 2. What is already established

| Ingredient | Closest references | What we may claim |
|---|---|---|
| Convex performance envelope and hierarchical control | P01, P02 | Adaptation to our declared model, not invention |
| Competitor-aware energy/game optimization | P03–P05, P08 | Prior foundations for interaction and continuation |
| HMM beliefs and hidden rival energy | P06 | Baseline and motivation for uncertainty handling |
| Joint RL, energy, tyres and pit strategy | P09–P11 | Direct competing architecture; not our novelty |
| Multi-race component/lifecycle planning | P12 | Prior art; a fourth horizon is not a new contribution |
| Strategic belief manipulation / feints | P13 | Existing concept; our test protocol may differ |
| Branching, risk-sensitive MPC and belief search | P14, P15 | Established algorithms; scenario enumeration must be named accurately |
| Thermal tyres and battery degradation models | P16–P19 | Existing physics; our parameters are not F1 calibration |
| Decision calibration / robust partial-observation planning | P20–P22 | Closest general-method prior art; no broad first claim |
| Contextual opponent prediction and identifiability | P23, P24 | Stronger comparators and limits on interpretation |

Bibliographic status and review depth are in [references](10-references.md). Some recent items are preprints; a proposed extension in a paper is not necessarily available implementation.

## 3. Candidate contribution N1: a physical ambiguity benchmark

**Proposed artifact:** paired or grouped simulated histories that are similar under a declared sparse observation process but differ in hidden response capability and the consequences of attacking.

**Why useful:** testing a classifier on observations generated from its own emission table mainly checks agreement with that table. A physically generated benchmark can reveal cases where excellent classification on simple synthetic data does not translate into good energy decisions.

**Construction:** on development configurations, search over initial energy, thermal restrictions, tyre/car parameters and rival policy to generate nearby observable histories. Fix the distance metric, matching tolerance, history horizon and permitted sensors. Retain the resulting generation procedure, not just hand-selected pairs. Test it on held-out physical regimes and rival families, including cases where informative new observations resolve ambiguity.

**Evidence needed:** similarity of histories, difference in feasible response or action value, matching success/failure rate, sensitivity to observation cadence/noise/history length, and predictive separation after intervention where available.

**Limit:** a finite set of near-matching examples does not prove global unobservability. Call it empirical ambiguity under the specified sensor/model regime.

## 4. Candidate contribution N2: resource-aware commitment under retained ambiguity

**Proposed method:** evaluate the improvement of a feasible alternative over the reference across retained explanations, including remaining-race value and action-value error. Commit only when the selected criterion justifies the downside and cost.

**Why useful:** the controller may not need to decide whether the rival is “harvesting” or “depleted” if the preferred energy strategy is unchanged across those hypotheses. This reduces reliance on unjustified precise latent labels.

**What could be new:** the race-specific definition of decision-relevant physical ambiguity, its interaction with reserve/thermal/tyre constraints and persistence, and a demonstrated performance–risk advantage in the benchmark. Minimax, CVaR, robust POMDPs and calibration-aware decision making are not new [P14, P20–P22].

**Required comparisons:** B2 posterior mean, matched CVaR/minimax regret, no-ambiguity/no-margin ablations, stronger observable opponent prediction and the same candidate library. Show that gain is not merely “always wait” or extra compute.

**Falsification:** the method misses too many opportunities, a well-calibrated posterior-mean planner performs equally well, results vanish with independent physics, or gains depend on a conveniently weak opponent.

### A restricted mathematical statement, not a new theorem claim

If the actual hypothesis is included in the retained set, the same continuation/comparator is used, and the estimated paired gain error is bounded by `epsilon` for every candidate that may be selected, then `min estimated_gain - epsilon > margin` implies modeled gain greater than that margin under the actual retained hypothesis.

This follows directly from the assumed bound. It does not establish that public data supply such a set or error guarantee. A selected-action guarantee needs simultaneous/selection-aware error control, not an uncorrected confidence interval for one preselected action. Realizing and validating these assumptions is the difficult work. Do not market the elementary inequality as the scientific novelty.

## 5. Candidate contribution N3: event-aware persistent capability inference

**Proposed extension:** separate fast state beliefs, contextual driver/car parameters and component identity evidence, with different update/reset rules.

**Why useful:** retaining yesterday's estimated SOC is wrong, but discarding all learned response context can waste useful evidence. Tyre replacement, battery replacement and changed driving conditions imply different reset scopes.

**Research burden:** outperform both a pooled prior and an ordinary persistent filter under held-out session/context shifts, sparse history and uncertain component identity. HMMs already retain a posterior [P06]; “we gave an HMM memory” is not a valid novelty claim. Use shrinkage and forgetting baselines, not just a deliberately reset-to-zero comparator.

Treat this as a supporting extension until experiments show a distinct contribution. Do not inflate the paper into three unrelated primary claims.

## 6. What is an extension rather than a central novelty

Battery temperature, nonlinear compound-aware tyre wear, lifecycle pricing and strategic feints make the scenario more relevant but are established ideas. Include them to model mechanisms that change action value, and ablate them. The fourth horizon must solve a declared problem before it is claimed as implemented. RL should earn its place through comparison, not be attached to every estimation task.

The primary paper can focus on N1 + N2, with N3 as an ablation/extension. That gives a coherent story: observation ambiguity → costly commitments → proposed decision rule → controlled evidence.

## 7. Research execution after the event

1. Complete a closest-work full-text/code audit, including P09/P10/P12/P13/P20–P23. Record inaccessible artifacts and exact adaptation differences.
2. Freeze the benchmark generator and information contract before comparing new methods.
3. Implement strong baselines with matched compute and separate tuning budgets.
4. Add an independently developed plant or independently calibrated parameter family; quantify remaining shared assumptions.
5. Expand evaluation by event/opponent family and predefine statistical analysis and effect sizes worth detecting.
6. Seek authorized expert review and, if possible, own-car signals/maps. Do not require privileged rival signals for deployment.
7. Release permitted code/configurations, synthetic data, environment lock and negative results.

Venue choice follows the actual contribution: controls, intelligent transportation, autonomous racing or applied ML may fit different evidence. No submission venue or acceptance is promised in this package.

## 8. Paper outline and claim ledger

Suggested working title: **Decision-Relevant Opponent Uncertainty for Resource-Constrained Racing Strategy**. This is a descriptive title, not a claim of priority.

Sections: problem/information contract; related work; physical ambiguity benchmark; constrained planner and commitment rule; implementation/complexity; baselines and experimental protocol; results; limitations and external validity.

| Proposed claim | Present status | Promote only after |
|---|---|---|
| Similar observable histories can imply different attack consequences | Hypothesis | Constructed, quantified and held-out physical examples |
| Retained ambiguity reduces costly commitments | Untested | Matched benchmark and trade-off curves |
| Persistence helps under context changes | Untested | Pooled/persistent/forgetting baselines and reset tests |
| Health/tyre coupling changes useful decisions | Mechanistic proposal | Paired scenarios and full-method ablations |
| Fixed-deadline decision support works | Engineering target | Measured cutoff enforcement and tail latency |
| The approach is publishably novel | Unestablished | Closest-work distinction plus substantive evidence |
| Haas would benefit operationally | Proposed fit | Authorized engineer/team validation |
