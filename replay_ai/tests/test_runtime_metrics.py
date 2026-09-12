from src.intelligence.hierarchical import MotorsportIntelligence, RivalTelemetry


def test_runtime_metrics_expose_soh_energy_and_solver_diagnostics():
    model = MotorsportIntelligence()
    model.observe(RivalTelemetry(280, 99, 0, 0.8, lap=1), own_soc=65,
                  battery_soh=0.92, battery_temperature=82)
    metrics = model.runtime_metrics()
    assert metrics["hmm_source"] == "default"
    assert metrics["lap_map_source"] == "unavailable"
    assert metrics["battery_soh"] == 0.92
    assert metrics["battery_resistance"] > 1.0
    assert "battery_wear_cost" in metrics
    assert "scenario_values" in metrics
    assert "socp_feasible" in metrics
    assert metrics["scenario_particles"] > 0
    assert metrics["scenario_histories"] > 0
    assert len(metrics["spatial_speed_profile"]) == 5
    assert "kinetic_costates" in metrics
