"""Recorded pit-stop display in the progress bar timeline."""

from src.ui_components import RaceProgressBarComponent, extract_race_events


def _frame(index: int, in_pit: bool):
    return {
        "t": index * 0.04,
        "drivers": {
            "VER": {"lap": 10, "position": 1, "in_pit": in_pit},
            "HAM": {"lap": 10, "position": 2, "in_pit": False},
        },
    }


def test_extract_race_events_marks_each_pit_entry_once():
    # VER is in the pits for frames 100-119 on a single lap.
    frames = [_frame(i, in_pit=(100 <= i < 120)) for i in range(160)]

    events = extract_race_events(frames, [], 53)
    pits = [e for e in events
            if e["type"] == RaceProgressBarComponent.EVENT_PIT]

    assert len(pits) == 1
    assert pits[0]["label"] == "VER"
    assert pits[0]["lap"] == 10
    assert RaceProgressBarComponent.COLORS["pit"] == (235, 235, 240)
