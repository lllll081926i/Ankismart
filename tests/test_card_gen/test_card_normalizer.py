from __future__ import annotations

from ankismart.card_gen.card_normalizer import normalize_fields


def test_normalize_basic_alias_fields_to_front_back_answer_explanation_block() -> None:
    result = normalize_fields(
        note_type="Basic",
        strategy_id="basic",
        fields={
            "Question": "什么是事务原子性？",
            "Answer": "操作要么全成要么全败。解析：这是 ACID 的 A。",
        },
    )

    assert result.fields["Front"] == "什么是事务原子性？"
    assert result.fields["Back"].startswith("答案:")
    assert "解析:" in result.fields["Back"]


def test_normalize_single_choice_rewrites_front_and_back_to_standard_layout() -> None:
    result = normalize_fields(
        note_type="Basic",
        strategy_id="single_choice",
        fields={
            "Front": "Python 默认解释器是？ A. CPython B. JVM C. CLR D. Lua",
            "Back": "答案：A CPython 是官方实现。",
        },
    )

    assert result.fields["Front"].count("\n") >= 4
    assert result.fields["Back"].startswith("答案: A")
    assert "解析:" in result.fields["Back"]


def test_normalize_cloze_keeps_text_and_marks_invalid_when_token_missing() -> None:
    result = normalize_fields(
        note_type="AnkiSmart Cloze",
        strategy_id="cloze",
        fields={"Text": "plain text", "Extra": "hint"},
    )

    assert "cloze_syntax_invalid" in result.quality_flags
