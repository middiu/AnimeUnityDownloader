"""Subprocess orchestration for running the downloader from the GUI.

The graphical interface never imports the downloader directly: it spawns the
command-line script as a QProcess with the ``--progress-json`` flag and parses
the newline-delimited JSON events emitted on stdout. This keeps process
isolation and makes cancellation as simple as killing the child process.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# The PySide6 stubs confuse astroid's member resolution; the Qt imports below
# resolve correctly at runtime.
# pylint: disable=no-name-in-module
from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal


class DownloadWorker(QObject):
    """Run the downloader CLI as a QProcess and emit parsed JSON events."""

    event_received = Signal(object)  # A progress event dictionary
    log_line = Signal(str)          # A stderr line or an unparsable stdout line
    failed_to_start = Signal(str)    # A spawn failure message
    finished = Signal(int)          # The exit code of the process

    def __init__(self, parent: QObject | None = None) -> None:
        """Create the QProcess and connect its signals."""
        super().__init__(parent)
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._process = QProcess(self)
        self._process.setProcessChannelMode(
            QProcess.ProcessChannelMode.SeparateChannels,
        )
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        self._process.setProcessEnvironment(environment)
        self._process.readyReadStandardOutput.connect(self._on_ready_read_stdout)
        self._process.readyReadStandardError.connect(self._on_ready_read_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error_occurred)

    @property
    def is_running(self) -> bool:
        """Return whether the download process is currently running."""
        return self._process.state() != QProcess.ProcessState.NotRunning

    def start(
        self,
        script_path: Path,
        arguments: list[str],
        working_directory: str,
    ) -> None:
        """Start the downloader with the given command-line arguments.

        The ``arguments`` list contains only the user-facing flags (the anime
        URL, ``--progress-json``, range/episode selectors, etc.) — the worker
        is responsible for choosing the right program to run, because the
        answer differs between a regular Python install and a PyInstaller
        bundle.

        In a PyInstaller bundle (``sys.frozen``), ``sys.executable`` is the GUI
        binary itself — re-invoking it with a script path would launch a
        second GUI window instead of running the downloader. The bundled
        binary accepts a hidden ``--run-downloader`` flag (see ``gui.py``) that
        runs the CLI downloader in-process and exits, so we use that instead.
        ``script_path`` is unused in this mode (the downloader lives inside
        the bundle as a hidden import).

        In a normal Python install, ``sys.executable`` is the interpreter and
        the script path is the first positional argument passed to it.
        Prepending the script path here — rather than in the caller — keeps
        ``arguments`` free of host-specific paths so the same value can be
        reused in the frozen mode without the script path leaking into
        argparse.
        """
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self._process.setWorkingDirectory(working_directory)
        if getattr(sys, "frozen", False):
            # Bundled binary: drive the same binary in CLI mode. The
            # downloader script lives inside the bundle as a hidden import.
            self._process.setProgram(sys.executable)
            self._process.setArguments(["--run-downloader", *arguments])
        else:
            self._process.setProgram(sys.executable)
            self._process.setArguments([str(script_path), *arguments])
        self._process.start()

    def cancel(self) -> None:
        """Kill the running download process."""
        if self.is_running:
            self._process.kill()

    @staticmethod
    def _extract_lines(buffer: str) -> tuple[list[str], str]:
        """Split a buffer into complete lines and the trailing remainder."""
        *lines, remainder = buffer.split("\n")
        return lines, remainder

    def _on_ready_read_stdout(self) -> None:
        """Consume stdout bytes, split complete lines, and parse JSON events."""
        self._stdout_buffer += bytes(
            self._process.readAllStandardOutput(),
        ).decode("utf-8", errors="replace")
        lines, self._stdout_buffer = self._extract_lines(self._stdout_buffer)
        for line in lines:
            self._handle_stdout_line(line.strip())

    def _handle_stdout_line(self, line: str) -> None:
        """Parse one stdout line as a JSON event or forward it to the log."""
        if not line:
            return
        try:
            event = json.loads(line)
        except ValueError:
            self.log_line.emit(line)
            return

        if isinstance(event, dict) and "event" in event:
            self.event_received.emit(event)
        else:
            self.log_line.emit(line)

    def _on_ready_read_stderr(self) -> None:
        """Consume stderr bytes and forward each line to the log."""
        self._stderr_buffer += bytes(
            self._process.readAllStandardError(),
        ).decode("utf-8", errors="replace")
        lines, self._stderr_buffer = self._extract_lines(self._stderr_buffer)
        for line in lines:
            if line.strip():
                self.log_line.emit(line.strip())

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        """Reset the buffers and emit the finished signal."""
        self._stdout_buffer = ""
        self._stderr_buffer = ""
        self.finished.emit(exit_code)

    def _on_error_occurred(self, error: QProcess.ProcessError) -> None:
        """Report process errors, most notably a failure to start."""
        if error == QProcess.ProcessError.FailedToStart:
            self.failed_to_start.emit(
                "Failed to start the downloader process. "
                "Is a working Python interpreter available?"
            )
