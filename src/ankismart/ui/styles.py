"""UI styles and constants for Ankismart application."""

# Color constants
COLOR_SUCCESS = "#10b981"  # Green
COLOR_ERROR = "#ef4444"    # Red
COLOR_WARNING = "#f59e0b"  # Orange
COLOR_INFO = "#3b82f6"     # Blue

# Card widget styles
CARD_BORDER_RADIUS = 8
CARD_PADDING = 16

# Animation durations (ms)
ANIMATION_DURATION_SHORT = 150
ANIMATION_DURATION_MEDIUM = 300
ANIMATION_DURATION_LONG = 500

# Window constants
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 600

# File drag-drop area style
DRAG_DROP_AREA_STYLE = """
QLabel {
    border: 2px dashed rgba(0, 0, 0, 0.2);
    border-radius: 8px;
    padding: 40px;
    background-color: rgba(0, 0, 0, 0.02);
}
QLabel:hover {
    border-color: rgba(0, 0, 0, 0.3);
    background-color: rgba(0, 0, 0, 0.04);
}
"""

# Table widget styles
TABLE_ROW_HEIGHT = 40
TABLE_HEADER_HEIGHT = 36

# Progress ring size
PROGRESS_RING_SIZE = 80

# Icon sizes
ICON_SIZE_SMALL = 16
ICON_SIZE_MEDIUM = 24
ICON_SIZE_LARGE = 32

# Spacing constants (following QFluentWidgets official standards)
SPACING_SMALL = 8      # 小间距，用于紧密排列的元素
SPACING_MEDIUM = 16    # 中等间距，用于一般元素之间
SPACING_LARGE = 20     # 大间距，用于主要区块之间
SPACING_XLARGE = 24    # 超大间距，用于页面级别的分隔

# Margin constants
MARGIN_STANDARD = 20   # 标准边距，用于页面和卡片的外边距
MARGIN_SMALL = 10      # 小边距，用于紧凑布局
MARGIN_LARGE = 30      # 大边距，用于需要更多空白的区域

# Component-specific constants
PROVIDER_ITEM_HEIGHT = 72        # 提供商列表项高度
MAX_VISIBLE_PROVIDERS = 4        # 最大可见提供商数量（超过则显示滚动条）

# Font sizes
FONT_SIZE_SMALL = 12
FONT_SIZE_MEDIUM = 14
FONT_SIZE_LARGE = 16
FONT_SIZE_XLARGE = 20
FONT_SIZE_TITLE = 24


class Colors:
    """Light theme color palette."""

    BACKGROUND = "#f5f7fb"
    SURFACE = "#ffffff"
    BORDER = "#e5e7eb"
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#6b7280"
    ACCENT = "#2563eb"


class DarkColors:
    """Dark theme color palette."""

    BACKGROUND = "#111827"
    SURFACE = "#1f2937"
    BORDER = "#374151"
    TEXT_PRIMARY = "#f3f4f6"
    TEXT_SECONDARY = "#9ca3af"
    ACCENT = "#60a5fa"


def get_stylesheet(*, dark: bool = False) -> str:
    """Build the main app stylesheet for light/dark mode."""
    palette = DarkColors if dark else Colors
    return f"""
QWidget {{
    background-color: {palette.BACKGROUND};
    color: {palette.TEXT_PRIMARY};
    font-size: {FONT_SIZE_MEDIUM}px;
}}

#settingsPage QWidget#contentWidget,
#settingsPage QFrame,
QFrame#providerListContainer {{
    background-color: {palette.SURFACE};
    border: 1px solid {palette.BORDER};
    border-radius: 10px;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget {{
    background-color: {palette.SURFACE};
    color: {palette.TEXT_PRIMARY};
    border: 1px solid {palette.BORDER};
    border-radius: 8px;
    padding: 6px 8px;
}}

QLabel#caption, QLabel[role="secondary"] {{
    color: {palette.TEXT_SECONDARY};
}}

QPushButton, QToolButton {{
    border: 1px solid {palette.BORDER};
    background-color: {palette.SURFACE};
    border-radius: 8px;
    padding: 6px 12px;
}}

QPushButton:hover, QToolButton:hover {{
    border-color: {palette.ACCENT};
}}
"""
