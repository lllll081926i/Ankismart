from __future__ import annotations

from ankismart.card_gen.card_structure_validator import validate_normalized_card


def test_validate_single_choice_blocks_when_option_count_is_invalid() -> None:
    result = validate_normalized_card(
        note_type="Basic",
        card_kind="single_choice",
        fields={"Front": "题目\nA. 1\nB. 2", "Back": "答案: A\n解析:\nA. 对\nB. 错"},
    )

    assert result.status == "blocking"


def test_validate_basic_like_warns_when_explanation_missing() -> None:
    result = validate_normalized_card(
        note_type="Basic",
        card_kind="basic",
        fields={"Front": "Q", "Back": "答案: A"},
    )

    assert result.status == "warning"


def test_validate_ankismart_cloze_blocks_without_valid_cloze_token() -> None:
    result = validate_normalized_card(
        note_type="AnkiSmart Cloze",
        card_kind="cloze",
        fields={"Text": "plain text", "Extra": ""},
    )

    assert result.status == "blocking"
