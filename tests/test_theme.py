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
            "Front": ("Python 默认解释器是？ A. CPython B. JVM C. CLR D. Lua"),
            "Back": (
                "答案：A CPython 是官方实现。它与解释器生态兼容性最好，并且在多数平台具有成熟支持。"
            ),
        },
    )
    html = CardRenderer.render_card(card)

    assert 'class="flat-option-list"' in html
    assert html.count('class="flat-option-line"') >= 4
    assert 'class="flat-answer-line"' in html
    assert 'class="flat-block flat-explain"' in html


def test_choice_preview_uses_line_by_line_answer_and_explanation_layout() -> None:
    card = CardDraft(
        note_type="Basic",
        tags=["multiple_choice"],
        fields={
            "Front": (
                "下列关于线程的说法哪些正确？\n"
                "A. 线程共享进程地址空间\n"
                "B. 线程拥有彼此完全独立的地址空间\n"
                "C. 线程切换开销通常小于进程\n"
                "D. 线程间通信必须经过网络"
            ),
            "Back": (
                "答案：A, C\n"
                "解析:\n"
                "A. 同一进程内的线程通常共享地址空间。\n"
                "B. 独立地址空间对应的是进程，不是线程。\n"
                "C. 线程切换通常比进程切换更轻量。\n"
                "D. 线程间通信可直接依赖共享内存与同步机制。"
            ),
        },
    )

    html = CardRenderer.render_card(card)

    assert html.count('class="flat-answer-item"') == 2
    assert html.count('class="flat-explain-item"') >= 4
    assert 'class="flat-answer-key">A</span>' in html
    assert 'class="flat-answer-key">C</span>' in html


def test_card_preview_inserts_visual_spacers_between_sections() -> None:
    card = CardDraft(
        note_type="Basic",
        fields={
            "Front": "什么是事务的原子性？",
            "Back": "事务中的操作要么全部成功，要么全部失败。\n解析：这是 ACID 的 A。",
        },
    )

    html = CardRenderer.render_card(card)

    assert html.count('class="flat-section-spacer"') == 2


def test_choice_back_prefixed_answer_is_split() -> None:
    keys, explanation = CardRenderer._parse_choice_back(
        "B 该模式面向两条线路存在共线区段，车辆在换乘站区间前后衔接。"
    )

    assert keys == ["B"]
    assert "共线区段" in explanation


def test_concept_preview_highlights_focus_keyword_and_sections() -> None:
    card = CardDraft(
        note_type="Basic",
        tags=["concept"],
        fields={
            "Front": "CAP 定理",
            "Back": (
                "答案：分布式系统中一致性、可用性与分区容错性的权衡。\n"
                "解析：核心：发生分区时必须做取舍。\n"
                "关键场景：网络不稳定或跨机房部署。"
            ),
        },
    )

    html = CardRenderer.render_card(card)

    assert 'class="flat-focus-line"' in html
    assert 'class="flat-keyword">核心</span>' in html
    assert 'class="flat-keyword">关键场景</span>' in html


def test_cloze_preview_renders_answer_entries_as_structured_rows() -> None:
    card = CardDraft(
        note_type="Cloze",
        fields={"Text": "地球是太阳系第 {{c1::三}} 颗行星，简称 {{c2::蓝星::别称}}。"},
    )

    html = CardRenderer.render_card(card)

    assert html.count('class="flat-answer-item"') >= 2
    assert 'class="flat-answer-key">C1</span>' in html
    assert 'class="flat-answer-key">C2</span>' in html


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


def test_card_preview_duplicate_risk_filter_only_keeps_risky_cards() -> None:
    main = _make_card_preview_main()
    page = CardPreviewPage(main)
    risky_a = CardDraft(
        note_type="Basic",
        fields={
            "Front": "什么是布隆过滤器的核心思想？",
            "Back": "通过位数组和多个哈希函数做概率判重。",
        },
    )
    risky_b = CardDraft(
        note_type="Basic",
        fields={
            "Front": "什么是布隆过滤器的核心思想",
            "Back": "利用位数组与多个哈希函数实现概率判重。",
        },
    )
    safe = CardDraft(
        note_type="Basic",
        fields={
            "Front": "解释 CAP 定理中的一致性含义",
            "Back": "同一时刻所有节点看到相同数据视图。",
        },
    )

    page.load_cards([risky_a, risky_b, safe])
    assert len(page._filtered_cards) == 3

    page._on_toggle_duplicate_risk_filter(True)

    assert page._filtered_cards == [risky_a, risky_b]
    assert "近重复 2/3" in page._quality_overview_label.text()


def test_card_preview_list_marks_low_quality_and_duplicate_risk() -> None:
    main = _make_card_preview_main()
    page = CardPreviewPage(main)
    low = CardDraft(note_type="Basic", fields={"Front": "Q", "Back": "A"})
    risky = CardDraft(
        note_type="Basic",
        fields={
            "Front": "解释消息队列削峰填谷的典型场景",
            "Back": "通过异步缓冲平滑突发流量。",
        },
    )
    risky_copy = CardDraft(
        note_type="Basic",
        fields={
            "Front": "解释消息队列削峰填谷的典型场景。",
            "Back": "通过异步缓冲来平滑系统突发流量。",
        },
    )

    page.load_cards([low, risky, risky_copy])

    assert "[低分]" in page._card_list.item(0).text()
    assert "[近重复]" in page._card_list.item(1).text()
    assert "[近重复]" in page._card_list.item(2).text()


def test_card_preview_meta_labels_use_chinese_type_mapping_and_trim_tags() -> None:
    main = _make_card_preview_main()
    page = CardPreviewPage(main)
    card = CardDraft(
        note_type="Basic",
        deck_name="Ankismart::Demo",
        tags=["ankismart", "demo", "basic", "extra"],
        fields={"Front": "Q", "Back": "A"},
    )

    page._set_card_meta_labels(card)

    assert "类型: 基础问答" in page._note_type_label.text()
    assert "质量:" in page._note_type_label.text()
    assert page._deck_label.text() == "牌组: Ankismart::Demo"
    assert page._tags_label.text() == "标签: ankismart, demo, basic 等1个"
    assert page._tags_label.toolTip() == "ankismart, demo, basic, extra"


def test_card_preview_bottom_bar_keeps_only_core_actions() -> None:
    main = _make_card_preview_main()
    page = CardPreviewPage(main)

    assert hasattr(page, "_btn_export_apkg")
    assert hasattr(page, "_btn_export_csv")
    assert hasattr(page, "_btn_push")
    assert not hasattr(page, "_btn_export_json")
    assert not hasattr(page, "_btn_push_preview")
