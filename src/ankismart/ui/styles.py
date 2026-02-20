"""UI styles and constants for Ankismart application."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QFont, QScreen
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import BodyLabel, isDarkTheme

# Color constants
COLOR_SUCCESS = "#10b981"  # Green
COLOR_ERROR = "#ef4444"    # Red
COLOR_WARNING = "#f59e0b"  # Orange
COLOR_INFO = "#3b82f6"     # Blue
FIXED_THEME_ACCENT_HEX = "#2563eb"
FIXED_THEME_ACCENT_RGB = "37, 99, 235"
FIXED_PAGE_BACKGROUND_HEX = "#f5f7fb"
DARK_PAGE_BACKGROUND_HEX = "#202020"

# Card widget styles
CARD_BORDER_RADIUS = 8
CARD_PADDING = 16

# Animation durations (ms)
ANIMATION_DURATION_SHORT = 150
ANIMATION_DURATION_MEDIUM = 300
ANIMATION_DURATION_LONG = 500

# Window constants
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 900
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 540
TITLE_BAR_HEIGHT = 30

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
SPACING_MEDIUM = 12    # 中等间距，用于一般元素之间（从16减小到12）
SPACING_LARGE = 20     # 大间距，用于主要区块之间
SPACING_XLARGE = 24    # 超大间距，用于页面级别的分隔

# Margin constants
MARGIN_STANDARD = 20   # 标准边距，用于页面和卡片的外边距
MARGIN_SMALL = 10      # 小边距，用于紧凑布局
MARGIN_LARGE = 30      # 大边距，用于需要更多空白的区域

# Component-specific constants
PROVIDER_ITEM_HEIGHT = 36        # 提供商列表项高度（横向表格布局）
MAX_VISIBLE_PROVIDERS = 2        # 默认可见提供商数量（超过则显示滚动条）

# Font sizes
FONT_SIZE_SMALL = 12
FONT_SIZE_MEDIUM = 14
FONT_SIZE_LARGE = 16
FONT_SIZE_XLARGE = 20
FONT_SIZE_TITLE = 24
FONT_SIZE_PAGE_TITLE = 22
TEXT_SCALE_FACTOR = 0.78


def get_display_scale(*, screen: QScreen | None = None) -> float:
    """Get a stable UI scale factor based on current screen DPI."""
    app = QApplication.instance()
    target_screen = screen
    if target_screen is None and app is not None:
        active_window = app.activeWindow()
        if active_window is not None and active_window.screen() is not None:
            target_screen = active_window.screen()
        else:
            target_screen = app.primaryScreen()

    if target_screen is None:
        return 1.0

    logical_dpi = float(target_screen.logicalDotsPerInch() or 96.0)
    dpr = float(target_screen.devicePixelRatio() or 1.0)

    scale = max(logical_dpi / 96.0, dpr)
    return max(0.85, min(scale, 1.8))


def scale_px(value: int, *, scale: float | None = None, min_value: int = 0) -> int:
    """Scale pixel value using current display scale with optional lower bound."""
    factor = scale if scale is not None else get_display_scale()
    scaled = int(round(value * factor))
    return max(min_value, scaled)


def scale_text_px(value: int, *, scale: float | None = None, min_value: int = 1) -> int:
    """Scale text size with DPI and global text scale factor."""
    base = scale_px(value, scale=scale, min_value=min_value)
    return max(min_value, int(round(base * TEXT_SCALE_FACTOR)))


def apply_page_title_style(label: BodyLabel) -> None:
    """Apply unified style for top-level page titles."""
    font = label.font()
    base_title_px = scale_text_px(FONT_SIZE_PAGE_TITLE, min_value=1)
    title_px = max(int(round(base_title_px * 0.6)), scale_text_px(FONT_SIZE_SMALL, min_value=1))
    font.setPixelSize(title_px)
    font.setWeight(QFont.Weight.Bold)
    label.setFont(font)


def apply_compact_combo_metrics(
    combo: object,
    *,
    control_height: int | None = None,
    popup_item_height: int | None = None,
) -> None:
    """Apply compact size metrics to QFluent ComboBox-like widgets.

    This helper also patches popup menu creation so dropdown items are lower.
    """
    scale = get_display_scale()
    target_control_height = control_height or scale_px(24, scale=scale, min_value=22)
    target_popup_item_height = popup_item_height or scale_px(26, scale=scale, min_value=22)

    set_fixed_height = getattr(combo, "setFixedHeight", None)
    if callable(set_fixed_height):
        set_fixed_height(target_control_height)

    setattr(combo, "_ankismart_combo_item_height", target_popup_item_height)

    create_menu = getattr(combo, "_createComboMenu", None)
    if not callable(create_menu):
        return

    if getattr(combo, "_ankismart_original_create_combo_menu", None) is None:
        setattr(combo, "_ankismart_original_create_combo_menu", create_menu)

        def _create_compact_menu():
            base_create_menu = getattr(combo, "_ankismart_original_create_combo_menu", None)
            menu = base_create_menu() if callable(base_create_menu) else create_menu()
            try:
                item_height = int(getattr(combo, "_ankismart_combo_item_height", target_popup_item_height))
                menu.setItemHeight(item_height)
            except Exception:
                pass
            return menu

        setattr(combo, "_createComboMenu", _create_compact_menu)


class Colors:
    """Light theme color palette."""

    BACKGROUND = "#f5f7fb"
    SURFACE = "#ffffff"
    BORDER = "#e5e7eb"
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#6b7280"
    ACCENT = FIXED_THEME_ACCENT_HEX


class DarkColors:
    """Dark theme color palette."""

    BACKGROUND = DARK_PAGE_BACKGROUND_HEX
    SURFACE = "#2b2b2b"
    BORDER = "#3a3a3a"
    TEXT_PRIMARY = "#e6e6e6"
    TEXT_SECONDARY = "#a6a6a6"
    ACCENT = FIXED_THEME_ACCENT_HEX


@dataclass(frozen=True)
class ListWidgetPalette:
    """Theme-aware palette for list-like Qt widgets."""

    background: str
    border: str
    text: str
    text_disabled: str
    hover: str
    selected_background: str
    selected_text: str


def get_list_widget_palette(*, dark: bool | None = None) -> ListWidgetPalette:
    """Get unified list widget palette for light/dark theme."""
    if dark is None:
        dark = isDarkTheme()

    if dark:
        return ListWidgetPalette(
            background="rgba(39, 39, 39, 1)",
            border="rgba(255, 255, 255, 0.08)",
            text="rgba(255, 255, 255, 1)",
            text_disabled="rgba(255, 255, 255, 0.42)",
            hover="rgba(255, 255, 255, 0.06)",
            selected_background=f"rgba({FIXED_THEME_ACCENT_RGB}, 0.30)",
            selected_text="rgba(255, 255, 255, 1)",
        )

    return ListWidgetPalette(
        background="rgba(249, 249, 249, 1)",
        border="rgba(0, 0, 0, 0.08)",
        text="rgba(0, 0, 0, 1)",
        text_disabled="rgba(0, 0, 0, 0.42)",
        hover="rgba(0, 0, 0, 0.04)",
        selected_background=f"rgba({FIXED_THEME_ACCENT_RGB}, 0.15)",
        selected_text="rgba(0, 0, 0, 1)",
    )


def get_page_background_color(*, dark: bool | None = None) -> str:
    """Get page background color by theme: fixed blue for light, deep gray for dark."""
    if dark is None:
        dark = isDarkTheme()
    return DARK_PAGE_BACKGROUND_HEX if dark else FIXED_PAGE_BACKGROUND_HEX


def get_stylesheet(*, dark: bool = False) -> str:
    """Build the main app stylesheet for light/dark mode."""
    palette = DarkColors if dark else Colors
    page_background = get_page_background_color(dark=dark)
    scale = get_display_scale()
    combo_text_px = scale_text_px(FONT_SIZE_MEDIUM, scale=scale, min_value=12)
    input_radius = scale_px(8, scale=scale, min_value=8)
    input_padding_v = scale_px(6, scale=scale, min_value=6)
    input_padding_h = scale_px(8, scale=scale, min_value=8)
    combo_radius = scale_px(5, scale=scale, min_value=5)
    combo_padding_top = scale_px(2, scale=scale, min_value=1)
    combo_padding_bottom = scale_px(2, scale=scale, min_value=1)
    combo_padding_left = scale_px(10, scale=scale, min_value=8)
    combo_padding_right = scale_px(28, scale=scale, min_value=22)
    combo_min_height = max(scale_px(22, scale=scale, min_value=20), combo_text_px + scale_px(8, scale=scale, min_value=6))
    menu_border_radius = scale_px(9, scale=scale, min_value=7)
    menu_item_radius = scale_px(5, scale=scale, min_value=4)
    menu_item_padding_h = scale_px(10, scale=scale, min_value=8)
    menu_item_margin_h = scale_px(6, scale=scale, min_value=4)
    menu_item_margin_top = scale_px(2, scale=scale, min_value=1)
    menu_scroll_width = scale_px(8, scale=scale, min_value=6)
    menu_scroll_handle_min_height = scale_px(24, scale=scale, min_value=18)
    button_padding_v = scale_px(6, scale=scale, min_value=6)
    button_padding_h = scale_px(12, scale=scale, min_value=12)
    card_radius = scale_px(10, scale=scale, min_value=10)
    return f"""
