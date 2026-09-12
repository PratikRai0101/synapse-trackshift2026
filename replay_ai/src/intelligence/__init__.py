"""AI Motorsport Intelligence: real-time race-engineering decision support.

This package turns the replay's telemetry into *decisions*:

- :mod:`energy`      estimates energy deployment / harvest and battery state.
- :mod:`overtake`    scores overtake windows on reward vs. risk.
- :mod:`race_engineer` combines both into a live recommendation + compliance.

FastF1 exposes no ERS/battery channel, so energy values are transparent model
estimates derived from driver inputs. They are labelled as estimates in the UI.
"""

from .energy import (
    EnergyEstimator,
    EnergySnapshot,
    DeploymentAdvice,
    recommend_deployment_mode,
    step_energy,
)
from .config import ModelConfig, DEFAULT_CONFIG, load_config
from .overtake import OvertakeAssessment, evaluate_overtake_window
from .race_engineer import DecisionReport, RaceEngineer
from .telemetry_adapter import PublicTelemetryFrame, PublicTelemetryAdapter
from .lap_strategy import LapTimeSample, LapTimeMap, LapTarget, StrategyConfig, RaceEnergyPlanner
from .lap_dataset import extract_lap_samples
from .closed_loop import (
    HiddenRivalMode, SimulationConfig, CarState, PublicSimulationObservation,
    SimulationStep, ClosedLoopSimulator,
)
from .socp_envelope import SOCPConfig, SOCPPoint, SOCPProfile, SOCPPerformanceEnvelope
from .control_layers import (
    EnvelopeConfig, EnvelopePoint, PerformanceEnvelope, ScenarioAction,
    Level2Plan, BoundedScenarioPlanner, Level1Command, FastExecutionController,
)
from .hierarchical import (
    ERSMode, OverrideMode, TyreState, HMMState, STATES,
    RivalTelemetry, RivalFeatures, FeatureExtractor, HMMResult, FortyStateHMM,
    SeasonLifecycleManager, SOHDecision, MotorsportIntelligence,
    TacticalDecision,
)

__all__ = [
    "EnergyEstimator",
    "EnergySnapshot",
    "DeploymentAdvice",
    "recommend_deployment_mode",
    "step_energy",
    "ModelConfig",
    "DEFAULT_CONFIG",
    "load_config",
    "OvertakeAssessment",
    "evaluate_overtake_window",
    "DecisionReport",
    "RaceEngineer",
    "ERSMode",
    "OverrideMode",
    "TyreState",
    "HMMState",
    "STATES",
    "RivalTelemetry",
    "RivalFeatures",
    "FeatureExtractor",
    "HMMResult",
    "FortyStateHMM",
    "SeasonLifecycleManager",
    "SOHDecision",
    "MotorsportIntelligence",
    "TacticalDecision",
    "PublicTelemetryFrame",
    "PublicTelemetryAdapter",
    "LapTimeSample",
    "LapTimeMap",
    "LapTarget",
    "StrategyConfig",
    "RaceEnergyPlanner",
    "extract_lap_samples",
    "SOCPConfig",
    "SOCPPoint",
    "SOCPProfile",
    "SOCPPerformanceEnvelope",
    "EnvelopeConfig",
    "EnvelopePoint",
    "PerformanceEnvelope",
    "ScenarioAction",
    "Level2Plan",
    "BoundedScenarioPlanner",
    "Level1Command",
    "FastExecutionController",
    "HiddenRivalMode",
    "SimulationConfig",
    "CarState",
    "PublicSimulationObservation",
    "SimulationStep",
    "ClosedLoopSimulator",
]
