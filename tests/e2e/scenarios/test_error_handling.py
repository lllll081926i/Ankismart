from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.page_objects.card_preview_page import CardPreviewPageObject
from tests.e2e.page_objects.import_page import ImportPageObject
from tests.e2e.page_objects.preview_page import PreviewPageObject
from tests.e2e.page_objects.result_page import ResultPageObject


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
