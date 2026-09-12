from src.intelligence.vehicle_plant import PlantState, VehiclePlant


def test_plant_enforces_combined_grip_limit():
    plant = VehiclePlant(PlantState(speed_kmh=300))
    step = plant.step(1.0, 0.1, curvature=0.08)
    assert step.grip_limited
    assert (step.longitudinal_accel ** 2 + step.lateral_accel ** 2) ** 0.5 <= 1.45 * 9.81 + 1e-8


def test_plant_updates_energy_temperature_wear_and_distance():
    plant = VehiclePlant()
    step = plant.step(1.0, 0.5, curvature=0.01)
    assert step.distance_m > 0
    assert step.energy < 70
    assert step.battery_temperature >= 70
    assert step.tyre_wear > 0
    assert plant.state.fuel_mass_kg < 100
    assert step.battery_resistance >= 1.0


def test_regeneration_increases_energy_when_not_deploying():
    plant = VehiclePlant(PlantState(energy=50))
    step = plant.step(0.0, 1.0, regen_fraction=1.0)
    assert step.energy > 50


def test_hot_battery_increases_resistance_and_reduces_power_acceleration():
    cool = VehiclePlant(PlantState(battery_temperature=70.0))
    hot = VehiclePlant(PlantState(battery_temperature=110.0))
    cool_step = cool.step(1.0, 0.1)
    hot_step = hot.step(1.0, 0.1)
    assert hot_step.battery_resistance > cool_step.battery_resistance
    assert hot_step.longitudinal_accel < cool_step.longitudinal_accel


def test_slipstream_reduces_drag_and_pit_resets_wear_and_fuel():
    solo = VehiclePlant()
    draft = VehiclePlant()
    solo.step(0.5, 1.0, slipstream_gap_s=2.0)
    draft.step(0.5, 1.0, slipstream_gap_s=0.5)
    assert draft.state.speed_kmh >= solo.state.speed_kmh
    draft.state.tyre_wear = 0.7
    draft.state.fuel_mass_kg = 20.0
    draft.pit_stop()
    assert draft.state.tyre_wear == 0.0
    assert draft.state.fuel_mass_kg == 80.0
    assert draft.state.pit_stops == 1
