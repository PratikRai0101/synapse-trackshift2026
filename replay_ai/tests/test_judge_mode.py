from types import SimpleNamespace

import pytest

from src.interfaces.race_replay import F1RaceReplayWindow
from src.judge_mode import (
    BranchStart,
    JudgeModeController,
    JudgeModeModel,
    JudgeModePanel,
    JudgeWalkthroughController,
    JudgeWalkthroughPanel,
    build_bookmarks,
    build_walkthrough_steps,
    describe_capability_belief,
    run_counterfactual,
    scenario_label_from_session,
)


def _report(command="BURN"):
    tactical = SimpleNamespace(
        command=command,
        target_speed_kmh=312.0,
        lambda_kin=-0.42,
        lambda_b=0.8,
        envelope_feasible=True,
        reason="rival derate probability and continuation value support attack",
        lap_energy_target=12.0,
    )
    hmm = SimpleNamespace(
        ers_probabilities={"H": 0.08, "M": 0.12,
                           "Lharvest": 0.10, "Lderate": 0.70},
        features=SimpleNamespace(
            dv_baseline=-14.0, dgap=0.18, throttle_clip=0.75,
            brake_delta=-0.02, speed_variance=5.0, aero=1.0,
            tyre_life=11.0,
        ),
    )
    return SimpleNamespace(
        code="VER",
        position=2,
        energy=SimpleNamespace(soc=68.0, balance=-0.6, lap=14),
        tactical=tactical,
        rival_hmm=hmm,
        lap_plan=(SimpleNamespace(deploy_energy=12.0,
                                  reserve_after_lap=48.0),),
        runtime_metrics={
            "hmm_source": "artifacts/hmm-emissions.json",
            "lap_map_source": "artifacts/lap-time-map.json",
            "socp_feasible": True,
            "socp_residual": 0.0,
            "scenario_values": {"BURN": 1.2, "HARVEST": 0.2,
                                 "PROACTIVE TRAP": 0.6},
            "scenario_particles": 128,
            "scenario_histories": 16,
            "scenario_risk_values": {"BURN": 1.0, "HARVEST": 0.1,
                                      "PROACTIVE TRAP": 0.5},
        },
    )


def test_judge_snapshot_explains_action_without_claiming_rival_soc():
    snapshot = JudgeModeModel.from_report(_report())

    assert snapshot.command == "BURN"
    assert snapshot.confidence == pytest.approx(0.70)
    assert snapshot.rival_label == "ERS CAPABILITY BELIEF"
    assert len(snapshot.rival_modes) == 4
    assert {option.command for option in snapshot.options} == {
        "BURN", "HARVEST", "PROACTIVE TRAP"
    }
    assert any("below" in evidence.lower() for evidence in snapshot.evidence)
    assert any("clipping" in evidence.lower() for evidence in snapshot.evidence)
    assert "SOC" not in snapshot.rival_label
    assert snapshot.model_status == "SYNTHETIC ARTIFACT"
    assert "RIVAL SOC: unavailable" in snapshot.provenance[-1]
    assert snapshot.units.speed == "km/h"
    assert snapshot.units.gap == "s"
    assert snapshot.units.energy == "EU (estimated)"
    assert snapshot.units.probability == "% belief"
    assert snapshot.search_particles == 128
    assert "SOCP performance envelope" in snapshot.layer_activity


def test_evidence_reports_measured_clip_duration_not_a_fraction():
    report = _report()
    report.rival_hmm.features = SimpleNamespace(
        dv_baseline=-14.0, dgap=0.18, throttle_clip=0.75, clip_seconds=1.8,
        speed_variance=5.0, aero=1.0, tyre_life=11.0,
    )
    snapshot = JudgeModeModel.from_report(report)

    assert any("sustained 1.8s" in evidence for evidence in snapshot.evidence)


def test_judge_snapshot_uses_explicit_uncertainty_for_trap():
    snapshot = JudgeModeModel.from_report(_report("PROACTIVE TRAP"))

    assert 0.0 <= snapshot.confidence <= 1.0
    assert snapshot.command_color_name == "AMBER"
    assert snapshot.envelope_status == "FEASIBLE"