QWidget {{
    color: {palette.TEXT_PRIMARY};
}}

QWidget#importPage,
QWidget#previewPage,
QWidget#cardPreviewPage,
QWidget#resultPage,
QWidget#performancePage,
QScrollArea#settingsPage,
QWidget#scrollWidget {{
    background-color: {page_background};
}}

FluentWindowBase,
StackedWidget,
FluentTitleBar,
MSFluentTitleBar,
SplitTitleBar,
TitleBar,
NavigationInterface,
NavigationPanel[menu=true],
NavigationPanel[menu=false],
NavigationPanel[transparent=true] {{
    background-color: {page_background};
}}

QLabel, BodyLabel, CaptionLabel, TitleLabel, SubtitleLabel {{
    background: transparent;
}}

#settingsPage InfoBar QLabel,
#settingsPage StateToolTip QLabel,
#settingsPage InfoBar QFrame,
#settingsPage StateToolTip QFrame {{
    border: none;
    border-radius: 0px;
    background: transparent;
}}

#settingsPage QWidget#contentWidget,
#settingsPage QFrame,
QFrame#providerListContainer {{
    background-color: {palette.SURFACE};
    border: 1px solid {palette.BORDER};
    border-radius: {card_radius}px;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {{
    background-color: {palette.SURFACE};
    color: {palette.TEXT_PRIMARY};
    border: 1px solid {palette.BORDER};
    border-radius: {input_radius}px;
    padding: {input_padding_v}px {input_padding_h}px;
}}

