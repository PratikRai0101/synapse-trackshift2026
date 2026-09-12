from src.interfaces.race_replay import F1RaceReplayWindow


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