def test_capability_belief_separates_sandbagging_from_depletion():
    depleted, depleted_color = describe_capability_belief(
        {"H": 0.05, "M": 0.12, "Lharvest": 0.11, "Lderate": 0.72}
    )
    saving, saving_color = describe_capability_belief(
        {"H": 0.08, "M": 0.14, "Lharvest": 0.68, "Lderate": 0.10}
    )
    unresolved, unresolved_color = describe_capability_belief(
        {"H": 0.50, "M": 0.25, "Lharvest": 0.01, "Lderate": 0.24}
    )

    assert "DEPLETED" in depleted
    assert "SAVING" in saving
    assert "UNRESOLVED" in unresolved
    assert len({depleted_color, saving_color, unresolved_color}) == 3


def test_bookmarks_are_unique_bounded_and_numbered():
    bookmarks = build_bookmarks(frame_count=101, total_laps=10)

    assert len(bookmarks) == 6
    assert [bookmark.hotkey for bookmark in bookmarks] == ["5", "6", "7", "8", "9", "0"]
    assert all(0 <= bookmark.frame_index < 101 for bookmark in bookmarks)
    assert len({bookmark.frame_index for bookmark in bookmarks}) == len(bookmarks)


def test_empty_replay_has_no_bookmarks():
    assert build_bookmarks(frame_count=0, total_laps=None) == ()


def test_short_replay_never_duplicates_bookmark_frames():
    bookmarks = build_bookmarks(frame_count=3, total_laps=1)
    assert len(bookmarks) == 3
    assert len({bookmark.frame_index for bookmark in bookmarks}) == 3


def test_counterfactual_branch_is_separate_and_does_not_mutate_start():
    start = BranchStart(
        frame_index=42, timestamp_s=18.0, driver="EGO", rival="RIV",
        own_speed_kmh=300.0, rival_speed_kmh=298.0, gap_s=0.7,
        own_energy=62.0, battery_temperature=75.0, battery_soh=0.98,
    )
    branch = run_counterfactual(start, steps=3, seed=2)

    assert branch.run_mode == "counterfactual"
    assert branch.source_frame_index == 42
    assert branch.source_timestamp_s == 18.0
    assert len(branch.outcomes) == 3
    assert {outcome.action for outcome in branch.outcomes} == {
        "BURN", "HARVEST", "PROACTIVE TRAP"
    }
    assert all(outcome.plausible_modes == 3 for outcome in branch.outcomes)
    assert all(outcome.gap_change_s == pytest.approx(outcome.final_gap_s - start.gap_s)
               for outcome in branch.outcomes)
    assert start.own_energy == 62.0


def test_judge_panel_is_a_compact_non_overlapping_lower_third():
    panel = JudgeModePanel()
    bounds = panel.layout_bounds(
        window_width=1280, window_height=720,
        left_ui_margin=340, right_ui_margin=260,
    )

    assert bounds.height <= 240
    assert bounds.top <= panel.required_bottom_reserve(
        1280, 720, 340, 260
    )
    assert bounds.top < 720 * 0.50


def test_judge_panel_draws_counterfactual_results(monkeypatch):
    calls = []

    class FakeText:
        def __init__(self, *args, **kwargs):
            self.text = args[0] if args else ""
            self.x = self.y = 0
            self.color = kwargs.get("color", (255, 255, 255))
            self.font_size = 10
            self.bold = False

        def draw(self):
            calls.append(("text", self.text))

    monkeypatch.setattr("src.judge_mode.arcade.Text", FakeText)
    monkeypatch.setattr("src.judge_mode.arcade.draw_rect_filled",
                        lambda *args, **kwargs: None)
    monkeypatch.setattr("src.judge_mode.arcade.draw_rect_outline",
                        lambda *args, **kwargs: None)
    monkeypatch.setattr("src.judge_mode.arcade.draw_text",
                        lambda *args, **kwargs: None)
    window = SimpleNamespace(width=1280, height=720, left_ui_margin=340,
                             right_ui_margin=260, driver_colors={}, total_laps=10)
    branch = SimpleNamespace(
        status_text="COUNTERFACTUAL • 3 PLAUSIBLE MODES • 3 ACTIONS",
        outcomes=(
            SimpleNamespace(action="BURN", final_gap_s=0.4, final_energy=55.0,
                            energy_deployed=4.0, plausible_modes=3),
        ),
    )
    JudgeModePanel().draw(window, JudgeModeModel.from_report(_report()),
                          branch=branch)

    assert any("COUNTERFACTUAL BRANCH" in text for kind, text in calls if kind == "text")
    assert any("3 plausible responses" in text for kind, text in calls if kind == "text")


