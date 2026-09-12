"""Broadcast-style Race Engineer HUD.

Renders a :class:`~src.intelligence.race_engineer.DecisionReport` as an F1
broadcast "lower third": the recommended deployment mode, estimated battery
state, and the overtake-window risk/reward, plus compliance flags.

Text is drawn through cached :class:`arcade.Text` objects so the panel updates
every frame without the cost (and warning) of ``arcade.draw_text``.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import arcade

from src.intelligence.race_engineer import DecisionReport
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
    mode_color,
    soc_color,
    verdict_color,
)

RGB = Tuple[int, int, int]


class RaceEngineerHUD:
    """Draws the Race Engineer decision panel for the focus driver."""

    def __init__(self, width: float = 820.0, height: float = 168.0, bottom_y: float = 130.0):
        self.width = width
        self.height = height
        self.bottom_y = bottom_y
        self._texts: Dict[str, arcade.Text] = {}

    # -- text cache ---------------------------------------------------------
    def _t(
        self,
        key: str,
        text: str,
        x: float,
        y: float,
        size: int,
        color: RGB = TEXT,
        bold: bool = False,
        anchor_x: str = "left",
    ) -> None:
        obj = self._texts.get(key)
        if obj is None:
            obj = arcade.Text(text, x, y, color, size, bold=bold, anchor_x=anchor_x, anchor_y="center")
            self._texts[key] = obj
        else:
            obj.text = text
            obj.x = x
            obj.y = y
            obj.color = color
            obj.font_size = size
            obj.bold = bold
        obj.draw()

    # -- main draw ----------------------------------------------------------
    def draw(self, window, report: Optional[DecisionReport], visible: bool = True) -> None:
        if not visible or report is None:
            return

        # Fit between the left driver panels and the right leaderboard.
        left_bound = getattr(window, "left_ui_margin", 340) + 4
        right_bound = window.width - getattr(window, "right_ui_margin", 260) - 10
        avail = right_bound - left_bound
        if avail < 420:
            left_bound = 20
            right_bound = window.width - 20
            avail = right_bound - left_bound
        w = min(self.width, avail - 6)
        h = self.height
        cx = (left_bound + right_bound) / 2
        cy = self.bottom_y + h / 2
        left = cx - w / 2
        top = cy + h / 2
        pad = 18

        team = window.driver_colors.get(report.code, ELECTRIC)
        draw_panel(cx, cy, w, h, fill=PANEL, fill_alpha=232, edge=EDGE, edge_width=1,
                   accent=team, accent_width=6)

        # --- header ---
        self._t("title", "RACE ENGINEER", left + pad, top - 22, 12, MUTED, bold=True)
        title_w = getattr(self._texts.get("title"), "content_width", 110.0)
        draw_chip(left + pad + title_w + 8, top - 22, "EST", MUTED, size=8, height=14, pad_x=5)
        lap = report.energy.lap
        lap_total = getattr(window, "total_laps", None) or "-"
        self._t(
            "code",
            f"{report.code}   P{getattr(report, 'position', '-')}   LAP {lap}/{lap_total}",
            left + w - pad, top - 22, 12, TEXT, bold=True, anchor_x="right",
        )

        # --- energy row ---
        y = top - 54
        self._t("energy_lbl", "ENERGY", left + pad, y, 10, MUTED, bold=True)
        meter_x = left + 86
        meter_w = 190
        soc = report.energy.soc
        draw_meter(meter_x, y, meter_w, 12, soc / 100.0, soc_color(soc))
        self._t("soc", f"{soc:.0f}%", meter_x + meter_w + 8, y, 13, soc_color(soc), bold=True)

        mode = report.advice.mode
        cw = chip_width(mode, 11)
        draw_chip(left + w - pad - cw, y, mode, mode_color(mode), size=11, height=20)

        # --- meta row (energy balance + compliance) ---
        y = top - 82
        net = report.energy.balance
        self._t("net", f"net {net:+.1f} EU/s", left + 86, y, 10, GREEN if net >= 0 else AMBER)
        self._t("sustain", f"sustain {report.energy.sustainability:.2f}", left + 196, y, 10, MUTED)
        self._draw_compliance(right_bound=left + w - pad, y=y, report=report)

        # --- overtake row ---
        y = top - 112
        self._t("ot_lbl", "OVERTAKE", left + pad, y, 10, MUTED, bold=True)
        ov = report.overtake
        if ov is not None:
            self._t("gap", f"gap {self._gap_text(window)}", left + 104, y, 11, TEXT)
            self._t("rw_lbl", "reward", left + 200, y, 10, MUTED)
            draw_meter(left + 248, y, 70, 9, ov.reward / 100.0, GREEN)
            self._t("rw_val", f"{ov.reward:.0f}", left + 326, y, 11, GREEN, bold=True)
            self._t("rk_lbl", "risk", left + 362, y, 10, MUTED)
            draw_meter(left + 396, y, 70, 9, ov.risk / 100.0, DANGER)
            self._t("rk_val", f"{ov.risk:.0f}", left + 474, y, 11, DANGER, bold=True)

            vcw = chip_width(ov.verdict, 10, pad_x=8)
            vx = left + w - pad - vcw
            draw_chip(vx, y, ov.verdict, verdict_color(ov.verdict), size=10, height=18, pad_x=8)
            self._t("prob", f"{ov.probability * 100:.0f}%", vx - 8, y, 11, TEXT, bold=True, anchor_x="right")
        else:
            self._t("gap", "no car ahead", left + 104, y, 11, MUTED)

        # --- advice row ---
        y = top - 140
        self._t("advice", report.advice.reason, left + pad, y, 11, TEXT)

    # -- helpers ------------------------------------------------------------
    def _draw_compliance(self, right_bound: float, y: float, report: DecisionReport) -> None:
        flags: List[Tuple[str, RGB]] = []
        for flag in report.compliance:
            col = GREEN if flag.state == "ok" else (AMBER if flag.state == "warn" else MUTED)
            flags.append((flag.detail[:18], col))
        flags = flags[:3]
        if not flags:
            return
        gap = 8
        widths = [chip_width(t, 9, pad_x=7) for t, _ in flags]
        x = right_bound - (sum(widths) + gap * (len(flags) - 1))
        for (text, col), cw in zip(flags, widths):
            draw_chip(x, y, text, col, size=9, height=16, pad_x=7)
            x += cw + gap

    @staticmethod
    def _gap_text(window) -> str:
        gap = getattr(window, "_focus_gap_ahead_s", None)
        return "n/a" if gap is None else f"{gap:.1f}s"
