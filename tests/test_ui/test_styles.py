from ankismart.ui.styles import get_stylesheet, Colors, DarkColors


def test_light_stylesheet_contains_light_bg():
    css = get_stylesheet(dark=False)
    assert Colors.BACKGROUND in css
    assert len(css) > 100


def test_dark_stylesheet_contains_dark_bg():
    css = get_stylesheet(dark=True)
    assert DarkColors.BACKGROUND in css
    assert len(css) > 100


def test_dark_colors_differ_from_light():
    assert Colors.BACKGROUND != DarkColors.BACKGROUND
    assert Colors.TEXT_PRIMARY != DarkColors.TEXT_PRIMARY
    assert Colors.SURFACE != DarkColors.SURFACE