def test_judge_panel_draws_against_a_window_contract(monkeypatch):
    # Rendering is tested at the public panel seam with drawing primitives
    # replaced by a recorder; no OpenGL window is required in CI.
    calls = []

    class FakeText:
        def __init__(self, *args, **kwargs):
            self.text = args[0] if args else ""
            self.x = args[1] if len(args) > 1 else 0
            self.y = args[2] if len(args) > 2 else 0
            self.color = kwargs.get("color", (255, 255, 255))
            self.font_size = kwargs.get("font_size", 10)
            self.bold = kwargs.get("bold", False)

        def draw(self):
            calls.append(("text", self.text))

    monkeypatch.setattr("src.judge_mode.arcade.Text", FakeText)
    for name in ("draw_rect_filled", "draw_rect_outline", "draw_text"):
        monkeypatch.setattr("src.judge_mode.arcade." + name,
                            lambda *args, _name=name, **kwargs: calls.append((_name, args)))

    window = SimpleNamespace(width=1280, height=720, left_ui_margin=340,
                             right_ui_margin=260, driver_colors={"VER": (0, 0, 255)},
                             total_laps=10, _focus_gap_ahead_s=0.7)
    JudgeModePanel().draw(window, JudgeModeModel.from_report(_report()), visible=True)

    assert any(kind == "text" and "ATTACK NOW" in text for kind, text in calls)
    assert any(kind == "text" and "Lharvest" in text for kind, text in calls)
    assert any(kind == "text" and "Lderate" in text for kind, text in calls)
    assert any(kind == "text" and "POMCP" in text for kind, text in calls)
    # P3/P4: causal evidence and the alternatives table carry explicit labels.
    assert any(kind == "text" and "WHY THE MODEL CHANGED" in text
               for kind, text in calls)
    assert any(kind == "text" and text.startswith("✓") for kind, text in calls)
    assert {label for label in ("IMM. GAIN", "ENERGY", "LATER", "DECISION")
            if any(kind == "text" and label == text for kind, text in calls)} == {
        "IMM. GAIN", "ENERGY", "LATER", "DECISION"
    }
    assert any(kind == "draw_rect_filled" for kind, _ in calls)


def test_walkthrough_is_a_deterministic_monza_path():
    bookmarks = build_bookmarks(frame_count=101, total_laps=53)
    steps = build_walkthrough_steps(
        bookmarks,
        scenario_label=scenario_label_from_session({
            "event_name": "Italian Grand Prix",
            "circuit_name": "Monza",
            "country": "Italy",
        }),
    )

    assert len(steps) == 6
    assert [step.bookmark_index for step in steps] == [0, 1, 2, 3, 4, 5]
    assert steps[0].mode_label == "REAL TELEMETRY REPLAY"
    assert steps[4].mode_label == "COUNTERFACTUAL SIMULATION"
    assert "MONZA" in steps[0].body[0]
    assert "Press 5" in steps[0].action_hint
    assert scenario_label_from_session({"circuit_name": "Suzuka"}) == (
        "SUZUKA • DETERMINISTIC PATH"
    )


def test_walkthrough_controller_tracks_hint_and_bookmark_steps():
    controller = JudgeWalkthroughController(build_walkthrough_steps())

    assert controller.visible is False
    assert controller.first_run_hint_visible is True
    assert controller.open() is True
    assert controller.first_run_hint_visible is False
    assert controller.current_step.title == "START WITH REAL TELEMETRY"
    assert controller.step(1).title == "READ THE CAPABILITY BELIEF"
    assert controller.select_for_bookmark(4).title == "FORK THE DECISION"
    assert controller.step(1).title == "RETURN TO OBSERVED HISTORY"
    assert controller.step(1).title == "RETURN TO OBSERVED HISTORY"
    assert controller.close() is False


