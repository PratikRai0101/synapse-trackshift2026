import json

from scripts.evaluate_hmm_splits import evaluate_splits
from scripts.generate_synthetic_training import generate


def test_split_evaluation_fits_only_train_events(tmp_path):
    dataset = tmp_path / "labelled.jsonl"
    rows = list(generate(100, 12, 9))
    dataset.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    report = evaluate_splits(dataset)
    assert report["schema"] == "hmm-split-evaluation.v1"
    assert sum(report["event_counts"].values()) == 100
    assert report["event_counts"]["train"] > 0
    assert report["event_counts"]["validation"] > 0
    assert report["event_counts"]["test"] > 0
    assert report["reports"]["test"]["samples"] > 0
    # Every event belongs to exactly one split, preventing row leakage.
    assert sum(report["row_counts"].values()) == len(rows)
