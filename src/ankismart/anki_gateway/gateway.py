from __future__ import annotations

from typing import Any, Callable, Iterable, Literal

from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.styling import MODERN_CARD_CSS
from ankismart.anki_gateway.validator import validate_card_draft
from ankismart.card_gen.card_pipeline import normalize_card_draft
from ankismart.core.errors import AnkiGatewayError
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, CardPushStatus, PushResult
from ankismart.core.tracing import metrics, timed, trace_context

logger = get_logger("anki_gateway")

UpdateMode = Literal["create_only", "update_only", "create_or_update"]

ANKISMART_BASIC_MODEL = "AnkiSmart Basic"
ANKISMART_CLOZE_MODEL = "AnkiSmart Cloze"

_BASIC_LIKE_MODELS = {
    "Basic",
    "Basic (and reversed card)",
    "Basic (optional reversed card)",
    "Basic (type in the answer)",
}
_STYLEABLE_MODELS = {ANKISMART_BASIC_MODEL, ANKISMART_CLOZE_MODEL}

_ANKI_BASIC_QFMT = (
    '<div class="as-card as-card-front">'
    '<section class="as-block as-question-block">'
    '<div class="as-block-title">问题</div>'
    '<div class="as-block-content as-preformatted">{{Front}}</div>'
    "</section>"
    "</div>"
)

_ANKI_BASIC_AFMT = (
    "{{FrontSide}}"
    '<hr id="answer">'
    '<div class="as-card as-card-back">'
    '<section class="as-block as-answer-block">'
    '<div class="as-block-title">答案</div>'
    '<div class="as-block-content as-answer-box as-preformatted">{{Back}}</div>'
    "</section>"
    "</div>"
)

_ANKI_CLOZE_QFMT = (
    '<div class="as-card as-card-front">'
    '<section class="as-block as-question-block">'
    '<div class="as-block-title">问题</div>'
    '<div class="as-block-content as-preformatted">{{cloze:Text}}</div>'
    "</section>"
    "</div>"
)

_ANKI_CLOZE_AFMT = (
    "{{FrontSide}}"
    '<hr id="answer">'
    '<div class="as-card as-card-back">'
    '<section class="as-block as-answer-block">'
    '<div class="as-block-title">答案</div>'
    '<div class="as-block-content as-answer-box as-preformatted">{{cloze:Text}}</div>'
    "</section>"
    "{{#Extra}}"
    '<section class="as-block as-extra-block">'
    '<div class="as-block-title">解析</div>'
    '<div class="as-block-content as-extra as-preformatted">{{Extra}}</div>'
    "</section>"
    "{{/Extra}}"
    "</div>"
)


def _resolve_target_note_type(note_type: str) -> str:
    name = (note_type or "").strip()
    if name in _BASIC_LIKE_MODELS or name == ANKISMART_BASIC_MODEL:
        return ANKISMART_BASIC_MODEL
    if name in {"Cloze", ANKISMART_CLOZE_MODEL}:
        return ANKISMART_CLOZE_MODEL
    return name


def _resolve_card_note_type(card: CardDraft) -> CardDraft:
    target = _resolve_target_note_type(card.note_type)
    if target == card.note_type:
        return card
    return card.model_copy(update={"note_type": target})


def _build_anki_templates_payload(
    note_type: str,
    template_names: Iterable[str],
) -> dict[str, dict[str, str]]:
    names = [name for name in template_names if name]
    if note_type in _BASIC_LIKE_MODELS or note_type == ANKISMART_BASIC_MODEL:
        if not names:
            names = ["Card 1"]
        return {name: {"Front": _ANKI_BASIC_QFMT, "Back": _ANKI_BASIC_AFMT} for name in names}
    if note_type in {"Cloze", ANKISMART_CLOZE_MODEL}:
        if not names:
            names = ["Cloze"]
        return {name: {"Front": _ANKI_CLOZE_QFMT, "Back": _ANKI_CLOZE_AFMT} for name in names}
    return {}


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


