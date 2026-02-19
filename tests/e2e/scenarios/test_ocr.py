from __future__ import annotations

import pytest

from tests.e2e.page_objects.card_preview_page import CardPreviewPageObject
from tests.e2e.page_objects.import_page import ImportPageObject
from tests.e2e.page_objects.preview_page import PreviewPageObject
from tests.e2e.page_objects.result_page import ResultPageObject


@pytest.mark.p0
@pytest.mark.fast
@pytest.mark.gate
def test_e2e_ocr_pdf_workflow(
    window,
    e2e_files,
    monkeypatch,
    patch_batch_convert_worker,
    patch_batch_generate_worker,
    patch_push_worker,
):
    calls = {"prepare": 0, "ensure": 0}

    def _prepare(self) -> bool:
        calls["prepare"] += 1
        return True

    def _ensure(self) -> bool:
        calls["ensure"] += 1
        return True

    monkeypatch.setattr("ankismart.ui.import_page.ImportPage._prepare_local_ocr_runtime", _prepare)
    monkeypatch.setattr("ankismart.ui.import_page.ImportPage._ensure_ocr_models_ready", _ensure)

    patch_batch_convert_worker()
    patch_batch_generate_worker(cards_per_document=2)
    patch_push_worker(fail=False)

    import_page = ImportPageObject(window)
    preview_page = PreviewPageObject(window)
    card_preview_page = CardPreviewPageObject(window)
    result_page = ResultPageObject(window)

    import_page.prepare_files([e2e_files["pdf"]])
    import_page.configure(deck_name="Default", tags="ankismart,e2e,ocr", target_total=20)
    import_page.start_convert()

    assert calls["prepare"] == 1
    assert calls["ensure"] == 1
    assert window.batch_result is not None
    assert len(window.batch_result.documents) == 1
    assert window.batch_result.documents[0].result.source_format == "pdf"
    assert preview_page.converted_documents_count() == 1

    preview_page.generate_cards()
    assert len(window.cards) > 0

    card_preview_page.push_to_anki()
    assert result_page.push_result is not None
    assert result_page.push_result.failed == 0
