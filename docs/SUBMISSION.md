# Submission bundle

Status: checklist for the event. Nothing here depends on a service, a database,
or a paid API. Reproduce from a clean checkout with the commands below.

## Contents

| Item | Path |
|---|---|
| Engine source | `gridops/` |
| Dependency lock | `requirements.txt`, `pyproject.toml` |
| Scenario and ruleset | `configs/scenario_synthetic.json`, `gridops/contracts/ruleset.py` |
| Tests | `gridops/tests/` (135 passing, 1 xfailed) |
| Frozen batch results | `artifacts/batch_results.json`, `artifacts/batch_ablation.json` |
| Generated pitch bundle | `artifacts/pitch_bundle.json`, `artifacts/pitch_results.md` |
| Pitch | `docs/PITCH.md` |
| Specification | `docs/development/`, `CONTEXT.md` |
| Handoff and limitations | `HANDOFF.md` |

The replay application is a separate product in a separate repository and is not
an input to any claim here.

## Reproduce

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/python -m gridops.cli validate-config configs/scenario_synthetic.json
.venv/bin/python -m gridops.cli batch configs/scenario_synthetic.json --seeds 3 \
    --controllers reference,stationary,posterior_mean,convex,m \
    --out artifacts/batch_results.json
.venv/bin/python -m gridops.cli batch configs/scenario_synthetic.json --seeds 3 \
    --out artifacts/batch_ablation.json
.venv/bin/python -m gridops.cli report artifacts/batch_results.json \
    artifacts/batch_ablation.json --out artifacts/pitch_bundle.json \
    --markdown artifacts/pitch_results.md
```

## What is included and honest

- All physical parameters are synthetic and labelled as such.
- Failures are retained in every aggregate; completion rates are reported.
- Two claims are marked `not met` in the generated ledger and are stated in the
  pitch: no clean pass at the default episode length, and no demonstrated
  advantage of POMCP over posterior-mean planning under matched compute.
- The one `xfail` test is a genuine ambiguity, with a written reason, not a
  suppressed failure.

## What is not claimed

- No real-race lap-time or points gain.
- No measured rival battery state.
- No FIA certification or technical compliance.
- No battery-life improvement.
- No public-data forecast relevance (no replay adapter implemented).

## Before submitting

- [ ] Regenerate `artifacts/pitch_bundle.json` from the final code revision.
- [ ] Record the code revision and dependency hashes in the bundle.
- [ ] Confirm no credentials or restricted data are committed.
- [ ] Rehearse the demo against the recorded traces.
- [ ] Keep a backup recording of the demo.
- [ ] Read the two `not met` claims aloud in the presentation.
