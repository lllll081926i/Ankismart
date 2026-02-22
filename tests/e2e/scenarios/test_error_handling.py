from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from openai import APITimeoutError, RateLimitError
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

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


@pytest.mark.p0
@pytest.mark.fast
@pytest.mark.gate
def test_e2e_anki_unavailable_fallback_to_apkg(
    window,
    e2e_files,
    tmp_path: Path,
    monkeypatch,
    patch_batch_convert_worker,
    patch_batch_generate_worker,
    patch_push_worker,
):
    patch_batch_convert_worker()
    patch_batch_generate_worker(cards_per_document=2)
    patch_push_worker(fail=True, error_message="AnkiConnect unavailable")

    import_page = ImportPageObject(window)
    preview_page = PreviewPageObject(window)
    card_preview_page = CardPreviewPageObject(window)
    result_page = ResultPageObject(window)

    import_page.prepare_files([e2e_files["docx"]])
    import_page.configure(deck_name="Default", tags="ankismart,e2e,fallback", target_total=20)
    import_page.start_convert()
    preview_page.generate_cards()
    card_preview_page.push_to_anki()

    assert result_page.push_result is not None
    assert result_page.push_result.failed == len(window.cards)
    assert result_page.push_result.succeeded == 0

    export_path = tmp_path / "fallback.apkg"
    exported: dict[str, object] = {}

    def _fake_export(self, cards, output_path):
        output = Path(output_path)
        output.write_bytes(b"fake-apkg")
        exported["count"] = len(cards)
        exported["path"] = output
        return output

    monkeypatch.setattr(
        "ankismart.ui.result_page.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "Anki Package (*.apkg)"),
    )
    monkeypatch.setattr("ankismart.ui.result_page.ApkgExporter.export", _fake_export)

    result_page.export_apkg()

    assert export_path.exists()
    assert exported["count"] == len(window.cards)
    assert exported["path"] == export_path


@pytest.mark.p1
@pytest.mark.fast
def test_e2e_error_net_006_timeout_and_429_retry_then_recover(
    window,
    e2e_files,
    monkeypatch,
    patch_batch_convert_worker,
    patch_push_worker,
):
    patch_batch_convert_worker()
    patch_push_worker(fail=False)

    attempts = {"n": 0}

    def _fake_completion_create(**kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise APITimeoutError(request=MagicMock())
        if attempts["n"] == 2:
            response = httpx.Response(
                429,
                request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
            )
            response.headers = {}
            raise RateLimitError(message="rate limited", response=response, body=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='[{"Front":"Q1","Back":"A1"}]'))],
            usage=None,
        )

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=_fake_completion_create))

        def close(self):
            return None

    monkeypatch.setattr("ankismart.card_gen.llm_client.OpenAI", _FakeOpenAI)
    monkeypatch.setattr("ankismart.card_gen.llm_client.time.sleep", lambda _seconds: None)

    import_page = ImportPageObject(window)
    preview_page = PreviewPageObject(window)
    card_preview_page = CardPreviewPageObject(window)
    result_page = ResultPageObject(window)

    import_page.prepare_files([e2e_files["md"]])
    import_page.configure(deck_name="Default", tags="ankismart,e2e,net", target_total=1)
    import_page.start_convert()

    assert window.batch_result is not None
    assert len(window.batch_result.documents) == 1

    preview_page.generate_cards()
    _wait_until(lambda: len(window.cards) > 0)

    assert attempts["n"] >= 3
    assert len(window.cards) > 0

    card_preview_page.push_to_anki()
    _wait_until(lambda: result_page.push_result is not None)
    assert result_page.push_result is not None
    assert result_page.push_result.failed == 0
    assert result_page.push_result.succeeded == len(window.cards)


@pytest.mark.p1
@pytest.mark.fast
def test_e2e_error_file_007_invalid_file_then_recover(
    window,
    e2e_files,
    tmp_path: Path,
    patch_batch_convert_worker,
):
    bad_file = tmp_path / "bad.unsupported"
    bad_file.write_text("invalid payload", encoding="utf-8")

    patch_batch_convert_worker(fail_files={bad_file.name})

    import_page = ImportPageObject(window)
    preview_page = PreviewPageObject(window)

    import_page.prepare_files([bad_file])
    import_page.configure(deck_name="Default", tags="ankismart,e2e,file", target_total=10)
    import_page.start_convert()

    assert window.batch_result is None
    assert "没有成功转换的文件" in import_page.page._status_label.text()

    # Recovery: clear invalid file and convert a valid markdown file.
    import_page.page._clear_files()
    import_page.prepare_files([e2e_files["md"]])
    import_page.start_convert()

    assert window.batch_result is not None
    assert len(window.batch_result.documents) == 1
    assert window.batch_result.documents[0].result.source_format == "markdown"
    assert preview_page.converted_documents_count() == 1
