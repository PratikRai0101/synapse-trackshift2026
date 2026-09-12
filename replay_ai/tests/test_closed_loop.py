from src.intelligence.closed_loop import ClosedLoopSimulator, HiddenRivalMode


def test_closed_loop_produces_public_observations_without_hidden_truth():
    sim = ClosedLoopSimulator(HiddenRivalMode.DEPLETE)
    steps = sim.run(10)
    assert len(steps) == 10
    assert all(step.observation.gap_s >= 0 for step in steps)
    assert not hasattr(steps[0].observation, "rival_mode")
    assert all(step.decision.command in {"BURN", "HARVEST", "PROACTIVE TRAP"}
               for step in steps)


def test_different_actions_change_future_vehicle_state():
    conservative = ClosedLoopSimulator(HiddenRivalMode.CONSERVE)
    aggressive = ClosedLoopSimulator(HiddenRivalMode.DEPLETE)
    conservative.run(20)
    aggressive.run(20)
    assert (conservative.ego.speed_kmh != aggressive.ego.speed_kmh or
            conservative.ego.energy != aggressive.ego.energy or
            conservative.ego.gap_s != aggressive.ego.gap_s)


def test_closed_loop_applies_zone_mpc_output():
    sim = ClosedLoopSimulator(HiddenRivalMode.DEPLETE)
    sim.step()
    assert sim.last_mpc_result is not None
    assert sim.last_mpc_result.success
    assert 0.0 <= sim.last_mpc_result.power_fraction <= 1.0


def test_hidden_rival_policy_is_not_exposed_to_model():
    sim = ClosedLoopSimulator(HiddenRivalMode.CONSERVE)
    sim.step()
    assert not hasattr(sim.model.last_hmm, "rival_mode")
    assert sim.model.last_hmm is not None
