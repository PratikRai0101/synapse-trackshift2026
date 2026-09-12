import pandas as pd

from main import _example_lap_from_cached_frames


def test_cached_frames_reconstruct_track_geometry_without_loaded_fastf1_session():
    telemetry = {
        "frames": [
            {"drivers": {"AAA": {"lap": 1, "dist": 0, "x": 10, "y": 20,
                                  "speed": 100, "drs": 0}}},
            {"drivers": {"AAA": {"lap": 1, "dist": 50, "x": 15, "y": 25,
                                  "speed": 150, "drs": 12}}},
            {"drivers": {"AAA": {"lap": 2, "dist": 1, "x": 10, "y": 20,
                                  "speed": 110, "drs": 0}}},
        ]
    }
    lap = _example_lap_from_cached_frames(telemetry)
    assert isinstance(lap, pd.DataFrame)
    assert list(lap.columns) == ["X", "Y", "Distance", "Speed", "DRS"]
    assert list(lap["Distance"]) == [0.0, 50.0]
