from __future__ import annotations

import re

from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.card_gen.card_pipeline import normalize_card_draft, validate_card_for_output
from ankismart.core.errors import AnkiGatewayError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft
from ankismart.core.tracing import get_trace_id

logger = get_logger("anki_gateway.validator")

_CLOZE_PATTERN = re.compile(r"\{\{c\d+::.*?\}\}")


def validate_card_draft(draft: CardDraft, client: AnkiConnectClient) -> None:
    """Validate a CardDraft before writing to Anki. Raises AnkiGatewayError on failure."""
    trace_id = draft.trace_id or get_trace_id()
    normalized_draft = normalize_card_draft(draft)
    structural_validation = validate_card_for_output(normalized_draft)
    if structural_validation.status == "blocking":
        first_error = structural_validation.blocking_errors[0]
        raise AnkiGatewayError(
            _structure_error_message(first_error),
            code=(
                ErrorCode.E_CLOZE_SYNTAX_INVALID
                if first_error == "cloze_syntax_invalid"
                else ErrorCode.E_REQUIRED_FIELD_MISSING
            ),
            trace_id=trace_id,
        )

    # 1. Check deck exists
    decks = client.get_deck_names()
    if normalized_draft.deck_name not in decks:
        raise AnkiGatewayError(
            f"Deck not found: {normalized_draft.deck_name}",
            code=ErrorCode.E_DECK_NOT_FOUND,
            trace_id=trace_id,
        )

    # 2. Check note type exists
    models = client.get_model_names()
    if normalized_draft.note_type not in models:
        raise AnkiGatewayError(
            f"Note type not found: {normalized_draft.note_type}",
            code=ErrorCode.E_MODEL_NOT_FOUND,
            trace_id=trace_id,
        )

    # 3. Check required fields
    model_fields = client.get_model_field_names(normalized_draft.note_type)
    for field_name in model_fields:
        # First field is typically required
        if field_name == model_fields[0] and not normalized_draft.fields.get(field_name):
            raise AnkiGatewayError(
                f"Required field missing: {field_name}",
                code=ErrorCode.E_REQUIRED_FIELD_MISSING,
                trace_id=trace_id,
            )

    # 4. Cloze syntax validation
    if normalized_draft.note_type == "Cloze":
        text = normalized_draft.fields.get("Text", "")
        if not _CLOZE_PATTERN.search(text):
            raise AnkiGatewayError(
                "Cloze card missing valid {{cN::...}} syntax",
                code=ErrorCode.E_CLOZE_SYNTAX_INVALID,
                trace_id=trace_id,
            )

    # 5. Media validation
    for media_type in ("audio", "video", "picture"):
        items = getattr(normalized_draft.media, media_type, [])
        for item in items:
            sources = [item.data, item.path, item.url]
            provided = sum(1 for s in sources if s)
            if provided == 0:
                raise AnkiGatewayError(
                    f"Media item '{item.filename}' has no source (data/path/url)",
                    code=ErrorCode.E_MEDIA_INVALID,
                    trace_id=trace_id,
                )


def _structure_error_message(error_key: str) -> str:
    if error_key == "basic_missing_front":
        return "Required field missing: Front"
    return error_key
