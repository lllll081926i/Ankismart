from __future__ import annotations

from ankismart.card_gen.card_format_parsers import (
    normalize_html_to_text,
    parse_answer_block,
    parse_choice_back,
    parse_choice_front,
)


def test_parse_choice_front_supports_inline_html_and_fullwidth_punctuation() -> None:
    question, options = parse_choice_front(
        "Python 默认解释器是？<br>A：CPython B：JVM C：CLR D：Lua"
    )

    assert question == "Python 默认解释器是？"
    assert [key for key, _ in options] == ["A", "B", "C", "D"]


def test_parse_choice_back_extracts_answer_and_explanations_from_mixed_language_markers() -> None:
    answer_keys, explanation_lines = parse_choice_back("Answer: B\n解析:\nA. 错\nB. 对")

    assert answer_keys == ["B"]
    assert explanation_lines == ["A. 错", "B. 对"]


def test_parse_answer_block_splits_answer_and_explanation_without_number_prefixes() -> None:
    answer, explanation = parse_answer_block(
        "1. 答案: 原子性\n2. 解析:\n事务要么全部成功要么全部失败"
    )

    assert answer == "原子性"
    assert "事务要么全部成功要么全部失败" in explanation


def test_parse_answer_block_splits_inline_answer_and_explanation_marker() -> None:
    answer, explanation = parse_answer_block(
        "答案: 支路与支路相交通常采用无控制或优先控制；解析: 这体现道路等级匹配原则。"
    )

    assert answer == "支路与支路相交通常采用无控制或优先控制；"
    assert explanation == "这体现道路等级匹配原则。"


def test_normalize_html_to_text_preserves_angle_brackets_inside_mathjax() -> None:
    text = "答案: \\(a < b > c\\)<br>解析: 保留数学比较符。"

    normalized = normalize_html_to_text(text)

    assert "\\(a < b > c\\)" in normalized
    assert "解析: 保留数学比较符。" in normalized
