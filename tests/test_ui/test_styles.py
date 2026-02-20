from ankismart.ui.styles import (
    DARK_PAGE_BACKGROUND_HEX,
    Colors,
    DarkColors,
    get_list_widget_palette,
    get_page_background_color,
    get_stylesheet,
)


def test_light_stylesheet_contains_light_bg():
    css = get_stylesheet(dark=False)
    assert Colors.BACKGROUND in css
    assert len(css) > 100


def test_dark_stylesheet_contains_dark_bg():
    css = get_stylesheet(dark=True)
    assert DARK_PAGE_BACKGROUND_HEX in css
    assert DarkColors.TEXT_PRIMARY in css
    assert len(css) > 100


def test_dark_colors_differ_from_light():
    assert Colors.BACKGROUND != DarkColors.BACKGROUND
    assert Colors.TEXT_PRIMARY != DarkColors.TEXT_PRIMARY
    assert Colors.SURFACE != DarkColors.SURFACE


def test_list_widget_palette_light_and_dark_are_distinct():
    light = get_list_widget_palette(dark=False)
    dark = get_list_widget_palette(dark=True)

    assert light.background != dark.background
    assert light.border != dark.border
    assert light.selected_background != dark.selected_background


def test_page_background_color_matches_theme():
    assert get_page_background_color(dark=False) == Colors.BACKGROUND
    assert get_page_background_color(dark=True) == DARK_PAGE_BACKGROUND_HEX
