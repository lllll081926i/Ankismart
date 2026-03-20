from __future__ import annotations

import sys
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication, QLabel
from pytest import mark

from ankismart.core.models import (
    BatchConvertResult,
    ConvertedDocument,
    MarkdownResult,
    RegenerateRequest,
)
from ankismart.ui.preview_page import MarkdownHighlighter, PreviewPage

# QApplication must exist before any QWidget is created
_app = QApplication.instance() or QApplication(sys.argv)


def _make_doc(name: str, content: str) -> ConvertedDocument:
    return ConvertedDocument(
        result=MarkdownResult(
            content=content,
            source_path=f"/tmp/{name}",
            source_format="markdown",
        ),
        file_name=name,
    )


def _make_batch(*docs: ConvertedDocument, errors: list[str] | None = None) -> BatchConvertResult:
    return BatchConvertResult(
        documents=list(docs),
        errors=errors or [],
    )


def _make_main_window() -> MagicMock:
    main = MagicMock()
    main.config = MagicMock()
    main.import_page._deck_combo.currentText.return_value = "Default"
    main.import_page._tags_input.text.return_value = "ankismart"
    main.import_page.build_generation_config.return_value = {
        "mode": "single",
        "strategy": "basic",
    }
    return main


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


class TestPreviewPageLoadDocuments:
    def test_preview_page_does_not_render_sample_button(self):
        main = _make_main_window()
        page = PreviewPage(main)

        assert not hasattr(page, "_btn_preview")
        assert page._btn_generate is not None

    def test_preview_page_does_not_render_performance_hint(self):
        main = _make_main_window()
        page = PreviewPage(main)

        texts: list[str] = []
        for widget in page.findChildren(object):
            text = getattr(widget, "text", None)
            if callable(text):
                try:
                    value = text()
                except TypeError:
                    continue
                if isinstance(value, str) and value:
                    texts.append(value)

        assert all("最近耗时" not in text for text in texts)
        assert all("Recent generation timing" not in text for text in texts)

    def test_load_single_document(self):
        main = _make_main_window()
        page = PreviewPage(main)
        doc = _make_doc("test.md", "# Hello")
        batch = _make_batch(doc)

        page.load_documents(batch)

        assert page._file_list.count() == 1
        assert page._file_list.item(0).text() == "test.md"
        # File list hidden for single document
        assert not page._file_list.isVisible()
        # Editor shows content
        assert page._editor.toPlainText() == "# Hello"

    def test_load_multiple_documents(self):
        main = _make_main_window()
        page = PreviewPage(main)
        doc1 = _make_doc("a.md", "# File A")
        doc2 = _make_doc("b.md", "# File B")
        batch = _make_batch(doc1, doc2)

        page.load_documents(batch)

        assert page._file_list.count() == 2
        # isVisibleTo checks the explicit visibility flag (not effective visibility)
        assert page._file_list.isVisibleTo(page)
        # First file selected by default
        assert page._editor.toPlainText() == "# File A"

    def test_load_with_errors(self):
        main = _make_main_window()
        page = PreviewPage(main)
        doc = _make_doc("ok.md", "content")
        batch = _make_batch(doc, errors=["bad.pdf: OCR failed"])

        page.load_documents(batch)
        assert page._file_list.count() == 1
        assert page._editor.toPlainText() == "content"

    def test_load_empty_batch(self):
        main = _make_main_window()
        page = PreviewPage(main)
        batch = _make_batch()

        page.load_documents(batch)

        assert page._file_list.count() == 0
        assert page._editor.toPlainText() == ""

    def test_reload_clears_previous(self):
        main = _make_main_window()
        page = PreviewPage(main)

        doc1 = _make_doc("first.md", "first")
        page.load_documents(_make_batch(doc1))
        assert page._editor.toPlainText() == "first"

        doc2 = _make_doc("second.md", "second")
        page.load_documents(_make_batch(doc2))
        assert page._file_list.count() == 1
        assert page._editor.toPlainText() == "second"


class TestPreviewPageFileSwitching:
    def test_switch_preserves_edits(self):
        main = _make_main_window()
        page = PreviewPage(main)
        doc1 = _make_doc("a.md", "original A")
        doc2 = _make_doc("b.md", "original B")
        page.load_documents(_make_batch(doc1, doc2))

        # Edit file A
        page._editor.setPlainText("edited A")
        # Switch to file B
        page._file_list.setCurrentRow(1)
        assert page._editor.toPlainText() == "original B"

        # Switch back to file A -- edit should be preserved
        page._file_list.setCurrentRow(0)
        assert page._editor.toPlainText() == "edited A"

    def test_switch_to_negative_index_ignored(self):
        main = _make_main_window()
        page = PreviewPage(main)
        doc = _make_doc("a.md", "content")
        page.load_documents(_make_batch(doc))

        # Should not raise
        page._on_file_switched(-1)
        assert page._editor.toPlainText() == "content"


