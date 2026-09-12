"""Contact-safety supervisor: modelled contact is infeasible, not recorded."""

from __future__ import annotations

import pytest

from gridops.decision.safety import ContactGuard
from gridops.simulation.track import synthetic_circuit


@pytest.fixture(scope="module")
def guard() -> ContactGuard:
    return ContactGuard(synthetic_circuit())


def test_contact_predicted_when_closing_on_the_centreline(guard: ContactGuard) -> None:
    contacting = guard.predicts_contact(
        ego_progress_m=100.0, ego_speed_mps=85.0, ego_lateral_m=0.0,
        rival_progress_m=110.0, rival_speed_mps=80.0, rival_lateral_m=0.0,
        ego_target_speed_mps=90.0, ego_target_lateral_m=2.5, horizon_s=3.0,
    )
    assert contacting


def test_no_contact_when_already_separated_laterally(guard: ContactGuard) -> None:
    contacting = guard.predicts_contact(
        ego_progress_m=100.0, ego_speed_mps=85.0, ego_lateral_m=3.0,
        rival_progress_m=110.0, rival_speed_mps=80.0, rival_lateral_m=0.0,
        ego_target_speed_mps=90.0, ego_target_lateral_m=3.0, horizon_s=3.0,
    )
    assert not contacting


def test_safe_speed_is_capped_while_still_behind(guard: ContactGuard) -> None:
    safe = guard.max_safe_target_speed(
        ego_progress_m=100.0, ego_speed_mps=85.0, ego_lateral_m=0.0,
        rival_progress_m=110.0, rival_speed_mps=80.0, rival_lateral_m=0.0,
        desired_target_speed_mps=90.0, ego_target_lateral_m=2.5, horizon_s=3.0,
    )
    assert safe <= 90.0
    # the capped target must not project a contact
    assert not guard.predicts_contact(
        ego_progress_m=100.0, ego_speed_mps=85.0, ego_lateral_m=0.0,
        rival_progress_m=110.0, rival_speed_mps=80.0, rival_lateral_m=0.0,
        ego_target_speed_mps=safe, ego_target_lateral_m=2.5, horizon_s=3.0,
    )


def test_closing_is_permitted_once_laterally_clear(guard: ContactGuard) -> None:
    safe = guard.max_safe_target_speed(
        ego_progress_m=100.0, ego_speed_mps=90.0, ego_lateral_m=3.0,
        rival_progress_m=110.0, rival_speed_mps=80.0, rival_lateral_m=0.0,
        desired_target_speed_mps=95.0, ego_target_lateral_m=3.0, horizon_s=3.0,
    )
    assert safe == pytest.approx(95.0)
