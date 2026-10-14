"""Entry point for the AnimeUnity downloader desktop interface.

Usage:
    python3 gui.py

Requires the optional GUI dependencies:
    pip install -r requirements-gui.txt
"""

from __future__ import annotations

import sys

try:
    from src.gui.app import main

except ImportError:
    print("PySide6 is not installed. Run: pip install -r requirements-gui.txt")
    sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