class TestPreviewPageBuildDocuments:
    def test_build_returns_edited_content(self):
        main = _make_main_window()
        page = PreviewPage(main)
        doc = _make_doc("a.md", "original")
        page.load_documents(_make_batch(doc))

        page._editor.setPlainText("edited")
        page._save_current_edit()

        built = page._build_documents()
        assert len(built) == 1
        assert built[0].result.content == "edited"
        assert built[0].file_name == "a.md"

    def test_build_unedited_keeps_original(self):
        main = _make_main_window()
        page = PreviewPage(main)
        doc = _make_doc("a.md", "original")
        page.load_documents(_make_batch(doc))

        built = page._build_documents()
        assert built[0].result.content == "original"

    def test_build_multiple_mixed_edits(self):
        main = _make_main_window()
        page = PreviewPage(main)
        doc1 = _make_doc("a.md", "A")
        doc2 = _make_doc("b.md", "B")
        page.load_documents(_make_batch(doc1, doc2))

        # Edit only file A
        page._editor.setPlainText("A edited")
        page._save_current_edit()

        built = page._build_documents()
        assert built[0].result.content == "A edited"
        assert built[1].result.content == "B"


class TestMarkdownHighlighter:
    def test_highlighter_attached(self):
        main = _make_main_window()
        page = PreviewPage(main)
        assert isinstance(page._highlighter, MarkdownHighlighter)
        assert page._highlighter.document() is page._editor.document()

    def test_highlighter_does_not_crash_on_content(self):
        main = _make_main_window()
        page = PreviewPage(main)
        md = (
            "# Heading\n"
            "## Sub heading\n"
            "Normal text with **bold** and *italic*.\n"
            "`inline code` and [link](http://example.com)\n"
            "![image](img.png)\n"
            "> blockquote\n"
            "- list item\n"
            "1. ordered item\n"
            "```python\nprint('hi')\n```\n"
            "---\n"
        )
        # Loading content triggers the highlighter -- should not raise
        page._editor.setPlainText(md)
        assert page._editor.toPlainText() == md

    def test_highlighter_rules_exist(self):
        hl = MarkdownHighlighter()
        assert len(hl._rules) > 0
        # Each rule is (pattern, format)
        for pattern, fmt in hl._rules:
            assert hasattr(pattern, "finditer")


class TestPreviewPageFlow:
    def test_push_finished_does_not_auto_navigate(self):
        main = _make_main_window()
        page = PreviewPage(main)
        page._main.cards = []

        page._on_push_finished(MagicMock())

        main.switch_to_result.assert_not_called()

    def test_generation_metrics_are_not_rendered_as_hint(self):
        main = _make_main_window()
        main.config.language = "zh"
        main.config.ops_generation_durations = [9.0, 15.0]
        main.config.task_history = [
            {
                "event": "batch_generate",
                "status": "success",
                "summary": "生成 12 张卡片",
                "payload": {"duration_seconds": 15.0},
            }
        ]
        page = PreviewPage(main)
        texts: list[str] = []
        for widget in page.findChildren(object):
            text = getattr(widget, "text", None)
            if callable(text):
                try:
                    value = text()
                except TypeError:
                    continue
                if isinstance(value, str) and value:
                    texts.append(value)

        assert all("最近生成" not in text for text in texts)
        assert all("P50" not in text for text in texts)

    @mark.parametrize(
        ("callback_name", "args"),
        [
            ("_on_generation_finished", ([MagicMock()],)),
            ("_on_generation_error", ("boom",)),
        ],
    )
    def test_generation_callbacks_do_not_record_metric_again(
        self, monkeypatch, callback_name: str, args: tuple[object, ...]
    ):
        main = _make_main_window()
        main.config.language = "zh"
        page = PreviewPage(main)
        page._generation_start_ts = 0.0

        metric_calls = {"count": 0}
        monkeypatch.setattr("ankismart.ui.preview_page.append_task_history", lambda *a, **k: None)
        monkeypatch.setattr(
            "ankismart.ui.preview_page.record_operation_metric",
            lambda *a, **k: metric_calls.__setitem__("count", metric_calls["count"] + 1),
        )
        monkeypatch.setattr("ankismart.ui.preview_page.save_config", lambda cfg: None)
        monkeypatch.setattr(
            "ankismart.ui.preview_page.build_error_display",
            lambda error, language: {"title": "失败", "content": error},
        )
        monkeypatch.setattr(
            "ankismart.ui.preview_page.InfoBar",
            type(
                "_InfoBarStub",
                (),
                {
                    "warning": staticmethod(lambda *a, **k: None),
                    "success": staticmethod(lambda *a, **k: None),
                    "info": staticmethod(lambda *a, **k: None),
                    "error": staticmethod(lambda *a, **k: None),
                },
            ),
        )
        monkeypatch.setattr(PreviewPage, "_count_low_quality_cards", lambda self, cards: 0)

        getattr(page, callback_name)(*args)

        assert metric_calls["count"] == 0


