from __future__ import annotations

from unittest.mock import MagicMock

from ankismart.anki_gateway.gateway import AnkiGateway, _card_to_note_params
from ankismart.core.errors import AnkiGatewayError, ErrorCode
from ankismart.core.models import (
    CardDraft,
    CardOptions,
    DuplicateScopeOptions,
    MediaAttachments,
    MediaItem,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_client(add_note_return: int = 1001) -> MagicMock:
    client = MagicMock()
    client.add_note.return_value = add_note_return
    client.check_connection.return_value = True
    client.get_deck_names.return_value = ["Default"]
    client.get_model_names.return_value = ["Basic"]
    client.get_model_field_names.return_value = ["Front", "Back"]
    return client


def _card(**overrides) -> CardDraft:
    defaults = {
        "fields": {"Front": "Q", "Back": "A"},
        "note_type": "Basic",
        "deck_name": "Default",
    }
    defaults.update(overrides)
    return CardDraft(**defaults)


# ---------------------------------------------------------------------------
# _card_to_note_params
# ---------------------------------------------------------------------------

class TestCardToNoteParams:
    def test_basic_conversion(self) -> None:
        card = _card()
        params = _card_to_note_params(card)
        assert params["deckName"] == "Default"
        assert params["modelName"] == "Basic"
        assert params["fields"] == {"Front": "Q", "Back": "A"}
        assert params["tags"] == []
        assert params["options"]["allowDuplicate"] is False
        assert params["options"]["duplicateScope"] == "deck"

    def test_tags_included(self) -> None:
        card = _card(tags=["vocab", "ch1"])
        params = _card_to_note_params(card)
        assert params["tags"] == ["vocab", "ch1"]

    def test_media_audio_included(self) -> None:
        media = MediaAttachments(
            audio=[MediaItem(filename="a.mp3", url="http://x.com/a.mp3", fields=["Front"])]
        )
        card = _card(media=media)
        params = _card_to_note_params(card)
        assert "audio" in params
        assert len(params["audio"]) == 1
        assert params["audio"][0]["filename"] == "a.mp3"

    def test_media_empty_not_included(self) -> None:
        card = _card()
        params = _card_to_note_params(card)
        assert "audio" not in params
        assert "video" not in params
        assert "picture" not in params

    def test_custom_options(self) -> None:
        opts = CardOptions(
            allow_duplicate=True,
            duplicate_scope="collection",
            duplicate_scope_options=DuplicateScopeOptions(
                deck_name="Mining",
                check_children=True,
                check_all_models=True,
            ),
        )
        card = _card(options=opts)
        params = _card_to_note_params(card)
        assert params["options"]["allowDuplicate"] is True
        assert params["options"]["duplicateScope"] == "collection"
        scope_opts = params["options"]["duplicateScopeOptions"]
        assert scope_opts["deckName"] == "Mining"
        assert scope_opts["checkChildren"] is True
        assert scope_opts["checkAllModels"] is True


# ---------------------------------------------------------------------------
# AnkiGateway – delegation methods
# ---------------------------------------------------------------------------

class TestGatewayDelegation:
    def test_check_connection(self) -> None:
        client = _fake_client()
        gw = AnkiGateway(client)
        assert gw.check_connection() is True
        client.check_connection.assert_called_once()

    def test_get_deck_names(self) -> None:
        client = _fake_client()
        gw = AnkiGateway(client)
        assert gw.get_deck_names() == ["Default"]

    def test_get_model_names(self) -> None:
        client = _fake_client()
        gw = AnkiGateway(client)
        assert gw.get_model_names() == ["Basic"]

    def test_get_model_field_names(self) -> None:
        client = _fake_client()
        gw = AnkiGateway(client)
        assert gw.get_model_field_names("Basic") == ["Front", "Back"]


# ---------------------------------------------------------------------------
# AnkiGateway.push
# ---------------------------------------------------------------------------

class TestPush:
    def test_push_single_success(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client(add_note_return=999)
        gw = AnkiGateway(client)
        result = gw.push([_card()])

        assert result.total == 1
        assert result.succeeded == 1
        assert result.failed == 0
        assert result.results[0].note_id == 999
        assert result.results[0].success is True

    def test_push_multiple_all_succeed(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        gw = AnkiGateway(client)
        result = gw.push([_card(), _card(), _card()])

        assert result.total == 3
        assert result.succeeded == 3
        assert result.failed == 0

    def test_push_validation_failure_tracked(self, monkeypatch) -> None:
        def fail_validate(card, client):
            raise AnkiGatewayError("bad card", code=ErrorCode.E_DECK_NOT_FOUND)

        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", fail_validate
        )
        client = _fake_client()
        gw = AnkiGateway(client)
        result = gw.push([_card()])

        assert result.total == 1
        assert result.succeeded == 0
        assert result.failed == 1
        assert result.results[0].success is False
        assert "bad card" in result.results[0].error

    def test_push_mixed_success_and_failure(self, monkeypatch) -> None:
        call_count = {"n": 0}

        def sometimes_fail(card, client):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise AnkiGatewayError("fail on second", code=ErrorCode.E_ANKICONNECT_ERROR)

        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", sometimes_fail
        )
        client = _fake_client()
        gw = AnkiGateway(client)
        result = gw.push([_card(), _card(), _card()])

        assert result.total == 3
        assert result.succeeded == 2
        assert result.failed == 1
        assert result.results[1].success is False

    def test_push_add_note_failure_tracked(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        client.add_note.side_effect = AnkiGatewayError(
            "duplicate", code=ErrorCode.E_ANKICONNECT_ERROR
        )
        gw = AnkiGateway(client)
        result = gw.push([_card()])

        assert result.failed == 1
        assert result.succeeded == 0
        assert "duplicate" in result.results[0].error

    def test_push_trace_id_in_result(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        gw = AnkiGateway(client)
        result = gw.push([_card(trace_id="my-trace")])
        # trace_id should be set (either "my-trace" or generated)
        assert result.trace_id

    def test_push_index_tracking(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        gw = AnkiGateway(client)
        result = gw.push([_card(), _card()])

        assert result.results[0].index == 0
        assert result.results[1].index == 1
