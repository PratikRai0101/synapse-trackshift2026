from src.intelligence.hierarchical import MotorsportIntelligence, RivalTelemetry
from src.intelligence.lap_strategy import LapTimeMap, LapTimeSample


def test_runtime_loads_map_and_plans_once_per_lap(tmp_path):
    artifact = tmp_path / "lap-map.json"
    LapTimeMap().fit([
        LapTimeSample(90.0, 0, 0, 0),
        LapTimeSample(89.0, 5, 0, 0),
    ]).save(str(artifact))
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
