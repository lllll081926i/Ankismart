from __future__ import annotations

from typing import Any

from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.validator import validate_card_draft
from ankismart.core.errors import AnkiGatewayError
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, CardPushStatus, PushResult
from ankismart.core.tracing import timed, trace_context

logger = get_logger("anki_gateway")


def _card_to_note_params(card: CardDraft) -> dict[str, Any]:
    """Convert a CardDraft to AnkiConnect note params."""
    params: dict[str, Any] = {
        "deckName": card.deck_name,
        "modelName": card.note_type,
        "fields": card.fields,
        "tags": card.tags,
        "options": {
            "allowDuplicate": card.options.allow_duplicate,
            "duplicateScope": card.options.duplicate_scope,
            "duplicateScopeOptions": {
                "deckName": card.options.duplicate_scope_options.deck_name,
                "checkChildren": card.options.duplicate_scope_options.check_children,
                "checkAllModels": card.options.duplicate_scope_options.check_all_models,
            },
        },
    }

    # Add media if present
    for media_type in ("audio", "video", "picture"):
        items = getattr(card.media, media_type, [])
        if items:
            params[media_type] = [
                {k: v for k, v in item.model_dump().items() if v is not None and v != []}
                for item in items
            ]

    return params


class AnkiGateway:
    def __init__(self, client: AnkiConnectClient) -> None:
        self._client = client

    def check_connection(self) -> bool:
        return self._client.check_connection()

    def get_deck_names(self) -> list[str]:
        return self._client.get_deck_names()

    def get_model_names(self) -> list[str]:
        return self._client.get_model_names()

    def get_model_field_names(self, model_name: str) -> list[str]:
        return self._client.get_model_field_names(model_name)

    def push(self, cards: list[CardDraft]) -> PushResult:
        initial_trace_id = cards[0].trace_id if cards else None
        with trace_context(initial_trace_id) as trace_id:
            with timed("anki_push_total"):
                results: list[CardPushStatus] = []
                succeeded = 0
                failed = 0

                for i, card in enumerate(cards):
                    try:
                        validate_card_draft(card, self._client)
                        note_params = _card_to_note_params(card)
                        note_id = self._client.add_note(note_params)
                        results.append(CardPushStatus(index=i, note_id=note_id, success=True))
                        succeeded += 1
                    except AnkiGatewayError as exc:
                        logger.warning(
                            "Card push failed",
                            extra={"index": i, "error": exc.message, "trace_id": trace_id},
                        )
                        results.append(CardPushStatus(index=i, success=False, error=exc.message))
                        failed += 1

                logger.info(
                    "Push completed",
                    extra={
                        "trace_id": trace_id,
                        "total": len(cards),
                        "succeeded": succeeded,
                        "failed": failed,
                    },
                )

                return PushResult(
                    total=len(cards),
                    succeeded=succeeded,
                    failed=failed,
                    results=results,
                    trace_id=trace_id,
                )

    def push_or_update(self, cards: list[CardDraft]) -> PushResult:
        """Push cards, updating existing notes when a duplicate is found."""
        initial_trace_id = cards[0].trace_id if cards else None
        with trace_context(initial_trace_id) as trace_id:
            with timed("anki_push_or_update_total"):
                results: list[CardPushStatus] = []
                succeeded = 0
                failed = 0

                for i, card in enumerate(cards):
                    try:
                        validate_card_draft(card, self._client)
                        # Try to find existing note by front field
                        existing_id = self._find_existing_note(card)
                        if existing_id is not None:
                            self._client.update_note_fields(existing_id, card.fields)
                            results.append(CardPushStatus(
                                index=i, note_id=existing_id, success=True,
                            ))
                            logger.info(
                                "Updated existing note",
                                extra={"index": i, "note_id": existing_id, "trace_id": trace_id},
                            )
                        else:
                            note_params = _card_to_note_params(card)
                            note_id = self._client.add_note(note_params)
                            results.append(CardPushStatus(index=i, note_id=note_id, success=True))
                        succeeded += 1
                    except AnkiGatewayError as exc:
                        logger.warning(
                            "Card push/update failed",
                            extra={"index": i, "error": exc.message, "trace_id": trace_id},
                        )
                        results.append(CardPushStatus(index=i, success=False, error=exc.message))
                        failed += 1

                logger.info(
                    "Push/update completed",
                    extra={
                        "trace_id": trace_id,
                        "total": len(cards),
                        "succeeded": succeeded,
                        "failed": failed,
                    },
                )

                return PushResult(
                    total=len(cards),
                    succeeded=succeeded,
                    failed=failed,
                    results=results,
                    trace_id=trace_id,
                )

    def _find_existing_note(self, card: CardDraft) -> int | None:
        """Search for an existing note matching the card's front field in the same deck."""
        # Determine the primary field to search by
        front = card.fields.get("Front") or card.fields.get("Text")
        if not front:
            return None
        # Escape quotes in search query
        escaped = front.replace('"', '\\"')
        field_name = "Front" if "Front" in card.fields else "Text"
        model_name = card.note_type.replace('"', '\\"')
        query = f'note:"{model_name}" deck:"{card.deck_name}" "{field_name}:{escaped}"'
        try:
            note_ids = self._client.find_notes(query)
            return note_ids[0] if note_ids else None
        except AnkiGatewayError:
            return None
