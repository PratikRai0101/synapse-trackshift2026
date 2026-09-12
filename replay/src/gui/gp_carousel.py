"""Grand Prix carousel: browse the season by circuit layout.

Each card shows the circuit outline (rendered from FastF1 telemetry, cached to
disk) with the Grand Prix name and circuit/country/date beneath it. Navigate
with the arrow buttons, the keyboard, or the dot strip; ``Select`` returns the
chosen event to the caller.

Circuit images are rendered lazily on a background thread so browsing never
blocks, and a stylised placeholder is shown until (or unless) the real map is
available.
"""

from __future__ import annotations

import os
import threading
from datetime import date as _date
from typing import List, Optional

from PySide6.QtCore import Qt, QThread, Signal, QSize
from src.gui.workers import DaemonWorker
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.track_map import cached_track_map, render_track_map

CARD_W = 720
CARD_H = 440
MAP_W = 660
MAP_H = 320

# Keep running render threads alive even if their dialog is closed.
_ACTIVE_WORKERS = set()

# Avoid rendering the same circuit twice across on-demand + prefetch threads.
_INFLIGHT = set()
_INFLIGHT_LOCK = threading.Lock()


def _claim(year: int, round_number: int) -> bool:
    key = (int(year), int(round_number))
    with _INFLIGHT_LOCK:
        if key in _INFLIGHT:
            return False
        _INFLIGHT.add(key)
        return True


def _release(year: int, round_number: int) -> None:
    with _INFLIGHT_LOCK:
        _INFLIGHT.discard((int(year), int(round_number)))


def _track(worker, registry):
    registry.add(worker)
    worker.finished.connect(lambda w=worker: registry.discard(w))

_BG = "#0b0b0e"
_PANEL = "#18181f"
_EDGE = "#3a3a48"
_RED = "#e10600"
_TEXT = "#f2f2f5"
_MUTED = "#8c8c98"


class TrackMapWorker(DaemonWorker):
    done = Signal(int, object)  # index, path or None

    def __init__(self, index: int, year: int, round_number: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.year = year
        self.round_number = round_number

    def run(self):
        if not _claim(self.year, self.round_number):
            self.done.emit(self.index, None)
            return
        try:
            path = render_track_map(self.year, self.round_number)
        except Exception:
            path = None
        finally:
            _release(self.year, self.round_number)
        self.done.emit(self.index, path)


class PrefetchWorker(DaemonWorker):
    """Renders missing circuit maps in the background, nearest cards first."""

    ready = Signal(int, object)  # round_number, path

    def __init__(self, year: int, rounds: List[int], parent=None):
        super().__init__(parent)
        self.year = year
        self.rounds = rounds

    def run(self):
        for rn in self.rounds:
            if self.isInterruptionRequested():
                return
            if cached_track_map(self.year, rn):
                self.ready.emit(int(rn), cached_track_map(self.year, rn))
                continue
            if not _claim(self.year, rn):
                continue
            try:
                path = render_track_map(self.year, rn)
            except Exception:
                path = None
            finally:
                _release(self.year, rn)
            if path:
                self.ready.emit(int(rn), path)


def _is_upcoming(ev: dict) -> bool:
    """True when the race weekend is in the future (no telemetry exists yet)."""
    date_str = str(ev.get("date", ""))
    if not date_str:
        return False
    try:
        return _date.fromisoformat(date_str[:10]) > _date.today()
    except ValueError:
        return False


def _placeholder_pixmap(text: str = "CIRCUIT MAP") -> QPixmap:
    pm = QPixmap(MAP_W, MAP_H)
    pm.fill(QColor(_PANEL))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(_EDGE), 3, Qt.DashLine))
    p.drawRoundedRect(24, 24, MAP_W - 48, MAP_H - 48, 40, 60)
    p.setPen(QColor(_MUTED))
    p.setFont(QFont("Helvetica", 13, QFont.Bold))
    p.drawText(pm.rect(), Qt.AlignCenter, text)
    p.end()
    return pm


