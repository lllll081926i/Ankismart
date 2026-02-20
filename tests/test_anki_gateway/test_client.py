from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.core.errors import AnkiGatewayError, ErrorCode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    resp = httpx.Response(status_code, json=json_data, request=httpx.Request("POST", "http://test"))
    return resp


# ---------------------------------------------------------------------------
# _request – basic behaviour
# ---------------------------------------------------------------------------

class TestRequest:
    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_request_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": 42})
        client = AnkiConnectClient()
        result = client._request("someAction")
        assert result == 42
        call_body = mock_post.call_args[1]["json"]
        assert call_body["action"] == "someAction"
        assert call_body["version"] == 6
        assert "params" not in call_body
        assert "key" not in call_body

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_request_with_params(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": "ok"})
        client = AnkiConnectClient()
        client._request("act", {"foo": "bar"})
        call_body = mock_post.call_args[1]["json"]
        assert call_body["params"] == {"foo": "bar"}

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_request_with_key(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": "ok"})
        client = AnkiConnectClient(key="secret")
        client._request("act")
        call_body = mock_post.call_args[1]["json"]
        assert call_body["key"] == "secret"

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_request_skips_proxy_for_loopback(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": "ok"})
        client = AnkiConnectClient(url="http://127.0.0.1:8765", proxy_url="http://proxy:7890")
        client._request("version")
        assert "proxy" not in mock_post.call_args[1]

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_request_uses_proxy_for_remote_endpoint(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": "ok"})
        client = AnkiConnectClient(url="http://10.0.0.2:8765", proxy_url="http://proxy:7890")
        client._request("version")
        assert mock_post.call_args[1]["proxy"] == "http://proxy:7890"

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_request_ankiconnect_error(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": "deck not found", "result": None})
        client = AnkiConnectClient()
        with pytest.raises(AnkiGatewayError, match="deck not found") as exc_info:
            client._request("addNote")
        assert exc_info.value.code == ErrorCode.E_ANKICONNECT_ERROR

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_request_connect_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = httpx.ConnectError("refused")
        client = AnkiConnectClient()
        with pytest.raises(AnkiGatewayError, match="Cannot connect") as exc_info:
            client._request("version")
        assert exc_info.value.code == ErrorCode.E_ANKICONNECT_ERROR

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_request_http_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = httpx.HTTPStatusError(
            "500", request=httpx.Request("POST", "http://test"), response=httpx.Response(500)
        )
        client = AnkiConnectClient()
        with pytest.raises(AnkiGatewayError, match="HTTP error"):
            client._request("version")

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_request_result_none_is_returned(self, mock_post: MagicMock) -> None:
        """When AnkiConnect returns result=None with no error, _request returns None."""
        mock_post.return_value = _mock_response({"error": None, "result": None})
        client = AnkiConnectClient()
        assert client._request("someAction") is None


# ---------------------------------------------------------------------------
# check_connection
# ---------------------------------------------------------------------------

class TestCheckConnection:
    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_check_connection_ok(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": 6})
        assert AnkiConnectClient().check_connection() is True

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_check_connection_fail(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = httpx.ConnectError("refused")
        assert AnkiConnectClient().check_connection() is False


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------

class TestConvenienceMethods:
    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_get_deck_names(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": ["Default", "Mining"]})
        assert AnkiConnectClient().get_deck_names() == ["Default", "Mining"]

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_get_model_names(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": ["Basic", "Cloze"]})
        assert AnkiConnectClient().get_model_names() == ["Basic", "Cloze"]

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_get_model_field_names(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": ["Front", "Back"]})
        assert AnkiConnectClient().get_model_field_names("Basic") == ["Front", "Back"]

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_create_deck(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": 123})
        assert AnkiConnectClient().create_deck("Default") == 123

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_add_note_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": 12345})
        note_id = AnkiConnectClient().add_note({"deckName": "Default"})
        assert note_id == 12345

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_add_note_null_result(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": None})
        with pytest.raises(AnkiGatewayError, match="duplicate"):
            AnkiConnectClient().add_note({"deckName": "Default"})

    @patch("ankismart.anki_gateway.client.httpx.post")
    def test_add_notes(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_response({"error": None, "result": [1, None, 3]})
        result = AnkiConnectClient().add_notes([{}, {}, {}])
        assert result == [1, None, 3]