QLabel#caption, QLabel[role="secondary"] {{
    color: {palette.TEXT_SECONDARY};
}}

QPushButton, QToolButton {{
    border: 1px solid {palette.BORDER};
    background-color: {palette.SURFACE};
    border-radius: {input_radius}px;
    padding: {button_padding_v}px {button_padding_h}px;
}}

QPushButton:hover, QToolButton:hover {{
    border-color: {palette.ACCENT};
}}

ComboBox, ModelComboBox, EditableComboBox {{
    border: 1px solid {palette.BORDER};
    border-radius: {combo_radius}px;
    padding: {combo_padding_top}px {combo_padding_right}px {combo_padding_bottom}px {combo_padding_left}px;
    color: {palette.TEXT_PRIMARY};
    background-color: {palette.SURFACE};
    text-align: left;
    min-height: {combo_min_height}px;
}}

ComboBox:hover, ModelComboBox:hover, EditableComboBox:hover {{
    background-color: {"rgba(255, 255, 255, 0.085)" if dark else "rgba(0, 0, 0, 0.035)"};
}}

ComboBox:pressed, ModelComboBox:pressed, EditableComboBox:pressed {{
    background-color: {"rgba(255, 255, 255, 0.045)" if dark else "rgba(0, 0, 0, 0.025)"};
}}

MenuActionListWidget {{
    border: 1px solid {palette.BORDER};
    border-radius: {menu_border_radius}px;
    background-color: {palette.SURFACE};
    outline: none;
    padding: 0px;
}}

MenuActionListWidget::item {{
    padding-left: {menu_item_padding_h}px;
    padding-right: {menu_item_padding_h}px;
    border-radius: {menu_item_radius}px;
    margin-left: {menu_item_margin_h}px;
    margin-right: {menu_item_margin_h}px;
    border: none;
    color: {palette.TEXT_PRIMARY};
}}

MenuActionListWidget::item:disabled {{
    color: {palette.TEXT_SECONDARY};
}}

MenuActionListWidget::item:hover {{
    background-color: {"rgba(255, 255, 255, 0.08)" if dark else "rgba(0, 0, 0, 0.06)"};
}}

MenuActionListWidget::item:selected {{
    background-color: {"rgba(255, 255, 255, 0.12)" if dark else "rgba(0, 0, 0, 0.08)"};
    color: {palette.TEXT_PRIMARY};
}}

#comboListWidget::item {{
    margin-top: {menu_item_margin_top}px;
}}

MenuActionListWidget QScrollBar:vertical {{
    background: transparent;
    width: {menu_scroll_width}px;
    margin: 0px;
    border: none;
}}

MenuActionListWidget QScrollBar::handle:vertical {{
    background: {"rgba(255, 255, 255, 0.35)" if dark else "rgba(0, 0, 0, 0.25)"};
    border-radius: {menu_scroll_width // 2}px;
    min-height: {menu_scroll_handle_min_height}px;
}}

MenuActionListWidget QScrollBar::add-line:vertical,
MenuActionListWidget QScrollBar::sub-line:vertical,
MenuActionListWidget QScrollBar::add-page:vertical,
MenuActionListWidget QScrollBar::sub-page:vertical {{
    background: transparent;
    border: none;
    height: 0px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 0px;
    margin: 0px;
    border: none;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 0px;
    margin: 0px;
    border: none;
}}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal,
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    background: transparent;
    border: none;
    width: 0px;
    height: 0px;
}}
"""
