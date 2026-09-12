from src.intelligence.vehicle_plant import PlantState, VehiclePlant


def test_plant_enforces_combined_grip_limit():
    plant = VehiclePlant(PlantState(speed_kmh=300))
    step = plant.step(1.0, 0.1, curvature=0.08)
    assert step.grip_limited
    assert (step.longitudinal_accel ** 2 + step.lateral_accel ** 2) ** 0.5 <= 1.45 * 9.81 + 1e-8


def test_plant_updates_energy_temperature_wear_and_distance():
    plant = VehiclePlant()
    before = plant.state
    step = plant.step(1.0, 0.5, curvature=0.01)
    assert step.distance_m > 0
    assert step.energy < 70
    assert step.battery_temperature >= 70
    assert step.tyre_wear > 0


def test_regeneration_increases_energy_when_not_deploying():
    plant = VehiclePlant(PlantState(energy=50))
    step = plant.step(0.0, 1.0, regen_fraction=1.0)
    assert step.energy > 50
