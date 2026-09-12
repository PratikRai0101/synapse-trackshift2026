import json

from scripts.evaluate_hmm import evaluate
from scripts.fit_hmm_emissions import fit
from scripts.generate_synthetic_training import generate


def test_calibrated_hmm_evaluation_reports_confusion(tmp_path):
    dataset = tmp_path / "data.jsonl"
    rows = list(generate(3, 30, 4))
    dataset.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps({"means": fit(dataset)}))
    report = evaluate(dataset, artifact)
    assert report["samples"] == len(rows)
    assert 0.0 <= report["accuracy"] <= 1.0
    assert set(report["confusion"]) <= {"H", "M", "Lharvest", "Lderate"}
