from __future__ import annotations

import time
from pathlib import Path

import pytest
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from ankismart.core.errors import AnkiGatewayError, ErrorCode
from tests.e2e.page_objects.card_preview_page import CardPreviewPageObject
from tests.e2e.page_objects.import_page import ImportPageObject
from tests.e2e.page_objects.preview_page import PreviewPageObject
from tests.e2e.page_objects.result_page import ResultPageObject


def _wait_until(predicate, timeout: float = 20.0) -> None:
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication is not initialized")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return
        QTest.qWait(10)
    raise AssertionError("timeout waiting for condition")


@pytest.fixture
def patch_gate_dependencies(monkeypatch):
    records = {"notes_added": []}

    monkeypatch.setattr(
        "ankismart.card_gen.llm_client.LLMClient.chat",
        lambda self, system_prompt, user_prompt: '[{"Front":"Gate Q","Back":"Gate A"}]',
    )

    monkeypatch.setattr(
        "ankismart.anki_gateway.client.AnkiConnectClient.get_deck_names",
        lambda self: ["Default", "E2EDeck"],
    )
    monkeypatch.setattr(
        "ankismart.anki_gateway.client.AnkiConnectClient.get_model_names",
        lambda self: ["Basic", "Cloze"],
    )
    monkeypatch.setattr(
        "ankismart.anki_gateway.client.AnkiConnectClient.get_model_field_names",
        lambda self, model_name: ["Text", "Extra"] if model_name == "Cloze" else ["Front", "Back"],
    )
    monkeypatch.setattr(
        "ankismart.anki_gateway.client.AnkiConnectClient.find_notes",
        lambda self, query: [],
    )

    def _add_note(self, note_params):
        records["notes_added"].append(note_params)
        return 100000 + len(records["notes_added"])

    monkeypatch.setattr("ankismart.anki_gateway.client.AnkiConnectClient.add_note", _add_note)
    return records


@pytest.mark.p0
@pytest.mark.gate
@pytest.mark.gate_real
def test_gate_real_main_workflow_success(window, e2e_files, patch_gate_dependencies):
    import_page = ImportPageObject(window)
    preview_page = PreviewPageObject(window)
    card_preview_page = CardPreviewPageObject(window)
    result_page = ResultPageObject(window)

    import_page.prepare_files([e2e_files["docx"], e2e_files["md"]])
    import_page.configure(deck_name="Default", tags="ankismart,gate", target_total=20)
    import_page.start_convert()

    _wait_until(lambda: window.batch_result is not None and len(window.batch_result.documents) == 2)
    formats = {doc.result.source_format for doc in window.batch_result.documents}
    assert formats == {"docx", "markdown"}

    preview_page.generate_cards()
    _wait_until(lambda: len(window.cards) > 0)
    assert card_preview_page.card_count() == len(window.cards)

    card_preview_page.push_to_anki()
    _wait_until(lambda: result_page.push_result is not None)

    assert result_page.push_result.succeeded == len(window.cards)
    assert result_page.push_result.failed == 0
    assert len(patch_gate_dependencies["notes_added"]) == len(window.cards)


@pytest.mark.p0
@pytest.mark.gate
@pytest.mark.gate_real
def test_gate_real_push_failure_then_export_apkg(window, e2e_files, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "ankismart.card_gen.llm_client.LLMClient.chat",
        lambda self, system_prompt, user_prompt: '[{"Front":"Fallback Q","Back":"Fallback A"}]',
    )
    monkeypatch.setattr(
        "ankismart.anki_gateway.client.AnkiConnectClient.get_deck_names",
        lambda self: ["Default"],
    )
    monkeypatch.setattr(
        "ankismart.anki_gateway.client.AnkiConnectClient.get_model_names",
        lambda self: ["Basic"],
    )
    monkeypatch.setattr(
        "ankismart.anki_gateway.client.AnkiConnectClient.get_model_field_names",
        lambda self, model_name: ["Front", "Back"],
    )

    def _fail_add_note(self, note_params):
        raise AnkiGatewayError(
            "AnkiConnect unavailable",
            code=ErrorCode.E_ANKICONNECT_ERROR,
            trace_id="gate-e2e",
        )

    monkeypatch.setattr("ankismart.anki_gateway.client.AnkiConnectClient.add_note", _fail_add_note)

    import_page = ImportPageObject(window)
    preview_page = PreviewPageObject(window)
    card_preview_page = CardPreviewPageObject(window)
    result_page = ResultPageObject(window)

    import_page.prepare_files([e2e_files["md"]])
    import_page.configure(deck_name="Default", tags="ankismart,gate,fallback", target_total=10)
    import_page.start_convert()

    _wait_until(lambda: window.batch_result is not None and len(window.batch_result.documents) == 1)

    preview_page.generate_cards()
    _wait_until(lambda: len(window.cards) > 0)

    card_preview_page.push_to_anki()
    _wait_until(lambda: result_page.push_result is not None)
    assert result_page.push_result is not None
    assert result_page.push_result.failed == len(window.cards)

    export_path = tmp_path / "gate-fallback.apkg"
    monkeypatch.setattr(
        "ankismart.ui.result_page.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "Anki Package (*.apkg)"),
    )
    result_page.export_apkg()
    assert export_path.exists()
    assert export_path.stat().st_size > 0
