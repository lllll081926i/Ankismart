from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

from ankismart.card_gen.postprocess import build_card_drafts
from ankismart.core.models import CardDraft, CardMetadata, RegenerateRequest
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


def test_regenerate_selected_cards_reuses_source_document(monkeypatch) -> None:
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
    captured: dict[str, RegenerateRequest] = {}
    monkeypatch.setattr(
        page,
        "_dispatch_regenerate_request",
        lambda request: captured.setdefault("request", request),
    )
    page._card_list.setCurrentRow(0)

    page._regenerate_selected_cards()

    assert captured["request"].scope == "selected_cards"
    assert captured["request"].source_documents == ["sample.md"]


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
