from __future__ import annotations

import random
from pathlib import Path

import genanki

from ankismart.core.errors import AnkiGatewayError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft
from ankismart.core.tracing import get_trace_id, timed

logger = get_logger("anki_gateway.apkg_exporter")

# Pre-defined genanki models for standard note types
_BASIC_MODEL = genanki.Model(
    1607392319,  # Fixed ID for consistency
    "Basic",
    fields=[{"name": "Front"}, {"name": "Back"}],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "{{Front}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
        },
    ],
)

_CLOZE_MODEL = genanki.Model(
    1607392320,
    "Cloze",
    fields=[{"name": "Text"}, {"name": "Extra"}],
    templates=[
        {
            "name": "Cloze",
            "qfmt": "{{cloze:Text}}",
            "afmt": "{{cloze:Text}}<br>{{Extra}}",
        },
    ],
    model_type=genanki.Model.CLOZE,
)

_MODEL_MAP: dict[str, genanki.Model] = {
    "Basic": _BASIC_MODEL,
    "Basic (and reversed card)": _BASIC_MODEL,
    "Basic (optional reversed card)": _BASIC_MODEL,
    "Basic (type in the answer)": _BASIC_MODEL,
    "Cloze": _CLOZE_MODEL,
}


def _get_model(note_type: str) -> genanki.Model:
    model = _MODEL_MAP.get(note_type)
    if model is None:
        raise AnkiGatewayError(
            f"No APKG model template for note type: {note_type}",
            code=ErrorCode.E_MODEL_NOT_FOUND,
        )
    return model


class ApkgExporter:
    def export(self, cards: list[CardDraft], output_path: Path) -> Path:
        trace_id = get_trace_id()
        if not cards:
            raise AnkiGatewayError(
                "No cards to export",
                code=ErrorCode.E_ANKICONNECT_ERROR,
                trace_id=trace_id,
            )

        with timed("apkg_export"):
            # Group cards by deck
            decks_map: dict[str, genanki.Deck] = {}
            media_files: set[str] = set()
            for card in cards:
                if card.deck_name not in decks_map:
                    deck_id = random.randrange(1 << 30, 1 << 31)
                    decks_map[card.deck_name] = genanki.Deck(deck_id, card.deck_name)

                deck = decks_map[card.deck_name]
                model = _get_model(card.note_type)

                # Build field values in model field order
                field_values = [card.fields.get(f["name"], "") for f in model.fields]

                note = genanki.Note(
                    model=model,
                    fields=field_values,
                    tags=card.tags,
                )
                deck.add_note(note)

                for media_items in (
                    card.media.picture,
                    card.media.audio,
                    card.media.video,
                ):
                    for media in media_items:
                        if media.path:
                            media_path = Path(media.path)
                            if media_path.exists():
                                media_files.add(str(media_path))

            # Write to .apkg
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            package = genanki.Package(list(decks_map.values()))
            package.media_files = sorted(media_files)
            package.write_to_file(str(output_path))

            logger.info(
                "APKG exported",
                extra={
                    "trace_id": trace_id,
                    "card_count": len(cards),
                    "deck_count": len(decks_map),
                    "path": str(output_path),
                },
            )
            return output_path
