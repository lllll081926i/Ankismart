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

def get_stylesheet() -> str:
    return f"""
    /* Global Reset & Base */
    QWidget {{
        font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
        font-size: 14px;
        color: {Colors.TEXT_PRIMARY};
        background-color: {Colors.BACKGROUND};
    }}

    /* Main Window & Containers */
    QMainWindow {{
        background-color: {Colors.BACKGROUND};
    }}

    QStackedWidget {{
        background-color: {Colors.BACKGROUND};
    }}

    /* Panel/Card style for pages */
    QWidget#page_content {{
        background-color: {Colors.SURFACE};
        border-radius: 12px;
        border: 1px solid {Colors.BORDER};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 8px 16px;
        color: {Colors.TEXT_PRIMARY};
        font-weight: 500;
    }}

    QPushButton:hover {{
        background-color: #F0F0F2;
        border-color: {Colors.DIVIDER};
    }}

    QPushButton:pressed {{
        background-color: #E5E5EA;
    }}

    QPushButton:disabled {{
        background-color: {Colors.BACKGROUND};
        color: {Colors.TEXT_DISABLED};
        border-color: {Colors.BORDER};
    }}

    /* Primary Actions (Classes need to be set in code) */
    QPushButton[role="primary"] {{
        background-color: {Colors.PRIMARY};
        color: {Colors.WHITE};
        border: none;
        font-weight: 600;
    }}

    QPushButton[role="primary"]:hover {{
        background-color: {Colors.PRIMARY_HOVER};
    }}

    QPushButton[role="primary"]:pressed {{
        background-color: {Colors.PRIMARY_PRESSED};
    }}

    QPushButton[role="primary"]:disabled {{
        background-color: {Colors.BORDER};
        color: {Colors.TEXT_DISABLED};
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
        color: {Colors.TEXT_SECONDARY};
    }}

    QPushButton[role="nav"]:checked {{
        background-color: {Colors.SURFACE};
        color: {Colors.PRIMARY};
        font-weight: bold;
        border: 1px solid {Colors.BORDER};
    }}

    QPushButton[role="nav"]:hover:!checked {{
        background-color: rgba(0, 0, 0, 0.05);
        color: {Colors.TEXT_PRIMARY};
    }}

    /* Input Fields */
    QLineEdit, QComboBox, QPlainTextEdit {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 8px;
        selection-background-color: {Colors.PRIMARY};
    }}

    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
        border: 1px solid {Colors.PRIMARY};
    }}

    /* ComboBox Dropdown */
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}

    /* Table View */
    QTableWidget {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        gridline-color: {Colors.BORDER};
        selection-background-color: {Colors.PRIMARY}33; /* 20% opacity approx */
        selection-color: {Colors.TEXT_PRIMARY};
    }}

    QHeaderView::section {{
        background-color: {Colors.BACKGROUND};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {Colors.BORDER};
        border-right: 1px solid {Colors.BORDER};
        font-weight: 600;
        color: {Colors.TEXT_SECONDARY};
    }}

    QHeaderView::section:last {{
        border-right: none;
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        border: none;
        background: {Colors.BACKGROUND};
        width: 10px;
        margin: 0px;
        border-radius: 5px;
    }}
    QScrollBar::handle:vertical {{
        background: {Colors.DIVIDER};
        min-height: 20px;
        border-radius: 5px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Status Bar */
    QStatusBar {{
        background-color: {Colors.SURFACE};
        color: {Colors.TEXT_SECONDARY};
        border-top: 1px solid {Colors.BORDER};
    }}

    /* Labels */
    QLabel[role="heading"] {{
        font-size: 20px;
        font-weight: 700;
        color: {Colors.TEXT_PRIMARY};
        margin-bottom: 12px;
    }}

    QLabel[role="subtitle"] {{
        font-size: 13px;
        color: {Colors.TEXT_SECONDARY};
    }}

    /* List Widget */
    QListWidget {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        outline: none;
    }}

    QListWidget::item {{
        padding: 10px 14px;
        border-bottom: 1px solid {Colors.BORDER};
    }}

    QListWidget::item:selected {{
        background-color: {Colors.PRIMARY}33;
        color: {Colors.TEXT_PRIMARY};
        border-radius: 4px;
    }}

    QListWidget::item:hover:!selected {{
        background-color: {Colors.BACKGROUND};
    }}

    /* Plain Text Edit */
    QPlainTextEdit {{
        background-color: {Colors.SURFACE};
        border: 1px solid {Colors.BORDER};
        border-radius: 8px;
        padding: 10px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: 13px;
    }}
    """
