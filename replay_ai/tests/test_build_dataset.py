import json
import pickle

from scripts.build_dataset import build_dataset, event_split


def test_event_split_is_stable_and_dataset_is_event_partitioned(tmp_path):
    frames = [{
        "t": 1.0, "lap": 1,
        "drivers": {
            "EGO": {"speed": 300},
            "RIV": {"speed": 305, "throttle": 100, "brake": 0},
        },
    }]
    source = tmp_path / "race.pkl"
    with source.open("wb") as handle:
        pickle.dump({"frames": frames}, handle)
    output = tmp_path / "dataset"
    counts = build_dataset([("race-a", source)], "EGO", "RIV", output, 1, None)
    assert sum(counts.values()) == 1
    split = event_split("race-a")
    record = json.loads((output / f"{split}.jsonl").read_text())
    assert record["event"] == "race-a"
    assert record["split"] == split
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["schema"] == "public-telemetry-dataset.v1"
