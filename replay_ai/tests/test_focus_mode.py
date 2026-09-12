from types import SimpleNamespace

from src.interfaces.race_replay import F1RaceReplayWindow
from src.judge_mode import (
    BranchStart,
    JudgeModeController,
    JudgeModePanel,
    build_bookmarks,
)


def test_judge_panel_reservation_keeps_track_above_panel():
    window = SimpleNamespace(
        width=1280,
        height=720,
        left_ui_margin=340,
        right_ui_margin=260,
        top_ui_reserved=96,
        selected_drivers=["VER"],
        selected_driver="VER",
        judge_panel=JudgeModePanel(),
        judge_mode_controller=JudgeModeController(enabled=True),
    )

    panel = window.judge_panel.layout_bounds(1280, 720, 340, 260)
    reserve = F1RaceReplayWindow._required_bottom_ui_reserve(window)

    assert panel.top < reserve
    assert reserve < window.height - window.top_ui_reserved


def test_track_reclaims_original_space_without_a_focus_driver():
    window = SimpleNamespace(
        selected_drivers=[], selected_driver=None,
        judge_mode_controller=JudgeModeController(enabled=True),
    )
    assert F1RaceReplayWindow._required_bottom_ui_reserve(window) == 300.0


def test_judge_bookmark_seek_is_observational_and_resets_inference(monkeypatch):
    window = object.__new__(F1RaceReplayWindow)
    frames = [{"t": 0.0}, {"t": 1.0}, {"t": 2.0}, {"t": 3.0}]
    window.frames = frames
    window.n_frames = len(frames)
    window.frame_index = 0.0
    window.paused = False
    window.judge_bookmarks = build_bookmarks(len(frames), 1)
    window.judge_mode_controller = JudgeModeController(
        enabled=True, bookmarks=window.judge_bookmarks
    )
    window._intelligence_models = {"pair": object()}
    window._intelligence_cache = {"frame": object()}
    window._last_intelligence_key = "frame"
    window._last_tactical = object()
    window._last_rival_hmm = object()
    window._last_lap_plan = object()
    window._last_runtime_metrics = {"stale": True}
    window._counterfactual_branch = object()
    window._counterfactual_status = None
    window._broadcast_telemetry_state = lambda: None

    original_frames = list(window.frames)
    window._select_judge_bookmark(3)

    assert window.frame_index == window.judge_bookmarks[3].frame_index
    assert window.paused is True
    assert window.frames == original_frames
    assert window._intelligence_models == {}
    assert window._intelligence_cache == {}
    assert window._counterfactual_branch is None


def test_counterfactual_launch_uses_branch_without_touching_frames(monkeypatch):
    window = object.__new__(F1RaceReplayWindow)
    frames = [{"t": 0.0, "drivers": {"EGO": {"speed": 300.0}}}]
    window.frames = frames
    window._focus_report = type("Report", (), {
        "branch_start": BranchStart(
            frame_index=0, timestamp_s=0.0, driver="EGO", rival="RIV",
            own_speed_kmh=300.0, rival_speed_kmh=299.0, gap_s=0.7,
            own_energy=60.0,
        )
    })()
    window._counterfactual_running = False
    window._counterfactual_branch = None
    window._counterfactual_status = None
    window.paused = False
    sentinel = object()
    monkeypatch.setattr(
        "src.interfaces.race_replay.run_counterfactual",
        lambda start, steps, seed: sentinel,
    )

    original_frames = list(window.frames)
    window._launch_counterfactual()

    assert window._counterfactual_branch is sentinel
    assert window.paused is True
    assert window.frames == original_frames


def test_battle_group_single_selection_middle():
    ordered = ["VER", "NOR", "PIA", "HAM", "LEC", "RUS", "ALO"]
    battle, battle_set = F1RaceReplayWindow.get_battle_group(ordered, ["HAM"], radius=2)
    assert battle == ["NOR", "PIA", "HAM", "LEC", "RUS"]
    assert battle_set == set(battle)


def test_battle_group_at_front_clamps():
    ordered = ["VER", "NOR", "PIA", "HAM"]
    battle, _ = F1RaceReplayWindow.get_battle_group(ordered, ["VER"], radius=2)
    assert battle == ["VER", "NOR", "PIA"]


def test_battle_group_at_back_clamps():
    ordered = ["VER", "NOR", "PIA", "HAM"]
    battle, _ = F1RaceReplayWindow.get_battle_group(ordered, ["HAM"], radius=2)
    assert battle == ["NOR", "PIA", "HAM"]


