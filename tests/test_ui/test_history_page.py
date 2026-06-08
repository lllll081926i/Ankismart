from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

from ankismart.core.config import AppConfig
from ankismart.core.history_store import SQLiteHistoryStore
from ankismart.core.models import CardDraft, CardMetadata
from ankismart.ui.history_page import HistoryPage


@pytest.fixture(scope="session", name="_qapp")
def _qapp_fixture():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _main() -> SimpleNamespace:
    return SimpleNamespace(config=AppConfig(language="zh"))


def _card(index: int, *, source_document: str = "lesson.md") -> CardDraft:
    return CardDraft(
        trace_id=f"trace-{index}",
        deck_name="Default",
        note_type="Basic",
        fields={"Front": f"问题 {index}", "Back": f"答案 {index}"},
        tags=["ankismart"],
        metadata=CardMetadata(source_document=source_document, strategy_id="basic"),
    )


def test_history_page_lists_generation_batches(_qapp, tmp_path: Path) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1)], batch_id="batch-1", title="第一批")
    store.save_generation_batch(
        [_card(2), _card(3, source_document="chapter.md")],
        batch_id="batch-2",
        title="第二批",
    )

    page = HistoryPage(_main(), history_store=store)
    page.refresh_history()

    assert page._table.rowCount() == 2
    assert page._total_records_value.text() == "2"
    assert page._total_cards_value.text() == "3"
    assert "chapter.md" in page._table.item(0, 2).text()


def test_history_page_exports_selected_batch_to_json(_qapp, tmp_path: Path, monkeypatch) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1)], batch_id="batch-1", title="第一批")
    page = HistoryPage(_main(), history_store=store)
    page.refresh_history()
    output = tmp_path / "selected.json"

    page._selected_batch_ids = {"batch-1"}
    page._export_format_combo.setCurrentIndex(1)
    monkeypatch.setattr(
        "ankismart.ui.history_page.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(output), "JSON Files (*.json)"),
    )
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: None)

    page._export_selected()

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["card_count"] == 1
    assert payload["cards"][0]["fields"]["Front"] == "问题 1"


def test_history_page_delete_selected_uses_fluent_dialog(
    _qapp, tmp_path: Path, monkeypatch
) -> None:
    store = SQLiteHistoryStore(tmp_path / "history.sqlite3")
    store.save_generation_batch([_card(1)], batch_id="batch-1", title="第一批")
    page = HistoryPage(_main(), history_store=store)
    page.refresh_history()
    page._selected_batch_ids = {"batch-1"}
    dialogs: list[object] = []

    class _Button:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, text: str) -> None:
            self.text = text

    class _Dialog:
        def __init__(self, title: str, content: str, parent=None) -> None:
            self.title = title
            self.content = content
            self.yesButton = _Button()
            self.cancelButton = _Button()
            dialogs.append(self)

        def exec(self) -> bool:
            return True

    monkeypatch.setattr("ankismart.ui.history_page.FluentMessageBox", _Dialog)
    monkeypatch.setattr(page, "_show_info_bar", lambda *args, **kwargs: None)

    page._delete_selected()

    assert len(dialogs) == 1
    assert dialogs[0].title == "确认删除"
    assert dialogs[0].yesButton.text == "是"
    assert dialogs[0].cancelButton.text == "否"
    assert store.list_generation_batches() == []
