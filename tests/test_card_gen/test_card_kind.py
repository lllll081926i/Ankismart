from __future__ import annotations

from ankismart.card_gen.card_kind import detect_card_kind, detect_card_kind_from_parts
from ankismart.core.models import CardDraft, CardMetadata


def test_detect_card_kind_prefers_strategy_id_over_tags_and_note_type() -> None:
    card = CardDraft(
        note_type="Basic",
        tags=["basic"],
        fields={"Front": "Q", "Back": "A"},
        metadata=CardMetadata(strategy_id="single_choice"),
    )

    assert detect_card_kind(card) == "single_choice"


def test_detect_card_kind_falls_back_to_tags_then_note_type_then_field_shape() -> None:
    tagged = CardDraft(
        note_type="Basic",
        tags=["multiple_choice"],
        fields={"Front": "Q", "Back": "A"},
    )
    assert detect_card_kind(tagged) == "multiple_choice"

    cloze = CardDraft(
        note_type="AnkiSmart Cloze",
        fields={"Text": "{{c1::value}}", "Extra": "hint"},
    )
    assert detect_card_kind(cloze) == "cloze"

    heuristic = CardDraft(
        note_type="Custom",
        fields={"Text": "{{c1::value}}", "Extra": "hint"},
    )
    assert detect_card_kind(heuristic) == "cloze"


def test_detect_card_kind_identifies_multiple_choice_from_basic_field_shape() -> None:
    assert (
        detect_card_kind_from_parts(
            note_type="Basic",
            fields={
                "Front": "下列哪些属于 Python 数据类型？ A. list B. tuple C. interface D. dict",
                "Back": "答案：A, B, D\n解析:\nA. 对\nB. 对\nC. 错\nD. 对",
            },
        )
        == "multiple_choice"
    )