def test_battle_group_no_selection_empty():
    ordered = ["VER", "NOR", "PIA"]
    battle, battle_set = F1RaceReplayWindow.get_battle_group(ordered, [], radius=2)
    assert battle == []
    assert battle_set == set()


def test_battle_group_unknown_driver_ignored():
    ordered = ["VER", "NOR", "PIA"]
    battle, battle_set = F1RaceReplayWindow.get_battle_group(ordered, ["XXX"], radius=2)
    assert battle == []
    assert battle_set == set()


def test_battle_group_multi_select_union():
    ordered = ["A", "B", "C", "D", "E", "F", "G"]
    battle, _ = F1RaceReplayWindow.get_battle_group(ordered, ["B", "F"], radius=1)
    assert battle == ["A", "B", "C", "E", "F", "G"]


def test_gap_between_matches_existing_math():
    # progress is in metres; time = metres / 55.56 m/s (~200 km/h).
    dist_m, time_s = F1RaceReplayWindow.gap_between(1000.0, 0.0)
    assert dist_m == 1000.0
    assert abs(time_s - (1000.0 / 55.56)) < 1e-9


def test_gap_between_one_second():
    # 55.56 m at the reference speed is exactly 1.0s (regression: no /10 bug).
    dist_m, time_s = F1RaceReplayWindow.gap_between(55.56, 0.0)
    assert abs(dist_m - 55.56) < 1e-9
    assert abs(time_s - 1.0) < 1e-9


def test_connector_drawn_for_close_battle():
    # DRS-range gap, cars close on screen -> connector is useful
    assert F1RaceReplayWindow.should_draw_connector(
        0.8, 120.0, screen_w=1920, screen_h=1080
    )


def test_connector_skipped_for_large_time_gap():
    # Adjacent in track order but 20s apart -> no tether across the map
    assert not F1RaceReplayWindow.should_draw_connector(
        20.0, 120.0, screen_w=1920, screen_h=1080
    )


def test_connector_skipped_for_long_screen_streak():
    # Small time gap but cars far apart in screen space -> skip
    assert not F1RaceReplayWindow.should_draw_connector(
        0.5, 900.0, screen_w=1920, screen_h=1080
    )


def test_connector_handles_none_and_bad_values():
    assert not F1RaceReplayWindow.should_draw_connector(None, 10.0)
    assert not F1RaceReplayWindow.should_draw_connector("nan", 10.0)


# --- label decluttering helpers -------------------------------------------

def test_rects_overlap_detects_and_ignores():
    W = F1RaceReplayWindow
    assert W._rects_overlap((0, 0, 10, 10), [(5, 5, 15, 15)])
    assert not W._rects_overlap((0, 0, 10, 10), [(10, 10, 20, 20)])
    assert not W._rects_overlap((0, 0, 10, 10), [])


def test_label_rect_anchor_sides():
    W = F1RaceReplayWindow
    left = W._label_rect(100, 50, 40, 10, "left")
    right = W._label_rect(100, 50, 40, 10, "right")
    assert left == (100, 45, 140, 55)
    assert right == (60, 45, 100, 55)


def test_place_label_returns_free_spot():
    W = F1RaceReplayWindow
    occupied = []
    placed = W._place_label(500, 500, 1.0, 0.0, "VER", occupied, forbidden=[])
    assert placed is not None
    lx, ly, anchor = placed
    assert anchor == "left"          # normal points right
    assert len(occupied) == 1


def test_place_label_avoids_existing_label():
    W = F1RaceReplayWindow
    occupied = []
    first = W._place_label(500, 500, 1.0, 0.0, "VER", occupied, forbidden=[])
    second = W._place_label(500, 500, 1.0, 0.0, "NOR", occupied, forbidden=[])
    assert second is not None
    # Second placement must not overlap the first.
    r1 = W._label_rect(*first[:2], 10 * 7 + 10, 15, first[2])
    r2 = W._label_rect(*second[:2], 10 * 7 + 10, 15, second[2])
    assert not W._rects_overlap(r1, [r2])


def test_place_label_none_when_all_blocked():
    W = F1RaceReplayWindow
    forbidden = [(-10000, -10000, 10000, 10000)]
    assert W._place_label(500, 500, 1.0, 0.0, "VER", [], forbidden) is None
