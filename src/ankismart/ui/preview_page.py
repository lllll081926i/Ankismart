from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, PlainTextEdit, PrimaryPushButton, PushButton

from ankismart.core.models import BatchConvertResult, ConvertedDocument

if TYPE_CHECKING:
    from ankismart.ui.main_window import MainWindow


class MarkdownHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Markdown text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._setup_rules()

    def _setup_rules(self):
        """Setup highlighting rules for Markdown syntax."""
        # Heading format
        heading_fmt = QTextCharFormat()
        heading_fmt.setForeground(QColor("#0078D4"))
        heading_fmt.setFontWeight(QFont.Weight.Bold)
        self._rules.append((re.compile(r"^#{1,6}\s+.*$", re.MULTILINE), heading_fmt))

        # Bold format
        bold_fmt = QTextCharFormat()
        bold_fmt.setFontWeight(QFont.Weight.Bold)
        self._rules.append((re.compile(r"\*\*(.+?)\*\*"), bold_fmt))
        self._rules.append((re.compile(r"__(.+?)__"), bold_fmt))

        # Italic format
        italic_fmt = QTextCharFormat()
        italic_fmt.setFontItalic(True)
        self._rules.append((re.compile(r"\*(.+?)\*"), italic_fmt))
        self._rules.append((re.compile(r"_(.+?)_"), italic_fmt))

        # Inline code format
        code_fmt = QTextCharFormat()
        code_fmt.setForeground(QColor("#D73A49"))
        code_fmt.setFontFamily("Consolas")
        self._rules.append((re.compile(r"`([^`]+)`"), code_fmt))

        # Link format
        link_fmt = QTextCharFormat()
        link_fmt.setForeground(QColor("#0366D6"))
        link_fmt.setFontUnderline(True)
        self._rules.append((re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), link_fmt))

        # Image format
        image_fmt = QTextCharFormat()
        image_fmt.setForeground(QColor("#22863A"))
        self._rules.append((re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"), image_fmt))

        # Blockquote format
        quote_fmt = QTextCharFormat()
        quote_fmt.setForeground(QColor("#6A737D"))
        self._rules.append((re.compile(r"^>\s+.*$", re.MULTILINE), quote_fmt))

        # List format
        list_fmt = QTextCharFormat()
        list_fmt.setForeground(QColor("#005A9E"))
        self._rules.append((re.compile(r"^[\*\-\+]\s+.*$", re.MULTILINE), list_fmt))
        self._rules.append((re.compile(r"^\d+\.\s+.*$", re.MULTILINE), list_fmt))

        # Horizontal rule format
        hr_fmt = QTextCharFormat()
        hr_fmt.setForeground(QColor("#E1E4E8"))
        self._rules.append((re.compile(r"^[\*\-_]{3,}$", re.MULTILINE), hr_fmt))

    def highlightBlock(self, text: str):
        """Apply syntax highlighting to a block of text."""
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, fmt)


class PreviewPage(QWidget):
    """Page for previewing and editing converted markdown documents."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.setObjectName("previewPage")
        self._main = main_window
        self._documents: list[ConvertedDocument] = []
        self._edited_content: dict[int, str] = {}
        self._current_index = -1

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Title
        title = BodyLabel()
        title.setText("文档预览与编辑")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(10)

        # Left: File list
        self._file_list = QListWidget()
        self._file_list.setMaximumWidth(250)
        self._file_list.currentRowChanged.connect(self._on_file_switched)
        content_layout.addWidget(self._file_list)

        # Right: Editor
        editor_layout = QVBoxLayout()
        editor_layout.setSpacing(10)

        self._editor = PlainTextEdit()
        self._editor.setPlaceholderText("在此编辑 Markdown 内容...")
        self._highlighter = MarkdownHighlighter(self._editor.document())
        editor_layout.addWidget(self._editor)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self._btn_save = PushButton("保存编辑")
        self._btn_save.clicked.connect(self._save_current_edit)
        button_layout.addWidget(self._btn_save)

        self._btn_generate = PrimaryPushButton("生成卡片")
        self._btn_generate.clicked.connect(self._on_generate_cards)
        button_layout.addWidget(self._btn_generate)

        button_layout.addStretch()
        editor_layout.addLayout(button_layout)

        content_layout.addLayout(editor_layout, stretch=1)
        layout.addLayout(content_layout, stretch=1)

    def load_documents(self, batch_result: BatchConvertResult):
        """Load documents from batch conversion result."""
        self._documents = list(batch_result.documents)
        self._edited_content.clear()
        self._current_index = -1

        # Clear and populate file list
        self._file_list.clear()
        for doc in self._documents:
            self._file_list.addItem(doc.file_name)

        # Show/hide file list based on document count
        if len(self._documents) == 1:
            self._file_list.setVisible(False)
        else:
            self._file_list.setVisible(True)

        # Load first document
        if self._documents:
            self._file_list.setCurrentRow(0)
        else:
            self._editor.clear()

    def _on_file_switched(self, index: int):
        """Handle file selection change."""
        if index < 0 or index >= len(self._documents):
            return

        # Save current edits before switching
        self._save_current_edit()

        # Load new document
        self._current_index = index
        doc = self._documents[index]

        # Load edited content if exists, otherwise original
        if index in self._edited_content:
            content = self._edited_content[index]
        else:
            content = doc.result.content

        self._editor.setPlainText(content)

    def _save_current_edit(self):
        """Save current editor content to edited content dict."""
        if self._current_index < 0 or self._current_index >= len(self._documents):
            return

        current_text = self._editor.toPlainText()
        self._edited_content[self._current_index] = current_text

    def _build_documents(self) -> list[ConvertedDocument]:
        """Build document list with edited content applied."""
        # Save current edit first
        self._save_current_edit()

        result = []
        for i, doc in enumerate(self._documents):
            if i in self._edited_content:
                # Create new document with edited content
                new_doc = ConvertedDocument(
                    result=doc.result.model_copy(
                        update={"content": self._edited_content[i]}
                    ),
                    file_name=doc.file_name,
                )
                result.append(new_doc)
            else:
                result.append(doc)

        return result

    def _on_generate_cards(self):
        """Handle generate cards button click."""
        # Build documents with edits
        documents = self._build_documents()

        # Create new batch result
        batch_result = BatchConvertResult(
            documents=documents,
            errors=[],
        )

        # Update main window batch result
        self._main.batch_result = batch_result

        # Switch to result page for card generation
        if hasattr(self._main, "switch_to_result"):
            self._main.switch_to_result()
