"""UI styles and constants for Ankismart application."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from PyQt6.QtGui import QColor, QFont, QScreen
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import BodyLabel, isDarkTheme

from ankismart.core.logging import get_logger

logger = get_logger("ui.styles")

# Color constants
COLOR_SUCCESS = "#10b981"  # Green
COLOR_ERROR = "#ef4444"  # Red
COLOR_WARNING = "#f59e0b"  # Orange
DEFAULT_THEME_ACCENT_HEX = "#2563eb"
DEFAULT_THEME_ACCENT_RGB = "37, 99, 235"
COLOR_INFO = DEFAULT_THEME_ACCENT_HEX
FIXED_THEME_ACCENT_HEX = DEFAULT_THEME_ACCENT_HEX
FIXED_THEME_ACCENT_RGB = DEFAULT_THEME_ACCENT_RGB
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
TITLE_BAR_HEIGHT = 36

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
SPACING_SMALL = 8  # 小间距，用于紧密排列的元素
SPACING_MEDIUM = 12  # 中等间距，用于一般元素之间（从16减小到12）
SPACING_LARGE = 20  # 大间距，用于主要区块之间
SPACING_XLARGE = 24  # 超大间距，用于页面级别的分隔

# Margin constants
MARGIN_STANDARD = 20  # 标准边距，用于页面和卡片的外边距
MARGIN_SMALL = 10  # 小边距，用于紧凑布局
MARGIN_LARGE = 30  # 大边距，用于需要更多空白的区域

# Component-specific constants
PROVIDER_ITEM_HEIGHT = 36  # 提供商列表项高度（横向表格布局）
MAX_VISIBLE_PROVIDERS = 2  # 默认可见提供商数量（超过则显示滚动条）

# Font sizes
FONT_SIZE_SMALL = 12
FONT_SIZE_MEDIUM = 14
FONT_SIZE_LARGE = 16
FONT_SIZE_XLARGE = 20
FONT_SIZE_TITLE = 24
FONT_SIZE_PAGE_TITLE = 22
TEXT_SCALE_FACTOR = 0.78
_THEME_ACCENT_CACHE: tuple[int, str] = (0, DEFAULT_THEME_ACCENT_HEX)


def _normalize_hex_color(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not text.startswith("#"):
        text = f"#{text}"
    if len(text) != 7:
        return None
    try:
        int(text[1:], 16)
    except ValueError:
        return None
    return text.lower()


def _hex_to_rgb_tuple(hex_color: str) -> tuple[int, int, int]:
    color = QColor(hex_color)
    return color.red(), color.green(), color.blue()


def _rgb_tuple_to_hex(rgb: tuple[int, int, int]) -> str:
    red, green, blue = rgb
    return f"#{red:02x}{green:02x}{blue:02x}"


def _blend_hex_colors(base_hex: str, overlay_hex: str, ratio: float) -> str:
    base = QColor(base_hex)
    overlay = QColor(overlay_hex)
    amount = max(0.0, min(ratio, 1.0))
    rgb = (
        round(base.red() * (1 - amount) + overlay.red() * amount),
        round(base.green() * (1 - amount) + overlay.green() * amount),
        round(base.blue() * (1 - amount) + overlay.blue() * amount),
    )
    return _rgb_tuple_to_hex(rgb)


def _read_windows_dwm_accent_hex() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes

        color = ctypes.c_uint()
        opaque = ctypes.c_bool()
        result = ctypes.windll.dwmapi.DwmGetColorizationColor(
            ctypes.byref(color),
            ctypes.byref(opaque),
        )
        if result != 0:
            return None
        argb = int(color.value)
        red = (argb >> 16) & 0xFF
        green = (argb >> 8) & 0xFF
        blue = argb & 0xFF
        return _rgb_tuple_to_hex((red, green, blue))
    except Exception:
        return None


def _read_windows_registry_accent_hex() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
            value, _ = winreg.QueryValueEx(key, "ColorizationColor")
        argb = int(value)
        red = (argb >> 16) & 0xFF
        green = (argb >> 8) & 0xFF
        blue = argb & 0xFF
        return _rgb_tuple_to_hex((red, green, blue))
    except Exception:
        return None


def _read_windows_accent_hex() -> str | None:
    return _read_windows_dwm_accent_hex() or _read_windows_registry_accent_hex()


def get_theme_accent_hex() -> str:
    global _THEME_ACCENT_CACHE

    reader_id = id(_read_windows_accent_hex)
    if _THEME_ACCENT_CACHE[0] == reader_id:
        return _THEME_ACCENT_CACHE[1]

    _THEME_ACCENT_CACHE = (reader_id, DEFAULT_THEME_ACCENT_HEX)
    return DEFAULT_THEME_ACCENT_HEX


def refresh_theme_accent_cache() -> str:
    global _THEME_ACCENT_CACHE

    reader_id = id(_read_windows_accent_hex)
    accent_hex = _normalize_hex_color(_read_windows_accent_hex()) or DEFAULT_THEME_ACCENT_HEX
    _THEME_ACCENT_CACHE = (reader_id, accent_hex)
    return accent_hex


def get_theme_accent_rgb() -> str:
    red, green, blue = _hex_to_rgb_tuple(get_theme_accent_hex())
    return f"{red}, {green}, {blue}"


def get_theme_accent_text_hex(*, dark: bool | None = None) -> str:
    if dark is None:
        dark = isDarkTheme()
    accent_hex = get_theme_accent_hex()
    if not dark:
        return accent_hex
    return _blend_hex_colors(accent_hex, "#ffffff", 0.35)


def get_theme_accent_hover_hex(*, dark: bool | None = None) -> str:
    if dark is None:
        dark = isDarkTheme()
    accent_hex = get_theme_accent_hex()
    overlay = "#ffffff" if dark else "#000000"
    return _blend_hex_colors(accent_hex, overlay, 0.16)


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
    max_visible_items: int = 8,
) -> None:
    """Apply compact size metrics to QFluent ComboBox-like widgets.

    This helper also patches popup menu creation so dropdown items are lower.
    """
    scale = get_display_scale()
    target_control_height = control_height or scale_px(30, scale=scale, min_value=28)
    target_popup_item_height = popup_item_height or scale_px(32, scale=scale, min_value=30)
    target_max_visible_items = max(1, int(max_visible_items or 8))

    set_fixed_height = getattr(combo, "setFixedHeight", None)
    if callable(set_fixed_height):
        set_fixed_height(target_control_height)
    set_minimum_height = getattr(combo, "setMinimumHeight", None)
    if callable(set_minimum_height):
        set_minimum_height(target_control_height)
    set_maximum_height = getattr(combo, "setMaximumHeight", None)
    if callable(set_maximum_height):
        set_maximum_height(target_control_height)
    set_max_visible_items = getattr(combo, "setMaxVisibleItems", None)
    if callable(set_max_visible_items):
        set_max_visible_items(target_max_visible_items)

    base_style = getattr(combo, "_ankismart_base_stylesheet", None)
    if base_style is None:
        style_sheet = getattr(combo, "styleSheet", None)
        base_style = style_sheet() if callable(style_sheet) else ""
        setattr(combo, "_ankismart_base_stylesheet", base_style)

    compact_style = (
        "\nComboBox, ModelComboBox, EditableComboBox {\n    padding: 0px 31px 0px 11px;\n}\n"
    )
    set_style_sheet = getattr(combo, "setStyleSheet", None)
    if callable(set_style_sheet):
        set_style_sheet(f"{base_style}{compact_style}")

    setattr(combo, "_ankismart_combo_item_height", target_popup_item_height)
    setattr(combo, "_ankismart_combo_max_visible_items", target_max_visible_items)

    create_menu = getattr(combo, "_createComboMenu", None)
    if not callable(create_menu):
        return

    if getattr(combo, "_ankismart_original_create_combo_menu", None) is None:
        setattr(combo, "_ankismart_original_create_combo_menu", create_menu)

        def _create_compact_menu():
            base_create_menu = getattr(combo, "_ankismart_original_create_combo_menu", None)
            menu = base_create_menu() if callable(base_create_menu) else create_menu()
            try:
                item_height = int(
                    getattr(combo, "_ankismart_combo_item_height", target_popup_item_height)
                )
                menu.setItemHeight(item_height)
                max_items = int(
                    getattr(
                        combo,
                        "_ankismart_combo_max_visible_items",
                        target_max_visible_items,
                    )
                )
                set_menu_max_visible_items = getattr(menu, "setMaxVisibleItems", None)
                if callable(set_menu_max_visible_items):
                    set_menu_max_visible_items(max_items)
            except Exception as exc:
                logger.debug(
                    "Failed to apply compact combo menu item height",
                    extra={
                        "event": "ui.styles.combo_menu_item_height_failed",
                        "error_detail": str(exc),
                    },
                )
            return menu

        setattr(combo, "_createComboMenu", _create_compact_menu)


class Colors:
    """Light theme color palette."""

    BACKGROUND = "#f5f7fb"
    SURFACE = "#ffffff"
    BORDER = "#e5e7eb"
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#6b7280"
    ACCENT = DEFAULT_THEME_ACCENT_HEX


class DarkColors:
    """Dark theme color palette."""

    BACKGROUND = DARK_PAGE_BACKGROUND_HEX
    SURFACE = "#2b2b2b"
    BORDER = "#3a3a3a"
    TEXT_PRIMARY = "#e6e6e6"
    TEXT_SECONDARY = "#a6a6a6"
    ACCENT = DEFAULT_THEME_ACCENT_HEX


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
    accent_rgb = get_theme_accent_rgb()

    if dark:
        return ListWidgetPalette(
            background="rgba(39, 39, 39, 1)",
            border="rgba(255, 255, 255, 0.08)",
            text="rgba(255, 255, 255, 1)",
            text_disabled="rgba(255, 255, 255, 0.42)",
            hover="rgba(255, 255, 255, 0.06)",
            selected_background=f"rgba({accent_rgb}, 0.30)",
            selected_text="rgba(255, 255, 255, 1)",
        )

    return ListWidgetPalette(
        background="rgba(249, 249, 249, 1)",
        border="rgba(0, 0, 0, 0.08)",
        text="rgba(0, 0, 0, 1)",
        text_disabled="rgba(0, 0, 0, 0.42)",
        hover="rgba(0, 0, 0, 0.04)",
        selected_background=f"rgba({accent_rgb}, 0.15)",
        selected_text="rgba(0, 0, 0, 1)",
    )


def get_page_background_color(*, dark: bool | None = None) -> str:
    """Get page background color by theme with light-mode accent tint."""
    if dark is None:
        dark = isDarkTheme()
    if dark:
        return DARK_PAGE_BACKGROUND_HEX
    return _blend_hex_colors(get_theme_accent_hex(), "#ffffff", 0.94)


def get_stylesheet(*, dark: bool = False) -> str:
    """Build the main app stylesheet for light/dark mode."""
    palette = DarkColors if dark else Colors
    page_background = get_page_background_color(dark=dark)
    accent = get_theme_accent_text_hex(dark=dark)
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
    combo_min_height = max(
        scale_px(30, scale=scale, min_value=28),
        combo_text_px + scale_px(8, scale=scale, min_value=6),
    )
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
    border-color: {accent};
}}

ComboBox, ModelComboBox, EditableComboBox {{
    border: 1px solid {palette.BORDER};
    border-radius: {combo_radius}px;
    padding:
        {combo_padding_top}px
        {combo_padding_right}px
        {combo_padding_bottom}px
        {combo_padding_left}px;
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

RoundMenu,
FlyoutView,
QWidget#roundMenu {{
    background-color: {palette.SURFACE};
    border: 1px solid {palette.BORDER};
    border-radius: {menu_border_radius}px;
}}

RoundMenu QLabel,
FlyoutView QLabel {{
    color: {palette.TEXT_PRIMARY};
    background: transparent;
}}

RoundMenu::item,
FlyoutView::item {{
    color: {palette.TEXT_PRIMARY};
    background: transparent;
    padding: 6px 12px;
}}

RoundMenu::item:selected,
FlyoutView::item:selected {{
    background-color: {"rgba(255, 255, 255, 0.10)" if dark else "rgba(0, 0, 0, 0.06)"};
    color: {palette.TEXT_PRIMARY};
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
