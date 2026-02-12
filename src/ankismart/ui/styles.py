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

# Spacing
SPACING_SMALL = 8
SPACING_MEDIUM = 16
SPACING_LARGE = 24
SPACING_XLARGE = 32

# Font sizes
FONT_SIZE_SMALL = 12
FONT_SIZE_MEDIUM = 14
FONT_SIZE_LARGE = 16
FONT_SIZE_XLARGE = 20
FONT_SIZE_TITLE = 24
