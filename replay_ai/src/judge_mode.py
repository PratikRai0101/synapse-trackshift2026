"""Judge-facing decision view, bookmarks and presentation helpers.

The replay application has a useful engineering HUD, but the intelligence story
needs a projection designed for a judge: one recommendation, the evidence that
caused it, the uncertainty around rival capability, and the alternatives that
were rejected. This module keeps that projection independent from the Arcade
window so it can be tested without an OpenGL context.
"""
from __future__ import annotations

from dataclasses import dataclass
import textwrap
from typing import Any, Mapping, Optional, Sequence

import arcade

from src.ui_theme import (
    AMBER,
    DANGER,
    EDGE,
    EDGE_SOFT,
    ELECTRIC,
    F1_RED,
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

# A marginal above this is treated as the dominant explanation for the rival's
# pace. Four modes split the mass, so 0.40 is already a strong signal.
_BELIEF_DOMINANCE = 0.40


def describe_capability_belief(
    probabilities: Mapping[str, float],
) -> tuple[str, RGB]:
    """Return a judge-readable read of the rival ERS belief and its colour.

    The tactically important distinction is deliberate energy saving
    (``Lharvest``) versus physical depletion (``Lderate``): the first is a
    trap, the second is an opportunity. The four raw probabilities are
    deliberately not enough on their own for a non-technical judge.
    """
    harvest = max(0.0, float(probabilities.get("Lharvest", 0.0)))
    derate = max(0.0, float(probabilities.get("Lderate", 0.0)))
    if derate >= _BELIEF_DOMINANCE and derate >= harvest:
        return "PHYSICALLY DEPLETED · ATTACK WINDOW", GREEN
    if harvest >= _BELIEF_DOMINANCE and harvest > derate:
        return "DELIBERATELY SAVING · HOLD", AMBER
    return "CAPABILITY UNRESOLVED · PROBE", MUTED


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
        # Each line names the public channel, the observation, and (via the
        # panel) the belief it feeds, so the update is auditable end to end.
        evidence: list[str] = []
        clip_seconds = float(getattr(features, "clip_seconds", 0.0) or 0.0)
        if clip_seconds > 0.0:
            evidence.append(f"THROTTLE super-clipping sustained {clip_seconds:.1f}s")
        elif features.throttle_clip > 0.0:
            evidence.append(
                "THROTTLE super-clipping on "
                f"{features.throttle_clip * 100:.0f}% of full-throttle samples"
            )
        if features.dv_baseline < -0.5:
            evidence.append(
                f"SPEED {abs(features.dv_baseline):.0f} km/h below 5-lap baseline"
            )
        elif features.dv_baseline > 0.5:
            evidence.append(
                f"SPEED {features.dv_baseline:.0f} km/h above 5-lap baseline"
            )
        if features.dgap > 0.02:
            evidence.append(f"GAP closing {features.dgap:+.2f}s (rival slowing)")
        elif features.dgap < -0.02:
            evidence.append(f"GAP opening {features.dgap:+.2f}s")
        if features.aero >= 0.5:
            evidence.append("AERO active (DRS proxy on)")
        if getattr(features, "tyre_life", 0.0) > 0.0:
            evidence.append(f"TYRE life {features.tyre_life:.0f} laps")
        return tuple(
            evidence or ("Public telemetry updated; evidence remains ambiguous",)
        )

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


def _nearest_free_frame(frame: int, used: set[int], count: int) -> int:
    for offset in range(1, count + 1):
        for candidate in (frame - offset, frame + offset):
            if 0 <= candidate < count and candidate not in used:
                return candidate
    return frame


def build_scenario_bookmarks(
    scenario_frames: Mapping[str, int],
    frame_count: int,
    total_laps: Optional[int] = None,
) -> tuple[JudgeBookmark, ...]:
    """Fill the six 5-0 slots with detected decision scenarios.

    A scenario the scan could not find falls back to the phase bookmark for
    that slot, so the demo always exposes exactly six deterministic moments
    rather than a variable-length list.
    """
    # Imported lazily: scenario detection pulls the inference stack, which the
    # panel module otherwise avoids at import time.
    from src.intelligence.scenarios import SCENARIOS

    generic = build_bookmarks(frame_count, total_laps)
    count = max(0, int(frame_count))
    if count == 0:
        return ()
    frames = scenario_frames or {}
    used: set[int] = set()
    points: list[JudgeBookmark] = []
    for index, spec in enumerate(SCENARIOS):
        frame = frames.get(spec.key)
        title, subtitle = spec.title, spec.subtitle
        if frame is None and index < len(generic):
            fallback = generic[index]
            frame = fallback.frame_index
            title, subtitle = fallback.title, fallback.subtitle
        frame = max(0, min(int(frame if frame is not None else 0), count - 1))
        if frame in used:
            frame = _nearest_free_frame(frame, used, count)
        used.add(frame)
        points.append(
            JudgeBookmark(frame, BOOKMARK_HOTKEYS[index], title, subtitle)
        )
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
class JudgeWalkthroughStep:
    """One teachable moment in the deterministic judge demonstration."""

    title: str
    summary: str
    body: tuple[str, ...]
    action_hint: str
    mode_label: str
    mode_color: RGB
    bookmark_index: Optional[int] = None


def scenario_label_from_session(session_info: Optional[Mapping[str, Any]]) -> str:
    """Return a truthful, short name for the replay used by the walkthrough."""
    if not session_info:
        return "DETERMINISTIC REPLAY PATH"
    values = " ".join(
        str(session_info.get(key, ""))
        for key in ("event_name", "circuit_name", "country")
    ).lower()
    if "monza" in values or "italian" in values:
        return "MONZA • ITALIAN GP"
    circuit = str(session_info.get("circuit_name", "")).strip()
    if circuit:
        return f"{circuit.upper()} • DETERMINISTIC PATH"
    return "DETERMINISTIC REPLAY PATH"


def build_walkthrough_steps(
    bookmarks: Sequence[JudgeBookmark] = (),
    scenario_label: str = "MONZA • ITALIAN GP",
) -> tuple[JudgeWalkthroughStep, ...]:
    """Build the fixed six-step explanation used by ``H``/``?``.

    The walkthrough is deliberately content-first. It never invents a hidden
    battery value; the live proof area is populated from the same snapshot and
    branch objects as Judge Mode itself.
    """
    hotkeys = tuple(bookmark.hotkey for bookmark in bookmarks)

    def jump(index: int) -> str:
        if index < len(hotkeys):
            return f"Press {hotkeys[index]} to load this fixed moment."
        return "Use the recorded replay controls to choose a moment."

    return (
        JudgeWalkthroughStep(
            title="START WITH REAL TELEMETRY",
            summary="History is the source of truth; the AI adds a decision layer.",
            body=(
                f"This {scenario_label} path starts from an observed replay frame.",
                "A bookmark pauses the recorded cars and keeps the frame reproducible.",
                "No counterfactual result can rewrite what actually happened.",
            ),
            action_hint=jump(0),
            mode_label="REAL TELEMETRY REPLAY",
            mode_color=ELECTRIC,
            bookmark_index=0,
        ),
        JudgeWalkthroughStep(
            title="READ THE CAPABILITY BELIEF",
            summary="Public signals become four explicit hidden-state probabilities.",
            body=(
                "The bars describe rival ERS capability, not rival battery SOC.",
                "Lharvest means deliberately saving; Lderate means physical depletion.",
                "That distinction is the counter-harvest insight in one glance.",
            ),
            action_hint=jump(1),
            mode_label="REAL TELEMETRY REPLAY",
            mode_color=ELECTRIC,
            bookmark_index=1,
        ),
        JudgeWalkthroughStep(
            title="FOLLOW THE CAUSAL EVIDENCE",
            summary="The Why panel makes the belief update auditable.",
            body=(
                "Speed, throttle, brake, gap response and aero proxy are public inputs.",
                "The model explains which signals changed the tactical belief.",
                "The recommendation is allowed to be uncertain when evidence is weak.",
            ),
            action_hint=jump(2),
            mode_label="REAL TELEMETRY REPLAY",
            mode_color=ELECTRIC,
            bookmark_index=2,
        ),
        JudgeWalkthroughStep(
            title="COMPARE THE REJECTED OPTIONS",
            summary="The winner is meaningful only beside the alternatives it beat.",
            body=(
                "POMCP compares BURN, HARVEST and PROACTIVE TRAP in decision units.",
                "Immediate gap, estimated energy and continuation value stay visible.",
                "Selected and rejected actions are shown from the same observed frame.",
            ),
            action_hint=jump(3),
            mode_label="REAL TELEMETRY REPLAY",
            mode_color=ELECTRIC,
            bookmark_index=3,
        ),
        JudgeWalkthroughStep(
            title="FORK THE DECISION",
            summary="Now ask what each action would do from this exact public state.",
            body=(
                "Pause on a bookmark, then press C to launch isolated branches.",
                "Each branch starts with recorded speed, gap and estimated own store.",
                "Results average three plausible hidden rival responses.",
            ),
            action_hint="Press C to run the counterfactual simulation.",
            mode_label="COUNTERFACTUAL SIMULATION",
            mode_color=AMBER,
            bookmark_index=4,
        ),
        JudgeWalkthroughStep(
            title="RETURN TO OBSERVED HISTORY",
            summary="Simulation is a fork, never a replacement for the replay.",
            body=(
                "The branch reports final gap, remaining store and energy used.",
                "Press SPACE to resume the recorded telemetry or choose another bookmark.",
                "The mode badge tells the judge which world is on screen right now.",
            ),
            action_hint=jump(5),
            mode_label="REAL TELEMETRY REPLAY",
            mode_color=ELECTRIC,
            bookmark_index=5,
        ),
    )


class JudgeWalkthroughController:
    """Pure interaction state for the in-app ``How It Works`` walkthrough."""

    def __init__(self, steps: Sequence[JudgeWalkthroughStep] = ()) -> None:
        self.steps = tuple(steps)
        self.visible = False
        self.step_index = 0
        self.first_run_hint_visible = bool(self.steps)

    @property
    def current_step(self) -> Optional[JudgeWalkthroughStep]:
        if not self.steps:
            return None
        return self.steps[self.step_index]

    def open(self) -> bool:
        self.visible = True
        self.first_run_hint_visible = False
        return self.visible

    def close(self) -> bool:
        self.visible = False
        return self.visible

    def toggle(self) -> bool:
        return self.close() if self.visible else self.open()

    def dismiss_hint(self) -> None:
        self.first_run_hint_visible = False

    def select(self, index: int) -> Optional[JudgeWalkthroughStep]:
        if not self.steps:
            return None
        self.step_index = max(0, min(len(self.steps) - 1, int(index)))
        return self.current_step

    def step(self, direction: int) -> Optional[JudgeWalkthroughStep]:
        if not self.steps:
            return None
        delta = 1 if direction >= 0 else -1
        return self.select(self.step_index + delta)

    def select_for_bookmark(self, bookmark_index: int) -> Optional[JudgeWalkthroughStep]:
        for index, step in enumerate(self.steps):
            if step.bookmark_index == int(bookmark_index):
                return self.select(index)
        return None


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
        # The panel content is laid out on a fixed 224 px grid. Never shrink
        # below it: a shorter panel makes the alternatives collide with the
        # footer, which is exactly the clutter this HUD must avoid.
        height = min(self.height, max(224.0, float(window_height) * 0.33))
        bottom = max(130.0, min(self.bottom_y, float(window_height) * 0.20))
        bottom = min(bottom, max(16.0, float(window_height) - height - 16.0))
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
        run_mode = (
            "COUNTERFACTUAL SIMULATION"
            if branch is not None and getattr(branch, "outcomes", ())
            else "REAL TELEMETRY REPLAY"
        )
        draw_chip(
            left + pad + 292,
            top - 17,
            run_mode,
            AMBER if run_mode.startswith("COUNTER") else ELECTRIC,
            size=7,
            height=16,
            pad_x=6,
        )
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

        content_top = top - 50
        command_x = left + pad + 4
        col_left_w = width * 0.36

        # --- left column: recommendation, then the alternatives it beat -------
        self._t("recommend", "RECOMMENDATION", command_x, content_top, 10,
                 MUTED, bold=True)
        self._t("command", snapshot.command_label, command_x, content_top - 24,
                 20, snapshot.command_color, bold=True)
        confidence_y = content_top - 48
        self._t("confidence", f"{snapshot.confidence * 100:.0f}% confidence",
                 command_x, confidence_y, 11, TEXT, bold=True)
        draw_meter(command_x, confidence_y - 15,
                   max(110.0, min(190.0, col_left_w - 20)), 8,
                   snapshot.confidence, snapshot.command_color)
        target = (
            f"TARGET {snapshot.target_speed_kmh:.0f} km/h"
            if snapshot.target_speed_kmh is not None else "TARGET pending"
        )
        self._t("detail", f"{target}  •  STORE {snapshot.own_energy_eu:.0f} EU",
                 command_x, confidence_y - 30, 8, MUTED)
        budget = (
            f"LAP {snapshot.lap_energy_target:.1f} EU"
            if snapshot.lap_energy_target is not None else "LAP pending"
        )
        if snapshot.reserve_after_lap is not None:
            budget += f"  •  RESERVE {snapshot.reserve_after_lap:.1f} EU"
        self._t("budget", budget, command_x, confidence_y - 43, 7, MUTED)

        # --- middle column: rival ERS capability belief ----------------------
        # Starts clear of the left column so the alternatives/branch rail can
        # right-align without touching the lowest belief row.
        belief_x = left + width * 0.40
        self._t("belief_header", snapshot.rival_label, belief_x, content_top, 10,
                 MUTED, bold=True)
        # The verdict is the five-second read: is the rival sandbagging (a trap)
        # or genuinely spent (an opportunity)? The bars below only evidence it.
        verdict, verdict_color = describe_capability_belief(
            {mode.mode: mode.probability for mode in snapshot.rival_modes}
        )
        self._t("belief_verdict", verdict, belief_x, content_top - 20, 8,
                 verdict_color, bold=True)
        # Size the meters from the gap to the evidence column so narrow windows
        # never push a percentage into the "why" text.
        why_x = left + width - max(240.0, width * 0.27)
        middle_span = max(160.0, why_x - belief_x - 16.0)
        meter_width = max(70.0, min(180.0, middle_span - 90.0))
        for index, mode in enumerate(snapshot.rival_modes):
            y = content_top - 40 - index * 20
            self._t(f"mode_label_{index}", mode.mode, belief_x, y, 9,
                     mode.color, bold=True)
            meter_left = belief_x + 62
            draw_meter(meter_left, y, meter_width, 9,
                       mode.probability, mode.color)
            self._t(f"mode_value_{index}", f"{mode.probability * 100:.0f}%",
                     meter_left + meter_width + 8, y, 9, TEXT, bold=True)

        # --- right column: the causal evidence -------------------------------
        self._t("why_header", "WHY THE MODEL CHANGED", why_x, content_top, 10,
                 MUTED, bold=True)
        for index, evidence in enumerate(snapshot.evidence[:3]):
            self._t(f"evidence_{index}", f"✓ {evidence}", why_x,
                     content_top - 23 - index * 16, 7, TEXT)
        self._t("why_footer", f"→ {snapshot.explanation[:40]}", why_x,
                 content_top - 74, 7, snapshot.command_color)
        layers = "  →  ".join(
            ("HMM40", "POMCP" if snapshot.search_particles else "SEARCH",
             "SOCP", "MPC")
        )
        self._t("layers", f"LAYER ACTIVITY  {layers}", why_x,
                 content_top - 92, 7, ELECTRIC, bold=True)

        # --- alternatives, pinned above the footer so it can never collide ---
        options_title_y = bottom + 70
        option_header_y = bottom + 58
        option_rows = (bottom + 45, bottom + 32, bottom + 19)
        cw = col_left_w
        if branch is not None and getattr(branch, "outcomes", ()):
            self._t("alternatives", "COUNTERFACTUAL BRANCH",
                     command_x, options_title_y, 9, ELECTRIC, bold=True)
            modes = max(
                (outcome.plausible_modes for outcome in branch.outcomes[:3]),
                default=0,
            )
            self._t("branch_modes", f"{modes} plausible responses",
                     command_x + cw, options_title_y, 7, ELECTRIC,
                     anchor_x="right")
            for index, outcome in enumerate(branch.outcomes[:3]):
                y = option_rows[index]
                color = snapshot.command_color if outcome.action == snapshot.command else MUTED
                self._t(f"branch_name_{index}", outcome.action, command_x, y, 8,
                         color, bold=outcome.action == snapshot.command)
                self._t(
                    f"branch_gap_{index}",
                    f"Δ {getattr(outcome, 'gap_change_s', 0.0):+.2f}s",
                    command_x + cw * 0.30, y, 7, TEXT,
                )
                self._t(
                    f"branch_final_{index}",
                    f"→ {outcome.final_gap_s:.2f}s",
                    command_x + cw * 0.54, y, 7, TEXT,
                )
                self._t(f"branch_energy_{index}",
                         f"store {outcome.final_energy:.0f} EU",
                         command_x + cw, y, 7, MUTED, anchor_x="right")
        else:
            search_title = (
                f"BOUNDED POMCP ALTERNATIVES  •  {snapshot.search_particles} PARTICLES"
                if snapshot.search_particles else "TACTICAL ALTERNATIVES"
            )
            self._t("alternatives", search_title, command_x,
                     options_title_y, 9, MUTED, bold=True)
            # Explicit units stop the solver's raw ranking from being read as
            # the decision. "Energy cost" is signed: + spends, - recovers.
            self._t("option_head_action", "ACTION", command_x,
                     option_header_y, 6, MUTED, bold=True)
            self._t("option_head_gain", "IMM. GAIN", command_x + cw * 0.30,
                     option_header_y, 6, MUTED, bold=True)
            self._t("option_head_energy", "ENERGY", command_x + cw * 0.52,
                     option_header_y, 6, MUTED, bold=True)
            self._t("option_head_later", "LATER", command_x + cw * 0.72,
                     option_header_y, 6, MUTED, bold=True)
            self._t("option_head_decision", "DECISION", command_x + cw,
                     option_header_y, 6, MUTED, bold=True, anchor_x="right")
            for index, option in enumerate(snapshot.options[:3]):
                y = option_rows[index]
                color = snapshot.command_color if option.selected else MUTED
                marker = "SELECTED" if option.selected else "REJECTED"
                self._t(f"option_name_{index}", option.command, command_x, y, 8,
                         color, bold=option.selected)
                self._t(f"option_gain_{index}",
                         f"{option.gap_gain_s:+.2f}s",
                         command_x + cw * 0.30, y, 7, TEXT)
                self._t(f"option_energy_{index}",
                         f"{option.energy_delta_eu:+.1f} EU",
                         command_x + cw * 0.52, y, 7, MUTED)
                self._t(f"option_later_{index}",
                         f"{option.continuation_value:+.2f}",
                         command_x + cw * 0.72, y, 7, TEXT)
                self._t(f"option_status_{index}", marker,
                         command_x + cw, y, 7, color,
                         bold=option.selected, anchor_x="right")

        footer_y = bottom + 9
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


class JudgeWalkthroughPanel:
    """Modal, presentation-first explanation of the Judge Mode workflow."""

    def __init__(self, width: float = 920.0, height: float = 520.0) -> None:
        self.width = width
        self.height = height
        self._texts: dict[str, arcade.Text] = {}
        self.action_rects: list[tuple[str, float, float, float, float]] = []
        self.step_rects: list[tuple[int, float, float, float, float]] = []
        self.hint_bounds: Optional[PanelBounds] = None

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

    def layout_bounds(self, window_width: float, window_height: float) -> PanelBounds:
        width = min(self.width, max(320.0, float(window_width) - 40.0))
        # 480 px is the smallest height at which the six-line step body and the
        # live-proof card both fit without spilling into each other.
        height = min(self.height, max(480.0, float(window_height) - 40.0))
        return PanelBounds(
            left=(float(window_width) - width) / 2.0,
            bottom=(float(window_height) - height) / 2.0,
            width=width,
            height=height,
        )

    @staticmethod
    def _contains(rect: tuple[float, float, float, float], x: float, y: float) -> bool:
        left, bottom, right, top = rect
        return left <= x <= right and bottom <= y <= top

    def _button(self, action: str, label: str, left: float, bottom: float,
                width: float, color: RGB = EDGE_SOFT) -> None:
        rect = (left, bottom, left + width, bottom + 28.0)
        self.action_rects.append((action, *rect))
        arcade.draw_rect_filled(
            arcade.XYWH(left + width / 2.0, bottom + 14.0, width, 28.0),
            color,
        )
        arcade.draw_rect_outline(
            arcade.XYWH(left + width / 2.0, bottom + 14.0, width, 28.0),
            ELECTRIC if action == "next" else EDGE,
            1,
        )
        self._t(
            f"button_{action}", label, left + width / 2.0, bottom + 14.0,
            9, TEXT, bold=True, anchor_x="center",
        )

    def _draw_live_proof(self, left: float, bottom: float, width: float,
                         top: float, step_index: int,
                         snapshot: Optional[JudgeModeSnapshot], branch: Any) -> None:
        draw_panel(
            left + width / 2.0,
            bottom + (top - bottom) / 2.0,
            width,
            top - bottom,
            fill=PANEL,
            fill_alpha=238,
            edge=EDGE,
            edge_width=1,
            accent=AMBER if branch is not None and getattr(branch, "outcomes", ())
            else ELECTRIC,
            accent_width=4,
        )
        pad = 14.0
        self._t("proof_header", "LIVE PROOF", left + pad, top - 20, 10,
                 MUTED, bold=True)

        if branch is not None and getattr(branch, "outcomes", ()):
            draw_chip(left + pad, top - 43, "COUNTERFACTUAL SIMULATION", AMBER,
                      size=7, height=17, pad_x=6)
            self._t(
                "proof_source",
                f"SOURCE: REAL TELEMETRY REPLAY  •  FRAME {branch.source_frame_index}",
                left + pad, top - 65, 7, TEXT, bold=True,
            )
            y = top - 94
            for index, outcome in enumerate(branch.outcomes[:3]):
                color = AMBER if index == 0 else MUTED
                self._t(
                    f"proof_branch_name_{index}",
                    outcome.action,
                    left + pad,
                    y,
                    9,
                    color,
                    bold=index == 0,
                )
                self._t(
                    f"proof_branch_gap_{index}",
                    f"Δ gap {getattr(outcome, 'gap_change_s', 0.0):+.2f}s",
                    left + pad + 100,
                    y,
                    8,
                    TEXT,
                )
                self._t(
                    f"proof_branch_store_{index}",
                    f"store {getattr(outcome, 'final_energy', 0.0):.1f} EU",
                    left + pad + 190,
                    y,
                    8,
                    MUTED,
                )
                y -= 25
            self._t(
                "proof_branch_note",
                "AVERAGED ACROSS 3 PLAUSIBLE RIVAL RESPONSES",
                left + pad,
                bottom + 22,
                7,
                AMBER,
                bold=True,
            )
            return

        draw_chip(left + pad, top - 43, "REAL TELEMETRY REPLAY", ELECTRIC,
                  size=7, height=17, pad_x=6)
        if snapshot is None:
            self._t("proof_empty", "SELECT A DRIVER TO POPULATE THE DECISION VIEW",
                     left + pad, top - 88, 9, TEXT, bold=True)
            self._t("proof_empty_2", "The car ahead becomes the inferred rival.",
                     left + pad, top - 113, 8, MUTED)
            return

        if step_index == 1:
            probabilities = {mode.mode: mode.probability
                             for mode in snapshot.rival_modes}
            verdict, verdict_color = describe_capability_belief(probabilities)
            self._t("proof_belief_header", "ERS CAPABILITY BELIEF",
                     left + pad, top - 78, 9, MUTED, bold=True)
            self._t("proof_belief_verdict", verdict, left + pad, top - 100, 8,
                     verdict_color, bold=True)
            descriptors = {
                "Lharvest": "deliberately saving energy",
                "Lderate": "physically depleted",
            }
            for index, mode in enumerate(snapshot.rival_modes):
                y = top - 128 - index * 26
                self._t(f"proof_mode_{index}", mode.mode, left + pad, y, 9,
                         mode.color, bold=True)
                meter_left = left + pad + 76
                meter_width = max(100.0, width - 210.0)
                draw_meter(meter_left, y, meter_width, 10,
                           mode.probability, mode.color)
                self._t(f"proof_mode_value_{index}",
                         f"{mode.probability * 100:.0f}%",
                         meter_left + meter_width + 8, y, 9, TEXT, bold=True)
                descriptor = descriptors.get(mode.mode)
                if descriptor:
                    self._t(f"proof_mode_desc_{index}", descriptor,
                             meter_left + meter_width + 56, y, 7, mode.color)
            self._t("proof_belief_note", "BELIEF ≠ RIVAL BATTERY SOC",
                     left + pad, bottom + 22, 7, AMBER, bold=True)
        elif step_index == 2:
            self._t("proof_evidence_header", "PUBLIC EVIDENCE → WHY",
                     left + pad, top - 78, 9, MUTED, bold=True)
            for index, evidence in enumerate(snapshot.evidence[:5]):
                self._t(f"proof_evidence_{index}", f"✓ {evidence}",
                         left + pad, top - 105 - index * 24, 8, TEXT)
            self._t("proof_evidence_note", "INPUTS STAY TRACEABLE TO PUBLIC CHANNELS",
                     left + pad, bottom + 22, 7, ELECTRIC, bold=True)
        elif step_index == 3:
            self._t("proof_options_header", "POMCP ALTERNATIVES",
                     left + pad, top - 78, 9, MUTED, bold=True)
            content_w = max(200.0, width - 2 * pad)
            columns = (
                (0.00, "ACTION", "left"),
                (0.30, "IMM. GAIN", "left"),
                (0.50, "ENERGY COST", "left"),
                (0.70, "LATER VALUE", "left"),
                (1.00, "DECISION", "right"),
            )
            for offset, label, anchor in columns:
                self._t(f"proof_option_head_{label}", label,
                         left + pad + content_w * offset, top - 100, 7,
                         MUTED, bold=True, anchor_x=anchor)
            for index, option in enumerate(snapshot.options[:3]):
                y = top - 127 - index * 25
                color = snapshot.command_color if option.selected else MUTED
                marker = "SELECTED" if option.selected else "REJECTED"
                self._t(f"proof_option_{index}", option.command, left + pad,
                         y, 9, color, bold=option.selected)
                self._t(f"proof_option_gain_{index}",
                         f"{option.gap_gain_s:+.2f}s",
                         left + pad + content_w * 0.30, y, 8, TEXT)
                self._t(f"proof_option_energy_{index}",
                         f"{option.energy_delta_eu:+.1f} EU",
                         left + pad + content_w * 0.50, y, 8, MUTED)
                self._t(f"proof_option_later_{index}",
                         f"{option.continuation_value:+.2f}",
                         left + pad + content_w * 0.70, y, 8, TEXT)
                self._t(f"proof_option_status_{index}", marker,
                         left + pad + content_w, y, 8, color,
                         bold=option.selected, anchor_x="right")
            self._t("proof_options_note", "UNITS, NOT RAW SOLVER SCORES",
                     left + pad, bottom + 22, 7, ELECTRIC, bold=True)
        else:
            self._t("proof_recommend_header", "RECOMMENDATION",
                     left + pad, top - 78, 9, MUTED, bold=True)
            self._t("proof_recommendation", snapshot.command_label,
                     left + pad, top - 108, 18, snapshot.command_color, bold=True)
            self._t("proof_confidence",
                     f"{snapshot.confidence * 100:.0f}% confidence  •  {snapshot.driver} P{snapshot.position}",
                     left + pad, top - 136, 9, TEXT, bold=True)
            self._t("proof_recommend_reason", snapshot.explanation[:72],
                     left + pad, top - 164, 8, MUTED)
            self._t("proof_recommend_note", "PRESS C WHEN PAUSED TO FORK THIS DECISION",
                     left + pad, bottom + 22, 7, AMBER, bold=True)

    def draw(self, window: Any, controller: JudgeWalkthroughController,
             snapshot: Optional[JudgeModeSnapshot] = None, branch: Any = None,
             scenario_label: str = "MONZA • ITALIAN GP",
             visible: bool = True) -> None:
        """Draw the walkthrough above the replay without changing replay state."""
        if not visible or not controller.visible:
            self.action_rects = []
            self.step_rects = []
            return
        bounds = self.layout_bounds(window.width, window.height)
        left, bottom, width, height = (
            bounds.left, bounds.bottom, bounds.width, bounds.height
        )
        right, top = bounds.right, bounds.top
        self.action_rects = []
        self.step_rects = []

        arcade.draw_rect_filled(
            arcade.XYWH(window.width / 2.0, window.height / 2.0,
                        window.width, window.height),
            (0, 0, 0, 165),
        )
        draw_panel(
            left + width / 2.0,
            bottom + height / 2.0,
            width,
            height,
            fill=PANEL,
            fill_alpha=252,
            edge=ELECTRIC,
            edge_width=1,
            accent=ELECTRIC,
            accent_width=6,
        )
        pad = 26.0
        self._t("walk_title", "HOW IT WORKS", left + pad, top - 28, 19,
                 TEXT, bold=True)
        draw_chip(left + pad + 250, top - 28, scenario_label, F1_RED,
                  size=8, height=19, pad_x=7)
        close_rect = (right - 112, top - 43, right - pad, top - 12)
        self.action_rects.append(("close", *close_rect))
        self._t("walk_close", "H / ?  CLOSE", right - pad, top - 28, 8,
                 MUTED, bold=True, anchor_x="right")
        # Header rule keeps the title, step rail and content visually separate.
        arcade.draw_rect_filled(
            arcade.XYWH(left + width / 2.0, top - 48, width - 2 * pad, 1),
            EDGE_SOFT,
        )

        steps = controller.steps
        step_count = len(steps)
        if step_count:
            rail_left = left + pad
            rail_width = width - 2.0 * pad
            gap = 6.0
            segment_width = (rail_width - gap * (step_count - 1)) / step_count
            for index in range(step_count):
                segment_left = rail_left + index * (segment_width + gap)
                segment_color = ELECTRIC if index == controller.step_index else EDGE_SOFT
                arcade.draw_rect_filled(
                    arcade.XYWH(segment_left + segment_width / 2.0,
                                top - 67,
                                segment_width,
                                5),
                    segment_color,
                )
                self.step_rects.append((
                    index, segment_left, top - 79,
                    segment_left + segment_width, top - 55,
                ))
                self._t(f"walk_step_number_{index}", str(index + 1),
                         segment_left + segment_width / 2.0, top - 88, 7,
                         ELECTRIC if index == controller.step_index else MUTED,
                         bold=True, anchor_x="center")

        step = controller.current_step
        if step is None:
            return
        index = controller.step_index
        content_top = top - 112
        left_width = width * 0.43
        self._t("walk_kicker", f"STEP {index + 1} / {step_count}  •  {step.mode_label}",
                 left + pad, content_top, 9, step.mode_color, bold=True)
        self._t("walk_step_title", step.title, left + pad, content_top - 32,
                 17, TEXT, bold=True)
        self._t("walk_summary", step.summary, left + pad, content_top - 62,
                 9, MUTED)

        # The callout and the live-proof card share a fixed lower band so a long
        # step body can never overlap either of them.
        callout_bottom = bottom + 74
        callout_top = callout_bottom + 86
        body_top = content_top - 92
        wrap_cols = max(30, int((left_width - pad - 24) / 5.2))
        max_body_lines = max(2, int((body_top - callout_top - 10) // 17))
        body_line_index = 0
        for line in step.body:
            for wrapped in textwrap.wrap(line, width=wrap_cols) or (line,):
                if body_line_index >= max_body_lines:
                    break
                self._t(f"walk_body_{body_line_index}", wrapped,
                         left + pad,
                         body_top - body_line_index * 17,
                         9,
                         TEXT)
                body_line_index += 1

        draw_panel(
            left + pad + (left_width - pad) / 2.0,
            callout_bottom + (callout_top - callout_bottom) / 2.0,
            left_width - pad,
            callout_top - callout_bottom,
            fill=(28, 28, 35),
            fill_alpha=238,
            edge=EDGE_SOFT,
            edge_width=1,
        )
        self._t("walk_action_label", "TRY IT", left + pad + 14,
                 callout_top - 20, 8, MUTED, bold=True)
        self._t("walk_action", step.action_hint, left + pad + 14,
                 callout_top - 49, 10, step.mode_color, bold=True)
        self._t("walk_action_note", "The live proof card updates from the same frame.",
                 left + pad + 14, callout_bottom + 16, 7, MUTED)

        proof_left = left + left_width + 4.0
        proof_bottom = callout_bottom
        proof_top = content_top
        self._draw_live_proof(
            proof_left,
            proof_bottom,
            right - pad - proof_left,
            proof_top,
            index,
            snapshot,
            branch,
        )

        # A rule separates the content from the fixed footer controls.
        arcade.draw_rect_filled(
            arcade.XYWH(left + width / 2.0, bottom + 64, width - 2 * pad, 1),
            EDGE_SOFT,
        )
        footer_y = bottom + 22
        self._button("previous", "←  PREVIOUS", left + pad, footer_y, 116.0)
        self._button("next", "NEXT  →", right - pad - 116.0, footer_y, 116.0,
                     color=(0, 95, 115))
        self._t("walk_footer", "5–0 BOOKMARKS  •  C SIMULATE  •  SPACE RETURN TO REPLAY",
                 left + width / 2.0, footer_y + 14.0, 7, MUTED,
                 bold=True, anchor_x="center")

    def hit_test(self, x: float, y: float) -> Optional[str]:
        """Return a walkthrough action from the most recent draw."""
        for action, left, bottom, right, top in self.action_rects:
            if self._contains((left, bottom, right, top), x, y):
                return action
        for index, left, bottom, right, top in self.step_rects:
            if self._contains((left, bottom, right, top), x, y):
                return f"step:{index}"
        return None

    def draw_first_run_hint(self, window: Any, scenario_label: str,
                            visible: bool = True) -> None:
        """Draw the small first-run invitation before a judge opens help."""
        if not visible:
            self.hint_bounds = None
            return
        width = min(620.0, max(320.0, float(window.width) - 40.0))
        height = 48.0
        center_x = float(window.width) / 2.0
        center_y = max(80.0, float(window.height) - 132.0)
        self.hint_bounds = PanelBounds(
            center_x - width / 2.0,
            center_y - height / 2.0,
            width,
            height,
        )
        draw_panel(center_x, center_y, width, height, fill=PANEL,
                   fill_alpha=245, edge=ELECTRIC, edge_width=1,
                   accent=ELECTRIC, accent_width=4)
        self._t("hint_title", "HOW IT WORKS", self.hint_bounds.left + 16,
                 center_y + 8, 9, ELECTRIC, bold=True)
        self._t(
            "hint_body",
            f"Press H or ? for the six-step {scenario_label} walkthrough",
            self.hint_bounds.left + 16,
            center_y - 10,
            9,
            TEXT,
        )


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
