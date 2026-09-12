"""F1 broadcast-style design tokens and drawing helpers.

The replay's original UI used plain primitives on flat black. This module gives
it a coherent broadcast personality: carbon background, glassy panels with
team-colour edges, electric/energy accents and a small set of semantic colours
used consistently by every HUD component.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

import arcade

RGB = Tuple[int, int, int]

# --- palette ---------------------------------------------------------------
CARBON: RGB = (10, 10, 13)
CARBON_2: RGB = (16, 16, 21)
PANEL: RGB = (20, 20, 26)
PANEL_2: RGB = (28, 28, 35)
EDGE: RGB = (58, 58, 72)
EDGE_SOFT: RGB = (38, 38, 48)
TRACK_ASPHALT: RGB = (46, 46, 52)

F1_RED: RGB = (225, 6, 0)
ELECTRIC: RGB = (0, 214, 255)
GREEN: RGB = (0, 210, 106)
AMBER: RGB = (255, 184, 0)
DANGER: RGB = (255, 72, 72)

TEXT: RGB = (242, 242, 245)
MUTED: RGB = (140, 140, 152)
WHITE: RGB = (255, 255, 255)

MODE_COLORS = {
    "ATTACK": F1_RED,
    "BALANCED": ELECTRIC,
    "HARVEST": GREEN,
    "LIFT & COAST": AMBER,
}

VERDICT_COLORS = {
    "HIGH": GREEN,
    "MEDIUM": AMBER,
    "LOW": MUTED,
    "AVOID": DANGER,
}


def mode_color(mode: str) -> RGB:
    return MODE_COLORS.get(mode, ELECTRIC)


def verdict_color(verdict: str) -> RGB:
    return VERDICT_COLORS.get(verdict, MUTED)


def soc_color(soc: float) -> RGB:
    """Green when healthy, amber when low, red when nearly empty."""
    if soc >= 55.0:
        return GREEN
    if soc >= 30.0:
        return AMBER
    return DANGER


def lerp_color(a: Sequence[int], b: Sequence[int], t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def draw_panel(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    *,
    fill: RGB = PANEL,
    fill_alpha: int = 228,
    edge: RGB = EDGE,
    edge_width: int = 1,
    accent: Optional[RGB] = None,
    accent_width: int = 6,
) -> None:
    """Draw a broadcast-style glass panel with an optional left accent bar."""
    rect = arcade.XYWH(center_x, center_y, width, height)
    arcade.draw_rect_filled(rect, (*fill, fill_alpha))
    arcade.draw_rect_outline(rect, edge, edge_width)
    if accent is not None:
        left = center_x - width / 2
        arcade.draw_rect_filled(
            arcade.XYWH(left + accent_width / 2, center_y, accent_width, height),
            accent,
        )


def draw_meter(
    left: float,
    center_y: float,
    width: float,
    height: float,
    frac: float,
    color: RGB,
    *,
    bg: RGB = (34, 34, 42),
    border: Optional[RGB] = EDGE_SOFT,
) -> None:
    """Draw a horizontal meter. ``frac`` is clamped to 0..1."""
    frac = max(0.0, min(1.0, frac))
    arcade.draw_rect_filled(arcade.XYWH(left + width / 2, center_y, width, height), bg)
    if frac > 0.0:
        arcade.draw_rect_filled(
            arcade.XYWH(left + (width * frac) / 2, center_y, width * frac, height),
            color,
        )
    if border is not None:
        arcade.draw_rect_outline(arcade.XYWH(left + width / 2, center_y, width, height), border, 1)


def chip_width(text: str, size: int = 11, pad_x: float = 10) -> float:
    """Width a :func:`draw_chip` chip will occupy for ``text``."""
    return pad_x * 2 + len(text) * size * 0.62


def draw_chip(
    left: float,
    center_y: float,
    text: str,
    color: RGB,
    *,
    size: int = 11,
    pad_x: float = 10,
    height: float = 20,
) -> float:
    """Draw a small filled label chip. Returns its width."""
    width = chip_width(text, size, pad_x)
    arcade.draw_rect_filled(arcade.XYWH(left + width / 2, center_y, width, height), color)
    arcade.draw_text(
        text,
        left + width / 2,
        center_y,
        (12, 12, 12),
        size,
        anchor_x="center",
        anchor_y="center",
        bold=True,
    )
    return width
