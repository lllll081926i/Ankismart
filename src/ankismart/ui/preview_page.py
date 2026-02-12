from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QMessageBox, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    PlainTextEdit,
    PrimaryPushButton,
    ProgressBar,
    ProgressRing,
    PushButton,
    StateToolTip,
    isDarkTheme,
)

from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.gateway import AnkiGateway
from ankismart.card_gen.llm_client import LLMClient
from ankismart.core.models import BatchConvertResult, ConvertedDocument
from ankismart.ui.workers import BatchGenerateWorker, PushWorker
from ankismart.ui.shortcuts import ShortcutKeys, create_shortcut, get_shortcut_text
from ankismart.ui.utils import ProgressMixin
from ankismart.ui.styles import SPACING_MEDIUM, MARGIN_STANDARD, MARGIN_SMALL

if TYPE_CHECKING:
    from ankismart.ui.main_window import MainWindow


class MarkdownHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Markdown text with theme support."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._setup_rules()

    def _setup_rules(self):
        """Setup highlighting rules for Markdown syntax based on current theme."""
        self._rules.clear()
        is_dark = isDarkTheme()

        # Heading format
        heading_fmt = QTextCharFormat()
        heading_fmt.setForeground(QColor("#60A5FA" if is_dark else "#0078D4"))
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
        code_fmt.setForeground(QColor("#F87171" if is_dark else "#D73A49"))
        code_fmt.setFontFamily("Consolas")
        self._rules.append((re.compile(r"`([^`]+)`"), code_fmt))

        # Link format
        link_fmt = QTextCharFormat()
        link_fmt.setForeground(QColor("#60A5FA" if is_dark else "#0366D6"))
        link_fmt.setFontUnderline(True)
        self._rules.append((re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), link_fmt))

        # Image format
        image_fmt = QTextCharFormat()
        image_fmt.setForeground(QColor("#34D399" if is_dark else "#22863A"))
        self._rules.append((re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"), image_fmt))

        # Blockquote format
        quote_fmt = QTextCharFormat()
        quote_fmt.setForeground(QColor("#9CA3AF" if is_dark else "#6A737D"))
        self._rules.append((re.compile(r"^>\s+.*$", re.MULTILINE), quote_fmt))

        # List format
        list_fmt = QTextCharFormat()
        list_fmt.setForeground(QColor("#60A5FA" if is_dark else "#005A9E"))
        self._rules.append((re.compile(r"^[\*\-\+]\s+.*$", re.MULTILINE), list_fmt))
        self._rules.append((re.compile(r"^\d+\.\s+.*$", re.MULTILINE), list_fmt))

        # Horizontal rule format
        hr_fmt = QTextCharFormat()
        hr_fmt.setForeground(QColor("#4B5563" if is_dark else "#E1E4E8"))
        self._rules.append((re.compile(r"^[\*\-_]{3,}$", re.MULTILINE), hr_fmt))

    def update_theme(self):
        """Update highlighting rules when theme changes."""
        self._setup_rules()
        self.rehighlight()

    def highlightBlock(self, text: str):
        """Apply syntax highlighting to a block of text."""
        for pattern, fmt in self._rules:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                self.setFormat(start, length, fmt)


class PreviewPage(ProgressMixin, QWidget):
    """Page for previewing and editing converted markdown documents."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.setObjectName("previewPage")
        self._main = main_window
        self._documents: list[ConvertedDocument] = []
        self._edited_content: dict[int, str] = {}
        self._current_index = -1
        self._generate_worker = None
        self._push_worker = None
        self._state_tooltip = None

        self._setup_ui()
        self._init_shortcuts()

    def _setup_ui(self):
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD)
        layout.setSpacing(MARGIN_SMALL)

        # Title bar with buttons on the right
        title_bar = QHBoxLayout()
        title_bar.setSpacing(MARGIN_SMALL)

        title = BodyLabel()
        title.setText("文档预览与编辑")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_bar.addWidget(title)

        title_bar.addStretch()

        is_zh = self._main.config.language == "zh"

        save_text = "保存编辑" if is_zh else "Save Edit"
        self._btn_save = PushButton(save_text)
        self._btn_save.clicked.connect(self._save_current_edit)
        title_bar.addWidget(self._btn_save)

        generate_text = "生成卡片" if is_zh else "Generate Cards"
        self._btn_generate = PrimaryPushButton(generate_text)
        self._btn_generate.clicked.connect(self._on_generate_cards)
        title_bar.addWidget(self._btn_generate)

        self._btn_cancel = PushButton("取消")
        self._btn_cancel.setIcon(FIF.CLOSE)
        self._btn_cancel.clicked.connect(self._cancel_generation)
        self._btn_cancel.hide()
        title_bar.addWidget(self._btn_cancel)

        layout.addLayout(title_bar)

        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(MARGIN_SMALL)

        # Left: File list
        self._file_list = QListWidget()
        self._file_list.setMaximumWidth(250)
        self._file_list.currentRowChanged.connect(self._on_file_switched)
        content_layout.addWidget(self._file_list)

        # Right: Editor
        self._editor = PlainTextEdit()
        self._editor.setPlaceholderText("在此编辑 Markdown 内容...")
        self._highlighter = MarkdownHighlighter(self._editor.document())
        content_layout.addWidget(self._editor, 1)  # Add stretch factor to fill space

        layout.addLayout(content_layout, 1)  # Main content takes all available space

        # Progress display
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(MARGIN_SMALL)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(MARGIN_SMALL)

        self._progress_ring = ProgressRing()
        self._progress_ring.setFixedSize(40, 40)
        self._progress_ring.hide()

        self._progress_bar = ProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.hide()

        progress_row.addWidget(self._progress_ring)
        progress_row.addWidget(self._progress_bar, 1)
        progress_layout.addLayout(progress_row)

        self._status_label = BodyLabel()
        self._status_label.setText("")
        self._status_label.setWordWrap(True)
        progress_layout.addWidget(self._status_label)

        layout.addLayout(progress_layout)

    def _init_shortcuts(self):
        """Initialize page-specific keyboard shortcuts."""
        # Ctrl+S: Save edit
        create_shortcut(self, ShortcutKeys.SAVE_EDIT, self._save_current_edit)

        # Ctrl+G: Generate cards
        create_shortcut(self, ShortcutKeys.START_GENERATION, self._on_generate_cards)

    def _update_button_tooltips(self):
        """Update button tooltips with shortcut hints."""
        is_zh = self._main.config.language == "zh"

        save_text = "保存编辑" if is_zh else "Save Edit"
        save_shortcut = get_shortcut_text(ShortcutKeys.SAVE_EDIT, self._main.config.language)
        self._btn_save.setToolTip(f"{save_text} ({save_shortcut})")

        generate_text = "生成卡片" if is_zh else "Generate Cards"
        generate_shortcut = get_shortcut_text(ShortcutKeys.START_GENERATION, self._main.config.language)
        self._btn_generate.setToolTip(f"{generate_text} ({generate_shortcut})")

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
        # Validate configuration
        provider = self._main.config.active_provider
        if not provider:
            QMessageBox.warning(
                self,
                "警告" if self._main.config.language == "zh" else "Warning",
                "请先配置 LLM 提供商" if self._main.config.language == "zh" else "Please configure LLM provider first"
            )
            return

        # Build documents with edits
        documents = self._build_documents()
        if not documents:
            QMessageBox.warning(
                self,
                "警告" if self._main.config.language == "zh" else "Warning",
                "没有可用的文档" if self._main.config.language == "zh" else "No documents available"
            )
            return

        # Get generation config from import page
        generation_config = self._main.import_page.build_generation_config()
        deck_name = self._main.import_page._deck_combo.currentText().strip()
        tags_text = self._main.import_page._tags_input.text().strip()
        tags = [t.strip() for t in tags_text.split(",") if t.strip()]

        if not deck_name:
            QMessageBox.warning(
                self,
                "警告" if self._main.config.language == "zh" else "Warning",
                "请输入牌组名称" if self._main.config.language == "zh" else "Please enter deck name"
            )
            return

        # Show progress
        self._btn_generate.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._btn_cancel.show()
        self._progress_ring.show()
        self._progress_bar.show()
        self._progress_bar.setValue(0)
        self._status_label.setText(
            "正在生成卡片..." if self._main.config.language == "zh" else "Generating cards..."
        )

        # Create LLM client
        llm_client = LLMClient(
            api_key=provider.api_key,
            base_url=provider.base_url,
            model=provider.model,
            rpm_limit=provider.rpm_limit,
            proxy_url=self._main.config.proxy_url,
        )

        # Start generation worker
        self._generate_worker = BatchGenerateWorker(
            documents=documents,
            generation_config=generation_config,
            llm_client=llm_client,
            deck_name=deck_name,
            tags=tags,
            enable_auto_split=self._main.config.enable_auto_split,
            split_threshold=self._main.config.split_threshold,
            config=self._main.config,
        )
        self._generate_worker.progress.connect(self._on_generation_progress)
        self._generate_worker.card_progress.connect(self._on_card_progress)
        self._generate_worker.finished.connect(self._on_generation_finished)
        self._generate_worker.error.connect(self._on_generation_error)
        self._generate_worker.cancelled.connect(self._on_generation_cancelled)
        self._generate_worker.start()

    def _on_generation_progress(self, message: str):
        """Handle generation progress message."""
        self._status_label.setText(message)

    def _on_card_progress(self, current: int, total: int):
        """Handle card generation progress."""
        percentage = int((current / total) * 100) if total > 0 else 0
        self._progress_bar.setValue(percentage)
        self._status_label.setText(
            f"正在生成卡片: {current}/{total} ({percentage}%)"
            if self._main.config.language == "zh"
            else f"Generating cards: {current}/{total} ({percentage}%)"
        )

    def _on_generation_finished(self, cards):
        """Handle generation completion."""
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)

        if not cards:
            QMessageBox.warning(
                self,
                "警告" if self._main.config.language == "zh" else "Warning",
                "没有生成任何卡片" if self._main.config.language == "zh" else "No cards generated"
            )
            return

        self._status_label.setText(
            f"生成完成: {len(cards)} 张卡片"
            if self._main.config.language == "zh"
            else f"Generation completed: {len(cards)} cards"
        )

        # Store cards and start push
        self._main.cards = cards
        self._start_push(cards)

    def _on_generation_error(self, error: str):
        """Handle generation error."""
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)
        self._status_label.setText(
            f"生成失败: {error}" if self._main.config.language == "zh" else f"Generation failed: {error}"
        )
        QMessageBox.critical(
            self,
            "错误" if self._main.config.language == "zh" else "Error",
            error
        )

    def _on_generation_cancelled(self):
        """Handle generation cancellation."""
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)
        self._status_label.setText(
            "生成已取消" if self._main.config.language == "zh" else "Generation cancelled"
        )

        InfoBar.warning(
            title="已取消" if self._main.config.language == "zh" else "Cancelled",
            content="卡片生成已被用户取消" if self._main.config.language == "zh" else "Card generation cancelled by user",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

    def _cancel_generation(self):
        """Cancel the current generation operation."""
        if self._generate_worker and self._generate_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认取消" if self._main.config.language == "zh" else "Confirm Cancel",
                "确定要取消卡片生成吗？" if self._main.config.language == "zh" else "Are you sure you want to cancel card generation?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._generate_worker.cancel()
                self._btn_cancel.setEnabled(False)
                self._status_label.setText(
                    "正在取消..." if self._main.config.language == "zh" else "Cancelling..."
                )
        elif self._push_worker and self._push_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认取消" if self._main.config.language == "zh" else "Confirm Cancel",
                "确定要取消推送操作吗？" if self._main.config.language == "zh" else "Are you sure you want to cancel push operation?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._push_worker.cancel()
                self._btn_cancel.setEnabled(False)
                self._status_label.setText(
                    "正在取消..." if self._main.config.language == "zh" else "Cancelling..."
                )

    def _start_push(self, cards):
        """Start pushing cards to Anki."""
        self._btn_generate.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._btn_cancel.show()
        self._progress_ring.show()
        self._progress_bar.show()
        self._progress_bar.setValue(0)
        self._status_label.setText(
            f"正在推送 {len(cards)} 张卡片到 Anki..."
            if self._main.config.language == "zh"
            else f"Pushing {len(cards)} cards to Anki..."
        )

        # Apply duplicate check settings to cards
        config = self._main.config
        for card in cards:
            if card.options is None:
                from ankismart.core.models import CardOptions
                card.options = CardOptions()
            card.options.allow_duplicate = config.allow_duplicate
            card.options.duplicate_scope = config.duplicate_scope
            card.options.duplicate_scope_options.deck_name = card.deck_name
            card.options.duplicate_scope_options.check_children = False
            card.options.duplicate_scope_options.check_all_models = not config.duplicate_check_model

        # Create gateway
        client = AnkiConnectClient(
            url=config.anki_connect_url,
            api_key=config.anki_connect_key,
            proxy_url=config.proxy_url,
        )
        gateway = AnkiGateway(client)

        # Start push worker
        self._push_worker = PushWorker(
            gateway=gateway,
            cards=cards,
            update_mode=config.last_update_mode or "create_only",
        )
        self._push_worker.progress.connect(self._on_push_progress)
        self._push_worker.finished.connect(self._on_push_finished)
        self._push_worker.error.connect(self._on_push_error)
        self._push_worker.cancelled.connect(self._on_push_cancelled)
        self._push_worker.start()

    def _on_push_progress(self, message: str):
        """Handle push progress message."""
        self._status_label.setText(message)

    def _on_push_finished(self, result):
        """Handle push completion."""
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)

        self._status_label.setText(
            f"推送完成: 成功 {result.succeeded} 张，失败 {result.failed} 张"
            if self._main.config.language == "zh"
            else f"Push completed: {result.succeeded} succeeded, {result.failed} failed"
        )

        # Load result page
        self._main.result_page.load_result(result, self._main.cards)
        self._main.switch_to_result()

    def _on_push_error(self, error: str):
        """Handle push error."""
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)
        self._status_label.setText(
            f"推送失败: {error}" if self._main.config.language == "zh" else f"Push failed: {error}"
        )
        QMessageBox.critical(
            self,
            "错误" if self._main.config.language == "zh" else "Error",
            error
        )

    def _on_push_cancelled(self):
        """Handle push cancellation."""
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)
        self._status_label.setText(
            "推送已取消" if self._main.config.language == "zh" else "Push cancelled"
        )

        InfoBar.warning(
            title="已取消" if self._main.config.language == "zh" else "Cancelled",
            content="卡片推送已被用户取消" if self._main.config.language == "zh" else "Card push cancelled by user",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )


    def retranslate_ui(self):
        """Retranslate UI elements when language changes."""
        is_zh = self._main.config.language == "zh"

        # Update button text
        self._btn_save.setText("保存编辑" if is_zh else "Save Edit")
        self._btn_generate.setText("生成卡片" if is_zh else "Generate Cards")
        self._btn_cancel.setText("取消" if is_zh else "Cancel")

        # Update tooltips with shortcuts
        self._update_button_tooltips()

        # Update editor placeholder
        self._editor.setPlaceholderText(
            "在此编辑 Markdown 内容..." if is_zh else "Edit Markdown content here..."
        )

    def update_theme(self):
        """Update theme-dependent components when theme changes."""
        if self._highlighter:
            self._highlighter.update_theme()

    def closeEvent(self, event):
        """Clean up worker threads before closing."""
        # Stop generate worker if running
        if self._generate_worker and self._generate_worker.isRunning():
            self._generate_worker.cancel()
            self._generate_worker.wait(3000)  # Wait up to 3 seconds
            if self._generate_worker.isRunning():
                self._generate_worker.terminate()
                self._generate_worker.wait()

        # Stop push worker if running
        if self._push_worker and self._push_worker.isRunning():
            self._push_worker.cancel()
            self._push_worker.wait(3000)  # Wait up to 3 seconds
            if self._push_worker.isRunning():
                self._push_worker.terminate()
                self._push_worker.wait()

        event.accept()
