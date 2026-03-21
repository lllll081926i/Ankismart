from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from .card_format_parsers import (
    has_valid_cloze,
    parse_answer_block,
    parse_choice_back,
    parse_choice_front,
)


@dataclass(slots=True)
class ValidationResult:
    status: Literal["normalized", "warning", "blocking"]
    warnings: list[str] = field(default_factory=list)
    blocking_errors: list[str] = field(default_factory=list)


def validate_normalized_card(
    *,
    note_type: str,
    card_kind: str,
    fields: Mapping[str, str],
) -> ValidationResult:
    warnings: list[str] = []
    blocking_errors: list[str] = []

    if card_kind in {"basic", "concept", "key_terms", "image_qa", "basic_reversed"}:
        front = str(fields.get("Front", "")).strip()
        back = str(fields.get("Back", "")).strip()
        answer, explanation = parse_answer_block(back)
        if not front:
            blocking_errors.append("basic_missing_front")
        if not answer:
            blocking_errors.append("basic_missing_answer")
        if not explanation:
            warnings.append("missing_explanation")
    elif card_kind == "single_choice":
        question, options = parse_choice_front(str(fields.get("Front", "")))
        answer_keys, explanation_lines = parse_choice_back(str(fields.get("Back", "")))
        option_keys = {key for key, _ in options}
        if not question.strip():
            blocking_errors.append("choice_missing_question")
        if len(options) != 4:
            blocking_errors.append("invalid_option_count")
        if len(answer_keys) != 1:
            blocking_errors.append("choice_missing_answer")
        if any(key not in option_keys for key in answer_keys):
            blocking_errors.append("choice_answer_not_in_options")
        if not explanation_lines:
            warnings.append("missing_explanation")
    elif card_kind == "multiple_choice":
        question, options = parse_choice_front(str(fields.get("Front", "")))
        answer_keys, explanation_lines = parse_choice_back(str(fields.get("Back", "")))
        option_keys = {key for key, _ in options}
        if not question.strip():
            blocking_errors.append("choice_missing_question")
        if not 4 <= len(options) <= 5:
            blocking_errors.append("invalid_option_count")
        if len(answer_keys) < 2:
            blocking_errors.append("insufficient_correct_options")
        if any(key not in option_keys for key in answer_keys):
            blocking_errors.append("choice_answer_not_in_options")
        if not explanation_lines:
            warnings.append("missing_explanation")
    elif card_kind == "cloze" or "cloze" in str(note_type or "").lower():
        text = str(fields.get("Text", "")).strip()
        if not has_valid_cloze(text):
            blocking_errors.append("cloze_syntax_invalid")
    else:
        blocking_errors.append("unsupported_generic_structure")

    if blocking_errors:
        status: Literal["normalized", "warning", "blocking"] = "blocking"
    elif warnings:
        status = "warning"
    else:
        status = "normalized"
    return ValidationResult(status=status, warnings=warnings, blocking_errors=blocking_errors)
