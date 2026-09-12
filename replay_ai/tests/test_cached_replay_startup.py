import numpy as np
import pandas as pd
import pytest

from main import _example_lap_from_cached_frames, _rotation_from_cached_geometry


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


def test_cached_geometry_rotation_matches_start_finish_orientation():
    # Cached telemetry's start straight points at 85 degrees. FastF1's display
    # convention points it left, requiring the same ~95 degree Monza rotation
    # used by the original replay.
    angle = np.deg2rad(85.0)
    distance = np.linspace(0.0, 400.0, 20)
    lap = pd.DataFrame({
        "X": np.cos(angle) * distance,
        "Y": np.sin(angle) * distance,
        "Distance": distance,
    })

    assert _rotation_from_cached_geometry(lap) == pytest.approx(95.0, abs=0.5)
