from __future__ import annotations

from collections.abc import Mapping, Sequence

from ankismart.core.models import CardDraft

from .card_format_parsers import has_valid_cloze, parse_choice_front

SUPPORTED_CARD_KINDS = {
    "basic",
    "concept",
    "key_terms",
    "single_choice",
    "multiple_choice",
    "cloze",
    "image_qa",
    "generic",
}

_TAG_ALIASES = {
    "basic": "basic",
    "concept": "concept",
    "key_terms": "key_terms",
    "keyterms": "key_terms",
    "single_choice": "single_choice",
    "singlechoice": "single_choice",
    "multiple_choice": "multiple_choice",
    "multiplechoice": "multiple_choice",
    "image": "image_qa",
    "image_qa": "image_qa",
    "cloze": "cloze",
}


def detect_card_kind(card: CardDraft) -> str:
    return detect_card_kind_from_parts(
        note_type=card.note_type,
        strategy_id=card.metadata.strategy_id,
        tags=card.tags,
        fields=card.fields,
    )


def detect_card_kind_from_parts(
    *,
    note_type: str,
    strategy_id: str = "",
    tags: Sequence[str] | None = None,
    fields: Mapping[str, object] | None = None,
) -> str:
    strategy = str(strategy_id or "").strip().lower()
    if strategy in SUPPORTED_CARD_KINDS:
        return strategy

    lowered_tags = {str(tag).strip().lower() for tag in tags or [] if str(tag).strip()}
    for tag in lowered_tags:
        normalized = _TAG_ALIASES.get(tag)
        if normalized:
            return normalized

    normalized_note_type = str(note_type or "").strip().lower()
    if "cloze" in normalized_note_type:
        return "cloze"
    if "image" in normalized_note_type:
        return "image_qa"
    if normalized_note_type.startswith("basic"):
        return "basic"

    normalized_fields = {str(key): str(value or "") for key, value in (fields or {}).items()}
    if has_valid_cloze(normalized_fields.get("Text", "")):
        return "cloze"

    front = normalized_fields.get("Front", "") or normalized_fields.get("Question", "")
    _, options = parse_choice_front(front)
    if len(options) >= 2:
        return "single_choice"

    if "Front" in normalized_fields or "Back" in normalized_fields:
        return "basic"
    return "generic"
