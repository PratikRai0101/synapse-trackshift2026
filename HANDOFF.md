# GRID//OPS — build handoff

Status as of Sat 12 Sep 2026, first build session. The specification package is
in `docs/development/`. The engine foundation is in `gridops/`. The replay
application is a **separate product and separate repository**; it is not
imported here.

## What is built and passing

62 tests, `python -m pytest`. See `gridops/README.md` for the module table.

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
  `convex` controller.
- Deterministic episode runner and a public-only decision input.
- Leakage gate: hidden rival state and future samples cannot reach the controller.
- CLI: `validate-config`, `run`, `benchmark`.

## First benchmark (synthetic, seed 1)

`python -m gridops.cli benchmark configs/scenario_synthetic.json --seed 1`

| controller | matching spent J | conserving spent J | passes (conserving) |
|---|---:|---:|---:|
| reference | 125 023 | 125 023 | 0 |
| stationary (B_stat) | 2 087 581 | 678 013 | 2 |
| posterior_mean (B_mean) | 1 987 540 | 577 758 | 1 |
| convex (planner only) | 1 416 304 | 1 416 304 | 0 |
| ambiguity_aware (M, fixed powers) | 425 699 | 425 699 | 1 |
| ambiguity_aware_convex (M, planner-realized) | 352 733 | 352 733 | 0 |

The intended result is visible: the base-paper stationary planner over-commits
(burns ~2 MJ against a defending rival for no pass), the guarded fixed-power M
spends ~5× less and passes the weak rival, and the planner-realized variant is
more frugal still. Treat this as a smoke test, not a result — one seed, one
synthetic circuit, no uncertainty intervals.

## Known limitations (do not hide these)

1. **Belief calibration is not converged.** `decision/belief.py` updates
   correctly in isolation, but the surrogate closure scale in
   `decision/tactical.py` does not match the plant's observed closure, so the
   controller's action distribution is currently dominated by the fixed probe
   schedule (constant 425 699 J across rival policies). The information is not
   yet changing the policy. This is the single most important open item.
2. **Pass claims are catch-up only.** No footprint/containment/persistence
   geometry model exists yet. The runner counts order changes, not completed
   passes.
3. **The surrogate is not validated against the plant.** POMCP ranks candidates
   on the surrogate; the nonlinear plant executes them. Model mismatch is not
   yet measured or reported per decision.
4. **Tyres and thermal state are absent from the plant.** The battery thermal
   state exists; tyre compound/thermal/wear does not.
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

## Next slices, by owner

**Developer A (simulation/control)**
1. Calibrate the family-to-planner mapping: for ATTACK, target rival pace plus a
   margin (or add a declared gap term), so a committed attack closes. Record the
   planner's predicted profile beside the plant's realized trajectory.
2. Add the geometric passing model: kinematic bicycle, footprints, track
   containment, separation and persistence. Until then, every output stays
   catch-up only.
3. Add tyre thermal/wear state to the plant and expose it as a grip modifier.
4. Cache candidate profiles per valid state to keep planner cost outside the
   rollout loop; benchmark cold vs warm solve time.

**Developer B (evidence/evaluation)**
1. **Calibrate the belief likelihood.** Either fit `_CLOSE_*` to plant
   closures or replace the rank update with a likelihood calibrated on paired
   surrogate/plant rollouts. Acceptance: against a conserving rival the
   credible set becomes weak-dominated and M commits `attack_now`; against a
   matching rival it retains. This is the G3 gate.
2. Wire the replay repository's FastF1 cache into an `adapters/` module that
   emits provenance-labelled observation frames with `available_at`. Replay is
   Phase 1 only; it cannot test reactivity.
3. Expand `benchmark` to multiple seeds with paired initial conditions and
   report failures, uncertainty intervals and missed opportunities.
4. Add the ablation matrix from the spec: full M, minus continuation value,
   minus worst-case margin, minus belief update, minus probe.

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
