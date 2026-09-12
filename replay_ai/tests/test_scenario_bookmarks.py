import json

from src.intelligence.scenarios import (
    SCENARIOS,
    ScenarioObservation,
    build_energy_soc,
    load_scenario_artifact,
    save_scenario_artifact,
    scan_recorded_driver,
    scenario_candidates,
    select_scenario_frames,
)
from src.judge_mode import build_bookmarks, build_scenario_bookmarks


def _obs(frame=0, harvest=0.0, derate=0.0, gap=0.6, soc=70.0,
         tyre=4.0, track=40.0):
    return ScenarioObservation(
        frame_index=frame, p_harvest=harvest, p_derate=derate, gap_s=gap,
        soc=soc, tyre_life=tyre, track_temp=track,
    )


def test_scenario_candidates_separate_depletion_from_sandbagging():
    saving = scenario_candidates(_obs(harvest=0.7, derate=0.05, gap=0.5))
    spent = scenario_candidates(_obs(harvest=0.02, derate=0.72, gap=0.4))

    assert "counter_harvest" in saving and "depletion" not in saving
    assert "depletion" in spent and "counter_harvest" not in spent
    # A depleted rival within reach is an attack when the budget allows it...
    assert "attack" in spent
    # ...and is blocked by the envelope when it does not.
    blocked = scenario_candidates(_obs(derate=0.72, gap=0.4, soc=18.0))
    assert "envelope" in blocked and "attack" not in blocked


def test_trap_requires_an_unresolved_belief_in_range():
    assert "trap" in scenario_candidates(_obs(harvest=0.2, derate=0.1, gap=1.0))
    assert "trap" not in scenario_candidates(_obs(harvest=0.7, derate=0.05, gap=1.0))
    assert "trap" not in scenario_candidates(_obs(harvest=0.2, derate=0.1, gap=3.0))


def test_select_scenario_frames_are_distinct_and_deterministic():
    observations = (
        _obs(10, harvest=0.7, gap=1.0),
        _obs(11, derate=0.7, gap=0.4, soc=70.0),
        _obs(12, derate=0.6, gap=0.5, soc=15.0),
        _obs(13, harvest=0.2, derate=0.1, gap=0.8),
        _obs(14, tyre=25.0, track=56.0),
    )
    first = select_scenario_frames(observations)
    second = select_scenario_frames(observations)

    assert first == second
    assert set(first) == {spec.key for spec in SCENARIOS if spec.key in first}
    # "depletion" and "attack" both match frame 11 but must not collide.
    assert len(set(first.values())) == len(first)


def test_build_scenario_bookmarks_falls_back_and_keeps_frames_unique():
    frames = 100
    targets = {"depletion": 40, "attack": 40, "trap": 60}
    bookmarks = build_scenario_bookmarks(targets, frames, total_laps=5)

    assert len(bookmarks) == 6
    assert [bookmark.hotkey for bookmark in bookmarks] == ["5", "6", "7", "8", "9", "0"]
    assert len({bookmark.frame_index for bookmark in bookmarks}) == 6
    assert bookmarks[1].title == "GENUINE DEPLETION"
    # An undiscovered scenario keeps the phase-bookmark fallback title.
    fallback_titles = {bookmark.title for bookmark in build_bookmarks(frames, 5)}
    assert bookmarks[5].title in fallback_titles


def test_empty_replay_has_no_scenario_bookmarks():
    assert build_scenario_bookmarks({"depletion": 0}, 0, None) == ()


def test_scenario_artifact_round_trip(tmp_path):
    path = str(tmp_path / "scenario_bookmarks_2026_13.json")
    save_scenario_artifact(path, {"VER": {"depletion": 1234}}, year=2026,
                           round_number=13)
    assert load_scenario_artifact(path) == {"VER": {"depletion": 1234}}
    assert load_scenario_artifact(str(tmp_path / "missing.json")) == {}


def test_scan_recorded_driver_tracks_the_car_ahead():
    frames = []
    for index in range(0, 200):
        lap = 1 + index // 50
        frames.append({
            "t": float(index),
            "weather": {"track_temp": 50.0},
            "drivers": {
                "EGO": {"position": 2, "lap": lap, "dist": 100.0 + index,
                        "speed": 250.0, "throttle": 100.0, "brake": 0.0,
                        "tyre_life": 3.0, "in_pit": False, "drs": 0},
                "RIV": {"position": 1, "lap": lap, "dist": 160.0 + index,
                        "speed": 240.0, "throttle": 100.0, "brake": 0.0,
                        "tyre_life": 3.0, "in_pit": False, "drs": 0},
            },
        })
    soc = build_energy_soc(frames, "EGO")
    observations = scan_recorded_driver(frames, "EGO", soc, sample_step=25,
                                        min_lap=2)

    assert observations
    assert all(o.frame_index % 25 == 0 for o in observations)
    assert all(o.gap_s > 0.0 for o in observations)
