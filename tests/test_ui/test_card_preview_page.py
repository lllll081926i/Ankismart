from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication
from qfluentwidgets import PushButton

from ankismart.card_gen.postprocess import build_card_drafts
from ankismart.core.models import CardDraft, CardMetadata
from ankismart.ui.card_preview_page import CardPreviewPage, CardRenderer

_APP = QApplication.instance() or QApplication(sys.argv)


def _make_card(
    *,
    front: str,
    back: str,
    quality_flags: list[str] | None = None,
    source_document: str = "",
    strategy_id: str = "basic",
) -> CardDraft:
    return CardDraft(
        fields={"Front": front, "Back": back},
        note_type="Basic",
        deck_name="Default",
        tags=["ankismart"],
        metadata=CardMetadata(
            quality_flags=list(quality_flags or []),
            source_document=source_document,
            strategy_id=strategy_id,
        ),
    )


def _make_main_window() -> MagicMock:
    main = MagicMock()
    main.config = SimpleNamespace(
        language="zh",
        allow_duplicate=False,
        duplicate_scope="deck",
        duplicate_check_model=True,
        semantic_duplicate_threshold=0.9,
        anki_connect_url="",
        anki_connect_key="",
        proxy_url="",
        last_update_mode="create_or_update",
    )
    main.switch_to_preview = MagicMock()
    main.preview_page = MagicMock()
    return main


def test_card_preview_can_filter_only_low_quality_cards() -> None:
    page = CardPreviewPage(_make_main_window())
    page.load_cards(
        [
            _make_card(
                front="Q",
                back="A",
                quality_flags=["too_short"],
                source_document="sample.md",
            ),
            _make_card(front="Long enough question", back="Long enough answer"),
        ]
    )

    page._on_toggle_low_quality_filter(True)

    assert page._card_list.count() == 1


def test_preview_page_shows_quality_flags_for_normalized_cards() -> None:
    page = CardPreviewPage(_make_main_window())
    page.load_cards(
        [
            _make_card(
                front="什么是事务原子性？",
                back="答案: 原子性",
                quality_flags=["missing_explanation"],
            )
        ]
    )

    assert "风险: 缺少解析" in page._note_type_label.text()


def test_card_preview_hides_bulk_regenerate_buttons_and_keeps_actions_right_aligned() -> None:
    page = CardPreviewPage(_make_main_window())

    button_texts = [button.text() for button in page.findChildren(PushButton)]

    assert "重生成当前卡" in button_texts
    assert "重生成所选" not in button_texts
    assert "重生成来源文档" not in button_texts
    assert not hasattr(page, "_btn_regenerate_selected")
    assert not hasattr(page, "_btn_regenerate_source")
    assert page._bottom_bar_layout.itemAt(0).widget() is page._count_label
    assert page._bottom_bar_layout.itemAt(1).spacerItem() is not None
    assert page._bottom_bar_layout.itemAt(2).widget() is page._btn_prev


def test_regenerate_current_card_reuses_source_document(monkeypatch) -> None:
    page = CardPreviewPage(_make_main_window())
    page.load_cards(
        [
            _make_card(
                front="Question",
                back="Answer",
                source_document="sample.md",
                strategy_id="basic",
            )
        ]
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        page,
        "_dispatch_regenerate_request",
        lambda request: captured.setdefault("request", request),
    )
    page._card_list.setCurrentRow(0)

    page._regenerate_current_card()

    assert captured["request"].scope == "current_card"
    assert captured["request"].source_documents == ["sample.md"]


def test_large_card_load_defers_duplicate_scan_and_renders_once(monkeypatch) -> None:
    page = CardPreviewPage(_make_main_window())
    cards = [_make_card(front=f"Question {index}", back=f"Answer {index}") for index in range(500)]
    duplicate_calls = {"count": 0}
    show_calls: list[int] = []

    def _collect_duplicate_risk_indices(cards_arg, threshold):
        duplicate_calls["count"] += 1
        return set()

    monkeypatch.setattr(page, "_collect_duplicate_risk_indices", _collect_duplicate_risk_indices)
    monkeypatch.setattr(page, "_show_card", lambda index: show_calls.append(index))

    page.load_cards(cards)

    assert duplicate_calls["count"] == 0
    assert page._duplicate_risk_pending is True
    assert page._card_list.count() == 500
    assert show_calls == [0]


def test_duplicate_filter_computes_deferred_duplicate_scan_once(monkeypatch) -> None:
    page = CardPreviewPage(_make_main_window())
    cards = [_make_card(front=f"Question {index}", back=f"Answer {index}") for index in range(500)]
    duplicate_calls = {"count": 0}

    def _collect_duplicate_risk_indices(cards_arg, threshold):
        duplicate_calls["count"] += 1
        return {1, 3}

    monkeypatch.setattr(page, "_collect_duplicate_risk_indices", _collect_duplicate_risk_indices)
    page.load_cards(cards)

    page._on_toggle_duplicate_risk_filter(True)
    page._on_toggle_duplicate_risk_filter(True)

    assert duplicate_calls["count"] == 1
    assert page._duplicate_risk_pending is False
    assert page._card_list.count() == 2


def test_preview_detects_choice_kind_from_strategy_id_not_only_tags() -> None:
    card = CardDraft(
        note_type="Basic",
        fields={"Front": "题目 A. 一 B. 二 C. 三 D. 四", "Back": "答案：B 二正确"},
        metadata=CardMetadata(strategy_id="single_choice"),
    )

    assert CardRenderer.detect_card_kind(card) == "single_choice"


def test_preview_renders_normalized_choice_layout_from_shared_parser() -> None:
    card = CardDraft(
        note_type="Basic",
        fields={"Front": "题目 A. 一 B. 二 C. 三 D. 四", "Back": "答案：B 二正确"},
        metadata=CardMetadata(strategy_id="single_choice"),
    )

    html = CardRenderer.render_card(card)

    assert "A." in html
    assert "答案" in html


def test_preview_splits_inline_answer_and_explanation_into_separate_blocks() -> None:
    card = CardDraft(
        note_type="Basic",
        fields={
            "Front": "问题",
            "Back": "答案: 支路与支路相交采用无控制或优先控制；解析: 道路等级越高越需要信号控制。",
        },
    )

    html = CardRenderer.render_card(card)
    answer_fragment = html.split('class="flat-answer-line"', maxsplit=1)[1].split(
        "</section>", maxsplit=1
    )[0]

    assert "解析" not in answer_fragment
    assert "道路等级越高越需要信号控制" in html


def test_generated_choice_card_keeps_preview_layout_after_shared_normalization() -> None:
    draft = build_card_drafts(
        raw_cards=[
            {
                "Front": "下列哪些属于 Python 数据类型？ A. list B. tuple C. interface D. dict",
                "Back": "答案：A, B, D\n解析:\nA. 对\nB. 对\nC. 错\nD. 对",
            }
        ],
        deck_name="Default",
        note_type="Basic",
        tags=["ankismart"],
        trace_id="t-preview-choice",
        strategy_id="multiple_choice",
    )[0]

    html = CardRenderer.render_card(draft)

    assert draft.fields["Front"].splitlines()[1].startswith("A.")
    assert draft.fields["Back"].startswith("答案: A, B, D")
    assert html.count('class="flat-option-line"') == 4
    assert html.count('class="flat-answer-item"') == 3
