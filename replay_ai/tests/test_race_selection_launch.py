from unittest.mock import Mock

from PySide6.QtWidgets import QApplication, QProgressDialog

from src.gui.race_selection import _close_progress_dialog


def test_successfully_closing_loading_dialog_does_not_terminate_replay():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)

    process = Mock()
    process.poll.return_value = None
    dialog = QProgressDialog("Loading", "Cancel", 0, 0)

    def cancel_playback():
        if process.poll() is None:
            process.terminate()

    dialog.canceled.connect(cancel_playback)
    dialog.show()
    app.processEvents()

    _close_progress_dialog(dialog, cancel_playback)
    app.processEvents()

    process.terminate.assert_not_called()
