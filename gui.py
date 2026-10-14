"""Entry point for the AnimeUnity downloader desktop interface.

Usage:
    python3 gui.py

When the app is launched from a PyInstaller bundle, the GUI also accepts a
hidden ``--run-downloader`` flag: in that mode the same binary runs the
CLI downloader in-process and exits, instead of opening a window. The GUI
subprocess worker uses this so the bundled app can drive its own download
script without needing a separate Python interpreter on the user's PATH.

Requires the optional GUI dependencies:
    pip install -r requirements-gui.txt
"""

from __future__ import annotations

import asyncio
import sys


def _run_downloader() -> int:
    """Run the CLI downloader in-process. Used by the bundled GUI subprocess."""
    # Lazy import: ``anime_downloader`` is not in the GUI's import graph
    # during a normal launch, and PyInstaller only bundles it as a hidden
    # import. Importing inside this function keeps the GUI startup clean and
    # matches the runbook documented in the workflow's build step.
    # pylint: disable=import-outside-toplevel
    import anime_downloader
    return asyncio.run(anime_downloader.main())


if __name__ == "__main__":
    if "--run-downloader" in sys.argv:
        # Strip the flag so argparse inside ``anime_downloader.main`` does
        # not see it and reject it as an unknown argument.
        sys.argv = [sys.argv[0]] + [
            arg for arg in sys.argv[1:] if arg != "--run-downloader"
        ]
        sys.exit(_run_downloader())

    try:
        from src.gui.app import main  # noqa: PLC0415
    except ImportError:
        print("PySide6 is not installed. Run: pip install -r requirements-gui.txt")
        sys.exit(1)

    sys.exit(main())
