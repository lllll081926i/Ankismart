"""Theme switching smoke tests."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from ankismart.anki_gateway.styling import PREVIEW_CARD_EXTRA_CSS
from ankismart.core.config import AppConfig
from ankismart.core.models import CardDraft
from ankismart.ui.card_preview_page import CardRenderer
from ankismart.ui.main_window import MainWindow
from ankismart.ui.shortcuts_dialog import ShortcutsHelpDialog
from ankismart.ui.styles import (
    DARK_PAGE_BACKGROUND_HEX,
    FIXED_PAGE_BACKGROUND_HEX,
    Colors,
    DarkColors,
)

_APP = QApplication.instance() or QApplication([])


def _get_app() -> QApplication:
    return _APP


def test_theme_switching(monkeypatch) -> None:
    monkeypatch.setattr("ankismart.ui.main_window.save_config", lambda _cfg: None)

    app = _get_app()
    window = MainWindow(config=AppConfig(theme="light", language="zh"))
    window.show()
    app.processEvents()

    window.switch_theme("dark")
    app.processEvents()
    assert window.config.theme == "dark"
    assert DarkColors.TEXT_PRIMARY in app.styleSheet()
    assert DARK_PAGE_BACKGROUND_HEX in app.styleSheet()

    window.switch_theme("light")
    app.processEvents()
    assert window.config.theme == "light"
    assert Colors.TEXT_PRIMARY in app.styleSheet()
    assert FIXED_PAGE_BACKGROUND_HEX in app.styleSheet()

    window.switch_theme("auto")
    app.processEvents()
    assert window.config.theme == "auto"

    window.close()
    app.processEvents()


def test_card_preview_uses_shared_preview_css() -> None:
    setTheme(Theme.LIGHT)
    html = CardRenderer._wrap_html("<div>demo</div>", "basic")
    assert ".card[data-card-type]" in PREVIEW_CARD_EXTRA_CSS
    assert ".card[data-card-type]" in html
    assert "Visual refresh from style demos" not in html


def test_card_preview_dark_class_keeps_compatibility() -> None:
    setTheme(Theme.DARK)
    html = CardRenderer._wrap_html("<div>demo</div>", "basic")
    assert '<body class="night_mode nightMode">' in html
    setTheme(Theme.LIGHT)


def test_shortcuts_dialog_can_construct_without_crash() -> None:
    dialog = ShortcutsHelpDialog("zh")
    dialog.close()


def test_cloze_preview_emphasizes_deletion_features() -> None:
    card = CardDraft(
        note_type="Cloze",
        fields={"Text": "地球是太阳系第 {{c1::三}} 颗行星，简称 {{c2::蓝星::别称}}。"},
    )
    html = CardRenderer.render_card(card)

    assert 'class="cloze cloze-emphasis"' in html
    assert 'class="cloze-answer-list"' in html
    assert "挖空要点" in html
    assert "C1" in html
    assert "C2" in html
    assert "提示：" in html


def test_choice_preview_keeps_question_answer_structure() -> None:
    card = CardDraft(
        note_type="Basic",
        tags=["single_choice"],
        fields={
            "Front": "Python 默认解释器是？\nA. CPython\nB. JVM\nC. CLR",
            "Back": "答案：A\nCPython 是官方实现。",
        },
    )
    html = CardRenderer.render_card(card)

    assert 'class="choice-question"' in html
    assert 'class="choice-options"' in html
    assert "choice-answer-box" in html
    assert "choice-explain" in html