class TestPreviewPageWorkerCleanup:
    def test_cleanup_generate_worker_keeps_reference_when_running(self):
        main = _make_main_window()
        page = PreviewPage(main)
        worker = _ThreadLikeWorker(running=True)
        page._generate_worker = worker

        page._cleanup_generate_worker()

        assert page._generate_worker is worker
        assert worker.cancel_called is True
        assert worker.wait_calls == [200]
        assert worker.deleted is False

    def test_cleanup_generate_worker_releases_finished_worker(self):
        main = _make_main_window()
        page = PreviewPage(main)
        worker = _ThreadLikeWorker(running=False)
        page._generate_worker = worker

        page._cleanup_generate_worker()

        assert page._generate_worker is None
        assert worker.deleted is True

    def test_cleanup_push_worker_keeps_reference_when_running(self):
        main = _make_main_window()
        page = PreviewPage(main)
        worker = _ThreadLikeWorker(running=True)
        page._push_worker = worker

        page._cleanup_push_worker()

        assert page._push_worker is worker
        assert worker.cancel_called is True
        assert worker.wait_calls == [200]
        assert worker.deleted is False

    def test_cleanup_push_worker_releases_finished_worker(self):
        main = _make_main_window()
        page = PreviewPage(main)
        worker = _ThreadLikeWorker(running=False)
        page._push_worker = worker

        page._cleanup_push_worker()

        assert page._push_worker is None
        assert worker.deleted is True

    def test_cleanup_sample_worker_keeps_reference_when_running(self):
        main = _make_main_window()
        page = PreviewPage(main)
        worker = _ThreadLikeWorker(running=True)
        page._sample_worker = worker

        page._cleanup_sample_worker()

        assert page._sample_worker is worker
        assert worker.wait_calls == [200]
        assert worker.deleted is False

    def test_cleanup_sample_worker_releases_finished_worker(self):
        main = _make_main_window()
        page = PreviewPage(main)
        worker = _ThreadLikeWorker(running=False)
        page._sample_worker = worker

        page._cleanup_sample_worker()

        assert page._sample_worker is None
        assert worker.deleted is True


def test_generation_message_localizes_strategy_for_zh():
    main = _make_main_window()
    main.config.language = "zh"
    page = PreviewPage(main)

    text = page._normalize_generation_message("正在从 demo.md 生成 2 张 single_choice 卡片")

    assert "单选题" in text
    assert "single_choice" not in text


def test_generation_message_wraps_long_text():
    main = _make_main_window()
    main.config.language = "zh"
    page = PreviewPage(main)

    long_message = "生成 multiple_choice 卡片时出错，" + ("错误详情" * 40)
    text = page._normalize_generation_message(long_message)

    assert "\n" in text
    assert len(text) < 220


def test_push_card_progress_updates_progress_infobar(monkeypatch):
    main = _make_main_window()
    main.config.language = "zh"
    page = PreviewPage(main)
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        page,
        "_show_progress_info_bar",
        lambda title, content: calls.append((title, content)),
    )

    page._on_push_card_progress(2, 5)

    assert calls == [("正在推送到 Anki", "已完成 2/5")]


def test_generation_warning_shows_visible_infobar(monkeypatch):
    main = _make_main_window()
    main.config.language = "zh"
    page = PreviewPage(main)
    warnings: list[dict] = []

    monkeypatch.setattr(
        "ankismart.ui.preview_page.InfoBar",
        type(
            "_InfoBarStub",
            (),
            {
                "warning": staticmethod(lambda *a, **k: warnings.append(k)),
                "success": staticmethod(lambda *a, **k: None),
                "info": staticmethod(lambda *a, **k: None),
                "error": staticmethod(lambda *a, **k: None),
            },
        ),
    )

    page._on_generation_warning("生成过程中存在超时，已返回部分可用卡片。")

    assert len(warnings) == 1
    assert "超时" in warnings[0]["content"]


