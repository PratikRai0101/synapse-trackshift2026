"""Lightweight background workers backed by daemon threads + Qt signals.

Qt aborts the whole process if a running ``QThread`` is destroyed during
shutdown ("QThread: Destroyed while thread is still running"). A plain daemon
thread avoids this entirely: the interpreter can exit without waiting, and there
is no ``QThread`` object for Qt to tear down.

The public API mirrors the subset of ``QThread`` the app uses
(``start``/``isRunning``/``wait``/``requestInterruption``/``isInterruptionRequested``),
so existing call sites are unchanged. Signals are emitted from the worker thread
and delivered to the UI thread through Qt's queued connections, which is safe.
"""

from __future__ import annotations

import threading
from typing import Optional

from PySide6.QtCore import QObject


class DaemonWorker(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: Optional[threading.Thread] = None
        self._interrupted = threading.Event()

    # -- QThread-compatible API --------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._guarded_run, daemon=True)
        self._thread.start()

    def isRunning(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def requestInterruption(self) -> None:
        self._interrupted.set()

    def isInterruptionRequested(self) -> bool:
        return self._interrupted.is_set()

    def wait(self, msecs: int = 0) -> bool:
        thread = self._thread
        if thread is None:
            return True
        thread.join(None if not msecs else msecs / 1000.0)
        return not thread.is_alive()

    # -- to override -------------------------------------------------------
    def run(self) -> None:
        raise NotImplementedError

    def _guarded_run(self) -> None:
        try:
            self.run()
        except Exception:
            pass
