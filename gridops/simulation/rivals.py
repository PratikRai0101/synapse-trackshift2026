"""Reactive rival policy families.

The base-paper assumption treats rivals as stationary. These families exist so
the reactive assumption can be tested against it. All are declared, bounded
policies -- not models of a real driver's intent.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..contracts.state import ActionFamily


class RivalPolicy(str, Enum):
    STATIONARY = "stationary"   # fixed reference, ignores the ego (base-paper assumption)
    IGNORING = "ignoring"       # ignores ego feints, holds reference
    MATCHING = "matching"       # defends by matching deployment
    AGGRESSIVE = "aggressive"   # attacks when close
    CONSERVING = "conserving"   # saves energy, gives up little
    DELAYED = "delayed"         # reacts only after a delay


@dataclass(frozen=True)
class RivalPolicyConfig:
    deploy_power_w: float = 120_000.0
    defend_power_w: float = 150_000.0
    conserve_power_w: float = 15_000.0
    reaction_delay_s: float = 1.0
    base_target_speed_mps: float = 80.0
    attack_target_speed_mps: float = 90.0
    close_gap_m: float = 25.0


def rival_control(
    policy: RivalPolicy,
    ego_family: ActionFamily,
    gap_m: float,
    since_ego_attack_s: float,
    config: RivalPolicyConfig,
) -> tuple[float, float]:
    """Return ``(p_k_dc_w, target_speed_mps)`` for the rival this step.

    ``gap_m`` is signed ego-minus-rival progress: negative means the ego is
    ahead. Policies only observe public state, never ego battery truth.
    """
    ego_attacking = ego_family in (ActionFamily.ATTACK_NOW, ActionFamily.PROBE)
    close = abs(gap_m) <= config.close_gap_m

    if policy in (RivalPolicy.STATIONARY, RivalPolicy.IGNORING):
        return config.deploy_power_w, config.base_target_speed_mps

    if policy is RivalPolicy.CONSERVING:
        return config.conserve_power_w, config.base_target_speed_mps

    if policy is RivalPolicy.MATCHING:
        if ego_attacking and close:
            return config.defend_power_w, config.attack_target_speed_mps
        return config.deploy_power_w, config.base_target_speed_mps

    if policy is RivalPolicy.AGGRESSIVE:
        if close:
            return config.defend_power_w, config.attack_target_speed_mps
        return config.deploy_power_w, config.base_target_speed_mps

    if policy is RivalPolicy.DELAYED:
        if ego_attacking and close and since_ego_attack_s >= config.reaction_delay_s:
            return config.defend_power_w, config.attack_target_speed_mps
        return config.deploy_power_w, config.base_target_speed_mps

    return config.deploy_power_w, config.base_target_speed_mps


def rival_target_speed(
    policy: RivalPolicy,
    ego_family: ActionFamily,
    gap_m: float,
    since_ego_attack_s: float,
    config: RivalPolicyConfig,
) -> float:
    """Declared target speed for a policy, independent of the plant.

    Used as the default response model when no calibrated model is supplied.
    """
    return rival_control(policy, ego_family, gap_m, since_ego_attack_s, config)[1]


#: Policy families used when a benchmark wants reactive opponents.
REACTIVE_POLICIES: tuple[RivalPolicy, ...] = (
    RivalPolicy.MATCHING,
    RivalPolicy.AGGRESSIVE,
    RivalPolicy.CONSERVING,
    RivalPolicy.DELAYED,
    RivalPolicy.IGNORING,
)
