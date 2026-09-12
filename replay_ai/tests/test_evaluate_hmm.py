import json

from scripts.evaluate_hmm import evaluate
from scripts.fit_hmm_emissions import fit
from scripts.generate_synthetic_training import generate


def _write_dataset(tmp_path, events=8, samples=60, seed=5):
    dataset = tmp_path / "data.jsonl"
    rows = list(generate(events, samples, seed))
    dataset.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    return dataset, rows


def test_calibrated_hmm_evaluation_reports_confusion(tmp_path):
    dataset, rows = _write_dataset(tmp_path)
    artifact = tmp_path / "artifact.json"
    means, sigma, counts = fit(dataset)
    artifact.write_text(json.dumps({"means": means, "sigma": sigma, "counts": counts}))
    report = evaluate(dataset, artifact)
    assert report["samples"] == len(rows)
    assert 0.0 <= report["accuracy"] <= 1.0
    assert set(report["confusion"]) <= {"H", "M", "Lharvest", "Lderate"}


def test_fitted_scale_beats_uncalibrated_sigma(tmp_path):
    """A single scalar sigma leaves the likelihood flat; fitted scales must win.

    This guards the fix for the flat-likelihood defect: with ``sigma=1.0`` every
    feature error is ~0.01-0.3, so all 40 states score within a few percent of
    each other and the filter just re-predicts its prior.
    """
    dataset, _ = _write_dataset(tmp_path, events=10, samples=60, seed=3)
    means, sigma, counts = fit(dataset)
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps({"means": means, "sigma": sigma, "counts": counts}))
    calibrated = evaluate(dataset, artifact)["accuracy"]
    uncalibrated = evaluate(dataset, None)["accuracy"]
    assert calibrated > uncalibrated
    # The critical pair is the decision that matters: trap vs genuine attack.
    assert evaluate(dataset, artifact)["harvest_vs_derate_accuracy"] > 0.8


def test_fit_returns_pooled_per_feature_scale(tmp_path):
    dataset, _ = _write_dataset(tmp_path)
    means, sigma, counts = fit(dataset)
    assert set(sigma) == {"dgap", "throttle_clip", "brake_delta"}
    assert all(value > 0.0 for value in sigma.values())
    # Metadata must not leak into the emission means the filter consumes.
    for values in means.values():
        assert set(values) == {"dgap", "throttle_clip", "brake_delta"}
    assert sum(counts.values()) == 8 * 60
