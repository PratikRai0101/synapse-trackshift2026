from src.intelligence.closed_loop import ClosedLoopSimulator, HiddenRivalMode
from src.intelligence.hierarchical import MotorsportIntelligence, RivalTelemetry
from src.intelligence.lap_strategy import LapTimeMap, LapTimeSample


def map_artifact(tmp_path):
    artifact = tmp_path / "lap-map.json"
    LapTimeMap().fit([
        LapTimeSample(90.0, 0, 0, 0),
        LapTimeSample(89.0, 5, 0, 0),
    ]).save(str(artifact))
    return artifact


def test_runtime_loads_map_and_plans_once_per_lap(tmp_path):
    artifact = map_artifact(tmp_path)
    model = MotorsportIntelligence(lap_map_artifact=str(artifact))
    first = model.observe(RivalTelemetry(300, 100, 0, 1.0, lap=1), own_soc=50)
    plan = model.last_lap_plan
    assert plan is not None
    assert len(plan) == 5
    model.observe(RivalTelemetry(301, 100, 0, 1.0, lap=1), own_soc=40)
    assert model.last_lap_plan is plan
    model.observe(RivalTelemetry(302, 100, 0, 1.0, lap=2), own_soc=40)
    assert model.last_lap_plan is not plan
    assert first.command in {"BURN", "HARVEST", "PROACTIVE TRAP"}


def test_closed_loop_tracks_runtime_lap_energy_target(tmp_path):
    sim = ClosedLoopSimulator(
        HiddenRivalMode.DEPLETE,
        lap_map_artifact=str(map_artifact(tmp_path)),
    )
    steps = sim.run(25)
    assert any(step.decision.lap_energy_target is not None for step in steps)
    assert sim.current_lap == 2
    assert all(step.ego_energy >= 0.0 for step in steps)