def _escape_anki_query_value(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


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
        resolved_card = _resolve_card_note_type(card)
        available_models = self._ensure_ankismart_models([resolved_card])
        if (
            resolved_card.note_type in _STYLEABLE_MODELS
            and resolved_card.note_type not in available_models
        ):
            resolved_card = card
        resolved_card = normalize_card_draft(resolved_card)
        deck_cache = self._fetch_deck_cache()
        self._ensure_deck_exists(resolved_card.deck_name, deck_cache)
        self._sync_model_styling([resolved_card])
        validate_card_draft(resolved_card, self._client)
        existing_id = self._find_existing_note(resolved_card)
        if existing_id is not None:
            self._client.update_note_fields(existing_id, resolved_card.fields)
            logger.info("Updated existing note", extra={"note_id": existing_id})
            return CardPushStatus(index=0, note_id=existing_id, success=True)
        note_params = _card_to_note_params(resolved_card)
        note_id = self._client.add_note(note_params)
        return CardPushStatus(index=0, note_id=note_id, success=True)

    # ------------------------------------------------------------------
    # Batch push with update_mode
    # ------------------------------------------------------------------

    def push(
        self,
        cards: list[CardDraft],
        update_mode: UpdateMode = "create_only",
        progress_callback: Callable[[int, int, CardPushStatus], None] | None = None,
    ) -> PushResult:
        metrics.increment("anki_push_batches_total")
        metrics.increment("anki_push_cards_total", value=len(cards))
        initial_trace_id = cards[0].trace_id if cards else None
        with trace_context(initial_trace_id) as trace_id:
            with timed("anki_push_total"):
                results: list[CardPushStatus] = []
                succeeded = 0
                failed = 0
                prepared_cards = [_resolve_card_note_type(card) for card in cards]
                available_models = self._ensure_ankismart_models(prepared_cards)
                prepared_cards = self._fallback_cards_without_models(
                    original_cards=cards,
                    prepared_cards=prepared_cards,
                    available_models=available_models,
                )
                prepared_cards = [normalize_card_draft(card) for card in prepared_cards]
                deck_cache = self._fetch_deck_cache()
                self._sync_model_styling(prepared_cards)

                # Validate all cards and track which ones pass
                # Dict: index -> error message (None if valid)
                validation_results: dict[int, str | None] = {}
                for i, card in enumerate(prepared_cards):
                    try:
                        self._ensure_deck_exists(card.deck_name, deck_cache)
                        validate_card_draft(card, self._client)
                        validation_results[i] = None  # Valid
                    except AnkiGatewayError as exc:
                        logger.warning(
                            f"Card {i} validation failed: {exc.message}",
                            extra={"index": i, "error": exc.message, "trace_id": trace_id},
                        )
                        validation_results[i] = exc.message  # Invalid

                # Use batch push for create_only mode (significant performance improvement)
                if update_mode == "create_only":
                    results = self._push_batch_create_only(
                        prepared_cards, validation_results, trace_id, progress_callback
                    )
                    succeeded = sum(1 for r in results if r.success)
                    failed = len(results) - succeeded
                else:
                    # For update modes, still need to check existing notes individually
                    for i, card in enumerate(prepared_cards):
                        # Check validation result first
                        validation_error = validation_results.get(i)
                        if validation_error is not None:
                            # Card failed validation, skip it
                            status = CardPushStatus(index=i, success=False, error=validation_error)
                            results.append(status)
                            failed += 1
                            metrics.increment("anki_push_failed_total")
                            if progress_callback is not None:
                                progress_callback(i + 1, len(prepared_cards), status)
                            continue

                        try:
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
                            status = CardPushStatus(index=i, success=False, error=exc.message)
                            results.append(status)
                            failed += 1
                            metrics.increment("anki_push_failed_total")

                        if progress_callback is not None:
                            progress_callback(i + 1, len(prepared_cards), status)

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

    def _push_batch_create_only(
        self,
        cards: list[CardDraft],
        validation_results: dict[int, str | None],
        trace_id: str,
        progress_callback: Callable[[int, int, CardPushStatus], None] | None = None,
    ) -> list[CardPushStatus]:
        """Batch push for create_only mode using AnkiConnect's addNotes API.

        This is significantly faster than pushing one-by-one since it makes fewer
        HTTP requests. Cards are pushed in batches of max 50 to avoid overwhelming
        AnkiConnect and ensure good responsiveness.

        Args:
            cards: List of cards to push
            validation_results: Dict mapping card index to error message (None if valid)
            trace_id: Trace ID for logging
            progress_callback: Optional progress callback

        Returns:
            List of push status results
        """
        results: list[CardPushStatus] = []

        if not cards:
            return results

        # Batch size limit to prevent overwhelming AnkiConnect
        batch_size = 50
        total_cards = len(cards)
        processed_count = 0

        # Process cards in batches
        for batch_start in range(0, total_cards, batch_size):
            batch_end = min(batch_start + batch_size, total_cards)
            batch_cards = cards[batch_start:batch_end]

            # Build note params for current batch (skip invalid cards)
            notes_params = []
            valid_indices = []
            for i, card in enumerate(batch_cards):
                global_index = batch_start + i

                # Check if card passed validation
                validation_error = validation_results.get(global_index)
                if validation_error is not None:
                    # Card failed validation, mark as failed immediately
                    status = CardPushStatus(
                        index=global_index,
                        success=False,
                        error=validation_error,
                    )
                    results.append(status)
                    metrics.increment("anki_push_failed_total")
                    processed_count += 1
                    if progress_callback is not None:
                        progress_callback(processed_count, total_cards, status)
                    continue

                try:
                    note_params = _card_to_note_params(card)
                    notes_params.append(note_params)
                    valid_indices.append(global_index)
                except Exception as exc:
                    logger.error(
                        f"Failed to build note params for card {global_index}: {exc}",
                        extra={"index": global_index, "trace_id": trace_id},
                    )
                    # Immediately mark as failed
                    status = CardPushStatus(
                        index=global_index,
                        success=False,
                        error=f"Failed to build note params: {exc}",
                    )
                    results.append(status)
                    metrics.increment("anki_push_failed_total")
                    processed_count += 1
                    if progress_callback is not None:
                        progress_callback(processed_count, total_cards, status)

            if not notes_params:
                continue

            # Call batch API for this batch
            try:
                note_ids = self._client.add_notes(notes_params)

                # Process results
                for i, note_id in enumerate(note_ids):
                    global_index = valid_indices[i]
                    if note_id is not None:
                        status = CardPushStatus(index=global_index, note_id=note_id, success=True)
                        metrics.increment("anki_push_succeeded_total")
                    else:
                        # None means duplicate or error
                        error_msg = "Duplicate or failed to add note (AnkiConnect returned null)"
                        status = CardPushStatus(index=global_index, success=False, error=error_msg)
                        metrics.increment("anki_push_failed_total")
                        logger.warning(
                            "Card push failed in batch",
                            extra={"index": global_index, "error": error_msg, "trace_id": trace_id},
                        )

                    results.append(status)
                    processed_count += 1

                    # Report progress with monotonically increasing processed count
                    if progress_callback is not None:
                        progress_callback(processed_count, total_cards, status)

            except AnkiGatewayError as exc:
                logger.error(
                    f"Batch push failed for batch {batch_start}-{batch_end}",
                    extra={"error": exc.message, "trace_id": trace_id},
                )
                # Mark all cards in this batch as failed
                for i in valid_indices:
                    status = CardPushStatus(index=i, success=False, error=exc.message)
                    results.append(status)
                    metrics.increment("anki_push_failed_total")
                    processed_count += 1
                    if progress_callback is not None:
                        progress_callback(processed_count, total_cards, status)

        # Sort results by index to maintain order
        results.sort(key=lambda x: x.index)

        logger.info(
            "Batch push completed",
            extra={
                "trace_id": trace_id,
                "total": total_cards,
                "succeeded": sum(1 for r in results if r.success),
                "failed": sum(1 for r in results if not r.success),
            },
        )

        return results

    def _push_single(
        self,
        index: int,
        card: CardDraft,
        update_mode: UpdateMode,
        trace_id: str,
    ) -> CardPushStatus:
        """Process a single card according to *update_mode*."""
        existing_id = self._find_existing_note(card) if update_mode != "create_only" else None

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
            logger.info(
                "Updated existing note",
                extra={"index": index, "note_id": existing_id, "trace_id": trace_id},
            )
            return CardPushStatus(index=index, note_id=existing_id, success=True)

        # create_or_update
        if existing_id is not None:
            self._client.update_note_fields(existing_id, card.fields)
            logger.info(
                "Updated existing note",
                extra={"index": index, "note_id": existing_id, "trace_id": trace_id},
            )
            return CardPushStatus(index=index, note_id=existing_id, success=True)
        note_params = _card_to_note_params(card)
        note_id = self._client.add_note(note_params)
        return CardPushStatus(index=index, note_id=note_id, success=True)

    def _find_existing_note(self, card: CardDraft) -> int | None:
        """Search for an existing note matching the card's front field in the same deck."""
        front = card.fields.get("Front") or card.fields.get("Text")
        if not front:
            return None
        field_name = "Front" if "Front" in card.fields else "Text"
        model_name = _escape_anki_query_value(card.note_type)
        deck_name = _escape_anki_query_value(card.deck_name)
        field_query = _escape_anki_query_value(f"{field_name}:{front}")
        query = f'note:"{model_name}" deck:"{deck_name}" "{field_query}"'
        note_ids = self._client.find_notes(query)
        return note_ids[0] if note_ids else None

    def _fetch_deck_cache(self) -> set[str]:
        """Fetch existing deck names, falling back to an empty cache on gateway errors."""
        try:
            return set(self._client.get_deck_names())
        except AnkiGatewayError as exc:
            logger.warning("Failed to query deck names before push", extra={"error": exc.message})
            return set()

    def _ensure_deck_exists(self, deck_name: str, cache: set[str]) -> None:
        """Ensure a target deck exists before card validation/push."""
        name = (deck_name or "").strip()
        if not name or name in cache:
            return

        self._client.create_deck(name)
        cache.add(name)
        logger.info("Deck created automatically", extra={"deck_name": name})

    @staticmethod
    def _fallback_cards_without_models(
        *,
        original_cards: list[CardDraft],
        prepared_cards: list[CardDraft],
        available_models: set[str],
    ) -> list[CardDraft]:
        if len(original_cards) != len(prepared_cards):
            raise ValueError("prepared card count mismatch")
        if not prepared_cards:
            return []
        if not available_models:
            return [
                original if prepared.note_type in _STYLEABLE_MODELS else prepared
                for original, prepared in zip(original_cards, prepared_cards, strict=True)
            ]
        return [
            original
            if prepared.note_type in _STYLEABLE_MODELS
            and prepared.note_type not in available_models
            else prepared
            for original, prepared in zip(original_cards, prepared_cards, strict=True)
        ]

    def _ensure_ankismart_models(self, cards: list[CardDraft]) -> set[str]:
        """Ensure Ankismart-specific note types exist before validation/push."""
        if not cards:
            return set()

        model_names = {
            (card.note_type or "").strip()
            for card in cards
            if (card.note_type or "").strip() in _STYLEABLE_MODELS
        }
        if not model_names:
            return set()

        get_model_names = getattr(self._client, "get_model_names", None)
        create_model = getattr(self._client, "create_model", None)
        if not callable(get_model_names) or not callable(create_model):
            logger.warning(
                "Client does not support model auto-creation, skip Ankismart model ensure",
                extra={
                    "missing_get_model_names": not callable(get_model_names),
                    "missing_create_model": not callable(create_model),
                },
            )
            return set()

        try:
            existing_models = set(get_model_names())
        except AnkiGatewayError as exc:
            logger.warning(
                "Failed to query model list before Ankismart model ensure",
                extra={"error": exc.message},
            )
            return set()

        available_models = set(existing_models) & model_names
        for model_name in model_names:
            if model_name in available_models:
                continue
            if model_name == ANKISMART_BASIC_MODEL:
                fields = ["Front", "Back"]
                templates = [
                    {"Name": "Card 1", "Front": _ANKI_BASIC_QFMT, "Back": _ANKI_BASIC_AFMT}
                ]
                is_cloze = False
            elif model_name == ANKISMART_CLOZE_MODEL:
                fields = ["Text", "Extra"]
                templates = [{"Name": "Cloze", "Front": _ANKI_CLOZE_QFMT, "Back": _ANKI_CLOZE_AFMT}]
                is_cloze = True
            else:
                continue

            try:
                create_model(
                    model_name=model_name,
                    fields=fields,
                    templates=templates,
                    css=MODERN_CARD_CSS,
                    is_cloze=is_cloze,
                )
                available_models.add(model_name)
                logger.info("Created Ankismart note type", extra={"model_name": model_name})
            except AnkiGatewayError as exc:
                logger.warning(
                    "Failed to create Ankismart note type, fallback to existing model",
                    extra={"model_name": model_name, "error": exc.message},
                )
        return available_models

    def _sync_model_styling(self, cards: list[CardDraft]) -> None:
        """Best-effort sync of Anki note templates/CSS to Ankismart style."""
        if not cards:
            return
        get_templates = getattr(self._client, "get_model_templates", None)
        update_templates = getattr(self._client, "update_model_templates", None)
        update_styling = getattr(self._client, "update_model_styling", None)
        if (
            not callable(get_templates)
            or not callable(update_templates)
            or not callable(update_styling)
        ):
            return
        model_names = {
            (card.note_type or "").strip()
            for card in cards
            if (card.note_type or "").strip() in _STYLEABLE_MODELS
        }
        for model_name in model_names:
            try:
                raw_templates = get_templates(model_name)
                template_names = (
                    list(raw_templates.keys()) if isinstance(raw_templates, dict) else []
                )
                payload = _build_anki_templates_payload(model_name, template_names)
                if not payload:
                    continue
                update_templates(model_name, payload)
                update_styling(model_name, MODERN_CARD_CSS)
                logger.info(
                    "Synchronized Anki model style",
                    extra={
                        "model_name": model_name,
                        "template_count": len(payload),
                    },
                )
            except AnkiGatewayError as exc:
                logger.warning(
                    "Failed to sync model style, continue pushing",
                    extra={"model_name": model_name, "error": exc.message},
                )
