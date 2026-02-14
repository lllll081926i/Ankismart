from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import QHBoxLayout, QListWidget, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    IndeterminateProgressBar,
    MessageBox,
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
from ankismart.core.logging import get_logger
from ankismart.core.models import BatchConvertResult, ConvertedDocument
from ankismart.ui.workers import BatchGenerateWorker, PushWorker
from ankismart.ui.shortcuts import ShortcutKeys, create_shortcut, get_shortcut_text
from ankismart.ui.utils import ProgressMixin, split_tags_text
from ankismart.ui.styles import (
    SPACING_MEDIUM,
    MARGIN_STANDARD,
    MARGIN_SMALL,
    apply_page_title_style,
    get_list_widget_palette,
)

if TYPE_CHECKING:
    from ankismart.ui.main_window import MainWindow

logger = get_logger(__name__)


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
        self._suspend_auto_save = False
        self._generate_worker = None
        self._push_worker = None
        self._sample_worker = None
        self._state_tooltip = None
        self._converting_info_bar = None  # InfoBar for conversion status
        self._pending_files_count = 0  # Track pending files
        self._ready_documents: set[str] = set()  # Track ready document names
        self._total_expected_docs = 0  # Total expected documents

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
        apply_page_title_style(title)
        title_bar.addWidget(title)

        title_bar.addStretch()

        is_zh = self._main.config.language == "zh"

        save_text = "保存编辑" if is_zh else "Save Edit"
        self._btn_save = PushButton(save_text)
        self._btn_save.setEnabled(True)  # Explicitly enable
        self._btn_save.clicked.connect(self._save_current_edit)
        title_bar.addWidget(self._btn_save)

        preview_text = "生成样本卡片" if is_zh else "Preview Sample"
        self._btn_preview = PushButton(preview_text)
        self._btn_preview.setEnabled(True)
        self._btn_preview.clicked.connect(self._on_preview_sample)
        title_bar.addWidget(self._btn_preview)

        generate_text = "开始制作卡片" if is_zh else "Generate Cards"
        self._btn_generate = PrimaryPushButton(generate_text)
        self._btn_generate.setEnabled(True)  # Explicitly enable
        self._btn_generate.clicked.connect(self._on_generate_cards)
        title_bar.addWidget(self._btn_generate)

        layout.addLayout(title_bar)

        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(MARGIN_SMALL)

        # Left column
        self._left_panel = QWidget()
        left_layout = QVBoxLayout(self._left_panel)
        left_layout.setContentsMargins(MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL)
        left_layout.setSpacing(MARGIN_SMALL)

        self._file_list = QListWidget()
        self._file_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._file_list.setWordWrap(False)
        self._file_list.currentRowChanged.connect(self._on_file_switched)
        left_layout.addWidget(self._file_list)
        content_layout.addWidget(self._left_panel, 3)

        # Right column
        self._right_panel = QWidget()
        right_layout = QVBoxLayout(self._right_panel)
        right_layout.setContentsMargins(MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL)
        right_layout.setSpacing(MARGIN_SMALL)

        self._editor = PlainTextEdit()
        self._editor.setPlaceholderText("在此编辑 Markdown 内容...")
        self._editor.textChanged.connect(self._on_editor_text_changed)
        self._highlighter = MarkdownHighlighter(self._editor.document())
        right_layout.addWidget(self._editor, 1)
        content_layout.addWidget(self._right_panel, 7)

        layout.addLayout(content_layout, 1)  # Main content takes all available space

        # Indeterminate progress bar for card generation
        self._progress_bar = IndeterminateProgressBar()
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        """Apply theme-aware styles for Qt widgets in preview page."""
        palette = get_list_widget_palette(dark=isDarkTheme())

        self._file_list.setStyleSheet(
            "QListWidget {"
            f"background-color: {palette.background};"
            f"border: 1px solid {palette.border};"
            "border-radius: 8px;"
            "padding: 8px;"
            "outline: none;"
            "}"
            "QListWidget::item {"
            f"color: {palette.text};"
            "font-size: 15px;"
            "padding: 8px 14px;"
            "border-radius: 6px;"
            "border: none;"
            "margin: 2px 0px;"
            "}"
            "QListWidget::item:hover {"
            f"background-color: {palette.hover};"
            "}"
            "QListWidget::item:selected {"
            f"background-color: {palette.selected_background};"
            f"color: {palette.selected_text};"
            "font-weight: 500;"
            "}"
            "QListWidget::item:selected:hover {"
            f"background-color: {palette.selected_background};"
            "}"
            "QListWidget::item:disabled {"
            f"color: {palette.text_disabled};"
            "}"
        )

        panel_style = (
            f"background-color: {palette.background};"
            f"border: 1px solid {palette.border};"
            "border-radius: 8px;"
        )
        self._left_panel.setStyleSheet(panel_style)
        self._right_panel.setStyleSheet(panel_style)

        self._editor.setStyleSheet(
            "QPlainTextEdit, QTextEdit {"
            f"background-color: {palette.background};"
            f"color: {palette.text};"
            f"border: 1px solid {palette.border};"
            "border-radius: 8px;"
            "padding: 8px;"
            "}"
        )

    def showEvent(self, event):
        """Handle show event to ensure buttons are enabled when page is displayed."""
        super().showEvent(event)
        # Ensure buttons are enabled when page is shown (unless actively processing)
        if not (self._generate_worker and self._generate_worker.isRunning()) and \
           not (self._push_worker and self._push_worker.isRunning()):
            if self._documents:  # Only enable if we have documents
                self._btn_save.setEnabled(True)
                self._btn_generate.setEnabled(True)

    def _hide_progress(self) -> None:
        """Hide all progress indicators (override from ProgressMixin)."""
        if self._progress_bar.isStarted():
            self._progress_bar.stop()
        self._progress_bar.hide()

    def _show_progress(self, message: str = "") -> None:
        """Show progress indicators (override from ProgressMixin)."""
        self._progress_bar.show()
        if not self._progress_bar.isStarted():
            self._progress_bar.start()

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

    def load_documents(self, batch_result: BatchConvertResult, pending_files_count: int = 0, total_expected: int = 0):
        """Load documents from batch conversion result.

        Args:
            batch_result: Batch conversion result with documents
            pending_files_count: Number of files still being converted
            total_expected: Total expected number of documents
        """
        self._documents = list(batch_result.documents)
        self._edited_content.clear()
        self._current_index = -1
        self._pending_files_count = pending_files_count
        self._total_expected_docs = total_expected if total_expected > 0 else len(self._documents)
        self._ready_documents.clear()

        # Mark all loaded documents as ready
        for doc in self._documents:
            self._ready_documents.add(doc.file_name)

        # Clear and populate file list
        self._file_list.clear()
        for doc in self._documents:
            item = self._file_list.addItem(doc.file_name)

        # Add placeholder items for pending documents
        for i in range(pending_files_count):
            item = self._file_list.addItem(f"转换中... ({i+1})")
            # Disable placeholder items
            item_widget = self._file_list.item(len(self._documents) + i)
            if item_widget:
                item_widget.setFlags(item_widget.flags() & ~Qt.ItemFlag.ItemIsEnabled)

        # Always show file list
        self._file_list.setVisible(True)

        # Update UI state
        self._update_ui_state()

        # Load first document
        if self._documents:
            self._file_list.setCurrentRow(0)
        else:
            self._suspend_auto_save = True
            try:
                self._editor.clear()
            finally:
                self._suspend_auto_save = False

    def _on_editor_text_changed(self):
        """Auto-save current document edits while typing."""
        if self._suspend_auto_save:
            return
        self._save_current_edit()

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

        self._suspend_auto_save = True
        try:
            self._editor.setPlainText(content)
        finally:
            self._suspend_auto_save = False

    def _save_current_edit(self):
        """Save current editor content to edited content dict."""
        if self._current_index < 0 or self._current_index >= len(self._documents):
            return

        current_text = self._editor.toPlainText()
        self._edited_content[self._current_index] = current_text

        # Keep in-memory documents and main batch result synchronized.
        original_doc = self._documents[self._current_index]
        if original_doc.result.content != current_text:
            updated_doc = ConvertedDocument(
                result=original_doc.result.model_copy(update={"content": current_text}),
                file_name=original_doc.file_name,
            )
            self._documents[self._current_index] = updated_doc

            batch_result = getattr(self._main, "batch_result", None)
            if batch_result and self._current_index < len(batch_result.documents):
                batch_result.documents[self._current_index] = updated_doc

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

    def _show_converting_info_bar(self, pending_count: int):
        """Show info bar indicating files are still being converted."""
        if self._converting_info_bar is not None:
            # Update existing info bar
            is_zh = self._main.config.language == "zh"
            content = (
                f"还有 {pending_count} 个文件正在转换中，请稍候..."
                if is_zh
                else f"{pending_count} file(s) still converting, please wait..."
            )
            # InfoBar doesn't have update method, so we need to close and recreate
            self._converting_info_bar.close()
            self._converting_info_bar = None

        is_zh = self._main.config.language == "zh"
        title = "文件转换中" if is_zh else "Converting Files"
        content = (
            f"还有 {pending_count} 个文件正在转换中，转换完成后才能开始制作卡片"
            if is_zh
            else f"{pending_count} file(s) still converting. Card generation will be available after conversion completes."
        )

        self._converting_info_bar = InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=False,
            position=InfoBarPosition.TOP,
            duration=-1,  # Don't auto-hide
            parent=self
        )

    def _hide_converting_info_bar(self):
        """Hide the converting info bar."""
        if self._converting_info_bar is not None:
            self._converting_info_bar.close()
            self._converting_info_bar = None

    def _update_ui_state(self):
        """Update UI state based on document readiness."""
        all_ready = len(self._ready_documents) >= self._total_expected_docs

        if all_ready:
            self._hide_converting_info_bar()
            self._btn_generate.setEnabled(True)
        else:
            pending = self._total_expected_docs - len(self._ready_documents)
            self._show_converting_info_bar(pending)
            self._btn_generate.setEnabled(False)

        self._btn_save.setEnabled(True)

    def update_converting_status(self, pending_count: int):
        """Update converting status and enable/disable generate button.

        Args:
            pending_count: Number of files still being converted
        """
        self._pending_files_count = pending_count
        self._update_ui_state()

    def add_converted_document(self, document: ConvertedDocument):
        """Add a newly converted document to the list.

        Args:
            document: The converted document to add
        """
        self._documents.append(document)
        self._ready_documents.add(document.file_name)

        # Find and replace placeholder item
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item and item.text().startswith("转换中..."):
                item.setText(document.file_name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled)
                break
        else:
            # No placeholder found, just add new item
            self._file_list.addItem(document.file_name)

        # Update main batch result
        if hasattr(self._main, 'batch_result') and self._main.batch_result:
            self._main.batch_result.documents.append(document)

        # Update UI state
        self._update_ui_state()

        # Show completion notification
        is_zh = self._main.config.language == "zh"
        InfoBar.success(
            title="文档就绪" if is_zh else "Document Ready",
            content=f"{document.file_name} 已转换完成" if is_zh else f"{document.file_name} converted",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )

    def _on_generate_cards(self):
        """Handle generate cards button click."""
        # Validate configuration
        provider = self._main.config.active_provider
        if not provider:
            InfoBar.warning(
                title="警告" if self._main.config.language == "zh" else "Warning",
                content="请先配置 LLM 提供商" if self._main.config.language == "zh" else "Please configure LLM provider first",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # Build documents with edits
        documents = self._build_documents()
        if not documents:
            InfoBar.warning(
                title="警告" if self._main.config.language == "zh" else "Warning",
                content="没有可用的文档" if self._main.config.language == "zh" else "No documents available",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # Get generation config from import page
        generation_config = self._main.import_page.build_generation_config()
        deck_name = self._main.import_page._deck_combo.currentText().strip()
        tags_text = self._main.import_page._tags_input.text().strip()
        tags = split_tags_text(tags_text)

        if not deck_name:
            InfoBar.warning(
                title="警告" if self._main.config.language == "zh" else "Warning",
                content="请输入牌组名称" if self._main.config.language == "zh" else "Please enter deck name",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # Show progress
        self._btn_generate.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._progress_bar.show()

        # Create LLM client
        llm_client = LLMClient(
            api_key=provider.api_key,
            base_url=provider.base_url,
            model=provider.model,
            rpm_limit=provider.rpm_limit,
            proxy_url=self._main.config.proxy_url,
        )

        # Start generation worker
        self._cleanup_generate_worker()
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
        self._generate_worker.document_completed.connect(self._on_document_completed)
        self._generate_worker.finished.connect(self._on_generation_finished)
        self._generate_worker.error.connect(self._on_generation_error)
        self._generate_worker.cancelled.connect(self._on_generation_cancelled)
        self._generate_worker.start()

    def _on_preview_sample(self):
        """Generate and show sample cards."""
        # Validate configuration
        provider = self._main.config.active_provider
        if not provider:
            InfoBar.warning(
                title="警告" if self._main.config.language == "zh" else "Warning",
                content="请先配置 LLM 提供商" if self._main.config.language == "zh" else "Please configure LLM provider first",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # Check if we have documents
        if not self._documents:
            InfoBar.warning(
                title="警告" if self._main.config.language == "zh" else "Warning",
                content="没有可用的文档" if self._main.config.language == "zh" else "No documents available",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # Use first document for sample
        document = self._documents[0]

        # Get generation config
        generation_config = self._main.import_page.build_generation_config()
        strategy_mix = generation_config.get("strategy_mix", [])

        if not strategy_mix:
            InfoBar.warning(
                title="警告" if self._main.config.language == "zh" else "Warning",
                content="请先配置卡片生成策略" if self._main.config.language == "zh" else "Please configure card generation strategy first",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # Show generating message
        is_zh = self._main.config.language == "zh"
        self._show_info_bar(
            "info",
            "生成中" if is_zh else "Generating",
            "正在生成样本卡片..." if is_zh else "Generating sample cards...",
            duration=2000,
        )

        # Generate sample cards in background
        from PyQt6.QtCore import QThread
        from ankismart.card_gen.llm_client import LLMClient
        from ankismart.card_gen.generator import CardGenerator
        from ankismart.core.models import GenerateRequest

        class SampleGenerateWorker(QThread):
            finished = pyqtSignal(list)
            error = pyqtSignal(str)

            def __init__(self, document, strategies, llm_client, deck_name, tags):
                super().__init__()
                self.document = document
                self.strategies = strategies
                self.llm_client = llm_client
                self.deck_name = deck_name
                self.tags = tags

            def run(self):
                try:
                    generator = CardGenerator(self.llm_client)
                    sample_cards = []

                    # Generate 1 card per strategy (max 5 strategies)
                    for strategy_item in self.strategies[:5]:
                        strategy = strategy_item.get("strategy", "")
                        if not strategy:
                            continue

                        request = GenerateRequest(
                            markdown=self.document.result.content[:5000],  # Use first 5000 chars for speed
                            strategy=strategy,
                            deck_name=self.deck_name,
                            tags=self.tags,
                            trace_id=self.document.result.trace_id,
                            source_path=self.document.result.source_path,
                            target_count=1,  # Only 1 card per strategy
                        )

                        cards = generator.generate(request)
                        sample_cards.extend(cards)

                    self.finished.emit(sample_cards)
                except Exception as e:
                    self.error.emit(str(e))

        # Create LLM client
        llm_client = LLMClient(
            api_key=provider.api_key,
            base_url=provider.base_url,
            model=provider.model,
            rpm_limit=provider.rpm_limit,
            temperature=self._main.config.llm_temperature,
            max_tokens=self._main.config.llm_max_tokens,
            proxy_url=self._main.config.proxy_url,
        )

        # Get deck and tags
        deck_name = self._main.import_page._deck_combo.currentText().strip() or "Default"
        tags_text = self._main.import_page._tags_input.text().strip()
        from ankismart.ui.utils import split_tags_text
        tags = split_tags_text(tags_text)

        # Start worker
        self._cleanup_sample_worker()
        self._sample_worker = SampleGenerateWorker(
            document, strategy_mix, llm_client, deck_name, tags
        )
        self._sample_worker.finished.connect(self._on_sample_finished)
        self._sample_worker.error.connect(self._on_sample_error)
        self._sample_worker.start()

    def _on_sample_finished(self, cards):
        """Handle sample generation completion."""
        self._cleanup_sample_worker()
        is_zh = self._main.config.language == "zh"

        if not cards:
            InfoBar.warning(
                title="警告" if is_zh else "Warning",
                content="未能生成样本卡片" if is_zh else "Failed to generate sample cards",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # Show sample cards in a dialog
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit
        from qfluentwidgets import SubtitleLabel, PushButton

        dialog = QDialog(self)
        dialog.setWindowTitle("样本卡片预览" if is_zh else "Sample Cards Preview")
        dialog.setMinimumSize(600, 400)

        layout = QVBoxLayout(dialog)

        title = SubtitleLabel()
        title.setText(f"生成了 {len(cards)} 张样本卡片" if is_zh else f"Generated {len(cards)} sample cards")
        layout.addWidget(title)

        # Show cards
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)

        card_texts = []
        for i, card in enumerate(cards, 1):
            card_text = f"### 卡片 {i} ({card.card_type})\n\n"
            card_text += f"**正面：**\n{card.front}\n\n"
            card_text += f"**背面：**\n{card.back}\n\n"
            if card.extra:
                card_text += f"**额外信息：**\n{card.extra}\n\n"
            card_text += "---\n\n"
            card_texts.append(card_text)

        text_edit.setMarkdown("\n".join(card_texts))
        layout.addWidget(text_edit)

        # Close button
        close_btn = PushButton("关闭" if is_zh else "Close")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)

        dialog.exec()

    def _on_sample_error(self, error: str):
        """Handle sample generation error."""
        self._cleanup_sample_worker()
        is_zh = self._main.config.language == "zh"
        InfoBar.error(
            title="错误" if is_zh else "Error",
            content=f"生成样本卡片失败：{error}" if is_zh else f"Failed to generate sample cards: {error}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )

    def _show_info_bar(self, level: str, title: str, content: str, duration: int = 3000):
        """Show info bar notification."""
        level_map = {
            "success": InfoBar.success,
            "warning": InfoBar.warning,
            "error": InfoBar.error,
            "info": InfoBar.info,
        }
        show = level_map.get(level, InfoBar.info)
        show(
            title=title,
            content=content,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=self,
        )

    def _show_state_tooltip(self, title: str, content: str) -> None:
        """Show or update workflow state tooltip."""
        if self._state_tooltip is None:
            self._state_tooltip = StateToolTip(title, content, self.window())
            self._state_tooltip.move(self._state_tooltip.getSuitablePos())
            self._state_tooltip.show()
            return

        self._state_tooltip.setContent(content)

    def _finish_state_tooltip(self, success: bool, content: str) -> None:
        """Finish workflow state tooltip and clear reference."""
        if self._state_tooltip is None:
            return

        tooltip = self._state_tooltip
        tooltip.setContent(content)
        tooltip.setState(success)
        self._state_tooltip = None
        if hasattr(tooltip, "deleteLater"):
            tooltip.deleteLater()

    def _cleanup_generate_worker(self) -> None:
        worker = self.__dict__.get("_generate_worker")
        self.__dict__["_generate_worker"] = None
        if worker is not None and hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def _cleanup_push_worker(self) -> None:
        worker = self.__dict__.get("_push_worker")
        self.__dict__["_push_worker"] = None
        if worker is not None and hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def _cleanup_sample_worker(self) -> None:
        worker = self.__dict__.get("_sample_worker")
        self.__dict__["_sample_worker"] = None
        if worker is not None and hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def _on_generation_progress(self, message: str):
        """Handle generation progress message."""
        is_zh = self._main.config.language == "zh"
        self._show_state_tooltip(
            "正在生成卡片" if is_zh else "Generating Cards",
            message,
        )
        logger.info(
            "generation progress",
            extra={"event": "ui.generation.progress", "message_detail": message},
        )

    def _on_card_progress(self, current: int, total: int):
        """Handle card generation progress."""
        if total <= 0:
            return

        is_zh = self._main.config.language == "zh"
        self._show_state_tooltip(
            "正在生成卡片" if is_zh else "Generating Cards",
            f"已生成 {current}/{total} 张卡片" if is_zh else f"Generated {current}/{total} cards",
        )

    def _on_document_completed(self, document_name: str, cards_count: int):
        """Handle document generation completion."""
        is_zh = self._main.config.language == "zh"
        InfoBar.success(
            title="文档完成" if is_zh else "Document Complete",
            content=f"{document_name} 生成了 {cards_count} 张卡片" if is_zh else f"{document_name}: {cards_count} cards generated",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2500,
            parent=self,
        )

    def _on_generation_finished(self, cards):
        """Handle generation completion."""
        self._cleanup_generate_worker()
        is_zh = self._main.config.language == "zh"
        self._finish_state_tooltip(
            True,
            "卡片生成完成" if is_zh else "Card generation completed",
        )
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)

        if not cards:
            InfoBar.warning(
                title="警告" if is_zh else "Warning",
                content="没有生成任何卡片" if is_zh else "No cards generated",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # Show completion notification
        InfoBar.success(
            title="制卡完成" if is_zh else "Generation Complete",
            content=f"成功生成 {len(cards)} 张卡片" if is_zh else f"Generated {len(cards)} cards",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

        # Store cards and switch to card preview page
        self._main.cards = cards
        self._main.card_preview_page.load_cards(cards)
        self._main._switch_page(2)  # Switch to card preview page (index 2)
        logger.info(
            "generation completed",
            extra={"event": "ui.generation.completed", "cards_count": len(cards)},
        )

    def _on_generation_error(self, error: str):
        """Handle generation error."""
        self._cleanup_generate_worker()
        is_zh = self._main.config.language == "zh"
        self._finish_state_tooltip(
            False,
            "卡片生成失败" if is_zh else "Card generation failed",
        )
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)
        InfoBar.error(
            title="错误" if is_zh else "Error",
            content=error,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )
        logger.error(
            "generation failed",
            extra={"event": "ui.generation.failed", "error_detail": error},
        )

    def _on_generation_cancelled(self):
        """Handle generation cancellation."""
        self._cleanup_generate_worker()
        is_zh = self._main.config.language == "zh"
        self._finish_state_tooltip(
            False,
            "已取消生成任务" if is_zh else "Generation cancelled",
        )
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)

        InfoBar.warning(
            title="已取消" if is_zh else "Cancelled",
            content="卡片生成已被用户取消" if is_zh else "Card generation cancelled by user",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

    def _cancel_generation(self):
        """Cancel the current generation operation."""
        if self._generate_worker and self._generate_worker.isRunning():
            w = MessageBox(
                "确认取消" if self._main.config.language == "zh" else "Confirm Cancel",
                "确定要取消卡片生成吗？" if self._main.config.language == "zh" else "Are you sure you want to cancel card generation?",
                self
            )
            if w.exec():
                self._generate_worker.cancel()
        elif self._push_worker and self._push_worker.isRunning():
            w = MessageBox(
                "确认取消" if self._main.config.language == "zh" else "Confirm Cancel",
                "确定要取消推送操作吗？" if self._main.config.language == "zh" else "Are you sure you want to cancel push operation?",
                self
            )
            if w.exec():
                self._push_worker.cancel()

    def _start_push(self, cards):
        """Start pushing cards to Anki."""
        self._btn_generate.setEnabled(False)
        self._btn_save.setEnabled(False)
        self._progress_bar.show()

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
            key=config.anki_connect_key,
            proxy_url=config.proxy_url,
        )
        gateway = AnkiGateway(client)

        # Start push worker
        self._cleanup_push_worker()
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
        is_zh = self._main.config.language == "zh"
        self._show_state_tooltip(
            "正在推送到 Anki" if is_zh else "Pushing to Anki",
            message,
        )

    def _on_push_finished(self, result):
        """Handle push completion."""
        self._cleanup_push_worker()
        is_zh = self._main.config.language == "zh"
        self._finish_state_tooltip(
            True,
            "推送完成" if is_zh else "Push completed",
        )
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)

        # Sync result data without automatic page navigation.
        self._main.result_page.load_result(result, self._main.cards)
        self._main.card_preview_page.load_cards(self._main.cards)

        InfoBar.success(
            title="推送完成" if is_zh else "Push Complete",
            content=(
                "已完成推送，结果页已更新；当前页面保持不跳转。"
                if is_zh
                else "Push completed. Result page is updated and current page stays unchanged."
            ),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3200,
            parent=self,
        )

    def _on_push_error(self, error: str):
        """Handle push error."""
        self._cleanup_push_worker()
        is_zh = self._main.config.language == "zh"
        self._finish_state_tooltip(
            False,
            "推送失败" if is_zh else "Push failed",
        )
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)
        InfoBar.error(
            title="错误" if is_zh else "Error",
            content=error,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )

    def _on_push_cancelled(self):
        """Handle push cancellation."""
        self._cleanup_push_worker()
        is_zh = self._main.config.language == "zh"
        self._finish_state_tooltip(
            False,
            "推送已取消" if is_zh else "Push cancelled",
        )
        self._hide_progress()
        self._btn_generate.setEnabled(True)
        self._btn_save.setEnabled(True)

        InfoBar.warning(
            title="已取消" if is_zh else "Cancelled",
            content="卡片推送已被用户取消" if is_zh else "Card push cancelled by user",
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
        self._btn_generate.setText("开始制作卡片" if is_zh else "Generate Cards")

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
        self._apply_theme_styles()

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

        # Stop sample worker if running
        if self._sample_worker and self._sample_worker.isRunning():
            self._sample_worker.wait(3000)
            if self._sample_worker.isRunning():
                self._sample_worker.terminate()
                self._sample_worker.wait()

        self._cleanup_generate_worker()
        self._cleanup_push_worker()
        self._cleanup_sample_worker()
        if self._state_tooltip is not None and hasattr(self._state_tooltip, "deleteLater"):
            self._state_tooltip.deleteLater()
            self._state_tooltip = None
        super().closeEvent(event)
