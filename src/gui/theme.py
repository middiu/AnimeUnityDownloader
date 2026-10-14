"""Visual theme of the desktop interface.

Pure-constants module holding the color palette and the Qt stylesheet applied
to the whole application. Keeping it free of Qt imports makes it trivial to
lint and to restyle.
"""

# ============================
# Palette
# ============================
BG = "#0B0B12"            # App background (deep near-black indigo)
SURFACE = "#14141F"       # Card background
SURFACE_ALT = "#1C1C26"   # Input fields and progress tracks
BORDER = "#262640"        # Card borders
INPUT_BORDER = "#2A2A3A"  # Input borders
TEXT = "#ECEAF4"          # Primary text
MUTED = "#8E8AA3"         # Secondary text
VIOLET = "#8B5CF6"        # Accent start
PINK = "#EC4899"          # Accent end
VIOLET_LIGHT = "#9F6FF8"  # Accent hover start
PINK_LIGHT = "#F061A8"    # Accent hover end
SUCCESS = "#34D399"       # Completion state
DANGER = "#F43F5E"        # Error and cancel state

# ============================
# Stylesheet
# ============================
STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Inter", -apple-system, "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 14px;
}}

/* ---------- Labels ---------- */
QLabel {{
    background: transparent;
    color: {TEXT};
}}
QLabel#titleLabel {{
    font-size: 22px;
    font-weight: 800;
}}
QLabel#subtitleLabel {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#fieldLabel {{
    color: {MUTED};
    font-size: 12px;
    font-weight: 600;
}}
QLabel#hintLabel {{
    color: {MUTED};
}}
QLabel#animeName {{
    font-size: 19px;
    font-weight: 700;
    color: #EDE9FE;
}}
QLabel#pathHint {{
    color: {MUTED};
    font-size: 12px;
}}
QLabel#episodeName {{
    font-size: 12px;
    color: {TEXT};
}}
QLabel#episodeState {{
    color: {MUTED};
    font-size: 11px;
}}

/* ---------- Cards ---------- */
QFrame#card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#episodeRow {{
    background: transparent;
    border: none;
}}

/* ---------- Inputs ---------- */
QLineEdit, QSpinBox {{
    background-color: {SURFACE_ALT};
    border: 1px solid {INPUT_BORDER};
    border-radius: 10px;
    padding: 10px 14px;
    color: {TEXT};
    font-size: 14px;
    min-height: 20px;
    selection-background-color: {VIOLET};
}}
QLineEdit:disabled, QSpinBox:disabled {{
    color: {MUTED};
}}
QLineEdit:focus, QSpinBox:focus {{
    border: 1px solid {VIOLET};
}}
QLineEdit[readOnly="true"] {{
    color: {MUTED};
}}

/* ---------- Buttons ---------- */
QPushButton#browseButton {{
    background-color: {SURFACE_ALT};
    color: {TEXT};
    border: 1px solid {INPUT_BORDER};
    border-radius: 10px;
    padding: 10px 18px;
    font-size: 14px;
    font-weight: 600;
    min-height: 18px;
}}
QPushButton#browseButton:hover {{
    border-color: {VIOLET};
}}
QPushButton#browseButton:disabled {{
    color: {MUTED};
}}
QPushButton#startButton {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {VIOLET}, stop:1 {PINK});
    color: #FFFFFF;
    font-weight: 700;
    font-size: 16px;
    border: none;
    border-radius: 12px;
    padding: 12px 32px;
    min-height: 26px;
}}
QPushButton#startButton:hover {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {VIOLET_LIGHT}, stop:1 {PINK_LIGHT});
}}
QPushButton#startButton:disabled {{
    background-color: {INPUT_BORDER};
    color: {MUTED};
}}
QPushButton#cancelButton {{
    background: transparent;
    color: {DANGER};
    border: 1px solid {DANGER};
    border-radius: 12px;
    padding: 12px 26px;
    font-size: 16px;
    font-weight: 700;
    min-height: 26px;
}}
QPushButton#cancelButton:disabled {{
    color: {MUTED};
    border-color: {INPUT_BORDER};
}}

/* ---------- Segmented mode buttons ---------- */
QToolButton#segButton {{
    background-color: transparent;
    color: {MUTED};
    border: 1px solid {INPUT_BORDER};
    border-radius: 10px;
    padding: 9px 20px;
    font-size: 14px;
    font-weight: 600;
    min-height: 18px;
}}
QToolButton#segButton:hover {{
    color: {TEXT};
}}
QToolButton#segButton:checked {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {VIOLET}, stop:1 {PINK});
    color: #FFFFFF;
    border: none;
}}
QToolButton#segButton:disabled {{
    color: {MUTED};
}}

/* ---------- Progress bars ---------- */
QProgressBar {{
    background-color: {SURFACE_ALT};
    border: none;
    border-radius: 7px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {VIOLET}, stop:1 {PINK});
    border-radius: 7px;
}}
QProgressBar#overallBar {{
    min-height: 20px;
    font-size: 12px;
    font-weight: 700;
    color: {TEXT};
}}
QProgressBar#episodeBar {{
    min-height: 8px;
    max-height: 8px;
}}

/* ---------- Scroll area ---------- */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {INPUT_BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

/* ---------- Log pane ---------- */
QPlainTextEdit#logPane {{
    background-color: #0A0A10;
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px;
    color: {MUTED};
    font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 11px;
}}
"""
