from __future__ import annotations

from collections.abc import Mapping, Sequence

from ankismart.core.models import CardDraft

from .card_kind import detect_card_kind
from .card_normalizer import NormalizationResult, normalize_fields
from .card_structure_validator import ValidationResult, validate_normalized_card


def normalize_raw_card(
    *,
    note_type: str,
    strategy_id: str,
    fields: Mapping[str, object],
    tags: Sequence[str] | None = None,
) -> NormalizationResult:
    return normalize_fields(
        note_type=note_type,
        strategy_id=strategy_id,
        fields=fields,
        tags=tags,
    )


def normalize_card_draft(draft: CardDraft) -> CardDraft:
    normalized = normalize_raw_card(
        note_type=draft.note_type,
        strategy_id=draft.metadata.strategy_id,
        fields=draft.fields,
        tags=draft.tags,
    )
    updated = draft.model_copy(deep=True)
    updated.fields = dict(normalized.fields)
    updated.metadata.quality_flags = _merge_flags(
        list(updated.metadata.quality_flags),
        normalized.quality_flags,
    )
    return updated


def normalize_cards(cards: Sequence[CardDraft]) -> list[CardDraft]:
    return [normalize_card_draft(card) for card in cards]


def validate_card_for_output(draft: CardDraft) -> ValidationResult:
    normalized = normalize_card_draft(draft)
    return validate_normalized_card(
        note_type=normalized.note_type,
        card_kind=detect_card_kind(normalized),
        fields=normalized.fields,
    )


def _merge_flags(*flag_lists: list[str]) -> list[str]:
    merged: list[str] = []
    for values in flag_lists:
        for value in values:
            if value and value not in merged:
                merged.append(value)
    return merged
