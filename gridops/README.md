# gridops — engine foundation

Headless, pure Python/NumPy. No arcade, no FastF1, no replay-app imports. The
documentation package (`docs/development/`) specifies the full system; this
directory is the first working slice of it.

## Commands

```sh
python -m gridops.cli validate-config configs/scenario_synthetic.json
python -m gridops.cli run configs/scenario_synthetic.json --controller ambiguity_aware
python -m gridops.cli run configs/scenario_synthetic.json --controller stationary --rival-policy conserving
python -m gridops.cli benchmark configs/scenario_synthetic.json --seed 1 --out artifacts/benchmark_seed1.json
python -m pytest
```

Use the venv at the repository root: `../.venv/bin/python`.

## Layout

| Module | Contents | Status |
|---|---|---|
| `contracts/` | units, provenance, state/params, records, `DecisionInput` | done, tested |
| `simulation/battery.py` | one-resistance electrothermal, signed accounting, saturation | done, tested |
| `simulation/plant.py` | longitudinal plant, grip envelope, corner cap, tracker | done, tested |
| `simulation/track.py` | fixed-path geometry, synthetic circuit | done |
| `simulation/rivals.py` | reactive policy families (stationary/matching/aggressive/conserving/delayed/ignoring) | done |
| `simulation/geometry.py` | world path, oriented footprints, SAT overlap, track containment, pass monitor | done, tested |
| `simulation/tyres.py` | compound thermal state + irreversible wear, grip map, set reset | done, tested |
| `decision/commitment.py` | pricing, reserve guard, no-progress guard, commitment ledger | done, tested |
| `decision/pomcp.py` | POMCP history-tree search over a generative model | done, tested |
| `decision/planning.py` | conditional convex deployment planner (CVXPY + Clarabel), DCP/residual/trust-region checks | done, tested |
| `decision/tactical.py` | cheap surrogate generative model for POMCP | calibration open |
| `decision/belief.py` | persistent particle belief, credible set, non-stationarity mixing | calibration open |
| `decision/hmm_belief.py` | compact four-mode HMM, forward filtering, stationary comparator | done, tested |
| `race_value/lap_map.py` | monotone terminal resource value, reserve band, finite-horizon value recursion | done, tested |
| `evaluation/controllers.py` | reference, stationary (B_stat), posterior-mean (B_mean), ambiguity-aware (M) | wired |
| `evaluation/runner.py` | deterministic episode, public-only `DecisionInput` | done, tested |
| `cli.py` | validate-config, run, benchmark | done |

## Test coverage

108 tests. Highlights:

- **Battery:** OCV/current-root identity, energy conservation derivative,
  current/voltage/SOC saturation, cooling, no post-hoc SOC clipping.
- **Plant:** action changes future state, deployment drains, recovery charges,
  coast-down, grip violation recorded in a tight corner.
- **Commitment:** terminal value monotone in energy; a futile attack has
  negative worst-case improvement; **ablation** shows that removing the
  terminal value reproduces battery-depleting attrition; reserve guard and
  no-progress guard tested; belief update bounds the number of attempts.
- **POMCP:** known-answer action choice, energy-retention preference,
  stochastic costs, wall-clock deadline, all actions visited, and a test that
  the history tree cannot branch on hidden state.
- **Leakage:** `DecisionInput` has no prohibited fields; future observations are
  invisible; mutating hidden rival state does not change the input.
- **Planner:** DCP verified, `optimal` status, primal residuals measured, power
  and trust-region bounds enforced, corner limit respected, terminal reserve
  floor held, scarce energy reduces deployment, infeasible targets reported.
- **Geometry:** world path generated from curvature, lateral offset
  perpendicular, footprint corners, SAT overlap and separation, track
  containment, and pass classification — contact and track exit can never be
  counted as a pass, clearance must persist, re-passes are counted separately.
- **Tyres:** wear never decreases, cooling recovers temperature but not wear,
  softer compounds wear faster, grip has a thermal optimum and is monotone in
  wear, a new set resets only tyre state, and the **R09 paired ablation** shows
  a worn set reduces pace and raises grip saturation.
- **HMM belief:** forward filtering concentrates on the explaining mode,
  ambiguity falls with consistent evidence, `update_on_outcome` does not
  double-count, the stationary configuration has an identity transition while
  the non-stationary one allows switching, and a poorly explained observation
  does not collapse the posterior.
- **Race value:** terminal reserve priced once at ``V_0``, value grows with laps
  remaining, out-of-domain queries flagged not extrapolated, deploy target
  respects the reserve floor and the per-lap cap, scarce energy does not deploy
  more than rich.
- **Risk criteria:** CVaR is more conservative than the mean and equals it at
  ``alpha=1``; minimax regret selects the action with the lowest worst regret.

## Conventions frozen at G0

- SI throughout. `p_k_dc_w` positive = deployment (discharge); current
  discharge-positive.
- `None` means unknown, never zero.
- Provenance vocabulary on every external value.
- The controller receives only `DecisionInput`. The plant is never passed to a
  controller object.
- `gridops` must import and run with `arcade` and `fastf1` absent.

## Claim boundary

The synthetic circuit, vehicle, battery and tyre parameters are declared
assumptions, not identified F1 calibration. Results are comparative statements
about this model, not real-race gains. `run_mode` labels replay,
counterfactual and simulation separately. No completed-pass claim is made until
the geometric passing model exists; the current runner reports catch-up only.
