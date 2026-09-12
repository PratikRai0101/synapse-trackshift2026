# GRID//OPS — build handoff

Status as of Sat 12 Sep 2026, first build session. The specification package is
in `docs/development/`. The engine foundation is in `gridops/`. The replay
application is a **separate product and separate repository**; it is not
imported here.

## What is built and passing

121 passing, 1 xfailed (`python -m pytest`). See `gridops/README.md` for the module table.

Working and verified:

- SI contracts, provenance, physical state, `DecisionInput`, recommendation record.
- Battery one-resistance model with signed accounting and an energy-conservation
  identity; saturation reasons recorded, never silent SOC clipping.
- Longitudinal plant with a combined grip envelope and cornering-speed cap.
  A feasible action changes future motion and battery state.
- **POMCP** history-tree search over a generative model, with particle
  reinvigoration, wall-clock deadline and a test that the tree cannot branch on
  hidden state.
- **Commitment machinery** — monotone terminal resource value, worst-case
  paired improvement, commitment margin, hard reserve floor, no-progress guard
  and a finite expiring commitment ledger.
- **The anti-attrition ablation**: removing the terminal resource value
  reproduces the exact failure the user asked about — repeated futile attacks
  deplete the battery to bankruptcy; with pricing the controlled run preserves
  the reserve, and the outcome-based belief update bounds the number of attempts.
- Persistent particle belief with credible-set selection and non-stationary mixing.
- **Conditional convex deployment planner** (`decision/planning.py`): CVXPY +
  Clarabel second-order-cone subproblem over a spatial grid, frozen local
  coefficients, trust region, measured primal residuals, DCP check, and an
  infeasible-target path that is reported rather than hidden. Wired as the
  `convex` controller and optionally inside M.
- **Geometric passing model** (`simulation/geometry.py`): world path generated
  from track curvature, oriented rectangular footprints, SAT overlap, track
  containment, and a pass monitor requiring clearance margin plus persistence
  with no contact or track exit. Order changes without those are `catch_up`.
  The model immediately reclassified every earlier "pass" as a contact.
- **Tyre compound thermal and wear model** (`simulation/tyres.py`): per-axle
  effective temperature and non-decreasing wear proxy, compound families, a
  bounded grip map with a thermal optimum and monotone wear penalty, and a set
  reset that touches only tyre state. Coupled into the plant's grip envelope.
  The **R09 paired ablation** shows wear 0 → 0.9 grows the gap 69 → 105 m and
  grip saturations 83 → 162.
- **Remaining-race value recursion** (`race_value/lap_map.py`): finite-horizon
  DP over usable energy, ``V_l(E)`` with the terminal reserve priced once at
  ``V_0``, interpolated between grid points, out-of-domain queries flagged.
- **Risk criteria** (`decision/commitment.py`): CVaR of paired improvement and
  minimax regret, completing the B3 comparator set alongside the worst-case
  commitment rule.
- **HMM belief backend** (`decision/hmm_belief.py`): a compact four-mode HMM
  with forward filtering, a transition matrix encoding non-stationarity, and a
  `stationary=True` configuration that reproduces the base-paper fixed-regime
  assumption. Exposes the same surface as the particle belief, so M can run on
  either backend and the two are directly comparable (`ambiguity_aware` vs
  `ambiguity_aware_hmm` vs `ambiguity_aware_hmm_stationary`).
- **Frozen paired batch and ablation matrix** (`evaluation/batch.py`): seeded
  controllers x rival policies x seeds, paired on initial conditions, failures
  recorded rather than dropped, completion rates beside every metric, per-seed
  paired deltas against a baseline, and one-factor ablation variants (no
  continuation value, no commitment margin, no belief update, no probe,
  posterior-mean criterion). CLI: `python -m gridops.cli batch <config>`.
- Deterministic episode runner and a public-only decision input.
- Leakage gate: hidden rival state and future samples cannot reach the controller.
- CLI: `validate-config`, `run`, `benchmark`.

## First benchmark (synthetic, seed 1)

`python -m gridops.cli benchmark configs/scenario_synthetic.json --seed 1`

| controller | matching spent J | conserving spent J | contacts (conserving) | verdict |
|---|---:|---:|---:|---|
| reference | 125 023 | 125 023 | 0 | no attack |
| stationary (B_stat) | 2 087 581 | 678 013 | 414 | over-commits, drives through |
| posterior_mean (B_mean) | 1 987 540 | 828 978 | 373 | over-commits, drives through |
| convex (planner only) | 1 416 304 | 1 416 304 | 463 | drives through |
| ambiguity_aware (M, fixed powers) | 425 699 | 425 699 | **0** | catch-up, clean |
| ambiguity_aware_convex (M, planner-realized) | 352 733 | 352 733 | **0** | catch-up, clean |

With the geometry and tyre models active the picture is: every baseline that
actually engages spends 0.7–2.1 MJ and incurs 370–460 contact frames (it drives
through the rival), while M spends ~0.4 MJ, incurs zero contacts and reaches
catch-up. One seed, one synthetic circuit — a smoke test, not a result.

## Ablation batch (3 seeds, 5 rival policies, development split)

`python -m gridops.cli batch configs/scenario_synthetic.json --seeds 3`

