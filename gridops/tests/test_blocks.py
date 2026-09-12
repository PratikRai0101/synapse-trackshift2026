"""Blocks 0, 1, 2, 3A, 4A, 4B: feature extraction, season DP, lap-time map,
40-state HMM, zone MPC and PMP cues."""

from __future__ import annotations

import numpy as np
import pytest

from gridops.contracts.state import BatteryParams, VehicleParams
from gridops.decision.features import RollingBaseline, TelemetrySample
from gridops.decision.hmm40 import HMMBelief40, HMM40Config, MODES, N_STATES
from gridops.decision.pmp import (
    CUE_COAST,
    CUE_FRICTION,
    CUE_MAX_ACCEL,
    CUE_REGEN,
    CUE_UNAVAILABLE,
    CostateState,
    guidance,
    switching_cue,
)
from gridops.decision.zone_mpc import EnergyZone, ZoneMPC
from gridops.race_value.lap_map import RaceValueMap, LapMapConfig, default_terminal_value
from gridops.race_value.lap_time_map import NeuralLapTimeMap, generate_dataset
from gridops.race_value.season import SeasonConfig, SeasonLifecycle
from gridops.simulation.rivals import RivalPolicy
from gridops.simulation.track import synthetic_circuit
from gridops.simulation.tyres import default_tyre_params


# -- Block 0 ---------------------------------------------------------------
def test_super_clipping_fraction_detects_full_throttle_slowdown() -> None:
    baseline = RollingBaseline(window=2, speed_tolerance_mps=1.0)
    for _ in range(12):
        baseline.ingest(TelemetrySample(0.0, 80.0, 0.99, 0.0, 1, 0), 0.0)
    baseline.complete_lap()
    for _ in range(12):
        baseline.ingest(TelemetrySample(0.0, 80.0, 0.99, 0.0, 1, 0), 0.0)
    baseline.complete_lap()
    features = baseline.ingest(TelemetrySample(0.0, 70.0, 1.0, 0.0, 1, 0), 0.0)
    assert features.super_clipping_fraction > 0.0
    assert features.speed_delta_mps < 0.0


def test_baseline_is_empty_before_any_lap_completes() -> None:
    baseline = RollingBaseline()
    features = baseline.ingest(TelemetrySample(0.0, 80.0, 0.5, 0.0, 1, 0), 0.0)
    assert features.speed_delta_mps == 0.0
    assert features.samples == 1


# -- Block 3A --------------------------------------------------------------
def test_hmm40_has_forty_states() -> None:
    assert N_STATES == 40
    belief = HMMBelief40()
    assert len(belief._posterior) == 40
    assert sum(belief._posterior) == pytest.approx(1.0)
    assert len(MODES) == 5


def test_hmm40_concentrates_on_the_observed_regime() -> None:
    belief = HMMBelief40(HMM40Config(emission_sigma_mps=0.8))
    expected = {m: (2.5 if m in (RivalPolicy.MATCHING, RivalPolicy.AGGRESSIVE) else 0.0) for m in MODES}
    for _ in range(6):
        belief.update_on_observation(2.5, expected)
    assert belief.strong_rival_mass() > 0.8


def test_hmm40_reserve_dimension_cannot_be_read_off_one_observation() -> None:
    """A depleted defender and a full conserving rival are close on one sample."""
    belief = HMMBelief40()
    expected = {m: (2.5 if m in (RivalPolicy.MATCHING, RivalPolicy.AGGRESSIVE) else 0.0) for m in MODES}
    belief.update_on_observation(1.0, expected)
    assert belief.ambiguity_index() > 0.0


# -- Block 4B --------------------------------------------------------------
def test_pmp_switching_bands() -> None:
    eta = 0.9
    assert switching_cue(CostateState(lambda_kin=1.0, lambda_b=1.0, eta_plus=eta, eta_minus=eta)) == CUE_FRICTION
    assert switching_cue(CostateState(lambda_kin=-1.5 * 0.9, lambda_b=1.0, eta_plus=eta, eta_minus=eta)) == CUE_MAX_ACCEL
    assert switching_cue(CostateState(lambda_kin=-0.95, lambda_b=1.0, eta_plus=eta, eta_minus=eta)) == CUE_COAST
    assert switching_cue(CostateState(lambda_kin=-0.5, lambda_b=1.0, eta_plus=eta, eta_minus=eta)) == CUE_REGEN
    assert switching_cue(CostateState(lambda_kin=-0.5, lambda_b=0.0)) == CUE_UNAVAILABLE


def test_pmp_guidance_from_the_race_value() -> None:
    battery = BatteryParams()
    race_value = RaceValueMap(default_terminal_value(battery), LapMapConfig(laps=20, n_energy_levels=41))
    plan = guidance(
        speed_mps=80.0,
        mass_kg=798.0,
        race_value=race_value,
        usable_energy_j=2_000_000.0,
        laps_remaining=10,
    )
    assert plan.cue in {"MAX_ACCEL", "COAST", "REGEN_BRAKE", "FRICTION_BRAKE"}
    assert np.isfinite(plan.lambda_kin) and np.isfinite(plan.lambda_b)
    assert plan.guidance