def test_update_converting_status_shows_top_infobar(monkeypatch):
    main = _make_main_window()
    main.config.language = "zh"
    page = PreviewPage(main)
    page._ready_documents = []
    page._total_expected_docs = 3
    warning_calls: list[dict] = []

    monkeypatch.setattr(
        "ankismart.ui.preview_page.InfoBar.warning",
        lambda *args, **kwargs: warning_calls.append(kwargs) or object(),
    )

    page.update_converting_status(2)

    assert len(warning_calls) == 1
    assert page._btn_generate.isEnabled() is False


def test_show_state_tooltip_applies_adaptive_max_width(monkeypatch):
    main = _make_main_window()
    main.config.language = "zh"
    page = PreviewPage(main)

    class _TooltipStub:
        def __init__(self, title, content, parent):
            self.title = title
            self.content = content
            self.parent = parent
            self.max_width = None
            self.min_width = None
            self.min_height = None
            self.position = None
            self.shown = False
            self.used_suitable_pos = False
            self.titleLabel = QLabel(title)
            self.contentLabel = QLabel(content)

        def setMaximumWidth(self, width):
            self.max_width = width

        def setMinimumWidth(self, width):
            self.min_width = width

        def setMinimumHeight(self, height):
            self.min_height = height

        def adjustSize(self):
            return None

        def move(self, pos):
            self.position = (pos.x(), pos.y())

        def getSuitablePos(self):
            self.used_suitable_pos = True
            return object()

        def sizeHint(self):
            class _SizeHint:
                def width(self):
                    return 420

                def height(self):
                    return 84

            return _SizeHint()

        def show(self):
            self.shown = True

        def setContent(self, content):
            self.content = content
            self.contentLabel.setText(content)

    monkeypatch.setattr("ankismart.ui.preview_page.StateToolTip", _TooltipStub)

    page.resize(1200, 800)
    page._show_state_tooltip("正在生成卡片", "这是一个非常长的提示内容" * 8)

    tooltip = page._state_tooltip
    assert tooltip is not None
    assert tooltip.max_width == 960
    assert tooltip.min_width == 720
    assert tooltip.min_height == 96
    assert tooltip.titleLabel.wordWrap() is False
    assert tooltip.contentLabel.wordWrap() is True
    assert tooltip.contentLabel.maximumHeight() <= (
        tooltip.contentLabel.fontMetrics().lineSpacing() * 2
    ) + 6
    assert tooltip.position == (424, 36)
    assert tooltip.used_suitable_pos is False
    assert tooltip.shown is True


def test_generation_warning_publishes_task_warning(monkeypatch):
    main = _make_main_window()
    main.config.language = "zh"
    page = PreviewPage(main)
    events = []

    monkeypatch.setattr(
        "ankismart.ui.preview_page.InfoBar",
        type(
            "_InfoBarStub",
            (),
            {
                "warning": staticmethod(lambda *args, **kwargs: None),
                "success": staticmethod(lambda *args, **kwargs: None),
                "info": staticmethod(lambda *args, **kwargs: None),
                "error": staticmethod(lambda *args, **kwargs: None),
            },
        ),
    )
    monkeypatch.setattr(page, "_publish_task_event", lambda event: events.append(event))

    page._current_task_id = "task-preview"
    page._on_generation_warning("partial result")

    assert events[-1].kind == "warning"
    assert events[-1].stage == "generate"


def test_build_documents_filters_pending_regenerate_source_documents():
    main = _make_main_window()
    page = PreviewPage(main)
    page._documents = [
        _make_doc("a.md", "# A"),
        _make_doc("b.md", "# B"),
    ]
    page._pending_regenerate_request = RegenerateRequest(
        scope="source_document",
        source_documents=["b.md"],
    )

    docs = page._build_documents()

    assert [doc.file_name for doc in docs] == ["b.md"]

def test_sample_error_marks_state_tooltip_failed(monkeypatch):
    main = _make_main_window()
    main.config.language = "zh"
    page = PreviewPage(main)
    calls: list[tuple[bool, str]] = []

    monkeypatch.setattr(
        page,
        "_finish_state_tooltip",
        lambda success, content: calls.append((success, content)),
    )
    monkeypatch.setattr(
        "ankismart.ui.preview_page.build_error_display",
        lambda error, language: {"title": "失败", "content": error},
    )
    monkeypatch.setattr("ankismart.ui.preview_page.InfoBar.error", lambda *args, **kwargs: None)

    page._on_sample_error("boom")

    assert calls == [(False, "样本卡片生成失败")]
