"""Race Engineer — live energy & overtake intelligence for the replay.

A PitWall insight window that consumes the telemetry stream and, for a selected
driver, plots the engine's view of the race as it unfolds:

1. Estimated state of charge (SoC) with the reserve / critical bands.
2. Instantaneous energy flow (harvest up, deploy down, in EU/s).
3. Overtake score (reward - risk) with mode-coloured background bands.

All numbers come from the same ``src.intelligence`` models the replay HUD uses,
integrated incrementally so the window stays cheap. Open it early for the full
race curve; opening mid-race shows the curve from that point forward.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

import numpy as np

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.patches import Patch

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.pit_wall_window import PitWallWindow
from src.intelligence.energy import (
    MODE_ATTACK,
    MODE_BALANCED,
    MODE_HARVEST,
    MODE_LIFT_COAST,
    recommend_deployment_mode,
    step_energy,
)
from src.intelligence.overtake import evaluate_overtake_window

# --- palette --------------------------------------------------------------
_BG = "#141419"
_PANEL = "#0b0b0e"
_GRID = "#2a2a33"
_TEXT = "#f2f2f5"
_DIM = "#8c8c98"
_GREEN = "#00D26A"
_RED = "#E10600"
_AMBER = "#FFB800"
_ELECTRIC = "#00D6FF"
_SPEED_REF_KPH = 55.56

_MODE_ID = {MODE_LIFT_COAST: 0, MODE_HARVEST: 1, MODE_BALANCED: 2, MODE_ATTACK: 3}
_MODE_COLOR = {3: _RED, 2: _ELECTRIC, 1: _GREEN, 0: _AMBER}
_MODE_LABEL = {3: "ATTACK", 2: "BALANCED", 1: "HARVEST", 0: "LIFT & COAST"}

_MAX_DT = 1.0  # cap integration step so seeks/jumps can't cause wild swings


def _f(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


class _DriverTrack:
    """Incremental per-driver engine state and history."""

    def __init__(self) -> None:
        self.t: List[float] = []
        self.soc: List[float] = []
        self.deploy: List[float] = []
        self.harvest: List[float] = []
        self.score: List[float] = []
        self.reward: List[float] = []
        self.risk: List[float] = []
        self.mode: List[int] = []
        self._soc = 100.0
        self._prev_t: Optional[float] = None

    def add(self, t, pos, gap_s, ahead_speed, position, total_laps) -> None:
        if self._prev_t is not None and t <= self._prev_t:
            return  # ignore duplicates / non-monotonic (seek) samples
        dt = 0.0 if self._prev_t is None else min(_MAX_DT, max(0.0, t - self._prev_t))
        self._prev_t = t

        throttle = _f(pos.get("throttle"))
        brake = _f(pos.get("brake"))
        speed = _f(pos.get("speed"))
        drs = pos.get("drs", 0) in (8, 10, 12, 14)
        tyre_life = _f(pos.get("tyre_life"))
        lap = int(_f(pos.get("lap", 1)) or 1)

        self._soc, dep, har = step_energy(self._soc, dt, throttle, brake, speed)
        laps_remaining = (int(total_laps) - lap) if total_laps else None

        sc = evaluate_overtake_window(
            gap_ahead_s=gap_s,
            speed_delta_kmh=(speed - ahead_speed) if ahead_speed is not None else 0.0,
            drs=drs,
            soc=self._soc,
            tyre_life=tyre_life,
            laps_remaining=laps_remaining,
            position=position,
        )
        advice = recommend_deployment_mode(
            soc=self._soc,
            gap_ahead_s=gap_s,
            laps_remaining=laps_remaining,
            drs=drs,
            tyre_life=tyre_life,
            overtake_score=sc.score,
        )

        self.t.append(t)
        self.soc.append(self._soc)
        self.deploy.append(dep)
        self.harvest.append(har)
        self.score.append(sc.score)
        self.reward.append(sc.reward)
        self.risk.append(sc.risk)
        self.mode.append(_MODE_ID.get(advice.mode, 2))


class RaceEngineerWindow(PitWallWindow):
    """Live Race Engineer analytics window."""

    def __init__(self) -> None:
        self._tracks: Dict[str, _DriverTrack] = {}
        self._order: List[str] = []
        self._selected: Optional[str] = None
        self._total_laps: Optional[int] = None
        self._last_draw = 0.0
        self._gap_by_code: Dict[str, Optional[float]] = {}
        self._focus_from_stream: Optional[str] = None
        super().__init__()
        self.setWindowTitle("Race Engineer — Energy & Overtake Intelligence")
        self.resize(1020, 880)

    # -- UI ----------------------------------------------------------------
    def setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 6)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Driver:"))
        self.combo = QComboBox()
        self.combo.currentTextChanged.connect(self._on_driver_changed)
        bar.addWidget(self.combo)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset)
        bar.addWidget(self.reset_btn)
        bar.addStretch()
        self.status = QLabel("Waiting for telemetry…")
        self.status.setStyleSheet(f"color: {_DIM};")
        bar.addWidget(self.status)
        root.addLayout(bar)

        self._fig, axes = plt.subplots(
            3, 1, sharex=True, figsize=(9, 8),
            gridspec_kw={"height_ratios": [2.0, 1.0, 2.0]},
        )
        self._ax_soc, self._ax_flow, self._ax_score = axes
        self._fig.patch.set_facecolor(_BG)
        self._fig.subplots_adjust(left=0.09, right=0.97, top=0.95, bottom=0.09, hspace=0.16)
        for ax in axes:
            self._style_axis(ax)
        self._ax_soc.set_title("Estimated state of charge", color=_TEXT, fontsize=10, loc="left")
        self._ax_flow.set_title("Energy flow  (harvest up / deploy down)", color=_TEXT, fontsize=10, loc="left")
        self._ax_score.set_title("Overtake window score  (bands = recommended mode)", color=_TEXT, fontsize=10, loc="left")
        self._canvas = FigureCanvas(self._fig)
        root.addWidget(self._canvas, 1)

    @staticmethod
    def _style_axis(ax) -> None:
        ax.set_facecolor(_PANEL)
        ax.grid(True, color=_GRID, linewidth=0.5, alpha=0.6)
        ax.tick_params(colors=_DIM, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(_GRID)
        ax.yaxis.label.set_color(_DIM)
        ax.xaxis.label.set_color(_DIM)

    # -- stream ------------------------------------------------------------
    def on_telemetry_data(self, data) -> None:
        frame = data.get("frame")
        if not frame:
            return
        drivers = frame.get("drivers") or {}
        if not drivers:
            return
        t = _f(frame.get("t"))
        session = data.get("session_data") or {}
        if session.get("total_laps"):
            self._total_laps = int(session["total_laps"])
        sel = data.get("selected_drivers") or []
        if sel:
            self._focus_from_stream = sel[0]

        order = sorted(
            drivers.items(),
            key=lambda kv: (_f(kv[1].get("lap", 1)), _f(kv[1].get("dist"))),
            reverse=True,
        )
        self._order = [c for c, _ in order]
        self._gap_by_code = {}
        for rank, (code, pos) in enumerate(order, start=1):
            gap_s = None
            ahead_speed = None
            if rank > 1:
                ahead = order[rank - 2][1]
                if _f(ahead.get("lap", 1)) == _f(pos.get("lap", 1)):
                    gap_s = abs(_f(ahead.get("dist")) - _f(pos.get("dist"))) / _SPEED_REF_KPH
                    ahead_speed = _f(ahead.get("speed"))
            self._gap_by_code[code] = gap_s
            track = self._tracks.get(code)
            if track is None:
                track = _DriverTrack()
                self._tracks[code] = track
            track.add(t, pos, gap_s, ahead_speed, rank, self._total_laps)

        self._sync_combo()
        now = time.monotonic()
        if now - self._last_draw >= 0.4:
            self._last_draw = now
            self._redraw()

    def _sync_combo(self) -> None:
        existing = {self.combo.itemText(i) for i in range(self.combo.count())}
        for code in self._order:
            if code not in existing:
                self.combo.addItem(code)
                existing.add(code)
        if self._selected is None and self._order:
            # Prefer the driver focused in the replay, then the closest battle,
            # then the leader.
            if self._focus_from_stream in self._order:
                self._selected = self._focus_from_stream
            else:
                with_gap = [c for c in self._order if self._gap_by_code.get(c) is not None]
                self._selected = (min(with_gap, key=lambda c: self._gap_by_code[c])
                                  if with_gap else self._order[0])
            self.combo.blockSignals(True)
            self.combo.setCurrentText(self._selected)
            self.combo.blockSignals(False)

    def _on_driver_changed(self, text: str) -> None:
        self._selected = text or None
        self._redraw()

    def _reset(self) -> None:
        self._tracks.clear()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.blockSignals(False)
        self._selected = None
        self._redraw()

    # -- plotting ----------------------------------------------------------
    def _redraw(self) -> None:
        ax_soc, ax_flow, ax_score = self._ax_soc, self._ax_flow, self._ax_score
        for ax in (ax_soc, ax_flow, ax_score):
            ax.clear()
            self._style_axis(ax)

        track = self._tracks.get(self._selected) if self._selected else None
        if track is None or not track.t:
            self.status.setText("Waiting for telemetry…")
            self._canvas.draw_idle()
            return

        t = np.asarray(track.t)
        soc = np.asarray(track.soc)
        dep = np.asarray(track.deploy)
        har = np.asarray(track.harvest)
        score = np.asarray(track.score)
        reward = np.asarray(track.reward)
        risk = np.asarray(track.risk)
        mode = np.asarray(track.mode)

        # 1) SoC
        ax_soc.plot(t, soc, color=_GREEN, linewidth=1.6)
        ax_soc.fill_between(t, soc, 0, color=_GREEN, alpha=0.12)
        ax_soc.axhline(35, color=_AMBER, linestyle="--", linewidth=0.8)
        ax_soc.axhline(15, color=_RED, linestyle="--", linewidth=0.8)
        ax_soc.set_ylim(0, 105)
        ax_soc.set_ylabel("Est. SoC %", fontsize=9)

        # 2) Energy flow
        ax_flow.plot(t, har, color=_GREEN, linewidth=1.1)
        ax_flow.plot(t, -dep, color=_RED, linewidth=1.1)
        ax_flow.axhline(0, color=_GRID, linewidth=0.8)
        ax_flow.set_ylabel("EU/s", fontsize=9)

        # 3) Overtake score + mode bands
        for mid, colour in _MODE_COLOR.items():
            mask = mode == mid
            if mask.any():
                ax_score.fill_between(t, -100, 100, where=mask, color=colour,
                                      alpha=0.09, step="post")
        ax_score.plot(t, reward, color=_GREEN, linewidth=0.7, alpha=0.45)
        ax_score.plot(t, risk, color=_RED, linewidth=0.7, alpha=0.45)
        ax_score.plot(t, score, color=_TEXT, linewidth=1.3)
        ax_score.axhline(0, color=_GRID, linewidth=0.8)
        ax_score.set_ylim(-100, 100)
        ax_score.set_ylabel("Overtake score", fontsize=9)
        ax_score.set_xlabel("Race time (s)", fontsize=9)
        handles = [Patch(facecolor=_MODE_COLOR[m], alpha=0.5, label=_MODE_LABEL[m]) for m in (3, 2, 1, 0)]
        ax_score.legend(handles=handles, loc="upper left", fontsize=7, ncol=4,
                        framealpha=0.15, labelcolor=_DIM)

        cur_mode = _MODE_LABEL.get(int(mode[-1]), "?")
        self.status.setText(
            f"{self._selected}  |  SoC {soc[-1]:.0f}%  |  mode {cur_mode}  "
            f"|  score {score[-1]:.0f}  |  reward {reward[-1]:.0f} / risk {risk[-1]:.0f}"
        )
        self._canvas.draw_idle()
