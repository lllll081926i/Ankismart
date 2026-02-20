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
    client.create_deck.return_value = 1
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

    def test_push_auto_creates_missing_deck(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        client.get_deck_names.return_value = ["ExistingDeck"]
        gw = AnkiGateway(client)

        result = gw.push([_card(deck_name="NewDeck")])

        assert result.succeeded == 1
        client.create_deck.assert_called_once_with("NewDeck")

    def test_push_auto_creates_missing_deck_only_once(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        client.get_deck_names.return_value = ["ExistingDeck"]
        gw = AnkiGateway(client)

        cards = [_card(deck_name="BatchDeck"), _card(deck_name="BatchDeck")]
        result = gw.push(cards)

        assert result.succeeded == 2
        client.create_deck.assert_called_once_with("BatchDeck")


class TestPushOrUpdate:
    def test_find_existing_note_query_scopes_model_and_deck(self) -> None:
        client = _fake_client()
        client.find_notes.return_value = [123]
        gw = AnkiGateway(client)

        card = _card(note_type="Basic", deck_name="Default", fields={"Front": "Question"})
        found = gw._find_existing_note(card)

        assert found == 123
        query = client.find_notes.call_args[0][0]
        assert 'note:"Basic"' in query
        assert 'deck:"Default"' in query
        assert '"Front:Question"' in query

    def test_push_or_update_updates_when_existing(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )

        client = _fake_client()
        client.find_notes.return_value = [777]
        gw = AnkiGateway(client)

        result = gw.push_or_update([_card(fields={"Front": "Q", "Back": "A"})])

        client.update_note_fields.assert_called_once_with(777, {"Front": "Q", "Back": "A"})
        client.add_note.assert_not_called()
        assert result.succeeded == 1
        assert result.results[0].note_id == 777

    def test_push_or_update_adds_when_not_found(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )

        client = _fake_client(add_note_return=888)
        client.find_notes.return_value = []
        gw = AnkiGateway(client)

        result = gw.push_or_update([_card()])

        client.update_note_fields.assert_not_called()
        client.add_note.assert_called_once()
        assert result.succeeded == 1
        assert result.results[0].note_id == 888


# ---------------------------------------------------------------------------
# AnkiGateway.find_notes / update_note / create_or_update_note
# ---------------------------------------------------------------------------

class TestFindNotes:
    def test_find_notes_delegates(self) -> None:
        client = _fake_client()
        client.find_notes.return_value = [10, 20]
        gw = AnkiGateway(client)
        assert gw.find_notes("deck:Default") == [10, 20]
        client.find_notes.assert_called_once_with("deck:Default")

    def test_find_notes_empty(self) -> None:
        client = _fake_client()
        client.find_notes.return_value = []
        gw = AnkiGateway(client)
        assert gw.find_notes("deck:Nothing") == []


class TestUpdateNote:
    def test_update_note_delegates(self) -> None:
        client = _fake_client()
        gw = AnkiGateway(client)
        gw.update_note(42, {"Front": "new Q", "Back": "new A"})
        client.update_note_fields.assert_called_once_with(42, {"Front": "new Q", "Back": "new A"})

    def test_update_note_propagates_error(self) -> None:
        client = _fake_client()
        client.update_note_fields.side_effect = AnkiGatewayError("not found")
        gw = AnkiGateway(client)
        import pytest
        with pytest.raises(AnkiGatewayError, match="not found"):
            gw.update_note(999, {"Front": "x"})


class TestCreateOrUpdateNote:
    def test_creates_when_no_existing(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client(add_note_return=500)
        client.find_notes.return_value = []
        gw = AnkiGateway(client)

        status = gw.create_or_update_note(_card())
        assert status.success is True
        assert status.note_id == 500
        client.add_note.assert_called_once()
        client.update_note_fields.assert_not_called()

    def test_updates_when_existing(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        client.find_notes.return_value = [42]
        gw = AnkiGateway(client)

        status = gw.create_or_update_note(_card(fields={"Front": "Q", "Back": "A2"}))
        assert status.success is True
        assert status.note_id == 42
        client.update_note_fields.assert_called_once_with(42, {"Front": "Q", "Back": "A2"})
        client.add_note.assert_not_called()

    def test_validation_error_propagates(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft",
            lambda card, client: (_ for _ in ()).throw(
                AnkiGatewayError("bad", code=ErrorCode.E_DECK_NOT_FOUND)
            ),
        )
        client = _fake_client()
        gw = AnkiGateway(client)
        import pytest
        with pytest.raises(AnkiGatewayError, match="bad"):
            gw.create_or_update_note(_card())


# ---------------------------------------------------------------------------
# AnkiGateway.push with update_mode parameter
# ---------------------------------------------------------------------------

class TestPushUpdateMode:
    def test_create_only_does_not_search(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client(add_note_return=100)
        gw = AnkiGateway(client)

        result = gw.push([_card()], update_mode="create_only")
        assert result.succeeded == 1
        client.find_notes.assert_not_called()
        client.add_note.assert_called_once()

    def test_update_only_updates_existing(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        client.find_notes.return_value = [55]
        gw = AnkiGateway(client)

        result = gw.push([_card(fields={"Front": "Q", "Back": "A"})], update_mode="update_only")
        assert result.succeeded == 1
        assert result.results[0].note_id == 55
        client.update_note_fields.assert_called_once_with(55, {"Front": "Q", "Back": "A"})
        client.add_note.assert_not_called()

    def test_update_only_fails_when_not_found(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        client.find_notes.return_value = []
        gw = AnkiGateway(client)

        result = gw.push([_card()], update_mode="update_only")
        assert result.succeeded == 0
        assert result.failed == 1
        assert "No existing note" in result.results[0].error
        client.add_note.assert_not_called()

    def test_create_or_update_creates_when_new(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client(add_note_return=200)
        client.find_notes.return_value = []
        gw = AnkiGateway(client)

        result = gw.push([_card()], update_mode="create_or_update")
        assert result.succeeded == 1
        assert result.results[0].note_id == 200
        client.add_note.assert_called_once()

    def test_create_or_update_updates_when_existing(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client()
        client.find_notes.return_value = [300]
        gw = AnkiGateway(client)

        result = gw.push([_card(fields={"Front": "Q", "Back": "A"})], update_mode="create_or_update")
        assert result.succeeded == 1
        assert result.results[0].note_id == 300
        client.update_note_fields.assert_called_once_with(300, {"Front": "Q", "Back": "A"})
        client.add_note.assert_not_called()

    def test_default_update_mode_is_create_only(self, monkeypatch) -> None:
        """push() without update_mode should behave as create_only."""
        monkeypatch.setattr(
            "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
        )
        client = _fake_client(add_note_return=400)
        gw = AnkiGateway(client)

        result = gw.push([_card()])
        assert result.succeeded == 1
        client.find_notes.assert_not_called()
        client.add_note.assert_called_once()
