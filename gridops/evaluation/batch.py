"""Frozen paired batch: controllers x rival policies x seeds, with ablations.

Every episode is seeded, paired on initial conditions and rival policy, and
retained whether it succeeds or fails. Failures are never dropped from an
aggregate; completion rate is reported alongside every metric.

Splits are explicit. A batch run against the ``test`` split must not be used to
tune anything.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .calibration import Calibration
from .controllers import (
    AmbiguityAwareController,
    Controller,
    ConvexPlannerController,
    PosteriorMeanPlanner,
    ReferenceController,
    StationaryPlanner,
)
from .runner import EpisodeRunner, EpisodeReport
from ..contracts.state import ActionFamily
from ..decision.belief import RivalBelief
from ..decision.hmm_belief import HMMBelief, HMMConfig
from ..decision.planning import ConditionalConvexPlanner, PlannerConfig
from ..decision.safety import ContactGuard

#: Declared model-error margin for the contact projection (metres). The guard
#: checks an inflated footprint, so a plan must clear the rival by this much.
CONTACT_MARGIN_M = 0.15
from ..race_value.lap_map import LapMapConfig, RaceValueMap
from ..simulation.rivals import REACTIVE_POLICIES, RivalPolicy

#: Controllers available to a batch, including ablations.
CONTROLLER_NAMES: tuple[str, ...] = (
    "reference",
    "stationary",
    "posterior_mean",
    "convex",
    "m",
    "m_convex",
    "m_hmm",
    "m_hmm_stationary",
    "m_no_continuation",
    "m_no_margin",
    "m_no_belief",
    "m_no_probe",
    "m_posterior_mean",
)

#: Default ablation matrix: a paired baseline plus the full method and
#: one-factor removals. The reference is included so paired deltas are defined.
ABLATION_NAMES: tuple[str, ...] = (
    "reference",
    "m",
    "m_no_continuation",
    "m_no_margin",
    "m_no_belief",
    "m_no_probe",
    "m_posterior_mean",
)


@dataclass(frozen=True)
class BatchManifest:
    manifest_id: str
    scenario_id: str
    split: str
    seeds: tuple[int, ...]
    rival_policies: tuple[str, ...]
    controllers: tuple[str, ...]
    created_utc: str
    code_revision: str = "unknown"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["seeds"] = list(self.seeds)
        data["rival_policies"] = list(self.rival_policies)
        data["controllers"] = list(self.controllers)
        return data


@dataclass
class EpisodeRow:
    controller: str
    rival_policy: str
    seed: int
    status: str
    split: str = ""
    error: str | None = None
    final_gap_m: float | None = None
    ego_energy_spent_j: float | None = None
    pass_events: int | None = None
    contacts: int | None = None
    catch_up_events: int | None = None
    decisions: int | None = None
    runtime_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchResult:
    manifest: BatchManifest
    rows: list[EpisodeRow] = field(default_factory=list)

    # -- rows --------------------------------------------------------------
    def row(self, controller: str, policy: str, seed: int) -> EpisodeRow | None:
        for item in self.rows:
            if (
                item.controller == controller
                and item.rival_policy == policy
                and item.seed == seed
            ):
                return item
        return None

    def controllers(self) -> list[str]:
        seen: list[str] = []
        for row in self.rows:
            if row.controller not in seen:
                seen.append(row.controller)
        return seen

    def policies(self) -> list[str]:
        seen: list[str] = []
        for row in self.rows:
            if row.rival_policy not in seen:
                seen.append(row.rival_policy)
        return seen

    # -- metrics -----------------------------------------------------------
    def completion_rate(self, controller: str) -> float:
        rows = [r for r in self.rows if r.controller == controller]
        if not rows:
            return 0.0
        return sum(1 for r in rows if r.status == "ok") / len(rows)

    def paired_deltas(
        self, controller: str, metric: str, baseline: str = "reference"
    ) -> list[float]:
        """Per-seed delta of ``metric`` against the baseline, paired on policy."""
        deltas: list[float] = []
        for policy in self.policies():
            for seed in self.manifest.seeds:
                a = self.row(controller, policy, seed)
                b = self.row(baseline, policy, seed)
                if a is None or b is None or a.status != "ok" or b.status != "ok":
                    continue
                left, right = getattr(a, metric), getattr(b, metric)
                if left is None or right is None:
                    continue
                deltas.append(left - right)
        return deltas

    def aggregate(self, baseline: str = "reference") -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for controller in self.controllers():
            rows = [r for r in self.rows if r.controller == controller and r.status == "ok"]
            gaps = [r.final_gap_m for r in rows if r.final_gap_m is not None]
            energies = [r.ego_energy_spent_j for r in rows if r.ego_energy_spent_j is not None]
            passes = [r.pass_events for r in rows if r.pass_events is not None]
            contacts = [r.contacts for r in rows if r.contacts is not None]
            catches = [r.catch_up_events for r in rows if r.catch_up_events is not None]
            deltas = self.paired_deltas(controller, "final_gap_m", baseline)
            out.append(
                {
                    "controller": controller,
                    "episodes": len([r for r in self.rows if r.controller == controller]),
                    "completed": len(rows),
                    "completion_rate": round(self.completion_rate(controller), 4),
                    "median_final_gap_m": round(statistics.median(gaps), 3) if gaps else None,
                    "mean_final_gap_m": round(statistics.fmean(gaps), 3) if gaps else None,
                    "mean_energy_spent_j": round(statistics.fmean(energies), 1) if energies else None,
                    "total_passes": sum(passes) if passes else 0,
                    "total_contacts": sum(contacts) if contacts else 0,
                    "total_catch_ups": sum(catches) if catches else 0,
                    "mean_paired_gap_delta_m": round(statistics.fmean(deltas), 3) if deltas else None,
                    "median_paired_gap_delta_m": round(statistics.median(deltas), 3) if deltas else None,
                    "paired_n": len(deltas),
                }
            )
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "aggregate": self.aggregate(),
            "rows": [r.to_dict() for r in self.rows],
        }


def build_controller(
    name: str,
    runner: EpisodeRunner,
    seed: int,
    calibration: Calibration | None = None,
    contact_margin_m: float = CONTACT_MARGIN_M,
) -> Controller:
    """Construct a controller or ablation variant by name."""
    closure_fn = calibration.closure_fn() if calibration else None
    response_fn = calibration.response_fn() if calibration else None
    sigma = calibration.response_sigma_mps if calibration else 0.8

    if name == "reference":
        return ReferenceController()
    if name == "stationary":
        return StationaryPlanner(runner.terminal_value, horizon=2, iterations=200)
    if name == "posterior_mean":
        return PosteriorMeanPlanner(runner.terminal_value, 0.5)
    if name == "convex":
        return ConvexPlannerController(
            ConditionalConvexPlanner(
                runner.track, runner.vehicle, runner.battery, runner.terminal_value,
                PlannerConfig(),
            )
        )
    if name == "m":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=False, emission_sigma_m=sigma)),
            horizon=3, iterations=300,
            contact_guard=ContactGuard(runner.track, margin_m=contact_margin_m), race_value=RaceValueMap(runner.terminal_value, LapMapConfig()), closure_fn=closure_fn, response_fn=response_fn, seed=seed,
        )
    if name == "m_convex":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=False, emission_sigma_m=sigma)),
            horizon=3, iterations=300,
            planner=ConditionalConvexPlanner(
                runner.track, runner.vehicle, runner.battery, runner.terminal_value,
                PlannerConfig(),
            ),
            contact_guard=ContactGuard(runner.track, margin_m=contact_margin_m), race_value=RaceValueMap(runner.terminal_value, LapMapConfig()), closure_fn=closure_fn, response_fn=response_fn, seed=seed,
        )
    if name == "m_hmm":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=False, emission_sigma_m=sigma)),
            horizon=3, iterations=300,
            contact_guard=ContactGuard(runner.track, margin_m=contact_margin_m), race_value=RaceValueMap(runner.terminal_value, LapMapConfig()), closure_fn=closure_fn, response_fn=response_fn, seed=seed,
        )
    if name == "m_hmm_stationary":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=True, emission_sigma_m=sigma)),
            horizon=3, iterations=300,
            contact_guard=ContactGuard(runner.track, margin_m=contact_margin_m), race_value=RaceValueMap(runner.terminal_value, LapMapConfig()), closure_fn=closure_fn, response_fn=response_fn, seed=seed,
        )
    if name == "m_no_continuation":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=False, emission_sigma_m=sigma)),
            horizon=3, iterations=300,
            contact_guard=ContactGuard(runner.track, margin_m=contact_margin_m), race_value=RaceValueMap(runner.terminal_value, LapMapConfig()), closure_fn=closure_fn, response_fn=response_fn,
            use_continuation_value=False, seed=seed,
        )
    if name == "m_no_margin":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=False, emission_sigma_m=sigma)),
            horizon=3, iterations=300,
            commitment_margin_s=-1.0,
            contact_guard=ContactGuard(runner.track, margin_m=contact_margin_m), race_value=RaceValueMap(runner.terminal_value, LapMapConfig()), closure_fn=closure_fn, response_fn=response_fn, seed=seed,
        )
    if name == "m_no_belief":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=False, emission_sigma_m=sigma)),
            horizon=3, iterations=300,
            contact_guard=ContactGuard(runner.track, margin_m=contact_margin_m), race_value=RaceValueMap(runner.terminal_value, LapMapConfig()), closure_fn=closure_fn, response_fn=response_fn,
            use_belief_update=False, seed=seed,
        )
    if name == "m_no_probe":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=False, emission_sigma_m=sigma)),
            horizon=3, iterations=300,
            contact_guard=ContactGuard(runner.track, margin_m=contact_margin_m), race_value=RaceValueMap(runner.terminal_value, LapMapConfig()), closure_fn=closure_fn, response_fn=response_fn,
            use_probe=False, seed=seed,
        )
    if name == "m_posterior_mean":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=False, emission_sigma_m=sigma)),
            horizon=3, iterations=300,
            contact_guard=ContactGuard(runner.track, margin_m=contact_margin_m), race_value=RaceValueMap(runner.terminal_value, LapMapConfig()), closure_fn=closure_fn, response_fn=response_fn,
            criterion="posterior_mean", seed=seed,
        )
    raise ValueError(f"unknown controller: {name}")


def run_batch(
    manifest: BatchManifest,
    runner_factory: Callable[[], EpisodeRunner],
    calibration: Calibration | None = None,
    contact_margin_m: float = CONTACT_MARGIN_M,
) -> BatchResult:
    """Run every controller x policy x seed. Failures are recorded, not dropped."""
    result = BatchResult(manifest=manifest)
    for controller_name in manifest.controllers:
        for policy_name in manifest.rival_policies:
            policy = RivalPolicy(policy_name)
            for seed in manifest.seeds:
                runner = runner_factory()
                start = time.perf_counter()
                try:
                    controller = build_controller(
                        controller_name, runner, seed, calibration, contact_margin_m
                    )
                    report: EpisodeReport = runner.run(controller, rival_policy=policy, seed=seed)
                    result.rows.append(
                        EpisodeRow(
                            controller=controller_name,
                            rival_policy=policy_name,
                            seed=seed,
                            status="ok",
                            split=manifest.split,
                            final_gap_m=report.final_gap_m,
                            ego_energy_spent_j=report.ego_energy_spent_j,
                            pass_events=report.pass_events,
                            contacts=report.contacts,
                            catch_up_events=report.catch_up_events,
                            decisions=len(report.decisions),
                            runtime_s=time.perf_counter() - start,
                        )
                    )
                except Exception as exc:  # a failure is a recorded result
                    result.rows.append(
                        EpisodeRow(
                            controller=controller_name,
                            rival_policy=policy_name,
                            seed=seed,
                            status="error",
                            split=manifest.split,
                            error=f"{type(exc).__name__}: {exc}",
                            runtime_s=time.perf_counter() - start,
                        )
                    )
    return result


def default_manifest(
    seeds: tuple[int, ...] = (1, 2, 3, 4, 5),
    split: str = "development",
    controllers: tuple[str, ...] = ABLATION_NAMES,
    policies: tuple[str, ...] | None = None,
    scenario_id: str = "synthetic-monza-like",
) -> BatchManifest:
    policy_names = policies or tuple(p.value for p in REACTIVE_POLICIES)
    return BatchManifest(
        manifest_id=f"{scenario_id}-{split}-{len(seeds)}seeds",
        scenario_id=scenario_id,
        split=split,
        seeds=seeds,
        rival_policies=policy_names,
        controllers=controllers,
        created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