| controller | median gap m | mean energy J | passes | contacts | median paired Δgap m |
|---|---:|---:|---:|---:|---:|
| reference | 47.86 | 125 023 | 0 | 0 | 0.00 |
| **M (full)** | **−1.39** | 1 585 979 | 1 | **1 086** | **−51.70** |
| M − continuation value | −6.88 | 1 635 744 | 6 | 1 206 | −54.75 |
| M − commitment margin | −2.35 | 1 683 679 | 0 | 4 272 | −49.60 |
| M − belief update | −3.33 | 1 518 617 | 0 | 1 386 | −50.43 |
| M − probe | −1.60 | 1 573 756 | 0 | 4 125 | −49.46 |
| M posterior-mean criterion | −1.39 | 1 584 696 | 1 | 1 086 | −48.81 |

Read this honestly:

- M beats the reference on position by ~52 m of median paired gap. Real for this
  synthetic model, and the headline.
- **M incurs ~1 086 modeled contacts**, about 14% of episode time overlapping the
  rival. The geometry layer reports them correctly; the lateral policy does not
  prevent them. **This is now the most important engineering defect and it must
  not be hidden.** A position gain obtained by driving through the rival is not a
  valid result.
- Removing the continuation value improves position (−54.75 m) but spends and
  contacts more: the safety/attrition trade-off the ablation was built to expose.
- Removing the commitment margin is worst by contacts (4 272), as the
  anti-attrition design predicts.

## Known limitations (do not hide these)

1. **Belief calibration is improved; one genuine ambiguity remains.** The
   original confound is fixed: the belief no longer updates on gap closure
   (which accumulates the ego's own advantage) but on the rival's public speed
   response, gated to sections where the circuit is not masking the policy, and
   the tactical closure is now measured over the 3 s planning horizon so a
   first-second acceleration transient cannot pose as a durable gain. Result:
   against a conserving rival the belief reads weak (strong-rival mass 0.00) and
   the controller commits, closes and holds position better than the reference
   (test passes). The remaining `xfail` is a **genuine ambiguity**: once a
   matching rival is far enough ahead it stops defending, so its response looks
   conserving and the controller commits. Distinguishing "stopped defending"
   from "conserving" needs traffic and context conditioning, which is the next
   step. Also open: the response signal is still only ~2.5 m/s, so more than one
   informative observation is needed before the posterior is decisive.
2. **Pass claims are now geometrically gated; only catch-up is reached at 25 s.**
   The geometry model exists and rejects contact/track-exit as passes. The
   guarded controller reaches catch-up within the 25 s benchmark and one clean
   pass at ~70 s. Lengthen the benchmark episode or raise the committed pace to
   get passes inside the default window.
3. **The surrogate is not validated against the plant.** POMCP ranks candidates
   on the surrogate; the nonlinear plant executes them. Model mismatch is not
   yet measured or reported per decision.
4. **Tyres are now in the plant; pit stops are not.** Compound thermal/wear
   affects grip and the R09 ablation passes. There is no pit-stop event that
   calls `reset_for_new_set`, and no compound choice optimisation.
5. **No public replay adapter.** The config produces synthetic observations;
   the replay repo would supply real ones.
6. **The planner realization is more frugal but does not yet close.**
   `AmbiguityAwareController` supports two realizations: fixed power
   (`ambiguity_aware`, validated, passes the weak rival) and convex profile
   (`ambiguity_aware_convex`, lower energy, no pass yet). The planner minimises
   time plus energy and has no position/gap term, and its lower trust bound is
   limited by available power (bounds tighter than ~4 m/s are infeasible from
   80 m/s). Fix by making ATTACK target the rival's pace plus a margin as a
   constraint, or adding a declared gap term to the objective. This is the next
   joint task.
7. **Model mismatch is not reported per decision.** The planner's predicted
   profile and the plant's realized trajectory are not yet compared in the
   episode record.

8. **Position gain is currently obtained through contact.** The ablation batch
   shows M beating the reference by ~52 m median paired gap, but with ~1 086
   modeled contact frames (~14% of episode time). The geometry layer is correct;
   the lateral policy and supervisor do not yet enforce separation. Until fixed,
   the position result is not a valid pass result. Fix: make modeled contact a
   hard infeasibility in the supervisor, not a post-hoc counter.

## Next slices, by owner

**Developer A (simulation/control)**
1. Calibrate the family-to-planner mapping so a committed attack closes; then
   record the planner's predicted profile beside the plant's realized
   trajectory per decision (model-mismatch reporting).
2. Wire a pit-stop event that calls `reset_for_new_set` and rebases the lap map.
3. Cache candidate profiles per valid state and benchmark cold vs warm solve
   time before the batch.
4. Unify the grip envelope: the plant uses a circular envelope, the planner an
   `rx/ry` ellipse.

**Developer B (evidence/evaluation)**
1. **Calibrate the belief likelihood.** Fit the surrogate closure means (or the
   HMM emission means) to paired surrogate/plant rollouts. Acceptance: against
   a conserving rival the credible set becomes weak-dominated and M commits
   `attack_now`; against a matching rival it retains. This is the G3 gate.
2. Wire the replay repository's FastF1 cache into an `adapters/` module that
   emits provenance-labelled observation frames with `available_at`. Replay is
   Phase 1 only; it cannot test reactivity.
3. Expand `benchmark` to multiple seeds with paired initial conditions and
   report failures, uncertainty intervals and missed opportunities.
4. Add the ablation matrix from the spec: full M, minus continuation value,
   minus worst-case margin, minus belief update, minus probe; and compare the
   particle and HMM backends under matched compute.

**Joint**
- Freeze the record schema version and commit a fixture episode as the
  integration seam.
- Decide whether the POMCP claim is carried or documented as not reached. If
  the search layer does not demonstrably beat B_mean under matched compute,
  label the delivery as bounded scenario planning and say so.

## Reproduction

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/python -m gridops.cli benchmark configs/scenario_synthetic.json --seed 1
```
