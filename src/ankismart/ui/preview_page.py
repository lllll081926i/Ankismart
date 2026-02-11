from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.models import BatchConvertResult, ConvertedDocument
from ankismart.ui.i18n import t
from ankismart.ui.workers import BatchGenerateWorker


# ---------------------------------------------------------------------------
# Markdown syntax highlighter
# ---------------------------------------------------------------------------

class MarkdownHighlighter(QSyntaxHighlighter):
    """Lightweight Markdown syntax highlighter for QPlainTextEdit."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._build_rules()

    def _make_fmt(
        self,
        *,
        color: str | None = None,
        bold: bool = False,
        italic: bool = False,
    ) -> QTextCharFormat:
        fmt = QTextCharFormat()
        if color:
            fmt.setForeground(QColor(color))
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if italic:
            fmt.setFontItalic(True)
        return fmt

    def _build_rules(self) -> None:
        # Headings: lines starting with 1-6 '#'
        self._rules.append((
            re.compile(r"^#{1,6}\s+.+", re.MULTILINE),
            self._make_fmt(color="#007AFF", bold=True),
        ))
        # Bold: **text** or __text__
        self._rules.append((
            re.compile(r"\*\*[^*]+\*\*|__[^_]+__"),
            self._make_fmt(bold=True),
        ))
        # Italic: *text* or _text_
        self._rules.append((
            re.compile(r"(?<!\*)\*(?!\*)[^*]+\*(?!\*)|(?<!_)_(?!_)[^_]+_(?!_)"),
            self._make_fmt(italic=True),
        ))
        # Inline code: `code`
        self._rules.append((
            re.compile(r"`[^`]+`"),
            self._make_fmt(color="#E45649"),
        ))
        # Code fence: ``` lines
        self._rules.append((
            re.compile(r"^```.*$", re.MULTILINE),
            self._make_fmt(color="#999999"),
        ))
        # Links: [text](url)
        self._rules.append((
            re.compile(r"\[[^\]]*\]\([^)]*\)"),
            self._make_fmt(color="#0062CC"),
        ))
        # Images: ![alt](url)
        self._rules.append((
            re.compile(r"!\[[^\]]*\]\([^)]*\)"),
            self._make_fmt(color="#0062CC", italic=True),
        ))
        # Blockquote: lines starting with >
        self._rules.append((
            re.compile(r"^>\s+.*", re.MULTILINE),
            self._make_fmt(color="#666666", italic=True),
        ))
        # Unordered list: lines starting with - or *
        self._rules.append((
            re.compile(r"^[\s]*[-*+]\s+", re.MULTILINE),
            self._make_fmt(color="#007AFF"),
        ))
        # Ordered list: lines starting with number.
        self._rules.append((
            re.compile(r"^[\s]*\d+\.\s+", re.MULTILINE),
            self._make_fmt(color="#007AFF"),
        ))
        # Horizontal rule: --- or *** or ___
        self._rules.append((
            re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE),
            self._make_fmt(color="#999999"),
        ))

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


class PreviewPage(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("page_content")
        self._main = main_window
        self._documents: list[ConvertedDocument] = []
        self._edited_contents: dict[int, str] = {}
        self._current_index: int = -1
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel(t("preview.title"))
        title.setProperty("role", "heading")
        title_row.addWidget(title)
        title_row.addStretch()

        self._btn_generate = QPushButton(t("preview.generate"))
        self._btn_generate.setMinimumHeight(40)
        self._btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_generate.setProperty("role", "primary")
        self._btn_generate.clicked.connect(self._start_generate)
        title_row.addWidget(self._btn_generate)

        self._btn_cancel = QPushButton(t("preview.cancel"))
        self._btn_cancel.setMinimumHeight(40)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.clicked.connect(self._cancel_generate)
        self._btn_cancel.hide()
        title_row.addWidget(self._btn_cancel)

        layout.addLayout(title_row)

        # Content area: file list + editor
        content_row = QHBoxLayout()

        self._file_list = QListWidget()
        self._file_list.setMaximumWidth(200)
        self._file_list.currentRowChanged.connect(self._on_file_switched)
        content_row.addWidget(self._file_list)

        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText(t("preview.editor_placeholder"))
        self._highlighter = MarkdownHighlighter(self._editor.document())
        content_row.addWidget(self._editor, 1)

        layout.addLayout(content_row, 1)

        # Progress bar + status
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: red;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+G"), self, self._start_generate)

    def load_documents(self, batch_result: BatchConvertResult) -> None:
        """Load converted documents into the preview page."""
        self._documents = list(batch_result.documents)
        self._edited_contents.clear()
        self._current_index = -1

        self._file_list.clear()
        self._editor.clear()
        self._error_label.hide()
        self._status_label.setText("")

        for doc in self._documents:
            self._file_list.addItem(doc.file_name)

        # Hide file list when there is only one document
        self._file_list.setVisible(len(self._documents) > 1)

        # Show errors if any
        if batch_result.errors:
            self._error_label.setText(
                t("preview.convert_errors", errors="\n".join(batch_result.errors))
            )
            self._error_label.show()

        # Select the first file
        if self._documents:
            self._file_list.setCurrentRow(0)

    def _on_file_switched(self, new_index: int) -> None:
        """Save current edits and load the newly selected file."""
        if new_index < 0:
            return

        # Save current editor content
        if 0 <= self._current_index < len(self._documents):
            self._edited_contents[self._current_index] = (
                self._editor.toPlainText()
            )

        # Load new file content
        self._current_index = new_index
        content = self._edited_contents.get(
            new_index, self._documents[new_index].result.content
        )
        self._editor.setPlainText(content)

    def _save_current_edit(self) -> None:
        """Persist the editor text for the current index."""
        if 0 <= self._current_index < len(self._documents):
            self._edited_contents[self._current_index] = (
                self._editor.toPlainText()
            )

    def _build_documents(self) -> list[ConvertedDocument]:
        """Return documents with edited markdown content applied."""
        result: list[ConvertedDocument] = []
        for i, doc in enumerate(self._documents):
            content = self._edited_contents.get(i, doc.result.content)
            updated_result = doc.result.model_copy(
                update={"content": content}
            )
            result.append(
                ConvertedDocument(
                    result=updated_result, file_name=doc.file_name
                )
            )
        return result

    def _start_generate(self) -> None:
        if not self._documents:
            QMessageBox.information(self, t("preview.error"), t("preview.no_docs"))
            return

        self._save_current_edit()

        # Read config from import_page
        import_page = self._main.import_page
        deck_name = import_page._deck_combo.currentText()
        tags = [
            tag.strip()
            for tag in import_page._tags_input.text().split(",")
            if tag.strip()
        ]
        generation_config = import_page.build_generation_config()

        documents = self._build_documents()
        config = self._main.config
        requests_config = {
            "deck_name": deck_name,
            "tags": tags,
            **generation_config,
        }

        self._btn_generate.setEnabled(False)
        self._progress.show()
        self._status_label.setText(t("preview.generating_status"))

        worker = BatchGenerateWorker(
            documents,
            requests_config,
            config,
        )
        worker.file_progress.connect(self._on_file_progress)
        worker.finished.connect(self._on_generate_done)
        worker.error.connect(self._on_error)
        worker.start()
        self._worker = worker
        self._btn_cancel.show()

    def _cancel_generate(self) -> None:
        if self._worker and hasattr(self._worker, 'cancel'):
            self._worker.cancel()
        self._btn_cancel.hide()
        self._status_label.setText(t("preview.cancelling"))

    def _on_file_progress(
        self, current: int, total: int, filename: str
    ) -> None:
        self._status_label.setText(
            t("preview.generating", current=current, total=total, filename=filename)
        )

    def _on_generate_done(self, cards: list) -> None:
        self._progress.hide()
        self._btn_generate.setEnabled(True)
        self._btn_cancel.hide()
        self._status_label.setText(t("preview.generated", count=len(cards)))

        self._main.cards = cards
        self._main.switch_to_results()

    def _on_error(self, msg: str) -> None:
        self._progress.hide()
        self._btn_generate.setEnabled(True)
        self._btn_cancel.hide()
        self._status_label.setText("")
        QMessageBox.warning(self, t("preview.error"), msg)

    def cancel_operation(self) -> None:
        """Cancel the current generation if running."""
        if self._worker and self._worker.isRunning():
            if hasattr(self._worker, 'cancel'):
                self._worker.cancel()
            self._status_label.setText(t("preview.cancelled"))
            self._progress.hide()
            self._btn_generate.setEnabled(True)
            if hasattr(self, '_btn_cancel'):
                self._btn_cancel.hide()
