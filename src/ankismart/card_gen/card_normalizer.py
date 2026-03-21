from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .card_format_parsers import (
    has_valid_cloze,
    normalize_html_to_text,
    parse_answer_block,
    parse_choice_back,
    parse_choice_front,
)
from .card_kind import detect_card_kind_from_parts


@dataclass(slots=True)
class NormalizationResult:
    fields: dict[str, str]
    quality_flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocking_errors: list[str] = field(default_factory=list)
    card_kind: str = "generic"


def normalize_fields(
    *,
    note_type: str,
    strategy_id: str,
    fields: Mapping[str, object],
    tags: Sequence[str] | None = None,
) -> NormalizationResult:
    normalized_input = {str(key): _coerce_text(value) for key, value in fields.items()}
    card_kind = detect_card_kind_from_parts(
        note_type=note_type,
        strategy_id=strategy_id,
        tags=tags,
        fields=normalized_input,
    )
    if card_kind in {"basic", "concept", "key_terms", "image_qa"}:
        return _normalize_basic_like(card_kind, normalized_input)
    if card_kind == "single_choice":
        return _normalize_single_choice(normalized_input)
    if card_kind == "multiple_choice":
        return _normalize_multiple_choice(normalized_input)
    if card_kind == "cloze":
        return _normalize_cloze(normalized_input)
    return _normalize_generic(normalized_input)


def _normalize_basic_like(card_kind: str, fields: Mapping[str, str]) -> NormalizationResult:
    front = _first_non_empty(fields, "Front", "Question", "Text")
    raw_back = _first_non_empty(fields, "Back", "Answer", "Extra")
    answer, explanation = parse_answer_block(raw_back)

    quality_flags: list[str] = []
    if not explanation:
        quality_flags.append("missing_explanation")
    if front and answer and front == answer:
        quality_flags.append("question_equals_answer")
    if len(front) < 3 or len(answer) < 3:
        quality_flags.append("too_short")

    return NormalizationResult(
        fields={
            "Front": normalize_html_to_text(front),
            "Back": _compose_answer_block(answer, explanation),
        },
        quality_flags=_dedupe(quality_flags),
        card_kind=card_kind,
    )


def _normalize_single_choice(fields: Mapping[str, str]) -> NormalizationResult:
    question, options = parse_choice_front(_first_non_empty(fields, "Front", "Question", "Text"))
    answer_keys, explanation_lines = parse_choice_back(_first_non_empty(fields, "Back", "Answer"))
    quality_flags: list[str] = []

    options = _dedupe_options(options)
    if len(answer_keys) > 1:
        quality_flags.append("multiple_answers_in_single_choice")
        answer_keys = answer_keys[:1]
    if len(options) > 4:
        quality_flags.append("single_choice_trimmed_extra_options")
        options = options[:4]
    if len(options) != 4:
        quality_flags.append("invalid_option_count")
    if not answer_keys:
        quality_flags.append("choice_missing_answer")
    if not explanation_lines:
        quality_flags.append("missing_explanation")

    return NormalizationResult(
        fields={
            "Front": _compose_choice_front(question, options),
            "Back": _compose_choice_back(answer_keys, explanation_lines),
        },
        quality_flags=_dedupe(quality_flags),
        card_kind="single_choice",
    )


def _normalize_multiple_choice(fields: Mapping[str, str]) -> NormalizationResult:
    question, options = parse_choice_front(_first_non_empty(fields, "Front", "Question", "Text"))
    answer_keys, explanation_lines = parse_choice_back(_first_non_empty(fields, "Back", "Answer"))
    quality_flags: list[str] = []

    options = _dedupe_options(options)
    if len(options) > 5:
        quality_flags.append("multiple_choice_trimmed_extra_options")
        options = options[:5]
    if not 4 <= len(options) <= 5:
        quality_flags.append("invalid_option_count")

    answer_keys = sorted(set(answer_keys), key=lambda item: "ABCDE".index(item))
    if len(answer_keys) < 2:
        quality_flags.append("insufficient_correct_options")
    if not explanation_lines:
        quality_flags.append("missing_explanation")

    return NormalizationResult(
        fields={
            "Front": _compose_choice_front(question, options),
            "Back": _compose_choice_back(answer_keys, explanation_lines),
        },
        quality_flags=_dedupe(quality_flags),
        card_kind="multiple_choice",
    )


def _normalize_cloze(fields: Mapping[str, str]) -> NormalizationResult:
    text = _first_non_empty(fields, "Text", "Front", "Question")
    extra = _first_non_empty(fields, "Extra", "Back Extra", "Back", "Answer")
    quality_flags: list[str] = []
    blocking_errors: list[str] = []
    if not has_valid_cloze(text):
        quality_flags.append("cloze_syntax_invalid")
        blocking_errors.append("cloze_syntax_invalid")

    return NormalizationResult(
        fields={
            "Text": normalize_html_to_text(text),
            "Extra": normalize_html_to_text(extra),
        },
        quality_flags=quality_flags,
        blocking_errors=blocking_errors,
        card_kind="cloze",
    )


def _normalize_generic(fields: Mapping[str, str]) -> NormalizationResult:
    cleaned = {str(key): normalize_html_to_text(value) for key, value in fields.items()}
    blocking_errors = [] if cleaned else ["unsupported_generic_structure"]
    return NormalizationResult(
        fields=cleaned,
        blocking_errors=blocking_errors,
        card_kind="generic",
    )


def _coerce_text(value: object) -> str:
    return str(value or "").strip()


def _first_non_empty(fields: Mapping[str, str], *keys: str) -> str:
    for key in keys:
        value = normalize_html_to_text(fields.get(key, ""))
        if value:
            return value
    return ""


def _compose_answer_block(answer: str, explanation: str) -> str:
    answer_line = f"答案: {answer}".rstrip()
    if not explanation:
        return answer_line
    return f"{answer_line}\n解析:\n{explanation}".strip()


def _compose_choice_front(question: str, options: list[tuple[str, str]]) -> str:
    option_lines = [f"{key}. {text}".strip() for key, text in options]
    return "\n".join(segment for segment in [question.strip(), *option_lines] if segment).strip()


def _compose_choice_back(answer_keys: list[str], explanation_lines: list[str]) -> str:
    answer_line = f"答案: {', '.join(answer_keys)}".rstrip(": ").strip()
    if not answer_keys:
        answer_line = "答案:"
    if not explanation_lines:
        return answer_line
    explanation = "\n".join(line for line in explanation_lines if line.strip()).strip()
    return f"{answer_line}\n解析:\n{explanation}".strip()


def _dedupe_options(options: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for key, text in options:
        normalized = key.upper()
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append((normalized, text.strip()))
    return result


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