# -- Block 4A --------------------------------------------------------------
def test_zone_mpc_is_an_lp_and_solves() -> None:
    battery = BatteryParams()
    zone = EnergyZone(
        e_kin_low_j=0.5 * 798.0 * 70.0**2,
        e_kin_high_j=0.5 * 798.0 * 85.0**2,
        e_bat_low_j=1.0e6,
        e_bat_high_j=3.0e6,
    )
    from gridops.simulation.plant import initial_state

    mpc = ZoneMPC(synthetic_circuit(), VehicleParams(), battery, horizon_m=300.0)
    plan = mpc.solve(0.0, 80.0, initial_state(battery).battery, zone)
    assert plan.is_dcp
    assert plan.accepted
    assert len(plan.p_k_dc_w) > 0
    assert np.all(plan.p_k_dc_w >= -1e-6)


def test_zone_mpc_rejects_an_inverted_zone() -> None:
    with pytest.raises(ValueError):
        EnergyZone(100.0, 50.0, 0.0, 1.0)


# -- Block 2 ---------------------------------------------------------------
@pytest.fixture(scope="module")
def lap_map() -> NeuralLapTimeMap:
    # A power-limited circuit: gentle corners and long straights, so deployment
    # actually changes lap time. The twisty default circuit is corner-limited and
    # would make the map insensitive to energy by construction.
    from gridops.simulation.track import build_track

    track = build_track(
        length_m=4000.0,
        corner_zones=[(0.35, 0.45, 420.0), (0.75, 0.85, 380.0)],
        n_samples=120,
    )
    samples = generate_dataset(
        track, VehicleParams(), BatteryParams(),
        n_samples=80, tyre_params=default_tyre_params(), seed=1,
    )
    return NeuralLapTimeMap(hidden=20, epochs=600, seed=0).fit(samples)


def test_lap_time_map_fits_simulated_laps(lap_map: NeuralLapTimeMap) -> None:
    assert lap_map.n_train >= 10
    assert lap_map.n_parameters > 0
    assert np.isfinite(lap_map.train_rmse_s)
    assert lap_map.train_rmse_s < 5.0


def test_lap_time_map_is_monotone_in_deployment(lap_map: NeuralLapTimeMap) -> None:
    low, high = lap_map.domain
    mid_mass, mid_soc = 0.5 * (low[1] + high[1]), 0.5 * (low[2] + high[2])
    slow = lap_map.predict(float(low[0]), float(mid_mass), float(mid_soc))
    fast = lap_map.predict(float(high[0]), float(mid_mass), float(mid_soc))
    assert fast <= slow


def test_lap_time_map_is_monotone_in_mass(lap_map: NeuralLapTimeMap) -> None:
    low, high = lap_map.domain
    mid_deploy, mid_soc = 0.5 * (low[0] + high[0]), 0.5 * (low[2] + high[2])
    light = lap_map.predict(float(mid_deploy), float(low[1]), float(mid_soc))
    heavy = lap_map.predict(float(mid_deploy), float(high[1]), float(mid_soc))
    assert heavy > light


def test_lap_time_map_refuses_out_of_domain() -> None:
    samples = generate_dataset(
        synthetic_circuit(), VehicleParams(), BatteryParams(),
        n_samples=20, tyre_params=default_tyre_params(), seed=2,
        deploy_range_w=(0.0, 100_000.0), mass_range_kg=(780.0, 820.0),
        soc_range=(0.5, 0.8),
    )
    model = NeuralLapTimeMap(epochs=50).fit(samples)
    with pytest.raises(ValueError):
        model.predict(500_000.0, 900.0, 0.9)


# -- Block 1 ---------------------------------------------------------------
def test_season_dp_prices_wear_and_allows_replacement() -> None:
    season = SeasonLifecycle(SeasonConfig(n_events=24, replacement_penalty=1.5))
    result = season.solve()
    assert np.isfinite(result.value)
    assert result.marginal_stress_price != 0.0
    assert result.provenance == "synthetic_parameter"


def test_season_never_replaces_when_there_is_no_wear() -> None:
    season = SeasonLifecycle(
        SeasonConfig(
            n_events=10, capacity_loss_per_event=0.0,
            resistance_growth_per_event=0.0, replacement_penalty=100.0,
        )
    )
    assert season.solve().replacement_events == ()


def test_season_replaces_under_severe_wear() -> None:
    season = SeasonLifecycle(
        SeasonConfig(
            n_events=30, capacity_loss_per_event=0.06,
            resistance_growth_per_event=0.05, replacement_penalty=0.5,
        )
    )
    assert len(season.solve().replacement_events) > 0
