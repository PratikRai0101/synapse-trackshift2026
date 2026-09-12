import json

from src.intelligence.closed_loop import ClosedLoopSimulator, HiddenRivalMode
from src.intelligence.hierarchical import MotorsportIntelligence


def test_runtime_loads_calibrated_artifact(tmp_path):
    artifact = tmp_path / "emissions.json"
    artifact.write_text(json.dumps({
        "schema": "hmm-emissions.v2",
        "means": {"Lderate": {"dgap": 0.5, "throttle_clip": 0.9, "brake_delta": 0.0}},
        "sigma": {"dgap": 0.1, "throttle_clip": 0.1, "brake_delta": 0.1},
    }))
    model = MotorsportIntelligence(str(artifact))
    assert model.hmm_source == str(artifact)
    assert model.hmm.emission_sigma["dgap"] == 0.1


def test_missing_artifact_falls_back_without_blocking_replay(tmp_path):
    model = MotorsportIntelligence(str(tmp_path / "missing.json"))
    assert model.hmm_source == "default"
    assert model.observe(__import__(
        "src.intelligence", fromlist=["RivalTelemetry"]
    ).RivalTelemetry(300, 100, 0, 1.0)).command


def test_closed_loop_reports_artifact_source(tmp_path):
    artifact = tmp_path / "emissions.json"
    artifact.write_text(json.dumps({"means": {}, "sigma": {}}))
    sim = ClosedLoopSimulator(HiddenRivalMode.MATCH, hmm_artifact=str(artifact))
    sim.step()
    assert sim.model.hmm_source == str(artifact)
