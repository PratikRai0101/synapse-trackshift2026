import json
import pickle

from scripts.build_lap_dataset import build
from scripts.evaluate_lap_map import evaluate


def make_pickle(path, offset=0):
    frames = []
    for lap in (1, 2, 3):
        start = offset + (lap - 1) * 45
        frames.extend([
            {"t": start, "drivers": {"HAM": {"lap": lap, "speed": 300,
                "throttle": 100, "tyre_life": lap}}},
            {"t": start + 45, "drivers": {"HAM": {"lap": lap, "speed": 300,
                "throttle": 100, "tyre_life": lap}}},
        ])
    with path.open("wb") as handle:
        pickle.dump({"frames": frames}, handle)


def test_lap_dataset_is_split_by_event_and_evaluated(tmp_path):
    inputs = []
    for index in range(100):
        path = tmp_path / f"{index}.pkl"
        make_pickle(path, offset=index)
        inputs.append((f"event-{index}", path))
    dataset = tmp_path / "dataset"
    manifest = build(inputs, "HAM", dataset)
    assert sum(manifest["event_counts"].values()) == 100
    report = evaluate(dataset)
    assert report["reports"]["test"]["samples"] > 0
    assert report["reports"]["test"]["mae_s"] is not None
