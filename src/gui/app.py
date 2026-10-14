"""Main window of the AnimeUnity downloader desktop application.

Collects the download parameters (URL, episode filters, destination folder),
runs the downloader through a QProcess, and renders its JSON progress events
as live progress bars.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# The PySide6 stubs confuse astroid's member resolution; the Qt imports below
# resolve correctly at runtime.
# pylint: disable=no-name-in-module
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.version import __version__
from .theme import DANGER, MUTED, STYLESHEET, SUCCESS, VIOLET
from .worker import DownloadWorker

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "anime_downloader.py"
ICON_PATH = REPO_ROOT / "assets" / "logo.png"

MODE_ALL = 0
MODE_RANGE = 1
MODE_EPISODES = 2

_STATUS_COLORS = {
    "idle": MUTED,
    "running": VIOLET,
    "success": SUCCESS,
    "error": DANGER,
}


class MainWindow(QMainWindow):
    """Main window of the AnimeUnity downloader desktop application."""

    # UI classes naturally hold many widget references and the builder methods
    # assign them outside __init__, which trips pylint's refactoring checks;
    # a window also exposes few truly public methods by design.
    # pylint: disable=too-many-instance-attributes, attribute-defined-outside-init
    # pylint: disable=too-few-public-methods

    def __init__(self) -> None:
        """Build the interface and restore persisted settings."""
        super().__init__()
        self._settings = QSettings("AnimeUnityDownloader", "GUI")
        self._worker = DownloadWorker(self)
        self._episode_rows: dict[int, dict] = {}
        self._overall_task_id: int | None = None
        self._last_error: str | None = None
        self._cancelled = False

        self._build_ui()
        self._connect_worker()
        self._restore_settings()

    # ============================
    # Interface construction
    # ============================
    def _build_ui(self) -> None:
        """Construct all widgets of the main window."""
        self.setWindowTitle("AnimeUnity Downloader")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(900, 820)
        self.setMinimumSize(780, 740)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_input_card())
        layout.addWidget(self._build_results_card(), 1)
        layout.addWidget(self._build_log_card())

        self.setCentralWidget(central)

    @staticmethod
    def _make_field_label(text: str) -> QLabel:
        """Create a small caption label used above input fields."""
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _build_header(self) -> QWidget:
        """Build the title header with the project logo."""
        header = QWidget()
        layout = QHBoxLayout(header)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(14)

        logo_label = QLabel()
        pixmap = QPixmap(str(ICON_PATH))
        if not pixmap.isNull():
            logo_label.setPixmap(
                pixmap.scaled(
                    36,
                    36,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ),
            )

        title = QLabel("AnimeUnity Downloader")
        title.setObjectName("titleLabel")
        subtitle = QLabel(f"v{__version__} · desktop interface")
        subtitle.setObjectName("subtitleLabel")

        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)

        layout.addWidget(logo_label)
        layout.addLayout(text_layout)
        layout.addStretch()
        return header

    def _build_input_card(self) -> QFrame:
        """Build the card with URL, episode filters, folder, and buttons."""
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum,
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(0)

        self._url_edit = QLineEdit()
        self._url_edit.setObjectName("urlEdit")
        self._url_edit.setPlaceholderText("https://www.animeunity.so/anime/…")
        self._url_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed,
        )

        outer.addWidget(self._make_field_label("Anime URL"))
        outer.addSpacing(4)
        outer.addWidget(self._url_edit)
        outer.addSpacing(12)
        outer.addWidget(self._build_mode_selector())
        outer.addSpacing(8)
        outer.addWidget(self._build_filter_stack())
        outer.addSpacing(12)
        outer.addWidget(self._build_folder_row())
        outer.addSpacing(10)
        outer.addWidget(self._build_workers_row())
        outer.addSpacing(14)
        outer.addWidget(self._build_button_row())
        return card

    def _build_mode_selector(self) -> QWidget:
        """Build the segmented control choosing the episode filter mode."""
        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed,
        )

        self._mode_group = QButtonGroup(self)
        self._mode_buttons: list[QToolButton] = []

        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for mode_id, text in enumerate(("All episodes", "Range", "Episodes")):
            button = QToolButton()
            button.setText(text)
            button.setCheckable(True)
            button.setObjectName("segButton")
            self._mode_group.addButton(button, mode_id)
            self._mode_buttons.append(button)
            row.addWidget(button)

        self._mode_buttons[MODE_ALL].setChecked(True)
        self._mode_group.idClicked.connect(self._on_mode_changed)
        row.addStretch()
        return container

    def _build_filter_stack(self) -> QStackedWidget:
        """Build the per-mode input widgets shown under the mode selector."""
        self._filter_stack = QStackedWidget()
        self._filter_stack.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed,
        )
        self._filter_stack.setMinimumHeight(32)

        all_page = QLabel("Every available episode will be downloaded.")
        all_page.setObjectName("hintLabel")
        self._filter_stack.addWidget(all_page)

        range_page = QWidget()
        range_layout = QHBoxLayout(range_page)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(8)
        start_label = self._make_field_label("From episode")
        end_label = self._make_field_label("to episode")
        self._start_spin = self._make_episode_spin("0 = not set")
        self._end_spin = self._make_episode_spin("0 = not set")
        range_layout.addWidget(start_label)
        range_layout.addWidget(self._start_spin)
        range_layout.addWidget(end_label)
        range_layout.addWidget(self._end_spin)
        range_layout.addStretch()
        self._filter_stack.addWidget(range_page)

        episodes_page = QWidget()
        episodes_layout = QHBoxLayout(episodes_page)
        episodes_layout.setContentsMargins(0, 0, 0, 0)
        episodes_layout.setSpacing(8)
        self._episodes_edit = QLineEdit()
        self._episodes_edit.setPlaceholderText("1,3,7 or 1 3 7")
        episodes_layout.addWidget(self._make_field_label("Episodes"))
        episodes_layout.addWidget(self._episodes_edit, 1)
        self._filter_stack.addWidget(episodes_page)

        self._filter_stack.setCurrentIndex(MODE_ALL)
        return self._filter_stack

    @staticmethod
    def _make_episode_spin(tooltip: str) -> QSpinBox:
        """Create a spin box for an episode bound, where 0 means 'not set'."""
        spin = QSpinBox()
        spin.setRange(0, 99999)
        spin.setToolTip(tooltip)
        return spin

    def _build_folder_row(self) -> QWidget:
        """Build the download folder selector row."""
        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed,
        )
        container.setMinimumHeight(32)

        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._folder_edit = QLineEdit()
        self._folder_edit.setObjectName("folderEdit")
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setPlaceholderText("Default: <project>/Downloads")

        self._browse_button = QPushButton("Browse…")
        self._browse_button.setObjectName("browseButton")
        self._browse_button.clicked.connect(self._on_browse_clicked)

        row.addWidget(self._make_field_label("Download folder"))
        row.addWidget(self._folder_edit, 1)
        row.addWidget(self._browse_button)
        return container

    def _build_workers_row(self) -> QWidget:
        """Build the row selecting how many episodes download in parallel."""
        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed,
        )
        container.setMinimumHeight(32)

        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._workers_spin = QSpinBox()
        self._workers_spin.setRange(1, 16)
        self._workers_spin.setValue(2)
        self._workers_spin.setToolTip(
            "How many episodes download simultaneously (1–16).",
        )

        suffix = QLabel("episodes in parallel")
        suffix.setObjectName("hintLabel")

        row.addWidget(self._make_field_label("Parallel downloads"))
        row.addWidget(self._workers_spin)
        row.addWidget(suffix, 1)
        return container

    def _build_button_row(self) -> QWidget:
        """Build the row with the start and cancel buttons."""
        container = QWidget()
        container.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed,
        )
        container.setMinimumHeight(40)

        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch()

        self._start_button = QPushButton("Start Download")
        self._start_button.setObjectName("startButton")
        self._start_button.clicked.connect(self._on_start_clicked)

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("cancelButton")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)

        row.addWidget(self._start_button)
        row.addWidget(self._cancel_button)
        return container

    def _build_results_card(self) -> QFrame:
        """Build the card with the anime info, overall bar, and episode rows."""
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding,
        )
        card.setMinimumHeight(320)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        self._anime_label = QLabel("Ready.")
        self._anime_label.setObjectName("animeName")
        self._status_label = QLabel("idle")
        self._status_label.setObjectName("statusLabel")
        header_row.addWidget(self._anime_label, 1)
        header_row.addWidget(self._status_label)

        self._path_label = QLabel("")
        self._path_label.setObjectName("pathHint")

        self._overall_bar = QProgressBar()
        self._overall_bar.setObjectName("overallBar")
        self._overall_bar.setRange(0, 1)
        self._overall_bar.setValue(0)
        self._overall_bar.setFormat("%v / %m episodes")

        rows_scroll = QScrollArea()
        rows_scroll.setWidgetResizable(True)
        rows_container = QWidget()
        self._rows_layout = QVBoxLayout(rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(6)
        self._rows_layout.addStretch()
        rows_scroll.setWidget(rows_container)

        layout.addLayout(header_row)
        layout.addWidget(self._path_label)
        layout.addWidget(self._overall_bar)
        layout.addWidget(rows_scroll, 1)
        return card

    def _build_log_card(self) -> QFrame:
        """Build the card with the read-only log pane."""
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum,
        )
        card.setMinimumHeight(140)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(6)

        self._log_pane = QPlainTextEdit()
        self._log_pane.setObjectName("logPane")
        self._log_pane.setReadOnly(True)
        self._log_pane.setMaximumHeight(130)

        layout.addWidget(self._make_field_label("Log"))
        layout.addWidget(self._log_pane)
        return card

    # ============================
    # Wiring
    # ============================
    def _connect_worker(self) -> None:
        """Wire the worker signals to the interface slots."""
        self._worker.event_received.connect(self._on_event)
        self._worker.log_line.connect(self._on_log_line)
        self._worker.failed_to_start.connect(self._on_failed_to_start)
        self._worker.finished.connect(self._on_worker_finished)

    def _restore_settings(self) -> None:
        """Restore the last used download folder and worker count."""
        folder = str(self._settings.value("last_folder", ""))
        if folder and Path(folder).is_dir():
            self._folder_edit.setText(folder)

        last_workers = self._settings.value("last_workers", 2)
        try:
            workers_value = int(last_workers)
        except (TypeError, ValueError):
            workers_value = 2
        workers_value = max(1, min(16, workers_value))
        self._workers_spin.setValue(workers_value)

    # ============================
    # Slots
    # ============================
    def _on_mode_changed(self, mode_id: int) -> None:
        """Show the input widgets matching the selected filter mode."""
        self._filter_stack.setCurrentIndex(mode_id)

    def _on_browse_clicked(self) -> None:
        """Open the native folder picker and persist the chosen folder."""
        current = self._folder_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select download folder",
            current,
        )
        if folder:
            self._folder_edit.setText(folder)
            self._settings.setValue("last_folder", folder)

    def _on_start_clicked(self) -> None:
        """Validate the form and launch the download process."""
        try:
            arguments = self._build_arguments()
        except ValueError as validation_error:
            self._set_status(str(validation_error), "error")
            return

        self._settings.setValue("last_workers", self._workers_spin.value())

        self._reset_results()
        self._last_error = None
        self._cancelled = False
        self._set_running(True)
        self._set_status("Fetching anime info…", "running")
        self._worker.start(SCRIPT_PATH, arguments, str(REPO_ROOT))

    def _on_cancel_clicked(self) -> None:
        """Abort the running download."""
        self._cancelled = True
        self._set_status("Cancelling…", "running")
        self._worker.cancel()

    def _on_event(self, event: dict) -> None:
        """React to a single progress event from the downloader."""
        kind = event.get("event")

        if kind == "anime":
            self._anime_label.setText(str(event.get("name", "Unknown")))
            self._path_label.setText(f"Saving to: {event.get('path', '')}")
        elif kind == "task":
            self._on_task_event(event)
        elif kind == "update":
            self._on_update_event(event)
        elif kind == "advance":
            if event.get("id") == self._overall_task_id:
                self._overall_bar.setValue(self._overall_bar.value() + 1)
        elif kind == "done":
            self._set_status("Download finished", "success")
        elif kind == "error":
            self._last_error = str(event.get("message", "Unknown error"))
            self._set_status(f"Error: {self._last_error}", "error")
        elif kind == "fail":
            self._on_fail_event(event)

    def _on_task_event(self, event: dict) -> None:
        """Register the overall task or create a row for an episode task."""
        task_id = event.get("id")
        description = str(event.get("desc", ""))

        if description == "Progress":
            self._overall_task_id = task_id
            total = int(event.get("total") or 0)
            self._overall_bar.setRange(0, max(total, 1))
            self._overall_bar.setValue(0)
            return

        row = self._create_episode_row(description)
        self._episode_rows[task_id] = row

    def _on_update_event(self, event: dict) -> None:
        """Apply a progress update to its episode row."""
        row = self._episode_rows.get(event.get("id"))
        if row is None:
            return

        completed = event.get("completed")
        visible = event.get("visible")

        if completed is not None:
            percentage = min(max(float(completed), 0.0), 100.0)
            value = int(round(percentage))
            row["bar"].setValue(value)
            row["bar"].setFormat(f"{value}%")
            # Any percentage update means the bar is no longer queued.
            self._set_row_state(row["bar"], "active")

        if visible is True:
            # Retry signal: ensure the bar shows the active gradient even
            # if the row had been marked failed.
            self._set_row_state(row["bar"], "active")
        elif visible is False and completed is not None and float(completed) >= 100.0:
            row["done"] = True
            row["bar"].setValue(100)
            row["bar"].setFormat("100%")
            self._set_row_state(row["bar"], "done")

    def _on_fail_event(self, event: dict) -> None:
        """Mark a single episode row as failed via its bar state."""
        row = self._episode_rows.get(event.get("id"))
        if row is None:
            return
        row["failed"] = True
        self._set_row_state(row["bar"], "failed")

    def _on_log_line(self, line: str) -> None:
        """Append a log line and keep the newest line visible."""
        self._log_pane.appendPlainText(line)

    def _on_failed_to_start(self, message: str) -> None:
        """Handle a failure to spawn the downloader process."""
        self._set_running(False)
        self._set_status(message, "error")

    def _on_worker_finished(self, exit_code: int) -> None:
        """Finalize the interface state after the downloader process ended."""
        self._set_running(False)

        if self._cancelled:
            self._mark_incomplete_rows()
            self._set_status(
                "Cancelled — partially downloaded files may remain.", "error",
            )
            return

        if exit_code != 0:
            self._mark_incomplete_rows()
            if self._last_error:
                self._set_status(f"Error: {self._last_error}", "error")
            else:
                self._set_status(
                    f"The downloader exited with code {exit_code}. See log.", "error",
                )
            return

        if not self._episode_rows:
            self._set_status("No episodes matched your filters.", "error")
            return

        completed = sum(1 for row in self._episode_rows.values() if row["done"])
        total = len(self._episode_rows)
        if completed < total:
            self._mark_incomplete_rows()
        failed = sum(1 for row in self._episode_rows.values() if row["failed"])
        if failed:
            self._set_status(
                f"Completed {completed} of {total} episodes ({failed} failed).",
                "success" if completed == total - failed else "error",
            )
            return
        self._set_status(f"Completed {completed} of {total} episodes.", "success")

    # ============================
    # Helpers
    # ============================
    def cleanup(self) -> None:
        """Kill the download process when the application is quitting."""
        if self._worker.is_running:
            self._worker.cancel()

    def _set_running(self, running: bool) -> None:
        """Toggle the interface between the running and idle states."""
        self._start_button.setEnabled(not running)
        self._cancel_button.setEnabled(running)

        widgets = (
            self._url_edit,
            self._start_spin,
            self._end_spin,
            self._episodes_edit,
            self._folder_edit,
            self._workers_spin,
        )
        for widget in widgets:
            widget.setEnabled(not running)
        for button in self._mode_buttons:
            button.setEnabled(not running)
        self._browse_button.setEnabled(not running)

    def _set_status(self, text: str, kind: str) -> None:
        """Show a status message colored by its kind."""
        color = _STATUS_COLORS.get(kind, MUTED)
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color};")

    def _reset_results(self) -> None:
        """Clear previous results before a new download starts."""
        self._anime_label.setText("Fetching anime info…")
        self._path_label.setText("")
        self._overall_task_id = None
        self._overall_bar.setRange(0, 1)
        self._overall_bar.setValue(0)

        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._episode_rows.clear()
        self._log_pane.clear()

    def _create_episode_row(self, description: str) -> dict:
        """Create one progress row for an episode and add it to the list."""
        frame = QFrame()
        frame.setObjectName("episodeRow")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        name_label = QLabel(description)
        name_label.setObjectName("episodeName")

        progress_bar = QProgressBar()
        progress_bar.setObjectName("episodeBar")
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setTextVisible(True)
        progress_bar.setFormat("0%")
        self._set_row_state(progress_bar, "queued")

        layout.addWidget(name_label, 1)
        layout.addWidget(progress_bar, 2)

        self._rows_layout.insertWidget(self._rows_layout.count() - 1, frame)
        # The row is freshly created with no parent; make it visible
        # immediately so the user sees the full scope of work as soon as
        # the downloader registers the task.
        frame.show()
        return {
            "frame": frame,
            "bar": progress_bar,
            "done": False,
            "failed": False,
        }

    @staticmethod
    def _set_row_state(progress_bar: QProgressBar, state: str) -> None:
        """Set the bar's state dynamic property and re-polish its style.

        The bar's ``state`` property (``queued``, ``active``, ``done``,
        ``failed``, ``incomplete``) is consumed by the QSS rules in
        ``src/gui/theme.py`` to recolour the chunk. ``unpolish`` + ``polish``
        forces Qt to re-evaluate the style so the new property takes effect
        immediately.
        """
        progress_bar.setProperty("state", state)
        progress_bar.style().unpolish(progress_bar)
        progress_bar.style().polish(progress_bar)

    def _mark_incomplete_rows(self) -> None:
        """Flag every episode row that did not reach completion."""
        for row in self._episode_rows.values():
            if not row["done"] and not row["failed"]:
                self._set_row_state(row["bar"], "incomplete")

    def _build_arguments(self) -> list[str]:
        """Validate the form and build the downloader command line."""
        url = self._url_edit.text().strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError(
                "Enter a valid anime URL (it must start with http:// or https://).",
            )

        arguments = [url, "--progress-json"]

        mode = self._mode_group.checkedId()
        if mode == MODE_RANGE:
            arguments += self._range_arguments()
        elif mode == MODE_EPISODES:
            arguments += self._episodes_arguments()

        folder = self._folder_edit.text().strip()
        if folder:
            arguments += ["--custom-path", folder]

        workers = self._workers_spin.value()
        arguments += ["--workers", str(workers)]

        return arguments

    def _range_arguments(self) -> list[str]:
        """Build the --start/--end arguments from the range spin boxes."""
        start = self._start_spin.value()
        end = self._end_spin.value()
        if start and end and start > end:
            raise ValueError("The start episode cannot exceed the end episode.")

        arguments: list[str] = []
        if start:
            arguments += ["--start", str(start)]
        if end:
            arguments += ["--end", str(end)]
        return arguments

    def _episodes_arguments(self) -> list[str]:
        """Build the --episodes argument from the free-form episode list."""
        numbers: list[int] = []
        for token in re.split(r"[,\s]+", self._episodes_edit.text().strip()):
            if not token:
                continue
            if not token.isdigit():
                raise ValueError(f"'{token}' is not a valid episode number.")
            numbers.append(int(token))

        if not numbers:
            raise ValueError("Enter at least one episode number.")

        return ["--episodes", ",".join(str(number) for number in numbers)]


def main() -> int:
    """Create the application, apply the theme, and run the main window."""
    application = QApplication(sys.argv)
    application.setApplicationName("AnimeUnity Downloader")
    application.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    application.aboutToQuit.connect(window.cleanup)
    return application.exec()
