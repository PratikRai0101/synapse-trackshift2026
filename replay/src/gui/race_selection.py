from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QPushButton, QTreeWidget, QTreeWidgetItem, QMessageBox, QDialog
)
from PySide6.QtWidgets import QProgressDialog
from PySide6.QtCore import QThread, Signal, Qt, QTimer
from src.gui.workers import DaemonWorker
#from PySide6.QtGui import QPixmap, QFont
import sys
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from src.f1_data import get_race_weekends_by_year, get_race_weekends_by_place, get_all_unique_race_names, load_session
from src.gui.settings_dialog import SettingsDialog
from src.gui.gp_carousel import GPCarouselDialog
from src.lib.season import get_season

def _close_progress_dialog(dialog, cancel_handler):
    """Close a completed progress dialog without emitting a false cancellation."""
    try:
        dialog.canceled.disconnect(cancel_handler)
    except (RuntimeError, TypeError):
        pass
    dialog.close()


# Worker thread to fetch schedule without blocking UI
class FetchScheduleWorker(DaemonWorker):
    result = Signal(object)
    error = Signal(str)

    def __init__(self, year, parent=None):
        super().__init__(parent)
        self.year = year

    def run(self): #check
        try:
            # enable cache if available in project
            try:
                from src.f1_data import enable_cache
                enable_cache()
            except Exception:
                pass
            events = get_race_weekends_by_year(self.year)
            self.result.emit(events)
        except Exception as e:
            self.error.emit(str(e))

class PopulatePlacesWorker(DaemonWorker):
    """Populate the race-name list without blocking the UI (scans many seasons)."""

    result = Signal(object)

    def run(self):
        try:
            from src.f1_data import enable_cache
            enable_cache()
        except Exception:
            pass
        try:
            self.result.emit(get_all_unique_race_names())
        except Exception:
            self.result.emit([])


class RaceSelectionWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self._places_worker = None
        self._session_worker = None
        self.loading_session = False
        self.selected_session_title = None
        self.current_year = get_season()
        self.selected_year=self.current_year 

        # Stop background QThreads before Qt tears down; otherwise
        # "QThread: Destroyed while thread is still running" aborts the process.
        try:
            app = QApplication.instance()
            if app is not None:
                app.aboutToQuit.connect(self._stop_workers)
        except Exception:
            pass

        self.setWindowTitle("F1 Race Replay - Session Selection")
        self._setup_ui()
        self.resize(1000, 700)
        self.setMinimumSize(800, 600)
        self.setWindowState(self.windowState())

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)

        # Header (title)
        header_layout = QHBoxLayout()
        header_label = QLabel("F1 Race Replay 🏎️")
        font = header_label.font()
        carousel_btn = QPushButton("🏁 Browse Grand Prix")
        carousel_btn.setCursor(Qt.PointingHandCursor)
        carousel_btn.setFixedHeight(32)
        carousel_btn.clicked.connect(self.open_carousel)
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setFixedHeight(32)
        settings_btn.clicked.connect(self.open_settings)
        font.setPointSize(18)
        font.setBold(True)
        header_label.setFont(font)
        header_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        header_layout.addWidget(carousel_btn)
        header_layout.addWidget(settings_btn)
        main_layout.addLayout(header_layout)

        # Year selection
        year_layout = QHBoxLayout()
        year_label = QLabel("Select Year:")
        self.year_combo = QComboBox()
        self.year_combo.addItem("All Years")

        for year in range(2018, self.current_year + 1):
            self.year_combo.addItem(str(year))

        self.year_combo.setCurrentText(str(self.current_year))
        self.year_combo.currentTextChanged.connect(self.load_by_year)

        year_layout.addWidget(year_label)
        year_layout.addWidget(self.year_combo)
        main_layout.addLayout(year_layout)

        #Race Selection
        place_layout=QHBoxLayout()
        place_label=QLabel("Select Race:")
        self.place_combo=QComboBox()
        self.place_combo.addItem("All Races")
        self.place_combo.currentTextChanged.connect(self.load_by_place)
        # Populate the race-name list off the UI thread (it scans many seasons).
        self._places_worker = PopulatePlacesWorker()
        self._places_worker.result.connect(self._populate_places)
        self._places_worker.start()


        place_layout.addWidget(place_label)
        place_layout.addWidget(self.place_combo)
        main_layout.addLayout(place_layout)

        # Main content: left = schedule, right = session list
        content_layout = QHBoxLayout()

        # Schedule tree (left)
        self.schedule_tree = QTreeWidget()
        self.schedule_tree.setHeaderLabels(["Round", "Event", "Country", "Start Date"])
        self.schedule_tree.setRootIsDecorated(False)
        content_layout.addWidget(self.schedule_tree, 3)
        self.schedule_tree.setColumnWidth(2, 180)

        # Session panel (right)
        self.session_panel = QWidget()
        self.session_panel_layout = QVBoxLayout()
        self.session_panel.setLayout(self.session_panel_layout)
        self.session_panel_layout.setAlignment(Qt.AlignTop)
        header_lbl = QLabel("Sessions")
        hdr_font = header_lbl.font()
        hdr_font.setPointSize(14)
        hdr_font.setBold(True)
        header_lbl.setFont(hdr_font)
        self.session_panel_layout.addWidget(header_lbl)

        # placeholder spacer
        self.session_list_container = QWidget()
        self.session_list_layout = QVBoxLayout()
        self.session_list_container.setLayout(self.session_list_layout)
        self.session_panel_layout.addWidget(self.session_list_container)

        content_layout.addWidget(self.session_panel, 1)

        main_layout.addLayout(content_layout)

        # connect click handler
        self.schedule_tree.itemClicked.connect(self.on_race_clicked)

        # Load initial schedule
        # hide sessions panel until a weekend is selected
        self.session_panel.hide()
        self.load_schedule(year=self.current_year)
        
    def load_schedule(self, year=None, events=None):
        if self.loading_session:
            return
        
        self.schedule_tree.clear()
        # hide sessions panel while loading / when nothing selected
        try:
            self.session_panel.hide()
        except Exception:
            pass
        
        #Race filter
        if events is not None:
            self.populate_schedule(events)
            self.loading_session = False
            return
        
        #Year filter
        if year is not None:
            self.loading_session = True
            self.worker = FetchScheduleWorker(int(year))
            self.worker.result.connect(self.populate_schedule)
            self.worker.error.connect(self.show_error)
            self.worker.start()
            return
        
        self.loading_session=False

    def load_by_year(self, year_text):
        if self.loading_session:
            return
        
        #Reset by_race filter
        if year_text!="All Years":
            self.place_combo.blockSignals(True)
            self.place_combo.setCurrentText("All Races")
            self.place_combo.blockSignals(False)

        if year_text=="All Years":
            self.selected_year=None
            self.schedule_tree.clear()
            return
        
        if not year_text.isdigit():
            return
        
        self.selected_year=int(year_text)
        self.load_schedule(year=self.selected_year)

    def load_by_place(self,race_name):
        if race_name=="All Races":
            if self.selected_year is not None:
                self.load_schedule(year=self.selected_year)
            return
        
        #Reset year filter
        self.year_combo.blockSignals(True)
        self.year_combo.setCurrentText("All Years")
        self.year_combo.blockSignals(False)
        self.selected_year=None

        self.schedule_tree.clear()
        
        events=get_race_weekends_by_place(race_name)
        self.load_schedule(events=events)

    def populate_schedule(self, events):
        self._events = list(events or [])
        for event in events:
            # Ensure all columns are strings (QTreeWidgetItem expects text)
            round_str = str(event.get("round_number", ""))
            name = str(event.get("event_name", ""))
            country = str(event.get("country", ""))
            date = str(event.get("date", ""))

            event_item = QTreeWidgetItem([round_str, name, country, date])
            event_item.setData(0, Qt.UserRole, event)
            self.schedule_tree.addTopLevelItem(event_item)

        # Make sure the round column is wide enough to be visible
        try:
            self.schedule_tree.resizeColumnToContents(0)
            self.schedule_tree.resizeColumnToContents(1)
        except Exception:
            pass

        self.loading_session = False

    def on_race_clicked(self, item, column):
        ev = item.data(0, Qt.UserRole)
        # ensure the sessions panel is visible when a race is selected
        try:
            self.session_panel.show()
        except Exception:
            pass
        # determine sessions to show
        ev_type = (ev.get("type") or "").lower()
        sessions = ["Qualifying", "Race"]
        if "sprint" in ev_type:
            sessions.insert(0, "Sprint Qualifying")
            # show sprint-related session
            sessions.insert(2, "Sprint")

        # clear existing session widgets
        for i in reversed(range(self.session_list_layout.count())):
            w = self.session_list_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        # determine which sessions have already occurred (data available)
        now = datetime.now(timezone.utc)
        session_dates = ev.get("session_dates", {})

        available_sessions = []
        for s in sessions:
            session_date_str = session_dates.get(s)
            if session_date_str:
                try:
                    session_dt = datetime.fromisoformat(session_date_str)
                    if session_dt <= now:
                        available_sessions.append(s)
                except Exception:
                    available_sessions.append(s)
            else:
                # no date info means historical data — assume available
                available_sessions.append(s)

        if not available_sessions:
            label = QLabel("Sessions not available")
            label.setAlignment(Qt.AlignCenter)
            self.session_list_layout.addWidget(label)
        else:
            for s in sessions:
                if s in available_sessions:
                    btn = QPushButton(s)
                    btn.clicked.connect(
                        lambda _, sname=s, e=ev: self._on_session_button_clicked(e, sname)
                    )
                    self.session_list_layout.addWidget(btn)

    def _on_session_button_clicked(self, ev, session_label):
        """Launch main.py in a separate process to run the selected session.

        Uses the same CLI flags that `main.py` understands: `--qualifying`,
        `--sprint-qualifying`, `--sprint`. Runs the command detached so the
        Qt UI remains responsive.
        """
        try:
            year = ev.get("year") or self.selected_year
        except Exception:
            year = None

        try:
            round_no = int(ev.get("round_number"))
        except Exception:
            round_no = None

        # map button labels to CLI flags
        flag = None
        if session_label == "Qualifying":
            flag = "--qualifying"
        elif session_label == "Sprint Qualifying":
            flag = "--sprint-qualifying"
        elif session_label == "Sprint":
            flag = "--sprint"

        main_path = os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "..", "main.py")
        )
        cmd = [sys.executable, main_path, "--viewer"]
        if year is not None:
            cmd += ["--year", str(year)]
        if round_no is not None:
            cmd += ["--round", str(round_no)]
        if flag:
            cmd.append(flag)
        if "--verbose" in sys.argv:
            cmd.append("--verbose")
        # Show a modal loading dialog and load the session in a background thread.
        event_name = ev.get("event_name", "session")
        dlg = QProgressDialog(
            f"Loading {event_name} — {session_label}…\n"
            "First run computes telemetry and can take a few minutes.",
            "Cancel", 0, 0, self,
        )
        dlg.setWindowTitle("Loading session")
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setRange(0, 0)

        launched_process = {"proc": None}

        def _cancel_load():
            try:
                proc = launched_process["proc"]
                if proc is not None and proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass

        dlg.canceled.connect(_cancel_load)
        dlg.show()
        QApplication.processEvents()

        # Map label -> fastf1 session type code
        session_code = 'R'
        if session_label == "Qualifying":
            session_code = 'Q'
        elif session_label == "Sprint Qualifying":
            session_code = 'SQ'
        elif session_label == "Sprint":
            session_code = 'S'

        class FetchSessionWorker(DaemonWorker):
            result = Signal(object)
            error = Signal(str)

            def __init__(self, year, round_no, session_type, parent=None):
                super().__init__(parent)
                self.year = year
                self.round_no = round_no
                self.session_type = session_type

            def run(self):
                try:
                    try:
                        from src.f1_data import enable_cache
                        enable_cache()
                    except Exception:
                        pass
                    sess = load_session(self.year, self.round_no, self.session_type)
                    self.result.emit(sess)
                except Exception as e:
                    self.error.emit(str(e))

        def _on_loaded(session_obj):
            if dlg.wasCanceled():
                try:
                    _close_progress_dialog(dlg, _cancel_load)
                except Exception:
                    pass
                return
            # create a unique ready-file path and pass it to the child
            ready_path = os.path.join(tempfile.gettempdir(), f"f1_ready_{uuid.uuid4().hex}")
            cmd_with_ready = list(cmd) + ["--ready-file", ready_path]

            try:
                proc = subprocess.Popen(cmd_with_ready)
                launched_process["proc"] = proc
            except Exception as exc:
                try:
                    _close_progress_dialog(dlg, _cancel_load)
                except Exception:
                    pass
                QMessageBox.critical(self, "Playback error", f"Failed to start playback:\n{exc}")
                return

            # Poll for ready file or child exit
            timer = QTimer(self)

            def _check_ready():
                try:
                    if os.path.exists(ready_path):
                        try:
                            _close_progress_dialog(dlg, _cancel_load)
                        except Exception:
                            pass
                        timer.stop()
                        try:
                            os.remove(ready_path)
                        except Exception:
                            pass
                        return
                    # if process exited early, show error
                    if proc.poll() is not None:
                        try:
                            _close_progress_dialog(dlg, _cancel_load)
                        except Exception:
                            pass
                        timer.stop()
                        QMessageBox.critical(self, "Playback error", "Playback process exited before signaling readiness")
                except Exception:
                    # ignore transient file-system errors
                    pass

            timer.timeout.connect(_check_ready)
            timer.start(200)
            # keep references
            self._play_proc = proc
            self._ready_timer = timer

        def _on_error(msg):
            try:
                _close_progress_dialog(dlg, _cancel_load)
            except Exception:
                pass
            QMessageBox.critical(self, "Load error", f"Failed to load session data:\n{msg}")

        worker = FetchSessionWorker(year, round_no, session_code)
        worker.result.connect(_on_loaded)
        worker.error.connect(_on_error)
        # Keep a reference so it doesn't get GC'd
        self._session_worker = worker
        worker.start()
    def show_error(self, message):
        QMessageBox.critical(self, "Error", f"Failed to load schedule: {message}")
        self.loading_session = False

    def _stop_workers(self):
        """Interrupt and join any running QThreads (prevents Qt shutdown abort)."""
        workers = [w for w in (
            getattr(self, "worker", None),
            getattr(self, "_places_worker", None),
            getattr(self, "_session_worker", None),
        ) if w is not None]
        for w in workers:
            try:
                if w.isRunning():
                    w.requestInterruption()
            except Exception:
                pass
        for w in workers:
            try:
                if w.isRunning():
                    w.wait(5000)
            except Exception:
                pass

    def closeEvent(self, event):
        self._stop_workers()
        super().closeEvent(event)

    def _populate_places(self, names):
        """Fill the race-name combo once the background scan finishes."""
        try:
            current = self.place_combo.currentText()
            self.place_combo.blockSignals(True)
            self.place_combo.addItems([n for n in (names or []) if n])
            self.place_combo.setCurrentText(current or "All Races")
            self.place_combo.blockSignals(False)
        except Exception:
            pass

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def open_carousel(self):
        """Open the circuit-first Grand Prix carousel and select the chosen GP."""
        events = getattr(self, "_events", None) or []
        year = self.selected_year or self.current_year
        if not events:
            try:
                events = get_race_weekends_by_year(year)
                self._events = list(events)
            except Exception as exc:
                self.show_error(str(exc))
                return
        dlg = GPCarouselDialog(events, year, self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_event:
            self._select_event_in_tree(dlg.selected_event)

    def _select_event_in_tree(self, ev):
        round_str = str(ev.get("round_number", ""))
        for i in range(self.schedule_tree.topLevelItemCount()):
            item = self.schedule_tree.topLevelItem(i)
            if item.text(0) == round_str:
                self.schedule_tree.setCurrentItem(item)
                self.on_race_clicked(item, 0)
                return
