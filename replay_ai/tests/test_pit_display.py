"""Recorded pit-stop display: progress events and Judge Mode pit state."""

from types import SimpleNamespace

from src.ui_components import RaceProgressBarComponent, extract_race_events
from src.judge_mode import JudgeModeModel, JudgeModePanel


def _frame(index: int, in_pit: bool):
    return {
        "t": index * 0.04,
        "drivers": {
            "VER": {"lap": 10, "position": 1, "in_pit": in_pit},
            "HAM": {"lap": 10, "position": 2, "in_pit": False},
        },
    }


def _minimal_report():
    return SimpleNamespace(
        code="VER",
        position=1,
        energy=SimpleNamespace(soc=70.0, lap=10),
        tactical=None,
        rival_hmm=None,
        runtime_metrics={},
    )


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


def test_judge_snapshot_carries_recorded_pit_state():
    pit_snapshot = JudgeModeModel.from_report(_minimal_report(), in_pit=True)
    green_snapshot = JudgeModeModel.from_report(_minimal_report())

    assert pit_snapshot.in_pit is True
    assert green_snapshot.in_pit is False


def test_judge_panel_shows_in_pit(monkeypatch):
    calls = []

    class FakeText:
        def __init__(self, *args, **kwargs):
            self.text = args[0] if args else ""

        def draw(self):
            calls.append(("text", self.text))

    monkeypatch.setattr("src.judge_mode.arcade.Text", FakeText)
    for name in ("draw_rect_filled", "draw_rect_outline", "draw_text"):
        monkeypatch.setattr("src.judge_mode.arcade." + name,
                            lambda *args, **kwargs: None)
    monkeypatch.setattr("src.judge_mode.draw_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.judge_mode.draw_meter", lambda *args, **kwargs: None)

    window = SimpleNamespace(width=1280, height=720, left_ui_margin=340,
                             right_ui_margin=260, total_laps=53)
    JudgeModePanel().draw(
        window,
        JudgeModeModel.from_report(_minimal_report(), in_pit=True),
    )

    assert any("IN PIT" in text for kind, text in calls if kind == "text")
