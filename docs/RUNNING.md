# Running GRID//OPS

Everything below runs locally, offline, on CPU. No API keys, no database, no
service. Times are for a laptop.

## 1. Set up

```sh
cd /Users/pratikrai/Development/synapse-trackshift2026
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 2. Test it

```sh
.venv/bin/python -m pytest
```

Expect `139+ passed, 1 xfailed`. The `xfail` is a documented genuine ambiguity,
not a suppressed failure. Add `-q` for less output, or `-k battery` to focus.

## 3. See one episode

```sh
.venv/bin/python -m gridops.cli run configs/scenario_synthetic.json \
    --controller ambiguity_aware --rival-policy conserving --seed 1 --show
```

You get a decision timeline: time, action family, status, gap, deployment power
and the machine-readable reason. Then a summary line. Swap `--controller` for
`reference`, `stationary`, `posterior_mean` or `convex` to compare, and
`--rival-policy` for `matching`, `aggressive`, `conserving`, `delayed`,
`ignoring`.

Without `--show` you get JSON, which is what a script or UI would consume.

## 4. Check the config

```sh
.venv/bin/python -m gridops.cli validate-config configs/scenario_synthetic.json
```

Validation refuses an incomplete manifest rather than guessing.

## 5. Run a batch and generate the numbers

```sh
# development split, 10 seeds, the main controllers
.venv/bin/python -m gridops.cli batch configs/scenario_synthetic.json --seeds 10 \
    --split development --controllers reference,stationary,posterior_mean,convex,m \
    --out artifacts/batch_results_dev.json

# held-out split: shifted physics, models calibrated on development
.venv/bin/python -m gridops.cli batch configs/scenario_synthetic.json --seeds 10 \
    --split test --controllers reference,stationary,posterior_mean,convex,m \
    --out artifacts/batch_results_test.json

# one-factor ablations
.venv/bin/python -m gridops.cli batch configs/scenario_synthetic.json --seeds 5 \
    --split development --out artifacts/batch_ablation.json

# pitch bundle: aggregate tables, claim ledger, split comparison
.venv/bin/python -m gridops.cli report artifacts/batch_results_dev.json \
    artifacts/batch_results_test.json artifacts/batch_ablation.json \
    --out artifacts/pitch_bundle.json --markdown artifacts/pitch_results.md
```

Each batch takes about 60 s for 10 seeds x 5 policies x 5 controllers.

## 6. Sweep a parameter

The contact margin is the one to understand:

```sh
for m in 0.0 0.15 0.25; do
  .venv/bin/python -m gridops.cli batch configs/scenario_synthetic.json --seeds 3 \
      --split test --controllers m --contact-margin $m --out /tmp/margin_$m.json
done
```

At `0.0` the held-out split produces contacts; at `0.15` it does not. That
sensitivity is a result, not a bug: the method operates near the contact
boundary.

## 7. What the outputs mean

| Field | Meaning |
|---|---|
| `median_final_gap_m` | rival progress minus ego progress. Lower is better; negative means the ego is ahead. |
| `ego_energy_spent_j` | usable electrical energy consumed over the episode. |
| `pass_events` | completed passes: clearance plus persistence, no contact, no track exit. |
| `catch_up_events` | order or gap improved without a completed pass. |
| `contacts` | modeled footprint overlaps. Must be zero for a result to be valid. |
| `completion_rate` | fraction of episodes that ran. Failures are retained, never dropped. |
| `paired gap delta` | per-seed difference against the reference baseline. |

## 8. Where things live

| Want | Look at |
|---|---|
| The pitch | `docs/PITCH.md` |
| The generated numbers | `artifacts/pitch_results.md`, `artifacts/pitch_bundle.json` |
| What is built and what is not | `HANDOFF.md` |
| Engineering detail | `gridops/README.md` |
| Submission checklist | `docs/SUBMISSION.md` |
| The spec | `docs/development/` |

## 9. A five-minute tour

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m gridops.cli run configs/scenario_synthetic.json --controller reference --rival-policy matching --seed 1 --show
.venv/bin/python -m gridops.cli run configs/scenario_synthetic.json --controller ambiguity_aware --rival-policy matching --seed 1 --show
.venv/bin/python -m gridops.cli run configs/scenario_synthetic.json --controller ambiguity_aware --rival-policy conserving --seed 1 --show
```

The first is the baseline that does nothing. The second shows the method
retaining against a rival it cannot beat. The third shows it committing and
closing against a rival it can.
