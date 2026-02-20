from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

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
        self.deleted = False

    def isRunning(self) -> bool:  # noqa: N802
        return self._running

    def wait(self, timeout: int) -> None:
        self.wait_calls.append(timeout)

    def cancel(self) -> None:
        self.cancel_called = True

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
        self.config = type("C", (), {
            "anki_connect_url": "",
            "anki_connect_key": "",
            "proxy_url": "",
            "last_update_mode": None,
            "allow_duplicate": False,
            "duplicate_scope": "deck",
            "duplicate_check_model": True,
            "language": "zh",
        })()


def test_update_combo_has_three_items(_qapp):
    """The update-mode combo exposes exactly 3 items with correct data values."""
    page = ResultPage(_FakeMainWindow())
    combo = page._update_combo
    assert combo.count() == 3
    assert combo.itemData(0) == "create_only"
    assert combo.itemData(1) == "update_only"
    assert combo.itemData(2) == "create_or_update"


def test_update_combo_default_is_create_only(_qapp):
    """The default selection of the update-mode combo is 'create_only'."""
    page = ResultPage(_FakeMainWindow())
    assert page._update_combo.currentData() == "create_only"


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

    info_calls = []
    monkeypatch.setattr(
        "ankismart.ui.result_page.InfoBar.info",
        lambda *args, **kwargs: info_calls.append(kwargs),
    )

    def _fail_push_worker(*args, **kwargs):
        raise AssertionError("PushWorker should not be created")

    monkeypatch.setattr("ankismart.ui.result_page.PushWorker", _fail_push_worker)

    page._retry_failed()

    assert len(info_calls) == 1


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
            self.finished = _SignalStub()
            self.error = _SignalStub()
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

    success_calls = []
    monkeypatch.setattr(
        "ankismart.ui.result_page.InfoBar.success",
        lambda *args, **kwargs: success_calls.append(kwargs),
    )

    page.load_result(result, cards)
    page._refresh()

    assert len(success_calls) == 1


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
