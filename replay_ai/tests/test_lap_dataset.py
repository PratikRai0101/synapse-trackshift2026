from src.intelligence.lap_dataset import extract_lap_samples
from src.intelligence.lap_strategy import LapTimeMap


def frames():
    return [
        {"t": 0.0, "drivers": {"HAM": {"lap": 1, "speed": 300,
            "throttle": 100, "tyre_life": 3}}},
        {"t": 45.0, "drivers": {"HAM": {"lap": 1, "speed": 290,
            "throttle": 100, "tyre_life": 3}}},
        {"t": 45.1, "drivers": {"HAM": {"lap": 2, "speed": 300,
            "throttle": 100, "tyre_life": 4}}},
        {"t": 91.0, "drivers": {"HAM": {"lap": 2, "speed": 290,
            "throttle": 80, "tyre_life": 4}}},
    ]


def test_extracts_completed_lap_features_and_energy_proxies():
    samples = extract_lap_samples(frames(), "HAM")
    assert len(samples) == 2
    assert samples[0].lap_time_s == 45.0
    assert samples[0].battery_deployed > 0
    assert samples[0].fuel_deployed > 0
    assert samples[1].tyre_wear == 4


def test_lap_map_serializes_and_round_trips(tmp_path):
    samples = extract_lap_samples(frames(), "HAM")
    original = LapTimeMap().fit(samples)
    restored = LapTimeMap.from_dict(original.to_dict())
    query = samples[0]
    assert restored.predict(query) == original.predict(query)
