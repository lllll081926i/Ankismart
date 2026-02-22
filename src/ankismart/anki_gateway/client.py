from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlparse

import httpx

from ankismart.core.errors import AnkiGatewayError, ErrorCode
from ankismart.core.logging import get_logger
from ankismart.core.tracing import get_trace_id

logger = get_logger("anki_gateway.client")


def _is_loopback_endpoint(url: str) -> bool:
    """Return True when *url* points to localhost/loopback."""
    host = (urlparse(url).hostname or "").strip().lower()
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class AnkiConnectClient:
    def __init__(self, url: str = "http://127.0.0.1:8765", key: str = "", proxy_url: str = "") -> None:
        self._url = url
        self._key = key
        self._proxy_url = proxy_url

    def _request(self, action: str, params: dict[str, Any] | None = None) -> Any:
        """Send a request to AnkiConnect and return the result."""
        trace_id = get_trace_id()
        body: dict[str, Any] = {"action": action, "version": 6}
        if params:
            body["params"] = params
        if self._key:
            body["key"] = self._key

        try:
            client_kwargs: dict[str, object] = {"timeout": 30}
            if self._proxy_url and not _is_loopback_endpoint(self._url):
                client_kwargs["proxy"] = self._proxy_url
            resp = httpx.post(self._url, json=body, **client_kwargs)
            resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise AnkiGatewayError(
                "Cannot connect to AnkiConnect. Is Anki running with AnkiConnect installed?",
                code=ErrorCode.E_ANKICONNECT_ERROR,
                trace_id=trace_id,
            ) from exc
        except httpx.HTTPError as exc:
            raise AnkiGatewayError(
                f"AnkiConnect HTTP error: {exc}",
                code=ErrorCode.E_ANKICONNECT_ERROR,
                trace_id=trace_id,
            ) from exc

        try:
            data = resp.json()
        except ValueError as exc:
            preview = (resp.text or "").strip()
            if len(preview) > 200:
                preview = f"{preview[:200]}..."
            raise AnkiGatewayError(
                (
                    f"AnkiConnect returned non-JSON response (HTTP {resp.status_code})"
                    + (f": {preview}" if preview else "")
                ),
                code=ErrorCode.E_ANKICONNECT_ERROR,
                trace_id=trace_id,
            ) from exc

        if not isinstance(data, dict):
            raise AnkiGatewayError(
                f"AnkiConnect returned invalid response payload: {type(data).__name__}",
                code=ErrorCode.E_ANKICONNECT_ERROR,
                trace_id=trace_id,
            )
        error = data.get("error")
        if error:
            raise AnkiGatewayError(
                f"AnkiConnect error: {error}",
                code=ErrorCode.E_ANKICONNECT_ERROR,
                trace_id=trace_id,
            )
        return data.get("result")

    def check_connection(self) -> bool:
        try:
            self._request("version")
            return True
        except AnkiGatewayError:
            return False

    def get_deck_names(self) -> list[str]:
        return self._request("deckNames")

    def create_deck(self, deck_name: str) -> int | None:
        """Create deck if missing and return deck id when provided by AnkiConnect."""
        return self._request("createDeck", {"deck": deck_name})

    def get_model_names(self) -> list[str]:
        return self._request("modelNames")

    def get_model_field_names(self, model_name: str) -> list[str]:
        return self._request("modelFieldNames", {"modelName": model_name})

    def get_model_templates(self, model_name: str) -> dict[str, dict[str, str]]:
        """Get note type template definitions keyed by template name."""
        return self._request("modelTemplates", {"modelName": model_name})

    def update_model_templates(
        self,
        model_name: str,
        templates: dict[str, dict[str, str]],
    ) -> None:
        """Update front/back templates for a note type."""
        self._request(
            "updateModelTemplates",
            {
                "model": {
                    "name": model_name,
                    "templates": templates,
                }
            },
        )

    def update_model_styling(self, model_name: str, css: str) -> None:
        """Update CSS styling for a note type."""
        self._request(
            "updateModelStyling",
            {
                "model": {
                    "name": model_name,
                    "css": css,
                }
            },
        )

    def create_model(
        self,
        *,
        model_name: str,
        fields: list[str],
        templates: list[dict[str, str]],
        css: str,
        is_cloze: bool = False,
    ) -> Any:
        """Create a new Anki note type (model)."""
        return self._request(
            "createModel",
            {
                "modelName": model_name,
                "inOrderFields": fields,
                "cardTemplates": templates,
                "css": css,
                "isCloze": is_cloze,
            },
        )

    def add_note(self, note_params: dict[str, Any]) -> int:
        """Add a single note. Returns the note ID."""
        result = self._request("addNote", {"note": note_params})
        if result is None:
            raise AnkiGatewayError(
                "addNote returned null - possible duplicate",
                code=ErrorCode.E_ANKICONNECT_ERROR,
            )
        return result

    def add_notes(self, notes_params: list[dict[str, Any]]) -> list[int | None]:
        """Add multiple notes. Returns list of note IDs (None for failures)."""
        return self._request("addNotes", {"notes": notes_params})

    def find_notes(self, query: str) -> list[int]:
        """Find note IDs matching an Anki search query."""
        return self._request("findNotes", {"query": query})

    def update_note_fields(self, note_id: int, fields: dict[str, str]) -> None:
        """Update fields of an existing note."""
        self._request("updateNoteFields", {"note": {"id": note_id, "fields": fields}})

    def notes_info(self, note_ids: list[int]) -> list[dict[str, Any]]:
        """Get detailed info for a list of note IDs."""
        return self._request("notesInfo", {"notes": note_ids})
