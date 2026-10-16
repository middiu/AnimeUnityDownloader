"""Visual theme of the desktop interface.

Pure-constants module holding the color palette and the Qt stylesheet applied
to the whole application. Keeping it free of Qt imports makes it trivial to
lint and to restyle.
"""

# ============================
# Palette
# ============================
BG = "#0E0E16"            # App background (deep near-black indigo)
SURFACE = "#171724"       # Card background
SURFACE_ALT = "#1F1F2E"   # Input fields and progress tracks
BORDER = "#2C2C44"        # Card borders
INPUT_BORDER = "#33334A"  # Input borders
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
    font-size: 19px;
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

/* ---------- Cards ---------- */
QFrame#card {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QFrame#card > QWidget,
QFrame#card > QStackedWidget,
QFrame#card > QStackedWidget > QWidget {{
    background: transparent;
}}
QFrame#episodeRow {{
    background: transparent;
    border: none;
}}

/* ---------- Inputs ---------- */
QLineEdit, QSpinBox, QAbstractSpinBox {{
    background-color: {SURFACE_ALT};
    border: 1px solid {INPUT_BORDER};
    border-radius: 8px;
    padding: 6px 12px;
    color: {TEXT};
    font-size: 13px;
    min-height: 14px;
    selection-background-color: {VIOLET};
}}
QLineEdit:disabled, QSpinBox:disabled, QAbstractSpinBox:disabled {{
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
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 600;
    min-height: 14px;
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
    font-size: 14px;
    border: none;
    border-radius: 10px;
    padding: 8px 22px;
    min-height: 18px;
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
    border-radius: 10px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 700;
    min-height: 18px;
}}
QPushButton#cancelButton:disabled {{
    color: {MUTED};
    border-color: {INPUT_BORDER};
}}
QPushButton#clearButton {{
    background-color: transparent;
    color: {MUTED};
    border: 1px solid {INPUT_BORDER};
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 600;
    min-height: 14px;
}}
QPushButton#clearButton:hover {{
    color: {TEXT};
    border-color: {MUTED};
}}
QPushButton#clearButton:disabled {{
    color: {MUTED};
    border-color: {INPUT_BORDER};
}}

/* ---------- Segmented mode buttons ---------- */
QToolButton#segButton {{
    background-color: transparent;
    color: {MUTED};
    border: 1px solid {INPUT_BORDER};
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 600;
    min-height: 14px;
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
    min-height: 14px;
    font-size: 11px;
    font-weight: 700;
    color: {TEXT};
}}
QProgressBar#episodeBar {{
    min-height: 12px;
    max-height: 14px;
    font-size: 10px;
    font-weight: 700;
    color: {TEXT};
    background-color: {SURFACE_ALT};
    border-radius: 6px;
    text-align: center;
}}
/* Default + active + queued: violet→pink gradient on the chunk. The
   bar's ``state`` dynamic property is flipped by ``MainWindow._set_row_state``
   to recolour the chunk per row state. */
QProgressBar#episodeBar::chunk,
QProgressBar#episodeBar[state="queued"]::chunk,
QProgressBar#episodeBar[state="active"]::chunk {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {VIOLET}, stop:1 {PINK});
    border-radius: 6px;
}}
/* Queued: outline so it reads as "idle" before the worker starts. */
QProgressBar#episodeBar[state="queued"] {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
}}
QProgressBar#episodeBar[state="done"]::chunk {{
    background-color: {SUCCESS};
    border-radius: 6px;
}}
QProgressBar#episodeBar[state="failed"]::chunk {{
    background-color: {DANGER};
    border-radius: 6px;
}}
QProgressBar#episodeBar[state="incomplete"]::chunk {{
    background-color: {MUTED};
    border-radius: 6px;
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
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
    color: {MUTED};
    font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 11px;
}}
"""
