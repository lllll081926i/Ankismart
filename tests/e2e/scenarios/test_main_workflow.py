from __future__ import annotations

import pytest

from tests.e2e.page_objects.card_preview_page import CardPreviewPageObject
from tests.e2e.page_objects.import_page import ImportPageObject
from tests.e2e.page_objects.preview_page import PreviewPageObject
from tests.e2e.page_objects.result_page import ResultPageObject


@pytest.mark.p0
@pytest.mark.fast
@pytest.mark.gate
@pytest.mark.parametrize(
    ("file_key", "expected_source_format"),
    [("docx", "docx"), ("md", "markdown")],
    ids=["E2E-MAIN-DOCX-001", "E2E-MAIN-MD-002"],
)
def test_e2e_main_workflow(window, e2e_files, patch_batch_convert_worker, patch_batch_generate_worker, patch_push_worker, file_key: str, expected_source_format: str):
    patch_batch_convert_worker()
    patch_batch_generate_worker(cards_per_document=2)
    patch_push_worker(fail=False)

    import_page = ImportPageObject(window)
    preview_page = PreviewPageObject(window)
    card_preview_page = CardPreviewPageObject(window)
    result_page = ResultPageObject(window)

    import_page.prepare_files([e2e_files[file_key]])
    import_page.configure(deck_name="Default", tags="ankismart,e2e", target_total=20)
    import_page.start_convert()

    assert window.batch_result is not None
    assert len(window.batch_result.documents) == 1
    assert window.batch_result.documents[0].result.source_format == expected_source_format
    assert preview_page.converted_documents_count() == 1

    preview_page.generate_cards()

    assert len(window.cards) > 0
    assert card_preview_page.card_count() == len(window.cards)

    card_preview_page.push_to_anki()

    assert result_page.push_result is not None
    assert result_page.push_result.total == len(window.cards)
    assert result_page.push_result.succeeded == len(window.cards)
    assert result_page.push_result.failed == 0
