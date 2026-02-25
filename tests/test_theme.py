"""Theme switching smoke tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme

from ankismart.anki_gateway.styling import PREVIEW_CARD_EXTRA_CSS
from ankismart.core.config import AppConfig
from ankismart.core.models import CardDraft
from ankismart.ui.card_preview_page import CardPreviewPage, CardRenderer
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


def _make_card_preview_main() -> MagicMock:
    main = MagicMock()
    main.config = AppConfig(language="zh")
    main.result_page = MagicMock()
    main.switchTo = MagicMock()
    return main


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

    assert 'class="flat-card"' in html
    assert html.count('class="flat-block') >= 3
    assert "问题" in html
    assert "答案" in html
    assert "解析" in html
    assert "C1" in html
    assert "C2" in html


def test_choice_preview_keeps_question_answer_structure() -> None:
    card = CardDraft(
        note_type="Basic",
        tags=["single_choice"],
        fields={
            "Front": (
                "Python 默认解释器是？ A. CPython B. JVM C. CLR D. Lua"
            ),
            "Back": (
                "答案：A CPython 是官方实现。它与解释器生态兼容性最好，"
                "并且在多数平台具有成熟支持。"
            ),
        },
    )
    html = CardRenderer.render_card(card)

    assert 'class="flat-option-list"' in html
    assert html.count('class="flat-option-line"') >= 4
    assert 'class="flat-answer-line"' in html
    assert 'class="flat-block flat-explain"' in html


def test_choice_back_prefixed_answer_is_split() -> None:
    keys, explanation = CardRenderer._parse_choice_back(
        "B 该模式面向两条线路存在共线区段，车辆在换乘站区间前后衔接。"
    )

    assert keys == ["B"]
    assert "共线区段" in explanation


def test_card_preview_push_finished_navigates_to_result(monkeypatch) -> None:
    main = _make_card_preview_main()
    page = CardPreviewPage(main)
    page._all_cards = [CardDraft(fields={"Front": "Q", "Back": "A"})]

    monkeypatch.setattr(
        "ankismart.ui.card_preview_page.InfoBar",
        type("_InfoBarStub", (), {"success": staticmethod(lambda *a, **k: None)}),
    )

    result = MagicMock()
    page._on_push_finished(result)

    main.result_page.load_result.assert_called_once_with(result, page._all_cards)
    main.switchTo.assert_called_once_with(main.result_page)


def test_card_preview_export_finished_does_not_navigate(monkeypatch) -> None:
    main = _make_card_preview_main()
    page = CardPreviewPage(main)
    page._all_cards = [CardDraft(fields={"Front": "Q", "Back": "A"})]

    monkeypatch.setattr(
        "ankismart.ui.card_preview_page.InfoBar",
        type("_InfoBarStub", (), {"success": staticmethod(lambda *a, **k: None)}),
    )

    page._on_export_finished("D:/tmp/cards.apkg")

    main.switchTo.assert_not_called()


def test_card_preview_quality_score_distinguishes_low_and_high() -> None:
    main = _make_card_preview_main()
    page = CardPreviewPage(main)

    low = CardDraft(note_type="Basic", fields={"Front": "Q", "Back": "A"})
    high = CardDraft(
        note_type="Basic",
        fields={
            "Front": "请解释布隆过滤器的核心思想与适用场景",
            "Back": "通过位数组和多个哈希函数实现概率判重，适合大规模去重与缓存预判。",
        },
    )

    assert page._compute_card_quality_score(low) < 60
    assert page._compute_card_quality_score(high) >= 80


def test_card_preview_low_quality_filter_only_keeps_low_cards() -> None:
    main = _make_card_preview_main()
    page = CardPreviewPage(main)
    low = CardDraft(note_type="Basic", fields={"Front": "Q", "Back": "A"})
    high = CardDraft(
        note_type="Basic",
        fields={
            "Front": "什么是幂等操作，为什么在分布式系统里重要？",
            "Back": "幂等表示重复执行结果一致，可降低重试带来的副作用。",
        },
    )

    page.load_cards([low, high])
    assert len(page._filtered_cards) == 2

    page._on_toggle_low_quality_filter(True)

    assert len(page._filtered_cards) == 1
    assert page._filtered_cards[0] is low
    assert "低分 1/2" in page._quality_overview_label.text()
