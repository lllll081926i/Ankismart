from __future__ import annotations


class Colors:
    PRIMARY = "#007AFF"
    PRIMARY_HOVER = "#0062CC"
    PRIMARY_PRESSED = "#004999"

    BACKGROUND = "#F5F5F7"
    SURFACE = "#FFFFFF"

    TEXT_PRIMARY = "#333333"
    TEXT_SECONDARY = "#666666"
    TEXT_DISABLED = "#999999"

    BORDER = "#E5E5EA"
    DIVIDER = "#D1D1D6"

    SUCCESS = "#34C759"
    ERROR = "#FF3B30"
    WARNING = "#FF9500"

    WHITE = "#FFFFFF"

    HOVER_BG = "#F0F0F2"
    PRESSED_BG = "#E5E5EA"
    NAV_HOVER_BG = "rgba(0, 0, 0, 0.05)"


class DarkColors:
    PRIMARY = "#7c9ff5"
    PRIMARY_HOVER = "#6b8de0"
    PRIMARY_PRESSED = "#5a7ccc"

    BACKGROUND = "#1e1e2e"
    SURFACE = "#2a2a3c"

    TEXT_PRIMARY = "#e0e0e0"
    TEXT_SECONDARY = "#a0a0b0"
    TEXT_DISABLED = "#606070"

    BORDER = "#3a3a4c"
    DIVIDER = "#3a3a4c"

    SUCCESS = "#6bcf7f"
    ERROR = "#f07070"
    WARNING = "#f0c060"

    WHITE = "#e0e0e0"

    HOVER_BG = "#353548"
    PRESSED_BG = "#3a3a5c"
    NAV_HOVER_BG = "rgba(255, 255, 255, 0.05)"


def get_stylesheet(dark: bool = False) -> str:
    c = DarkColors if dark else Colors
    return f"""
    /* Global Reset & Base */
    QWidget {{
        font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
        font-size: 14px;
        color: {c.TEXT_PRIMARY};
        background-color: {c.BACKGROUND};
    }}

    /* Main Window & Containers */
    QMainWindow {{
        background-color: {c.BACKGROUND};
    }}

    QStackedWidget {{
        background-color: {c.BACKGROUND};
    }}

    /* Panel/Card style for pages */
    QWidget#page_content {{
        background-color: {c.SURFACE};
        border-radius: 12px;
        border: 1px solid {c.BORDER};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 8px 16px;
        color: {c.TEXT_PRIMARY};
        font-weight: 500;
    }}

    QPushButton:hover {{
        background-color: {c.HOVER_BG};
        border-color: {c.DIVIDER};
    }}

    QPushButton:pressed {{
        background-color: {c.PRESSED_BG};
    }}

    QPushButton:disabled {{
        background-color: {c.BACKGROUND};
        color: {c.TEXT_DISABLED};
        border-color: {c.BORDER};
    }}

    /* Primary Actions (Classes need to be set in code) */
    QPushButton[role="primary"] {{
        background-color: {c.PRIMARY};
        color: {c.WHITE};
        border: none;
        font-weight: 600;
    }}

    QPushButton[role="primary"]:hover {{
        background-color: {c.PRIMARY_HOVER};
    }}

    QPushButton[role="primary"]:pressed {{
        background-color: {c.PRIMARY_PRESSED};
    }}

    QPushButton[role="primary"]:disabled {{
        background-color: {c.BORDER};
        color: {c.TEXT_DISABLED};
    }}

    /* Navigation Buttons (Sidebar/Top) - Modern Pill Style */
    QPushButton[role="nav"] {{
        border: none;
        border-radius: 8px;
        background-color: transparent;
        text-align: center;
        padding: 8px 16px;
        font-size: 15px;
        margin: 0 4px;
        color: {c.TEXT_SECONDARY};
    }}

    QPushButton[role="nav"]:checked {{
        background-color: {c.SURFACE};
        color: {c.PRIMARY};
        font-weight: bold;
        border: 1px solid {c.BORDER};
    }}

    QPushButton[role="nav"]:hover:!checked {{
        background-color: {c.NAV_HOVER_BG};
        color: {c.TEXT_PRIMARY};
    }}

    /* Input Fields */
    QLineEdit, QComboBox, QPlainTextEdit {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 8px;
        selection-background-color: {c.PRIMARY};
    }}

    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
        border: 1px solid {c.PRIMARY};
    }}

    /* ComboBox Dropdown */
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}

    /* Table View */
    QTableWidget {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        gridline-color: {c.BORDER};
        selection-background-color: {c.PRIMARY}33; /* 20% opacity approx */
        selection-color: {c.TEXT_PRIMARY};
    }}

    QHeaderView::section {{
        background-color: {c.BACKGROUND};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {c.BORDER};
        border-right: 1px solid {c.BORDER};
        font-weight: 600;
        color: {c.TEXT_SECONDARY};
    }}

    QHeaderView::section:last {{
        border-right: none;
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        border: none;
        background: {c.BACKGROUND};
        width: 10px;
        margin: 0px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {c.DIVIDER};
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Status Bar */
    QStatusBar {{
        background-color: {c.SURFACE};
        color: {c.TEXT_SECONDARY};
        border-top: 1px solid {c.BORDER};
    }}

    /* Labels */
    QLabel[role="heading"] {{
        font-size: 20px;
        font-weight: 700;
        color: {c.TEXT_PRIMARY};
        margin-bottom: 12px;
    }}

    QLabel[role="subtitle"] {{
        font-size: 13px;
        color: {c.TEXT_SECONDARY};
    }}

    /* List Widget */
    QListWidget {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        outline: none;
    }}

    QListWidget::item {{
        padding: 10px 14px;
        border-bottom: 1px solid {c.BORDER};
    }}

    QListWidget::item:selected {{
        background-color: {c.PRIMARY}33;
        color: {c.TEXT_PRIMARY};
        border-radius: 4px;
    }}

    QListWidget::item:hover:!selected {{
        background-color: {c.BACKGROUND};
    }}

    /* Plain Text Edit */
    QPlainTextEdit {{
        background-color: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-radius: 8px;
        padding: 10px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 13px;
    }}
    """
