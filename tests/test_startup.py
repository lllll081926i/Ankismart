"""Startup import smoke tests."""

from ankismart.ui.import_page import ImportPage
from ankismart.ui.preview_page import PreviewPage
from ankismart.ui.result_page import ResultPage
from ankismart.ui.settings_page import SettingsPage
from ankismart.ui.workers import BatchConvertWorker


def test_ui_imports_smoke() -> None:
    assert ImportPage is not None
    assert BatchConvertWorker is not None
    assert PreviewPage is not None
    assert ResultPage is not None
    assert SettingsPage is not None
