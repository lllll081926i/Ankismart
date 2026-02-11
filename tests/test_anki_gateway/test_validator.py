from __future__ import annotations

import pytest

from ankismart.anki_gateway.validator import validate_card_draft
from ankismart.core.errors import AnkiGatewayError, ErrorCode
from ankismart.core.models import CardDraft, MediaAttachments, MediaItem

# ---------------------------------------------------------------------------
# Fake client that returns configurable data
# ---------------------------------------------------------------------------

class _FakeClient:
    def __init__(
        self,
        decks: list[str] | None = None,
        models: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> None:
        self._decks = decks or ["Default"]
        self._models = models or ["Basic", "Cloze"]
        self._fields = fields or ["Front", "Back"]

    def get_deck_names(self) -> list[str]:
        return self._decks

    def get_model_names(self) -> list[str]:
        return self._models

    def get_model_field_names(self, model_name: str) -> list[str]:
        return self._fields


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _basic_card(**overrides) -> CardDraft:
    defaults = {
        "fields": {"Front": "Q", "Back": "A"},
        "note_type": "Basic",
        "deck_name": "Default",
    }
    defaults.update(overrides)
    return CardDraft(**defaults)


# ---------------------------------------------------------------------------
# 1. Deck validation
# ---------------------------------------------------------------------------

class TestDeckValidation:
    def test_valid_deck_passes(self) -> None:
        validate_card_draft(_basic_card(), _FakeClient())

    def test_missing_deck_raises(self) -> None:
        card = _basic_card(deck_name="NonExistent")
        with pytest.raises(AnkiGatewayError, match="Deck not found") as exc_info:
            validate_card_draft(card, _FakeClient())
        assert exc_info.value.code == ErrorCode.E_DECK_NOT_FOUND


# ---------------------------------------------------------------------------
# 2. Model validation
# ---------------------------------------------------------------------------

class TestModelValidation:
    def test_valid_model_passes(self) -> None:
        validate_card_draft(_basic_card(), _FakeClient())

    def test_missing_model_raises(self) -> None:
        card = _basic_card(note_type="SuperCustom")
        with pytest.raises(AnkiGatewayError, match="Note type not found") as exc_info:
            validate_card_draft(card, _FakeClient())
        assert exc_info.value.code == ErrorCode.E_MODEL_NOT_FOUND


# ---------------------------------------------------------------------------
# 3. Required field validation
# ---------------------------------------------------------------------------

class TestFieldValidation:
    def test_first_field_present_passes(self) -> None:
        validate_card_draft(_basic_card(), _FakeClient())

    def test_first_field_empty_raises(self) -> None:
        card = _basic_card(fields={"Front": "", "Back": "A"})
        with pytest.raises(AnkiGatewayError, match="Required field missing") as exc_info:
            validate_card_draft(card, _FakeClient())
        assert exc_info.value.code == ErrorCode.E_REQUIRED_FIELD_MISSING

    def test_first_field_missing_key_raises(self) -> None:
        card = _basic_card(fields={"Back": "A"})
        with pytest.raises(AnkiGatewayError, match="Required field missing"):
            validate_card_draft(card, _FakeClient())

    def test_second_field_empty_is_ok(self) -> None:
        card = _basic_card(fields={"Front": "Q", "Back": ""})
        validate_card_draft(card, _FakeClient())  # should not raise


# ---------------------------------------------------------------------------
# 4. Cloze syntax validation
# ---------------------------------------------------------------------------

class TestClozeValidation:
    def test_valid_cloze(self) -> None:
        card = _basic_card(
            note_type="Cloze",
            fields={"Text": "{{c1::answer}}", "Extra": ""},
        )
        client = _FakeClient(fields=["Text", "Extra"])
        validate_card_draft(card, client)

    def test_invalid_cloze_syntax_raises(self) -> None:
        card = _basic_card(
            note_type="Cloze",
            fields={"Text": "no cloze here", "Extra": ""},
        )
        client = _FakeClient(fields=["Text", "Extra"])
        with pytest.raises(AnkiGatewayError, match="(?i)cloze") as exc_info:
            validate_card_draft(card, client)
        assert exc_info.value.code == ErrorCode.E_CLOZE_SYNTAX_INVALID

    def test_cloze_empty_text_raises(self) -> None:
        card = _basic_card(
            note_type="Cloze",
            fields={"Text": "", "Extra": ""},
        )
        client = _FakeClient(fields=["Text", "Extra"])
        # Empty first field triggers required-field error before cloze check
        with pytest.raises(AnkiGatewayError):
            validate_card_draft(card, client)

    def test_cloze_multiple_deletions(self) -> None:
        card = _basic_card(
            note_type="Cloze",
            fields={"Text": "{{c1::one}} and {{c2::two}}", "Extra": ""},
        )
        client = _FakeClient(fields=["Text", "Extra"])
        validate_card_draft(card, client)  # should not raise


# ---------------------------------------------------------------------------
# 5. Media validation
# ---------------------------------------------------------------------------

class TestMediaValidation:
    def test_media_with_url_passes(self) -> None:
        media = MediaAttachments(
            audio=[MediaItem(filename="a.mp3", url="http://example.com/a.mp3")]
        )
        card = _basic_card(media=media)
        validate_card_draft(card, _FakeClient())

    def test_media_with_path_passes(self) -> None:
        media = MediaAttachments(
            picture=[MediaItem(filename="img.png", path="/tmp/img.png")]
        )
        card = _basic_card(media=media)
        validate_card_draft(card, _FakeClient())

    def test_media_with_data_passes(self) -> None:
        media = MediaAttachments(
            video=[MediaItem(filename="v.mp4", data="base64data")]
        )
        card = _basic_card(media=media)
        validate_card_draft(card, _FakeClient())

    def test_media_no_source_raises(self) -> None:
        media = MediaAttachments(
            audio=[MediaItem(filename="a.mp3")]
        )
        card = _basic_card(media=media)
        with pytest.raises(AnkiGatewayError, match="no source") as exc_info:
            validate_card_draft(card, _FakeClient())
        assert exc_info.value.code == ErrorCode.E_MEDIA_INVALID

    def test_media_multiple_types_no_source_raises(self) -> None:
        media = MediaAttachments(
            audio=[MediaItem(filename="a.mp3", url="http://x.com/a.mp3")],
            picture=[MediaItem(filename="bad.png")],  # no source
        )
        card = _basic_card(media=media)
        with pytest.raises(AnkiGatewayError, match="bad.png"):
            validate_card_draft(card, _FakeClient())

    def test_no_media_passes(self) -> None:
        card = _basic_card()
        validate_card_draft(card, _FakeClient())  # should not raise


# ---------------------------------------------------------------------------
# 6. trace_id propagation
# ---------------------------------------------------------------------------

class TestTraceIdPropagation:
    def test_trace_id_from_draft(self) -> None:
        card = _basic_card(deck_name="NonExistent", trace_id="my-trace")
        with pytest.raises(AnkiGatewayError) as exc_info:
            validate_card_draft(card, _FakeClient())
        assert exc_info.value.trace_id == "my-trace"

    def test_trace_id_generated_when_empty(self) -> None:
        card = _basic_card(deck_name="NonExistent", trace_id="")
        with pytest.raises(AnkiGatewayError) as exc_info:
            validate_card_draft(card, _FakeClient())
        # Should have a non-empty trace_id (auto-generated UUID)
        assert exc_info.value.trace_id