class GPCarouselDialog(QDialog):
    """A circuit-first Grand Prix selector."""

    def __init__(self, events: List[dict], year: int, parent=None):
        super().__init__(parent)
        self.events = [e for e in events if e.get("round_number")]
        self.year = year
        self.index = 0
        self.selected_event: Optional[dict] = None
        self._workers: dict[int, TrackMapWorker] = {}
        self._placeholder = _placeholder_pixmap("RENDERING CIRCUIT…")
        self._upcoming = _placeholder_pixmap("UPCOMING GRAND PRIX")
        self._unavailable = _placeholder_pixmap("CIRCUIT MAP UNAVAILABLE")

        self.setWindowTitle(f"{year} Grand Prix — Circuit Selector")
        self.setFixedSize(CARD_W + 80, CARD_H + 210)
        self.setStyleSheet(
            f"QDialog {{ background: {_BG}; }}"
            f"QLabel {{ color: {_TEXT}; }}"
        )
        self._build_ui()
        if self.events:
            self._show(self._default_index())
        self._start_prefetch()

    def _default_index(self) -> int:
        """Open on the latest completed race (so the first card has a map)."""
        last = 0
        for i, ev in enumerate(self.events):
            if not _is_upcoming(ev):
                last = i
        return last

    def _start_prefetch(self):
        """Warm the remaining circuit maps in the background.

        Upcoming races are included so the previous-season fallback can fill in
        their layouts; they stay behind the "upcoming" placeholder until ready.
        """
        missing: List[int] = []
        for ev in self.events:
            try:
                rn = int(ev.get("round_number") or 0)
            except (TypeError, ValueError):
                continue
            if rn and not cached_track_map(self.year, rn):
                missing.append(rn)
        if not missing:
            return
        self._prefetch = PrefetchWorker(self.year, missing, None)
        self._prefetch.ready.connect(self._on_prefetch_ready)
        _track(self._prefetch, _ACTIVE_WORKERS)
        self._prefetch.start()

    def _on_prefetch_ready(self, round_number: int, path):
        if not path:
            return
        try:
            if self.index < len(self.events):
                cur = self.events[self.index].get("round_number")
                if cur is not None and int(cur) == int(round_number):
                    self._set_map(path)
        except (RuntimeError, ValueError, TypeError):
            pass

    # -- UI -----------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 24, 30, 20)
        root.setSpacing(12)

        title = QLabel("SELECT GRAND PRIX")
        tf = title.font()
        tf.setPointSize(15)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet(f"color: {_TEXT}; letter-spacing: 2px;")
        root.addWidget(title, alignment=Qt.AlignLeft)

        accent = QFrame()
        accent.setFixedHeight(3)
        accent.setStyleSheet(f"background: {_RED};")
        root.addWidget(accent)

        # Card
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {_PANEL}; border: 1px solid {_EDGE}; border-radius: 10px; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(6)

        self.map_label = QLabel()
        self.map_label.setAlignment(Qt.AlignCenter)
        self.map_label.setFixedSize(MAP_W, MAP_H)
        self.map_label.setPixmap(self._placeholder)
        card_layout.addWidget(self.map_label, alignment=Qt.AlignCenter)

        self.name_label = QLabel("")
        nf = self.name_label.font()
        nf.setPointSize(19)
        nf.setBold(True)
        self.name_label.setFont(nf)
        self.name_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.name_label)

        self.sub_label = QLabel("")
        sf = self.sub_label.font()
        sf.setPointSize(12)
        self.sub_label.setFont(sf)
        self.sub_label.setStyleSheet(f"color: {_MUTED};")
        self.sub_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.sub_label)

        root.addWidget(card, alignment=Qt.AlignCenter)

        # Navigation row
        nav = QHBoxLayout()
        nav.setSpacing(10)
        self.prev_btn = QPushButton("◀")
        self.next_btn = QPushButton("▶")
        for b in (self.prev_btn, self.next_btn):
            b.setFixedSize(46, 40)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton {{ background: {_PANEL}; color: {_TEXT};"
                f" border: 1px solid {_EDGE}; border-radius: 8px; font-size: 16px; }}"
                f"QPushButton:hover {{ border-color: {_RED}; }}"
            )
        self.prev_btn.clicked.connect(lambda: self._step(-1))
        self.next_btn.clicked.connect(lambda: self._step(1))

        self.dots_label = QLabel("")
        self.dots_label.setAlignment(Qt.AlignCenter)
        self.dots_label.setStyleSheet(f"color: {_MUTED}; font-size: 13px;")

        nav.addStretch()
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.dots_label)
        nav.addWidget(self.next_btn)
        nav.addStretch()
        root.addLayout(nav)

        # Actions
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        select = QPushButton("Load this Grand Prix")
        for b in (cancel, select):
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(38)
            b.setStyleSheet(
                f"QPushButton {{ background: {_PANEL}; color: {_TEXT};"
                f" border: 1px solid {_EDGE}; border-radius: 8px; padding: 0 16px; }}"
                f"QPushButton:hover {{ border-color: {_RED}; }}"
            )
        select.setStyleSheet(
            f"QPushButton {{ background: {_RED}; color: white; font-weight: bold;"
            f" border: none; border-radius: 8px; padding: 0 18px; }}"
            f"QPushButton:hover {{ background: #ff2a1f; }}"
        )
        cancel.clicked.connect(self.reject)
        select.clicked.connect(self._accept)
        actions.addWidget(cancel)
        actions.addWidget(select)
        root.addLayout(actions)

    # -- navigation ---------------------------------------------------------
    def _step(self, delta: int):
        if not self.events:
            return
        self._show((self.index + delta) % len(self.events))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Left, Qt.Key_A):
            self._step(-1)
        elif event.key() in (Qt.Key_Right, Qt.Key_D):
            self._step(1)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._accept()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def _accept(self):
        if self.events:
            self.selected_event = self.events[self.index]
            self.accept()

    # -- rendering ----------------------------------------------------------
    def _show(self, index: int):
        if not self.events:
            return
        self.index = index
        ev = self.events[index]
        name = ev.get("event_name", "Grand Prix")
        location = ev.get("location", "")
        country = ev.get("country", "")
        date = ev.get("date", "")
        round_no = ev.get("round_number", "")

        self.name_label.setText(name)
        parts = [p for p in (location, country) if p]
        line = " • ".join(parts)
        if date:
            line = f"{line}    |    {date}" if line else date
        self.sub_label.setText(f"Round {round_no}    |    {line}")

        self.dots_label.setText(f"{index + 1} / {len(self.events)}")
        self.prev_btn.setEnabled(len(self.events) > 1)
        self.next_btn.setEnabled(len(self.events) > 1)

        # Prefer a cached map (including a previous-season fallback).
        cached = cached_track_map(self.year, int(round_no))
        if cached:
            self._set_map(cached)
            return

        # Future races have no telemetry yet: show an upcoming placeholder.
        # The background prefetch may still fill in a previous-season layout.
        if _is_upcoming(ev):
            self.map_label.setPixmap(self._upcoming)
            return

        self.map_label.setPixmap(self._placeholder)
        if index in self._workers:
            return
        worker = TrackMapWorker(index, self.year, int(round_no), None)
        worker.done.connect(self._on_map_ready)
        _track(worker, _ACTIVE_WORKERS)
        self._workers[index] = worker
        worker.start()

    def _set_map(self, path: str):
        pm = QPixmap(path)
        if pm.isNull():
            self.map_label.setPixmap(self._unavailable)
            return
        self.map_label.setPixmap(
            pm.scaled(MAP_W, MAP_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _on_map_ready(self, index: int, path):
        self._workers.pop(index, None)
        try:
            if self.index == index:
                if path:
                    self._set_map(path)
                else:
                    self.map_label.setPixmap(self._unavailable)
        except RuntimeError:
            # Dialog was torn down while the render finished; ignore.
            pass

    def closeEvent(self, event):
        # Stop background render threads before Qt tears down, otherwise a
        # running QThread is destroyed and aborts the process.
        for w in list(self._workers.values()):
            try:
                w.requestInterruption()
            except Exception:
                pass
        for w in list(self._workers.values()):
            try:
                if w.isRunning():
                    w.wait(4000)
            except Exception:
                pass
        try:
            if getattr(self, "_prefetch", None) is not None:
                self._prefetch.requestInterruption()
        except Exception:
            pass
        super().closeEvent(event)
