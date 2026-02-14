from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtWidgets import QApplication

from ankismart.core.models import (
    BatchConvertResult,
    ConvertedDocument,
    MarkdownResult,
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


class TestPreviewPageLoadDocuments:
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
