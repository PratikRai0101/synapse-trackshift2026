"""Judge-facing decision view, bookmarks and presentation helpers.

The replay application has a useful engineering HUD, but the intelligence story
needs a projection designed for a judge: one recommendation, the evidence that
caused it, the uncertainty around rival capability, and the alternatives that
were rejected. This module keeps that projection independent from the Arcade
window so it can be tested without an OpenGL context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import arcade

from src.ui_theme import (
    AMBER,
    DANGER,
    EDGE,
    ELECTRIC,
    GREEN,
    MUTED,
    PANEL,
    TEXT,
    chip_width,
    draw_chip,
    draw_meter,
    draw_panel,
)

RGB = tuple[int, int, int]

COMMAND_LABELS = {
    "BURN": "ATTACK NOW",
    "HARVEST": "PROTECT RESERVE",
    "PROACTIVE TRAP": "PROBE / TRAP",
}
COMMAND_COLORS = {
    "BURN": DANGER,
    "HARVEST": GREEN,
    "PROACTIVE TRAP": AMBER,
}
COMMAND_COLOR_NAMES = {
    "BURN": "RED",
    "HARVEST": "GREEN",
    "PROACTIVE TRAP": "AMBER",
}
MODE_COLORS = {
    "H": ELECTRIC,
    "M": (150, 160, 180),
    "Lharvest": GREEN,
    "Lderate": DANGER,
}
MODE_DESCRIPTIONS = {
    "H": "high deployment available",
    "M": "medium capability",
    "Lharvest": "deliberately saving energy",
    "Lderate": "physically depleted",
}
BOOKMARK_HOTKEYS = ("5", "6", "7", "8", "9", "0")


@dataclass(frozen=True)
class JudgeModeProbability:
    """One marginal ERS capability probability for the judge view."""

    mode: str
    probability: float
    description: str
    color: RGB


@dataclass(frozen=True)
class JudgeModeUnits:
    """Units shown by the judge view; percentages are beliefs, not SOC."""

    speed: str = "km/h"
    gap: str = "s"
    energy: str = "EU (estimated)"
    probability: str = "% belief"


@dataclass(frozen=True)
class JudgeActionOption:
    """A human-readable tactical alternative from the planner."""

    command: str
    score: float
    energy_delta_eu: float
    gap_gain_s: float
    continuation_value: float
    selected: bool


@dataclass(frozen=True)
class JudgeModeSnapshot:
    """Complete immutable input to :class:`JudgeModePanel`."""

    driver: str
    position: Any
    lap: Any
    command: str
    command_label: str
    command_color: RGB
    command_color_name: str
    confidence: float
    rival_label: str
    rival_modes: tuple[JudgeModeProbability, ...]
    evidence: tuple[str, ...]
    explanation: str
    options: tuple[JudgeActionOption, ...]
    own_energy_eu: float
    lap_energy_target: Optional[float]
    reserve_after_lap: Optional[float]
    target_speed_kmh: Optional[float]
    envelope_status: str
    envelope_residual: Optional[float]
    model_status: str
    lap_map_status: str
    hmm_source: str
    provenance: tuple[str, ...] = ()
    units: JudgeModeUnits = JudgeModeUnits()
    search_particles: int = 0
    search_histories: int = 0
    layer_activity: tuple[str, ...] = ()
    gap_s: Optional[float] = None
    timestamp_s: Optional[float] = None


@dataclass(frozen=True)
class JudgeBookmark:
    """A deterministic point in a recorded replay, never a new observation."""

    frame_index: int
    hotkey: str
    title: str
    subtitle: str


class JudgeModeModel:
    """Project backend records into judge-readable, explicitly estimated data."""

    @staticmethod
    def _confidence(command: str, probabilities: Mapping[str, float]) -> float:
        if command == "BURN":
            value = probabilities.get("Lderate", 0.0)
        elif command == "HARVEST":
            value = probabilities.get("Lharvest", 0.0)
        else:
            # A probe is useful precisely when capability is unresolved. Its
            # confidence is therefore the probability mass not committed to
            # either extreme response, rather than a fabricated certainty.
            value = (1.0 - probabilities.get("Lderate", 0.0)
                     - probabilities.get("Lharvest", 0.0))
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _evidence(report: Any) -> tuple[str, ...]:
        hmm = getattr(report, "rival_hmm", None)
        features = getattr(hmm, "features", None)
        if features is None:
            return ("Public telemetry evidence unavailable",)
        evidence: list[str] = []
        if features.throttle_clip > 0.0:
            evidence.append(
                f"Super-clipping persisted: {features.throttle_clip * 100:.0f}%"
            )
        if features.dv_baseline < -0.5:
            evidence.append(
                f"Speed {abs(features.dv_baseline):.1f} km/h below sector baseline"
            )
        elif features.dv_baseline > 0.5:
            evidence.append(
                f"Speed {features.dv_baseline:.1f} km/h above sector baseline"
            )
        if features.dgap > 0.02:
            evidence.append(f"Gap closing response: {features.dgap:+.2f} s")
        elif features.dgap < -0.02:
            evidence.append(f"Rival opening response: {features.dgap:+.2f} s")
        if features.aero >= 0.5:
            evidence.append("Active-aero / DRS proxy: ON")
        if getattr(features, "tyre_life", 0.0) > 0.0:
            evidence.append(f"Public tyre life: {features.tyre_life:.0f} laps")
        return tuple(evidence or ("Public telemetry updated; evidence remains ambiguous",))

    @classmethod
    def from_report(cls, report: Any, gap_s: Optional[float] = None,
                    timestamp_s: Optional[float] = None) -> JudgeModeSnapshot:
        tactical = getattr(report, "tactical", None)
        hmm = getattr(report, "rival_hmm", None)
        metrics = getattr(report, "runtime_metrics", {}) or {}
        probabilities = {
            key: max(0.0, float(value))
            for key, value in getattr(hmm, "ers_probabilities", {}).items()
        }
        total = sum(probabilities.values())
        if total > 0.0:
            probabilities = {key: value / total for key, value in probabilities.items()}
        modes = tuple(
            JudgeModeProbability(
                mode,
                probabilities.get(mode, 0.0),
                MODE_DESCRIPTIONS[mode],
                MODE_COLORS[mode],
            )
            for mode in ("H", "M", "Lharvest", "Lderate")
        )
        command = getattr(tactical, "command", "PROACTIVE TRAP")
        action_scores = getattr(report, "tactical_action_scores", ())
        options = tuple(
            JudgeActionOption(
                command=str(option.command),
                score=float(option.score),
                energy_delta_eu=float(option.energy_cost),
                gap_gain_s=float(option.expected_gap_change_s),
                continuation_value=float(option.continuation_value),
                selected=str(option.command) == command,
            )
            for option in action_scores
        )
        if not options:
            action_values = metrics.get("scenario_values", {})
            risk_values = metrics.get("scenario_risk_values", {})
            options = tuple(
                JudgeActionOption(
                    name,
                    float(action_values.get(name, 0.0)),
                    0.0,
                    0.0,
                    float(risk_values.get(name, 0.0)),
                    name == command,
                )
                for name in ("BURN", "HARVEST", "PROACTIVE TRAP")
            )

        lap_plan = getattr(report, "lap_plan", None)
        first_lap = lap_plan[0] if lap_plan else None
        residual = metrics.get("socp_residual")
        energy = getattr(report, "energy", None)
        return JudgeModeSnapshot(
            driver=str(getattr(report, "code", "-")),
            position=getattr(report, "position", "-"),
            lap=getattr(energy, "lap", "-"),
            command=command,
            command_label=COMMAND_LABELS.get(command, command),
            command_color=COMMAND_COLORS.get(command, ELECTRIC),
            command_color_name=COMMAND_COLOR_NAMES.get(command, "BLUE"),
            confidence=cls._confidence(command, probabilities),
            rival_label="ERS CAPABILITY BELIEF",
            rival_modes=modes,
            evidence=cls._evidence(report),
            explanation=str(getattr(tactical, "reason", "Waiting for public evidence")),
            options=options,
            own_energy_eu=max(0.0, min(100.0, float(getattr(energy, "soc", 0.0)))),
            lap_energy_target=(
                float(getattr(first_lap, "deploy_energy"))
                if first_lap is not None
                else getattr(tactical, "lap_energy_target", None)
            ),
            reserve_after_lap=(
                float(getattr(first_lap, "reserve_after_lap"))
                if first_lap is not None else None
            ),
            target_speed_kmh=(
                float(getattr(tactical, "target_speed_kmh"))
                if tactical is not None else None
            ),
            envelope_status=(
                "FEASIBLE" if metrics.get(
                    "socp_feasible", getattr(tactical, "envelope_feasible", False)
                ) else "CHECK"
            ),
            envelope_residual=(float(residual) if residual is not None else None),
            model_status=(
                "SYNTHETIC ARTIFACT" if metrics.get("hmm_source", "default") != "default"
                else "FALLBACK"
            ),
            lap_map_status=(
                "SYNTHETIC FIT" if metrics.get("lap_map_source", "unavailable")
                != "unavailable" else "UNAVAILABLE"
            ),
            hmm_source=str(metrics.get("hmm_source", "default")),
            provenance=(
                "INPUT: public speed / throttle / brake / gap / aero proxy",
                f"HMM: {str(metrics.get('hmm_source', 'default'))}",
                f"LAP MAP: {str(metrics.get('lap_map_source', 'unavailable'))}",
                "RIVAL SOC: unavailable; capability belief only",
            ),
            units=JudgeModeUnits(),
            search_particles=int(metrics.get("scenario_particles", 0) or 0),
            search_histories=int(metrics.get("scenario_histories", 0) or 0),
            layer_activity=(
                "HMM 40-state belief",
                ("POMCP search" if metrics.get("scenario_particles", 0)
                 else "bounded action search"),
                "SOCP performance envelope",
                "zone MPC execution",
            ),
            gap_s=gap_s,
            timestamp_s=timestamp_s,
        )


def build_bookmarks(frame_count: int, total_laps: Optional[int]) -> tuple[JudgeBookmark, ...]:
    """Build six stable, non-overlapping moments for a judge demonstration."""
    count = max(0, int(frame_count))
    if count == 0:
        return ()
    last = count - 1
    fractions = (0.05, 0.20, 0.40, 0.60, 0.80, 0.95)
    labels = (
        ("BASELINE", "Establish public evidence"),
        ("ERS SIGNAL", "Watch the capability belief form"),
        ("TACTICAL WINDOW", "Compare attack and conserve"),
        ("ENERGY CONSEQUENCE", "See the remaining-race cost"),
        ("LATE-RACE RESERVE", "Re-evaluate with less resource"),
        ("FINISH CONTEXT", "Review the final decision state"),
    )
    points: list[JudgeBookmark] = []
    used: set[int] = set()
    for fraction, (title, subtitle), hotkey in zip(
        fractions[: min(len(fractions), count)],
        labels[: min(len(labels), count)],
        BOOKMARK_HOTKEYS[: min(len(BOOKMARK_HOTKEYS), count)],
    ):
        point = min(last, max(0, int(round(last * fraction))))
        if point in used:
            candidates = sorted(range(count), key=lambda value: abs(value - point))
            point = next((value for value in candidates if value not in used), point)
        used.add(point)
        points.append(JudgeBookmark(point, hotkey, title, subtitle))
    return tuple(points)


class JudgeModeController:
    """Pure interaction state for Judge Mode and its bookmark selector."""

    def __init__(self, enabled: bool = False,
                 bookmarks: Sequence[JudgeBookmark] = ()) -> None:
        self.enabled = bool(enabled)
        self.bookmarks = tuple(bookmarks)
        self.active_index: Optional[int] = None

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def select(self, index: int) -> Optional[JudgeBookmark]:
        if not self.bookmarks:
            self.active_index = None
            return None
        self.active_index = max(0, min(len(self.bookmarks) - 1, int(index)))
        self.enabled = True
        return self.bookmarks[self.active_index]

    def select_hotkey(self, hotkey: str) -> Optional[JudgeBookmark]:
        try:
            return self.select(BOOKMARK_HOTKEYS.index(str(hotkey)))
        except ValueError:
            return None

    def step_bookmark(self, direction: int) -> Optional[JudgeBookmark]:
        if not self.bookmarks:
            return None
        current = self.active_index if self.active_index is not None else 0
        return self.select((current + (1 if direction >= 0 else -1)) % len(self.bookmarks))


@dataclass(frozen=True)
class PanelBounds:
    left: float
    bottom: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def top(self) -> float:
        return self.bottom + self.height


class JudgeModePanel:
    """Compact, docked broadcast panel for a :class:`JudgeModeSnapshot`."""

    def __init__(self, width: float = 980.0, height: float = 228.0,
                 bottom_y: float = 130.0) -> None:
        self.width = width
        self.height = height
        self.bottom_y = bottom_y
        self._texts: dict[str, arcade.Text] = {}
        self.bookmark_rects: list[tuple[int, float, float, float, float]] = []

    def _t(self, key: str, text: str, x: float, y: float, size: int,
           color: RGB = TEXT, bold: bool = False,
           anchor_x: str = "left") -> None:
        obj = self._texts.get(key)
        if obj is None:
            obj = arcade.Text(text, x, y, color, size, bold=bold,
                              anchor_x=anchor_x, anchor_y="center")
            self._texts[key] = obj
        else:
            obj.text = text
            obj.x = x
            obj.y = y
            obj.color = color
            obj.font_size = size
            obj.bold = bold
        obj.draw()

    def layout_bounds(self, window_width: float, window_height: float,
                      left_ui_margin: float, right_ui_margin: float) -> PanelBounds:
        left_bound = float(left_ui_margin) + 4.0
        right_bound = float(window_width - right_ui_margin - 10.0)
        available = right_bound - left_bound
        if available < 700.0:
            left_bound, right_bound = 16.0, float(window_width - 16.0)
            available = right_bound - left_bound
        width = min(self.width, available - 6.0)
        height = min(self.height, max(190.0, float(window_height) * 0.33))
        bottom = max(130.0, min(self.bottom_y, float(window_height) * 0.20))
        return PanelBounds(
            left=(left_bound + right_bound - width) / 2.0,
            bottom=bottom,
            width=width,
            height=height,
        )

    def required_bottom_reserve(self, window_width: float, window_height: float,
                                left_ui_margin: float,
                                right_ui_margin: float) -> float:
        return self.layout_bounds(
            window_width, window_height, left_ui_margin, right_ui_margin
        ).top + 12.0

    def draw(self, window: Any, snapshot: Optional[JudgeModeSnapshot],
             bookmarks: Sequence[JudgeBookmark] = (),
             active_bookmark: Optional[int] = None,
             branch: Any = None, status_text: Optional[str] = None,
             visible: bool = True) -> None:
        if not visible or snapshot is None:
            return
        bounds = self.layout_bounds(
            window.width,
            window.height,
            getattr(window, "left_ui_margin", 340),
            getattr(window, "right_ui_margin", 260),
        )
        width, height = bounds.width, bounds.height
        left, bottom, top = bounds.left, bounds.bottom, bounds.top
        cx, cy = left + width / 2.0, bottom + height / 2.0
        pad = 18.0
        draw_panel(cx, cy, width, height, fill=PANEL, fill_alpha=245,
                   edge=EDGE, edge_width=1, accent=snapshot.command_color,
                   accent_width=7)

        self._t("header", "AI RACE STRATEGIST", left + pad, top - 17, 12,
                 MUTED, bold=True)
        draw_chip(left + pad + 205, top - 17, "JUDGE MODE", ELECTRIC,
                  size=8, height=16, pad_x=6)
        self._t(
            "source",
            f"HMM {('SYNTHETIC' if 'SYNTHETIC' in snapshot.model_status else snapshot.model_status)}  •  "
            f"LAP MAP {('SYNTHETIC' if 'SYNTHETIC' in snapshot.lap_map_status else snapshot.lap_map_status)}  •  "
            "RIVAL SOC UNAVAILABLE",
            left + width - pad, top - 17, 7, MUTED, anchor_x="right",
        )
        total_laps = getattr(window, "total_laps", "-") or "-"
        context = f"{snapshot.driver} P{snapshot.position} • LAP {snapshot.lap}/{total_laps}"
        if active_bookmark is not None and active_bookmark < len(bookmarks):
            bookmark = bookmarks[active_bookmark]
            context += f" • SCENARIO {bookmark.hotkey}: {bookmark.title}"
        self._t("context", context, left + width - pad, top - 34, 9,
                 TEXT, bold=True, anchor_x="right")

        command_x = left + pad + 4
        command_top = top - 50
        self._t("recommend", "RECOMMENDATION", command_x, command_top, 10,
                 MUTED, bold=True)
        self._t("command", snapshot.command_label, command_x, command_top - 25,
                 20, snapshot.command_color, bold=True)
        confidence_y = command_top - 49
        self._t("confidence", f"{snapshot.confidence * 100:.0f}% confidence",
                 command_x, confidence_y, 11, TEXT, bold=True)
        draw_meter(command_x, confidence_y - 16, 190, 8,
                   snapshot.confidence, snapshot.command_color)
        self._t(
            "target",
            (f"TARGET {snapshot.target_speed_kmh:.0f} km/h"
             if snapshot.target_speed_kmh is not None else "TARGET pending"),
            command_x, confidence_y - 31, 8, MUTED,
        )
        self._t("energy", f"OWN STORE (EST.) {snapshot.own_energy_eu:.0f} EU",
                 command_x, confidence_y - 45, 8, MUTED)
        lap_budget = (
            f"LAP TARGET {snapshot.lap_energy_target:.1f} EU"
            if snapshot.lap_energy_target is not None else "LAP TARGET pending"
        )
        if snapshot.reserve_after_lap is not None:
            lap_budget += f"  •  RESERVE {snapshot.reserve_after_lap:.1f} EU"
        self._t("lap_budget", lap_budget, command_x, confidence_y - 59,
                 7, MUTED)
        self._t("validity", "VALID UNTIL NEXT OBSERVATION", command_x,
                 confidence_y - 73, 7, MUTED)

        belief_x = left + min(300.0, width * 0.31)
        belief_top = top - 50
        self._t("belief_header", snapshot.rival_label, belief_x, belief_top, 10,
                 MUTED, bold=True)
        for index, mode in enumerate(snapshot.rival_modes):
            y = belief_top - 23 - index * 23
            self._t(f"mode_label_{index}", mode.mode, belief_x, y, 10,
                     mode.color, bold=True)
            meter_left = belief_x + 70
            meter_width = max(80.0, min(190.0, width * 0.20))
            draw_meter(meter_left, y, meter_width, 10,
                       mode.probability, mode.color)
            self._t(f"mode_value_{index}", f"{mode.probability * 100:.0f}%",
                     meter_left + meter_width + 8, y, 10, TEXT, bold=True)

        why_x = left + width - max(250.0, width * 0.27)
        why_top = top - 50
        self._t("why_header", "WHY THIS CHANGED", why_x, why_top, 10,
                 MUTED, bold=True)
        for index, evidence in enumerate(snapshot.evidence[:3]):
            self._t(f"evidence_{index}", f"• {evidence}", why_x,
                     why_top - 23 - index * 18, 7, TEXT)
        self._t("why_footer", snapshot.explanation[:48], why_x,
                 why_top - 82, 7, snapshot.command_color)
        layers = "  →  ".join(
            ("HMM40", "POMCP" if snapshot.search_particles else "SEARCH",
             "SOCP", "MPC")
        )
        self._t("layers", f"LAYER ACTIVITY  {layers}", why_x,
                 why_top - 102, 7, ELECTRIC, bold=True)

        options_top = top - 160
        if branch is not None and getattr(branch, "outcomes", ()):
            self._t("alternatives", "COUNTERFACTUAL BRANCH • PUBLIC START",
                     left + pad, options_top, 9, ELECTRIC, bold=True)
            for index, outcome in enumerate(branch.outcomes[:3]):
                y = options_top - 18 - index * 16
                color = snapshot.command_color if outcome.action == snapshot.command else MUTED
                self._t(f"branch_name_{index}", outcome.action, left + pad, y, 9,
                         color, bold=outcome.action == snapshot.command)
                self._t(
                    f"branch_gap_{index}",
                    f"Δ gap {getattr(outcome, 'gap_change_s', 0.0):+.2f}s  "
                    f"→ {outcome.final_gap_s:.2f}s",
                    left + pad + 140, y, 8, TEXT,
                )
                self._t(f"branch_energy_{index}",
                         f"store {outcome.final_energy:.1f} EU  deploy {outcome.energy_deployed:.1f} EU",
                         left + pad + 280, y, 8, MUTED)
                self._t(f"branch_modes_{index}",
                         f"{outcome.plausible_modes} plausible responses",
                         left + width - pad, y, 8, color, anchor_x="right")
        else:
            search_title = (
                f"BOUNDED POMCP ALTERNATIVES  •  {snapshot.search_particles} PARTICLES"
                if snapshot.search_particles else "TACTICAL ALTERNATIVES"
            )
            self._t("alternatives", search_title, left + pad,
                     options_top, 9, MUTED, bold=True)
            option_x = left + pad
            for index, option in enumerate(snapshot.options[:3]):
                y = options_top - 18 - index * 16
                color = snapshot.command_color if option.selected else MUTED
                marker = "SELECTED" if option.selected else "REJECTED"
                self._t(f"option_name_{index}", option.command, option_x, y, 9,
                         color, bold=option.selected)
                self._t(f"option_status_{index}", marker, option_x + 112, y, 8,
                         color, bold=option.selected)
                self._t(f"option_gain_{index}", f"gap +{option.gap_gain_s:.2f}s",
                         option_x + 210, y, 8, TEXT)
                self._t(f"option_energy_{index}",
                         f"energy {option.energy_delta_eu:+.1f} EU",
                         option_x + 300, y, 8, MUTED)
                self._t(f"option_value_{index}",
                         f"continuation {option.continuation_value:+.2f}",
                         option_x + 430, y, 8, MUTED)
                self._t(f"option_score_{index}", f"score {option.score:+.2f}",
                         left + width - pad, y, 8, color, anchor_x="right")

        footer_y = bottom + 11
        envelope = f"ENVELOPE {snapshot.envelope_status}"
        if snapshot.envelope_residual is not None:
            envelope += f"  residual {snapshot.envelope_residual:.3g}"
        self._t("footer_left", envelope, left + pad, footer_y, 8,
                 GREEN if snapshot.envelope_status == "FEASIBLE" else AMBER)
        if branch is not None:
            self._t("branch", getattr(branch, "status_text", "COUNTERFACTUAL READY"),
                     left + width / 2, footer_y, 9, ELECTRIC, bold=True,
                     anchor_x="center")
        else:
            self._t(
                "controls",
                status_text or "J ENGINEERING VIEW   5–0 SCENARIO BOOKMARKS   C SIMULATE",
                left + width - pad, footer_y, 8,
                ELECTRIC if status_text else MUTED, anchor_x="right",
            )

        # Keyboard bookmarks stay available through 5–0/N/P and are named in
        # the header when selected. Avoid a second chip rail over playback
        # controls; the circuit remains the visual priority.
        self.bookmark_rects = []

    def bookmark_at(self, x: float, y: float) -> Optional[int]:
        """Return a clicked bookmark index from the most recent draw."""
        for index, left, bottom, right, top in self.bookmark_rects:
            if left <= x <= right and bottom <= y <= top:
                return index
        return None


@dataclass(frozen=True)
class BranchStart:
    """Publicly observed state from which a counterfactual branch begins."""

    frame_index: int
    timestamp_s: float
    driver: str
    rival: str
    own_speed_kmh: float
    rival_speed_kmh: float
    gap_s: float
    own_energy: float
    battery_temperature: float = 70.0
    battery_soh: float = 1.0
    lap: int = 1


@dataclass(frozen=True)
class CounterfactualOutcome:
    """Outcome averaged across plausible hidden rival responses."""

    action: str
    final_gap_s: float
    gap_change_s: float
    final_energy: float
    final_speed_kmh: float
    energy_deployed: float
    energy_recovered: float
    plausible_modes: int


@dataclass(frozen=True)
class CounterfactualReport:
    """Separate simulation result; never a mutation of recorded replay data."""

    run_mode: str
    source_frame_index: int
    source_timestamp_s: float
    driver: str
    rival: str
    outcomes: tuple[CounterfactualOutcome, ...]

    @property
    def status_text(self) -> str:
        modes = max((outcome.plausible_modes for outcome in self.outcomes), default=0)
        return (
            f"COUNTERFACTUAL • FROM FRAME {self.source_frame_index} • "
            f"{modes} PLAUSIBLE MODES • {len(self.outcomes)} ACTIONS"
        )


def run_counterfactual(
    start: BranchStart,
    actions: Sequence[str] = ("BURN", "HARVEST", "PROACTIVE TRAP"),
    steps: int = 20,
    seed: int = 0,
) -> CounterfactualReport:
    """Run isolated branches from public state under plausible rival modes.

    The simulator's hidden mode is used only by the evaluator inside each
    branch. Results shown to the judge are averaged across the three plausible
    modes, so the deployed decision never receives the hidden label.
    """
    from src.intelligence.closed_loop import ClosedLoopSimulator, HiddenRivalMode

    outcomes: list[CounterfactualOutcome] = []
    for action in actions:
        if action not in ("BURN", "HARVEST", "PROACTIVE TRAP"):
            raise ValueError(f"unknown counterfactual action: {action}")
        traces = []
        for offset, mode in enumerate(HiddenRivalMode):
            simulator = ClosedLoopSimulator(
                mode,
                seed=seed + offset,
                use_mpc=True,
                controller_variant="no_search",
                initial_speed_kmh=start.own_speed_kmh,
                initial_rival_speed_kmh=start.rival_speed_kmh,
                initial_gap_s=start.gap_s,
                initial_energy=start.own_energy,
                initial_temperature=start.battery_temperature,
                initial_battery_soh=start.battery_soh,
                initial_lap=start.lap,
            )
            simulator.run_forced(action, steps)
            traces.append(simulator)
        divisor = float(len(traces)) or 1.0
        outcomes.append(CounterfactualOutcome(
            action=action,
            final_gap_s=sum(simulator.ego.gap_s for simulator in traces) / divisor,
            gap_change_s=(sum(simulator.ego.gap_s for simulator in traces) / divisor
                          - start.gap_s),
            final_energy=sum(simulator.ego.energy for simulator in traces) / divisor,
            final_speed_kmh=sum(simulator.ego.speed_kmh for simulator in traces) / divisor,
            energy_deployed=sum(simulator.cumulative_deployed for simulator in traces) / divisor,
            energy_recovered=sum(simulator.cumulative_recovered for simulator in traces) / divisor,
            plausible_modes=len(traces),
        ))
    return CounterfactualReport(
        run_mode="counterfactual",
        source_frame_index=start.frame_index,
        source_timestamp_s=start.timestamp_s,
        driver=start.driver,
        rival=start.rival,
        outcomes=tuple(outcomes),
    )
