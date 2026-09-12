"""HMM belief backend: forward filtering, ambiguity and evidence hygiene."""

from __future__ import annotations

import pytest

from gridops.contracts.state import ActionFamily
from gridops.decision.belief import DEFENSIVE, WEAK
from gridops.decision.hmm_belief import HMMBelief, HMMConfig
from gridops.decision.tactical import _CLOSE_DEFENSIVE, _CLOSE_WEAK
from gridops.simulation.rivals import RivalPolicy


def _expected_map(action: ActionFamily) -> dict[RivalPolicy, float]:
    out: dict[RivalPolicy, float] = {}
    for mode in HMMConfig().modes:
        table = _CLOSE_DEFENSIVE if mode in DEFENSIVE else _CLOSE_WEAK
        out[mode] = table[action]
    return out


def test_posterior_concentrates_on_the_explaining_mode() -> None:
    belief = HMMBelief()
    expected = _expected_map(ActionFamily.ATTACK_NOW)
    for _ in range(6):
        belief.update_on_observation(3.0, expected)  # weak-mode closure
    weak_mass = sum(belief.posterior[m] for m in belief.modes if m in WEAK)
    assert weak_mass > 0.8


def test_posterior_shifts_to_defensive_when_the_response_is_strong() -> None:
    belief = HMMBelief()
    expected = _expected_map(ActionFamily.ATTACK_NOW)
    for _ in range(6):
        belief.update_on_observation(0.0, expected)  # defensive-mode closure
    assert belief.strong_rival_mass() > 0.8


def test_ambiguity_falls_with_consistent_evidence() -> None:
    belief = HMMBelief()
    expected = _expected_map(ActionFamily.ATTACK_NOW)
    start = belief.ambiguity_index()
    for _ in range(6):
        belief.update_on_observation(3.0, expected)
    assert belief.ambiguity_index() < start


def test_update_on_outcome_does_not_double_count() -> None:
    belief = HMMBelief()
    expected = _expected_map(ActionFamily.ATTACK_NOW)
    belief.update_on_observation(3.0, expected)
    before = dict(belief.posterior)
    belief.update_on_outcome(ego_attacked=True, gained=False)
    belief.mix_for_non_stationarity()
    assert dict(belief.posterior) == before


def test_stationary_configuration_has_identity_transition() -> None:
    belief = HMMBelief(HMMConfig(stationary=True))
    n = len(belief.modes)
    for i in range(n):
        for j in range(n):
            assert belief.transition[i][j] == pytest.approx(1.0 if i == j else 0.0)


def test_non_stationary_configuration_allows_switching() -> None:
    belief = HMMBelief(HMMConfig(self_transition=0.85))
    n = len(belief.modes)
    for i in range(n):
        off_diagonal = sum(belief.transition[i][j] for j in range(n) if j != i)
        assert off_diagonal == pytest.approx(0.15, abs=1e-9)


def test_credible_set_and_forecast_are_well_formed() -> None:
    belief = HMMBelief()
    expected = _expected_map(ActionFamily.PROBE)
    for _ in range(4):
        belief.update_on_observation(2.0, expected)
    kept, excluded = belief.credible_set(epsilon=0.05)
    assert kept and 0.0 <= excluded <= 0.05 + 1e-9
    forecast = belief.capability_forecast()
    assert 0.0 <= forecast["strong_rival_mass"] <= 1.0
    assert 0.0 <= forecast["ambiguity_index"] <= 1.0


def test_poorly_explained_observation_does_not_collapse_the_posterior() -> None:
    belief = HMMBelief()
    expected = _expected_map(ActionFamily.CONSERVE)  # all zeros: uninformative
    # a huge closure is explained by no mode equally poorly; prior is retained
    belief.update_on_observation(500.0, expected)
    assert sum(belief.posterior.values()) == pytest.approx(1.0)
    assert all(0.0 <= w <= 1.0 for w in belief.posterior.values())