def test_walkthrough_panel_draws_replay_and_simulation_badges(monkeypatch):
    calls = []

    class FakeText:
        def __init__(self, *args, **kwargs):
            self.text = args[0] if args else ""
            self.x = args[1] if len(args) > 1 else 0
            self.y = args[2] if len(args) > 2 else 0
            self.color = kwargs.get("color", (255, 255, 255))
            self.font_size = kwargs.get("font_size", 10)
            self.bold = kwargs.get("bold", False)

        def draw(self):
            calls.append(("text", self.text))

    monkeypatch.setattr("src.judge_mode.arcade.Text", FakeText)
    for name in ("draw_rect_filled", "draw_rect_outline", "draw_text"):
        monkeypatch.setattr("src.judge_mode.arcade." + name,
                            lambda *args, _name=name, **kwargs: calls.append((_name, args)))

    window = SimpleNamespace(width=1280, height=720)
    controller = JudgeWalkthroughController(build_walkthrough_steps())
    controller.open()
    panel = JudgeWalkthroughPanel()
    panel.draw(window, controller, snapshot=JudgeModeModel.from_report(_report()))

    assert any(kind == "text" and "HOW IT WORKS" in text for kind, text in calls)
    assert any(kind == "text" and "REAL TELEMETRY REPLAY" in text
               for kind, text in calls)

    calls.clear()
    controller.select_for_bookmark(4)
    branch = SimpleNamespace(
        source_frame_index=42,
        outcomes=(
            SimpleNamespace(action="BURN", gap_change_s=-0.2, final_energy=51.0),
            SimpleNamespace(action="HARVEST", gap_change_s=0.1, final_energy=63.0),
        ),
    )
    panel.draw(window, controller, snapshot=JudgeModeModel.from_report(_report()),
              branch=branch)

    assert any(kind == "text" and "COUNTERFACTUAL SIMULATION" in text
               for kind, text in calls)
    assert any(kind == "text" and "SOURCE: REAL TELEMETRY REPLAY" in text
               for kind, text in calls)


def test_walkthrough_window_flow_keeps_bookmark_and_branch_separate(monkeypatch):
    window = object.__new__(F1RaceReplayWindow)
    window.frames = [{"t": 0.0}, {"t": 1.0}, {"t": 2.0}, {"t": 3.0},
                     {"t": 4.0}, {"t": 5.0}, {"t": 6.0}]
    window.n_frames = len(window.frames)
    window.frame_index = 0.0
    window.paused = False
    window.judge_bookmarks = build_bookmarks(len(window.frames), 1)
    window.judge_mode_controller = JudgeModeController(
        enabled=True, bookmarks=window.judge_bookmarks
    )
    window.judge_walkthrough_controller = JudgeWalkthroughController(
        build_walkthrough_steps(window.judge_bookmarks)
    )
    window._judge_hint_age_s = 0.0
    window._counterfactual_branch = None
    window._counterfactual_status = None
    window._counterfactual_running = False
    window._intelligence_models = {}
    window._intelligence_cache = {}
    window._last_intelligence_key = None
    window._last_tactical = None
    window._last_rival_hmm = None
    window._last_lap_plan = None
    window._last_runtime_metrics = {}
    window._broadcast_telemetry_state = lambda: None
    window._refresh_decision_layout = lambda: None
    window._focus_report = SimpleNamespace(
        branch_start=BranchStart(
            frame_index=0, timestamp_s=0.0, driver="EGO", rival="RIV",
            own_speed_kmh=300.0, rival_speed_kmh=299.0, gap_s=0.7,
            own_energy=60.0,
        )
    )

    window._toggle_judge_walkthrough()
    assert window.judge_walkthrough_controller.visible is True
    assert window.frame_index == window.judge_bookmarks[0].frame_index
    assert window.paused is True

    for _ in range(4):
        window._step_judge_walkthrough(1)
    assert window.judge_walkthrough_controller.current_step.title == "FORK THE DECISION"
    assert window.frame_index == window.judge_bookmarks[4].frame_index

    branch = SimpleNamespace(status_text="COUNTERFACTUAL • 3 PLAUSIBLE MODES • 3 ACTIONS")
    monkeypatch.setattr("src.interfaces.race_replay.run_counterfactual",
                        lambda start, steps, seed: branch)
    window._launch_counterfactual()
    assert window._counterfactual_branch is branch
    assert window.frames[0]["t"] == 0.0

    # Selecting a different recorded bookmark clears only the isolated branch;
    # the original frame list remains byte-for-byte the same objects.
    original_frames = list(window.frames)
    window._select_judge_bookmark(5)
    assert window._counterfactual_branch is None
    assert window.frame_index == window.judge_bookmarks[5].frame_index
    assert window.frames == original_frames
