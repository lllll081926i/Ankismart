from __future__ import annotations

from typing import Any, Literal

from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.validator import validate_card_draft
from ankismart.core.errors import AnkiGatewayError
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, CardPushStatus, PushResult
from ankismart.core.tracing import metrics, timed, trace_context

logger = get_logger("anki_gateway")

UpdateMode = Literal["create_only", "update_only", "create_or_update"]


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

    # ------------------------------------------------------------------
    # Single-note operations
    # ------------------------------------------------------------------

    def find_notes(self, query: str) -> list[int]:
        """Find note IDs matching an Anki search query."""
        return self._client.find_notes(query)

    def update_note(self, note_id: int, fields: dict[str, str]) -> None:
        """Update fields of an existing note by ID."""
        self._client.update_note_fields(note_id, fields)
        logger.info("Note updated", extra={"note_id": note_id})

    def create_or_update_note(self, card: CardDraft) -> CardPushStatus:
        """Create a note or update it if a duplicate front field exists."""
        validate_card_draft(card, self._client)
        existing_id = self._find_existing_note(card)
        if existing_id is not None:
            self._client.update_note_fields(existing_id, card.fields)
            logger.info("Updated existing note", extra={"note_id": existing_id})
            return CardPushStatus(index=0, note_id=existing_id, success=True)
        note_params = _card_to_note_params(card)
        note_id = self._client.add_note(note_params)
        return CardPushStatus(index=0, note_id=note_id, success=True)

    # ------------------------------------------------------------------
    # Batch push with update_mode
    # ------------------------------------------------------------------

    def push(
        self,
        cards: list[CardDraft],
        update_mode: UpdateMode = "create_only",
    ) -> PushResult:
        metrics.increment("anki_push_batches_total")
        metrics.increment("anki_push_cards_total", value=len(cards))
        initial_trace_id = cards[0].trace_id if cards else None
        with trace_context(initial_trace_id) as trace_id:
            with timed("anki_push_total"):
                results: list[CardPushStatus] = []
                succeeded = 0
                failed = 0

                for i, card in enumerate(cards):
                    try:
                        validate_card_draft(card, self._client)
                        status = self._push_single(i, card, update_mode, trace_id)
                        results.append(status)
                        if status.success:
                            succeeded += 1
                            metrics.increment("anki_push_succeeded_total")
                        else:
                            failed += 1
                            metrics.increment("anki_push_failed_total")
                    except AnkiGatewayError as exc:
                        logger.warning(
                            "Card push failed",
                            extra={"index": i, "error": exc.message, "trace_id": trace_id},
                        )
                        results.append(CardPushStatus(index=i, success=False, error=exc.message))
                        failed += 1
                        metrics.increment("anki_push_failed_total")

                total_processed = succeeded + failed
                success_ratio = (succeeded / total_processed) if total_processed else 0.0
                metrics.set_gauge("anki_push_success_ratio", success_ratio)

                logger.info(
                    "Push completed",
                    extra={
                        "trace_id": trace_id,
                        "update_mode": update_mode,
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
        """Backward-compatible alias for ``push(cards, update_mode="create_or_update")``."""
        return self.push(cards, update_mode="create_or_update")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _push_single(
        self,
        index: int,
        card: CardDraft,
        update_mode: UpdateMode,
        trace_id: str,
    ) -> CardPushStatus:
        """Process a single card according to *update_mode*."""
        existing_id = (
            self._find_existing_note(card)
            if update_mode != "create_only"
            else None
        )

        if update_mode == "create_only":
            note_params = _card_to_note_params(card)
            note_id = self._client.add_note(note_params)
            return CardPushStatus(index=index, note_id=note_id, success=True)

        if update_mode == "update_only":
            if existing_id is None:
                msg = "No existing note found to update"
                logger.warning(msg, extra={"index": index, "trace_id": trace_id})
                return CardPushStatus(index=index, success=False, error=msg)
            self._client.update_note_fields(existing_id, card.fields)
            logger.info("Updated existing note", extra={"index": index, "note_id": existing_id, "trace_id": trace_id})
            return CardPushStatus(index=index, note_id=existing_id, success=True)

        # create_or_update
        if existing_id is not None:
            self._client.update_note_fields(existing_id, card.fields)
            logger.info("Updated existing note", extra={"index": index, "note_id": existing_id, "trace_id": trace_id})
            return CardPushStatus(index=index, note_id=existing_id, success=True)
        note_params = _card_to_note_params(card)
        note_id = self._client.add_note(note_params)
        return CardPushStatus(index=index, note_id=note_id, success=True)

    def _find_existing_note(self, card: CardDraft) -> int | None:
        """Search for an existing note matching the card's front field in the same deck."""
        front = card.fields.get("Front") or card.fields.get("Text")
        if not front:
            return None
        escaped = front.replace('"', '\\"')
        field_name = "Front" if "Front" in card.fields else "Text"
        model_name = card.note_type.replace('"', '\\"')
        query = f'note:"{model_name}" deck:"{card.deck_name}" "{field_name}:{escaped}"'
        try:
            note_ids = self._client.find_notes(query)
            return note_ids[0] if note_ids else None
        except AnkiGatewayError:
            return None
