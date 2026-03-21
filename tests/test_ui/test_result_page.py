from __future__ import annotations

import pytest
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QApplication

import ankismart.ui.result_page as result_page_module
from ankismart.core.models import CardDraft, CardPushStatus, PushResult
from ankismart.ui.card_edit_widget import CardEditWidget
from ankismart.ui.result_page import ResultPage


def _make_card(front: str = "Q", back: str = "A") -> CardDraft:
    return CardDraft(
        fields={"Front": front, "Back": back},
        note_type="Basic",
        deck_name="Test",
        tags=["test"],
    )


class _FakePlainTextEdit:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def toPlainText(self) -> str:
        return self._text

    def setPlainText(self, text: str) -> None:
        self._text = text


class _FakeListItem:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def setText(self, text: str) -> None:
        self._text = text


class _FakeListWidget:
    def __init__(self, count: int = 0) -> None:
        self._items = [_FakeListItem() for _ in range(count)]

    def item(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None


class _FakeSignal:
    def emit(self) -> None:
        pass


class _ThreadLikeWorker:
    def __init__(self, *, running: bool) -> None:
        self._running = running
        self.wait_calls: list[int] = []
        self.cancel_called = False
        self.terminate_called = False
        self.deleted = False

    def isRunning(self) -> bool:  # noqa: N802
        return self._running

    def wait(self, timeout: int) -> None:
        self.wait_calls.append(timeout)

    def cancel(self) -> None:
        self.cancel_called = True

    def terminate(self) -> None:
        self.terminate_called = True

    def deleteLater(self) -> None:  # noqa: N802
        self.deleted = True


class _SignalStub:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in list(self._callbacks):
            callback(*args)


def test_card_editor_get_cards_returns_edited():
    """CardEditWidget.get_cards returns cards with edits applied."""
    cards = [_make_card("Q1", "A1"), _make_card("Q2", "A2")]
    w = CardEditWidget.__new__(CardEditWidget)
    w._cards = list(cards)
    w._current_index = 0
    w._field_editors = {
        "Front": _FakePlainTextEdit("Edited"),
        "Back": _FakePlainTextEdit("A1"),
    }
    w._list = _FakeListWidget(2)
    w.cards_changed = _FakeSignal()

    result = w.get_cards()
    assert result[0].fields["Front"] == "Edited"
    assert result[1].fields["Front"] == "Q2"


def test_get_cards_reformats_basic_back_to_answer_explanation_block():
    card = _make_card("什么是事务原子性？", "原子性。解析：要么全成要么全败。")
    dialog = CardEditWidget.__new__(CardEditWidget)
    dialog._cards = [card]
    dialog._current_index = 0
    dialog._field_editors = {
        "Front": _FakePlainTextEdit("什么是事务原子性？"),
        "Back": _FakePlainTextEdit("原子性。解析：要么全成要么全败。"),
    }
    dialog._list = _FakeListWidget(1)
    dialog.cards_changed = _FakeSignal()

    result = dialog.get_cards()

    assert result[0].fields["Back"].startswith("答案:")
    assert "解析:" in result[0].fields["Back"]


# --- ResultPage update-mode combo tests ---


@pytest.fixture(scope="session")
def _qapp():
    """Ensure a QApplication exists for the test session."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakeMainWindow:
    def __init__(self):
        self.cards = []
        self.config = type(
            "C",
            (),
            {
                "anki_connect_url": "",
                "anki_connect_key": "",
                "proxy_url": "",
                "last_update_mode": None,
                "allow_duplicate": False,
                "duplicate_scope": "deck",
                "duplicate_check_model": True,
                "language": "zh",
            },
        )()


def test_update_combo_has_three_items(_qapp):
    """The update-mode combo exposes exactly 3 items with correct data values."""
    page = ResultPage(_FakeMainWindow())
    combo = page._update_combo
    assert combo.count() == 3
    assert combo.itemData(0) == "create_only"
    assert combo.itemData(1) == "update_only"
    assert combo.itemData(2) == "create_or_update"


def test_update_combo_default_is_create_or_update(_qapp):
    """The default selection of the update-mode combo is 'create_or_update'."""
    page = ResultPage(_FakeMainWindow())
    assert page._update_combo.currentData() == "create_or_update"


def test_cleanup_push_worker_keeps_reference_when_running(_qapp) -> None:
    page = ResultPage(_FakeMainWindow())
    worker = _ThreadLikeWorker(running=True)
    page._worker = worker

    page._cleanup_push_worker()

    assert page._worker is worker
    assert worker.cancel_called is True
    assert worker.wait_calls == [200]
    assert worker.deleted is False


def test_cleanup_push_worker_releases_finished_worker(_qapp) -> None:
    page = ResultPage(_FakeMainWindow())
    worker = _ThreadLikeWorker(running=False)
    page._worker = worker

    page._cleanup_push_worker()

    assert page._worker is None
    assert worker.deleted is True


def test_close_event_does_not_force_terminate_running_worker(_qapp, monkeypatch) -> None:
    page = ResultPage(_FakeMainWindow())
    worker = _ThreadLikeWorker(running=True)
    page._worker = worker

    warning_calls: list[str] = []
    monkeypatch.setattr(
        "ankismart.ui.result_page.logger.warning",
        lambda msg: warning_calls.append(msg),
    )

    page.closeEvent(QCloseEvent())

    assert worker.cancel_called is True
    assert worker.wait_calls == [200]
    assert worker.terminate_called is False
    assert page._worker is worker
    assert len(warning_calls) == 1


def test_retry_failed_returns_when_worker_running(_qapp, monkeypatch) -> None:
    page = ResultPage(_FakeMainWindow())
    page._cards = [_make_card()]
    page._push_result = PushResult(
        total=1,
        succeeded=0,
        failed=1,
        results=[CardPushStatus(index=0, success=False, error="failed")],
    )
    page._worker = _ThreadLikeWorker(running=True)

    info_calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        ResultPage,
        "_show_info_bar",
        lambda *args, **kwargs: info_calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        "ankismart.ui.result_page.InfoBar.info",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected direct infobar")),
    )

    def _fail_push_worker(*args, **kwargs):
        raise AssertionError("PushWorker should not be created")

    monkeypatch.setattr("ankismart.ui.result_page.PushWorker", _fail_push_worker)

    page._retry_failed()

    assert len(info_calls) == 1
    assert info_calls[0][0][2] == "请稍候"


def test_repush_all_returns_when_worker_running(_qapp, monkeypatch) -> None:
    page = ResultPage(_FakeMainWindow())
    page._cards = [_make_card()]
    page._worker = _ThreadLikeWorker(running=True)

    info_calls = []
    monkeypatch.setattr(
        "ankismart.ui.result_page.InfoBar.info",
        lambda *args, **kwargs: info_calls.append(kwargs),
    )

    def _fail_push_worker(*args, **kwargs):
        raise AssertionError("PushWorker should not be created")

    monkeypatch.setattr("ankismart.ui.result_page.PushWorker", _fail_push_worker)

    page._repush_all_cards()

    assert len(info_calls) == 1


def test_retry_failed_sync_finished_worker_is_cleaned_up(_qapp, monkeypatch) -> None:
    page = ResultPage(_FakeMainWindow())
    page._cards = [_make_card()]
    page._push_result = PushResult(
        total=1,
        succeeded=0,
        failed=1,
        results=[CardPushStatus(index=0, success=False, error="failed")],
    )
    page._display_result = lambda *_args, **_kwargs: None

    class _PushWorkerStub:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.progress = _SignalStub()
            self.card_progress = _SignalStub()
            self.finished = _SignalStub()
            self.error = _SignalStub()
            self.cancelled = _SignalStub()
            self.deleted = False

        def start(self) -> None:
            self.finished.emit(
                PushResult(
                    total=1,
                    succeeded=1,
                    failed=0,
                    results=[CardPushStatus(index=0, success=True, error="")],
                )
            )

        def isRunning(self) -> bool:  # noqa: N802
            return False

        def deleteLater(self) -> None:  # noqa: N802
            self.deleted = True

    monkeypatch.setattr("ankismart.ui.result_page.AnkiConnectClient", lambda **kwargs: object())
    monkeypatch.setattr("ankismart.ui.result_page.AnkiGateway", lambda client: object())
    monkeypatch.setattr("ankismart.ui.result_page.PushWorker", _PushWorkerStub)
    monkeypatch.setattr("ankismart.ui.result_page.InfoBar.info", lambda *args, **kwargs: None)
    monkeypatch.setattr("ankismart.ui.result_page.InfoBar.success", lambda *args, **kwargs: None)
    monkeypatch.setattr("ankismart.ui.result_page.InfoBar.error", lambda *args, **kwargs: None)

    page._retry_failed()

    assert page._worker is None


def test_load_result_only_shows_top_feedback_once(_qapp, monkeypatch) -> None:
    page = ResultPage(_FakeMainWindow())
    cards = [_make_card("问题一", "答案一")]
    result = PushResult(
        total=1,
        succeeded=1,
        failed=0,
        results=[CardPushStatus(index=0, success=True, error="")],
        trace_id="trace-feedback-once",
    )

    success_calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        ResultPage,
        "_show_info_bar",
        lambda *args, **kwargs: success_calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        "ankismart.ui.result_page.InfoBar.success",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected direct infobar")),
    )

    page.load_result(result, cards)
    page._refresh()

    assert len(success_calls) == 1
    assert success_calls[0][0][1] == "success"


def test_export_selected_apkg_without_selection_uses_page_infobar_helper(
    _qapp, monkeypatch
) -> None:
    page = ResultPage(_FakeMainWindow())
    page._cards = [_make_card()]
    page._selected_indices = set()
    calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(
        ResultPage,
        "_show_info_bar",
        lambda *args, **kwargs: calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        "ankismart.ui.result_page.InfoBar.info",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected direct infobar")),
    )

    page._export_selected_apkg()

    assert len(calls) == 1
    assert calls[0][0][1] == "info"


def test_export_apkg_uses_export_worker(monkeypatch, _qapp, tmp_path) -> None:
    page = ResultPage(_FakeMainWindow())
    page._cards = [_make_card()]
    monkeypatch.setattr(
        "ankismart.ui.result_page.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "out.apkg"), "Anki Package (*.apkg)"),
    )

    created = {}

    monkeypatch.setattr(
        "ankismart.ui.result_page._create_apkg_exporter",
        lambda: created.__setitem__("factory_called", True) or object(),
    )

    class _ExportWorkerStub:
        def __init__(self, exporter, cards, output_path):
            created["exporter"] = exporter
            created["cards"] = cards
            created["path"] = output_path
            created["worker"] = self
            self.finished = _SignalStub()
            self.error = _SignalStub()
            self.progress = _SignalStub()
            self.cancelled = _SignalStub()

        def start(self) -> None:
            created["started"] = True

    monkeypatch.setattr("ankismart.ui.result_page.ExportWorker", _ExportWorkerStub)

    page._export_apkg()

    assert created["cards"] == page._cards
    assert str(created["path"]).endswith("out.apkg")
    assert created["factory_called"] is True
    assert created["started"] is True
    assert page._btn_export_apkg.isEnabled() is False
    assert page._btn_retry.isEnabled() is False
    assert page._btn_repush_all.isEnabled() is False

    created["worker"].progress.emit("正在导出 1 张卡片到 APKG")

    assert "导出" in page._status_label.text()


def test_create_apkg_exporter_supports_string_path_monkeypatch(monkeypatch, tmp_path) -> None:
    calls = {}

    def _fake_export(self, cards, output_path):
        calls["cards"] = cards
        calls["path"] = output_path
        return output_path

    monkeypatch.setattr("ankismart.ui.result_page.ApkgExporter.export", _fake_export)

    exporter = result_page_module._create_apkg_exporter()
    output_path = tmp_path / "patched.apkg"
    result = exporter.export([_make_card()], output_path)

    assert result == output_path
    assert calls["cards"][0].fields["Front"] == "Q"
    assert calls["path"] == output_path


def test_export_error_publishes_failed_task_event(monkeypatch, _qapp) -> None:
    page = ResultPage(_FakeMainWindow())
    events = []

    monkeypatch.setattr(page, "_publish_task_event", lambda event: events.append(event))
    monkeypatch.setattr("ankismart.ui.result_page.InfoBar.error", lambda *args, **kwargs: None)
    page._current_task_id = "task-result"

    page._on_export_error("disk full")

    assert events[-1].kind == "failed"
    assert events[-1].stage == "export"


def test_export_error_uses_page_infobar_helper(monkeypatch, _qapp) -> None:
    page = ResultPage(_FakeMainWindow())
    calls: list[tuple[tuple, dict]] = []

    monkeypatch.setattr(
        ResultPage,
        "_show_info_bar",
        lambda *args, **kwargs: calls.append((args, kwargs)),
        raising=False,
    )
    monkeypatch.setattr(
        "ankismart.ui.result_page.InfoBar.error",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )

    page._on_export_error("disk full")

    assert len(calls) == 1
    assert calls[0][0][1] == "error"


def test_retry_failed_updates_persistent_push_status(monkeypatch, _qapp) -> None:
    page = ResultPage(_FakeMainWindow())
    page._cards = [_make_card()]
    page._push_result = PushResult(
        total=1,
        succeeded=0,
        failed=1,
        results=[CardPushStatus(index=0, success=False, error="failed")],
    )
    page._display_result(page._push_result, page._cards)

    class _PushWorkerStub:
        def __init__(self, **kwargs) -> None:
            self.progress = _SignalStub()
            self.finished = _SignalStub()
            self.error = _SignalStub()
            self.card_progress = _SignalStub()
            self.cancelled = _SignalStub()

        def start(self) -> None:
            self.card_progress.emit(1, 1)

        def isRunning(self) -> bool:  # noqa: N802
            return True

    monkeypatch.setattr("ankismart.ui.result_page.AnkiConnectClient", lambda **kwargs: object())
    monkeypatch.setattr("ankismart.ui.result_page.AnkiGateway", lambda client: object())
    monkeypatch.setattr("ankismart.ui.result_page.PushWorker", _PushWorkerStub)
    monkeypatch.setattr(ResultPage, "_show_info_bar", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(
        "ankismart.ui.result_page.InfoBar.info",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected direct infobar")),
    )

    page._retry_failed()

    assert "1/1" in page._status_label.text()


def test_repush_all_uses_lazy_gateway_factory(monkeypatch, _qapp) -> None:
    page = ResultPage(_FakeMainWindow())
    page._cards = [_make_card()]
    created = {"gateway_calls": 0}

    monkeypatch.setattr(
        "ankismart.ui.result_page._create_push_gateway",
        lambda config: (
            created.__setitem__("gateway_calls", created["gateway_calls"] + 1) or object()
        ),
    )

    class _PushWorkerStub:
        def __init__(self, **kwargs) -> None:
            created["gateway"] = kwargs["gateway"]
            self.progress = _SignalStub()
            self.finished = _SignalStub()
            self.error = _SignalStub()
            self.card_progress = _SignalStub()
            self.cancelled = _SignalStub()

        def start(self) -> None:
            created["started"] = True

        def isRunning(self) -> bool:  # noqa: N802
            return True

    monkeypatch.setattr("ankismart.ui.result_page.PushWorker", _PushWorkerStub)
    monkeypatch.setattr("ankismart.ui.result_page.InfoBar.info", lambda *args, **kwargs: None)

    page._repush_all_cards()

    assert created["gateway_calls"] == 1
    assert created["started"] is True


def test_table_title_uses_question_field_only(_qapp) -> None:
    page = ResultPage(_FakeMainWindow())
    card = CardDraft(
        fields={
            "Front": "这是一条非常关键的问题文本",
            "Back": "答案内容",
            "Extra": "额外字段不应作为标题",
        },
        note_type="Basic",
        deck_name="Default",
        tags=[],
    )
    status = CardPushStatus(index=0, success=True, error="")

    page._add_table_row(status, [card])

    assert page._table.item(0, 1).text().startswith("这是一条非常关键的问题文本")
