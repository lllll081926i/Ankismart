from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QListWidgetItem, QMessageBox, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    EditableComboBox,
    ExpandLayout,
    FluentIcon as FIF,
    LineEdit,
    ListWidget,
    PrimaryPushButton,
    ProgressRing,
    PushButton,
    RangeSettingCard,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    Slider,
    StateToolTip,
)

from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.gateway import AnkiGateway
from ankismart.card_gen.generator import CardGenerator
from ankismart.card_gen.llm_client import LLMClient
from ankismart.converter.converter import DocumentConverter
from ankismart.core.config import save_config
from ankismart.core.models import BatchConvertResult, ConvertedDocument


class BatchConvertWorker(QThread):
    """Worker thread for batch file conversion."""

    file_progress = Signal(str, int, int)  # filename, current, total
    finished = Signal(object)  # BatchConvertResult
    error = Signal(str)  # Error message

    def __init__(self, file_paths: list[Path], config=None) -> None:
        super().__init__()
        self._file_paths = file_paths
        self._config = config

    def run(self) -> None:
        try:
            documents = []
            errors = []

            for i, file_path in enumerate(self._file_paths, 1):
                self.file_progress.emit(file_path.name, i, len(self._file_paths))
                try:
                    # Create converter with OCR correction if enabled
                    ocr_correction_fn = None
                    if self._config and hasattr(self._config, "ocr_correction") and self._config.ocr_correction:
                        # Get LLM client from active provider
                        provider = self._config.active_provider
                        if provider:
                            llm_client = LLMClient(
                                api_key=provider.api_key,
                                base_url=provider.base_url,
                                model=provider.model,
                            )
                            generator = CardGenerator(llm_client)
                            ocr_correction_fn = generator.correct_ocr_text

                    converter = DocumentConverter(ocr_correction_fn=ocr_correction_fn)
                    result = converter.convert(file_path)
                    documents.append(
                        ConvertedDocument(result=result, file_name=file_path.name)
                    )
                except Exception as e:
                    errors.append(f"{file_path.name}: {str(e)}")

            batch_result = BatchConvertResult(documents=documents, errors=errors)
            self.finished.emit(batch_result)
        except Exception as e:
            self.error.emit(str(e))


class DeckLoaderWorker(QThread):
    """Worker thread for loading deck names from Anki."""

    finished = Signal(list)  # list[str]
    error = Signal(str)  # Error message

    def __init__(self, anki_url: str, anki_key: str = "") -> None:
        super().__init__()
        self._anki_url = anki_url
        self._anki_key = anki_key

    def run(self) -> None:
        try:
            client = AnkiConnectClient(url=self._anki_url, api_key=self._anki_key)
            gateway = AnkiGateway(client)
            decks = gateway.get_deck_names()
            self.finished.emit(decks)
        except Exception as e:
            self.error.emit(str(e))


class DropAreaWidget(QWidget):
    """Widget that accepts drag and drop files."""

    files_dropped = Signal(list)  # list[Path]
    clicked = Signal()  # Signal when clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)  # Show pointer cursor

        # Set a more visible border using QPalette and paintEvent
        self.setAutoFillBackground(False)

    def paintEvent(self, event):
        """Custom paint to draw dashed border."""
        from PySide6.QtGui import QPainter, QPen, QColor
        from PySide6.QtCore import Qt

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw dashed border
        pen = QPen(QColor("#cccccc"), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)

        # Draw rounded rectangle
        rect = self.rect().adjusted(1, 1, -1, -1)  # Adjust for pen width
        painter.drawRoundedRect(rect, 8, 8)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.update()  # Trigger repaint

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.update()  # Trigger repaint

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            file_paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_paths.append(Path(url.toLocalFile()))
            if file_paths:
                self.files_dropped.emit(file_paths)
            event.acceptProposedAction()
        self.update()  # Trigger repaint

    def mousePressEvent(self, event):
        """Handle mouse click to open file dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        """Mouse enter - change border color."""
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Mouse leave - restore border color."""
        self.update()
        super().leaveEvent(event)


class ImportPage(QWidget):
    """File import and configuration page."""

    def __init__(self, main_window):
        super().__init__()
        self._main = main_window
        self._file_paths: list[Path] = []
        self._worker: BatchConvertWorker | None = None
        self._deck_loader: DeckLoaderWorker | None = None
        self._state_tooltip: StateToolTip | None = None

        self.setObjectName("importPage")

        self._init_ui()
        self._load_decks()

    def _init_ui(self):
        """Initialize the user interface."""
        # Main horizontal layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # Left side (50% width) - File selection area
        left_widget = self._create_left_panel()
        main_layout.addWidget(left_widget, 5)  # 50% stretch

        # Right side (50% width) - Configuration area
        right_widget = self._create_right_panel()
        main_layout.addWidget(right_widget, 5)  # 50% stretch

    def _create_left_panel(self) -> QWidget:
        """Create left panel with file selection and list."""
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Drag and drop area - fills entire left panel
        self._drop_area = DropAreaWidget()
        self._drop_area.setObjectName("dropArea")
        self._drop_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._drop_area.files_dropped.connect(self._on_files_dropped)
        self._drop_area.clicked.connect(self._select_files)
        self._drop_area.setStyleSheet("background: transparent;")

        drop_layout = QVBoxLayout(self._drop_area)
        drop_layout.setContentsMargins(20, 20, 20, 20)
        drop_layout.setSpacing(12)

        # Top row: Title and file count
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        title = BodyLabel()
        title.setText("文件选择" if self._main.config.language == "zh" else "File Selection")
        title.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent;")
        top_row.addWidget(title)

        top_row.addStretch()

        # File count label - aligned right
        self._file_count_label = BodyLabel()
        self._file_count_label.setText(
            "已选择 0 个文件" if self._main.config.language == "zh" else "0 files selected"
        )
        self._file_count_label.setStyleSheet("font-size: 12px; color: #999; background: transparent;")
        top_row.addWidget(self._file_count_label)

        drop_layout.addLayout(top_row)

        # Center hint label - shown only when no files
        self._drop_label = BodyLabel()
        self._drop_label.setText(
            "拖拽文件到此处或点击选择文件"
            if self._main.config.language == "zh"
            else "Drag files here or click to select"
        )
        self._drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._drop_label.setStyleSheet("font-size: 16px; color: #ccc; background: transparent;")
        drop_layout.addStretch()
        drop_layout.addWidget(self._drop_label)
        drop_layout.addStretch()

        # File list - takes remaining space
        self._file_list = ListWidget()
        self._file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_list.customContextMenuRequested.connect(self._show_file_context_menu)
        self._file_list.setStyleSheet("background: transparent; border: none;")
        self._file_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._file_list.setMinimumHeight(200)
        self._file_list.setVisible(False)  # Hidden initially
        drop_layout.addWidget(self._file_list, 1)

        # Clear all button at bottom
        self._clear_files_btn = PushButton(
            "清空所有文件" if self._main.config.language == "zh" else "Clear All Files"
        )
        self._clear_files_btn.clicked.connect(self._clear_files)
        self._clear_files_btn.setVisible(False)  # Hidden initially
        drop_layout.addWidget(self._clear_files_btn)

        # Add drop area with stretch factor to fill panel
        layout.addWidget(self._drop_area, 1)

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create right panel with configuration options."""
        # Use ScrollArea for right panel
        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._scroll_widget = QWidget()
        self._scroll_widget.setStyleSheet("background: transparent;")
        scroll.setWidget(self._scroll_widget)

        # Use ExpandLayout for right panel content
        self.expand_layout = ExpandLayout(self._scroll_widget)
        self.expand_layout.setContentsMargins(0, 0, 0, 0)
        self.expand_layout.setSpacing(20)

        # Configuration area (without LLM provider)
        config_group = self._create_config_group()
        self.expand_layout.addWidget(config_group)

        # Strategy configuration group
        strategy_group = self._create_strategy_group()
        self.expand_layout.addWidget(strategy_group)

        # Action buttons
        button_widget = self._create_action_buttons()
        self.expand_layout.addWidget(button_widget)

        # Progress display
        progress_widget = self._create_progress_display()
        self.expand_layout.addWidget(progress_widget)

        return scroll

    def _create_config_group(self) -> SettingCardGroup:
        """Create configuration area using SettingCardGroup."""
        is_zh = self._main.config.language == "zh"

        group = SettingCardGroup(
            "生成配置" if is_zh else "Generation Config",
            self._scroll_widget
        )

        # Target count card
        self._count_card = SettingCard(
            FIF.LABEL,
            "目标卡片数量" if is_zh else "Target Card Count",
            "设置要生成的卡片总数" if is_zh else "Set total number of cards to generate",
            group
        )
        self._total_count_input = LineEdit()
        self._total_count_input.setText("20")
        self._total_count_input.setFixedWidth(100)
        self._count_card.hBoxLayout.addWidget(self._total_count_input)
        self._count_card.hBoxLayout.addSpacing(16)
        group.addSettingCard(self._count_card)

        # Mode combo (for test compatibility)
        self._total_count_mode_combo = ComboBox()
        self._total_count_mode_combo.addItem("custom")
        self._total_count_mode_combo.setCurrentText("custom")
        self._total_count_mode_combo.hide()  # Hidden but accessible for tests

        # Deck name card
        self._deck_card = SettingCard(
            FIF.FOLDER,
            "卡片组名称" if is_zh else "Deck Name",
            "选择或输入 Anki 卡片组名称" if is_zh else "Select or enter Anki deck name",
            group
        )
        self._deck_combo = EditableComboBox()
        self._deck_combo.addItem("Default")
        self._deck_combo.setCurrentText("Default")
        self._deck_card.hBoxLayout.addWidget(self._deck_combo)
        self._deck_card.hBoxLayout.addSpacing(16)
        group.addSettingCard(self._deck_card)

        # Tags card
        self._tags_card = SettingCard(
            FIF.TAG,
            "标签" if is_zh else "Tags",
            "添加标签，用逗号分隔" if is_zh else "Add tags, separated by commas",
            group
        )
        self._tags_input = LineEdit()
        self._tags_input.setPlaceholderText("ankismart")
        if self._main.config.last_tags:
            self._tags_input.setText(self._main.config.last_tags)
        self._tags_card.hBoxLayout.addWidget(self._tags_input)
        self._tags_card.hBoxLayout.addSpacing(16)
        group.addSettingCard(self._tags_card)

        return group

    def _create_strategy_group(self) -> SettingCardGroup:
        """Create strategy configuration group with RangeSettingCards."""
        is_zh = self._main.config.language == "zh"

        group = SettingCardGroup(
            "生成策略" if is_zh else "Generation Strategy",
            self._scroll_widget
        )

        # Strategy options with RangeSettingCards
        strategies = [
            ("basic", "基础问答" if is_zh else "Basic Q&A", "生成基础问答卡片" if is_zh else "Generate basic Q&A cards"),
            ("cloze", "填空题" if is_zh else "Cloze", "生成填空题卡片" if is_zh else "Generate cloze cards"),
            ("concept", "概念解释" if is_zh else "Concept", "生成概念解释卡片" if is_zh else "Generate concept cards"),
            ("key_terms", "关键术语" if is_zh else "Key Terms", "生成关键术语卡片" if is_zh else "Generate key term cards"),
            ("single_choice", "单选题" if is_zh else "Single Choice", "生成单选题卡片" if is_zh else "Generate single choice cards"),
            ("multiple_choice", "多选题" if is_zh else "Multiple Choice", "生成多选题卡片" if is_zh else "Generate multiple choice cards"),
        ]

        self._strategy_sliders: list[tuple[str, Slider, BodyLabel]] = []

        for i, (strategy_id, strategy_name, strategy_desc) in enumerate(strategies):
            # Create a simple SettingCard with slider
            from qfluentwidgets import SettingCard
            card = SettingCard(
                FIF.LABEL,
                strategy_name,
                strategy_desc,
                group
            )

            # Create slider
            slider = Slider(Qt.Orientation.Horizontal, card)
            slider.setRange(0, 100)
            slider.setValue(100 if i == 0 else 0)  # First strategy (basic) defaults to 100%
            slider.setMinimumWidth(200)

            # Create value label
            value_label = BodyLabel()
            value_label.setText(f"{100 if i == 0 else 0}%")
            value_label.setFixedWidth(50)

            # Connect slider to update label
            slider.valueChanged.connect(
                lambda v, lbl=value_label: lbl.setText(f"{v}%")
            )

            # Add slider and label to card layout
            card.hBoxLayout.addWidget(slider)
            card.hBoxLayout.addWidget(value_label)
            card.hBoxLayout.addSpacing(16)

            # Store reference
            self._strategy_sliders.append((strategy_id, slider, value_label))

            # Add card to group
            group.addSettingCard(card)

        return group

    def _create_action_buttons(self) -> QWidget:
        """Create action buttons."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._btn_convert = PrimaryPushButton(
            "开始生成" if self._main.config.language == "zh" else "Start Generation"
        )
        self._btn_convert.clicked.connect(self._start_convert)

        self._btn_clear = PushButton(
            "清除" if self._main.config.language == "zh" else "Clear"
        )
        self._btn_clear.clicked.connect(self._clear_all)

        layout.addWidget(self._btn_convert)
        layout.addWidget(self._btn_clear)
        layout.addStretch()

        return widget

    def _create_progress_display(self) -> QWidget:
        """Create progress display area."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self._progress = ProgressRing()
        self._progress.setFixedSize(40, 40)
        self._progress.hide()

        self._status_label = BodyLabel()
        self._status_label.setText("")
        self._status_label.setWordWrap(True)

        layout.addWidget(self._progress)
        layout.addWidget(self._status_label, 1)

        return widget

    def _on_files_dropped(self, file_paths: list[Path]):
        """Handle files dropped into the drop area."""
        self._add_files(file_paths)

    def _add_files(self, file_paths: list[Path]):
        """Add files to the file list."""
        for file_path in file_paths:
            if file_path not in self._file_paths:
                self._file_paths.append(file_path)
                item = QListWidgetItem(file_path.name)
                item.setData(Qt.ItemDataRole.UserRole, str(file_path))
                self._file_list.addItem(item)

        self._update_file_count()

    def _update_file_count(self):
        """Update file count label and toggle visibility of elements."""
        count = len(self._file_paths)
        self._file_count_label.setText(
            f"已选择 {count} 个文件" if self._main.config.language == "zh" else f"{count} files selected"
        )

        # Show/hide elements based on file presence
        has_files = count > 0
        self._drop_label.setVisible(not has_files)  # Hide hint when files present
        self._file_list.setVisible(has_files)  # Show list when files present
        self._clear_files_btn.setVisible(has_files)  # Show clear button when files present

    def _show_file_context_menu(self, pos):
        """Show context menu for file list."""
        item = self._file_list.itemAt(pos)
        if item:
            from qfluentwidgets import RoundMenu, Action
            menu = RoundMenu(parent=self)
            delete_action = Action(FIF.DELETE, "删除" if self._main.config.language == "zh" else "Delete")
            delete_action.triggered.connect(lambda: self._remove_file_item(item))
            menu.addAction(delete_action)
            menu.exec(self._file_list.mapToGlobal(pos))

    def _remove_file_item(self, item: QListWidgetItem):
        """Remove a file item from the list."""
        file_path_str = item.data(Qt.ItemDataRole.UserRole)
        file_path = Path(file_path_str)

        if file_path in self._file_paths:
            self._file_paths.remove(file_path)

        row = self._file_list.row(item)
        self._file_list.takeItem(row)

        self._update_file_count()

    def _clear_files(self):
        """Clear all files from the list."""
        self._file_paths.clear()
        self._file_list.clear()
        self._update_file_count()

    def _load_decks(self):
        """Load deck names from Anki in background."""
        if self._deck_loader and self._deck_loader.isRunning():
            return

        self._deck_loader = DeckLoaderWorker(
            self._main.config.anki_connect_url,
            self._main.config.anki_connect_key
        )
        self._deck_loader.finished.connect(self._on_decks_loaded)
        self._deck_loader.error.connect(lambda _: None)  # Silently ignore errors
        self._deck_loader.start()

    def _on_decks_loaded(self, decks: list[str]):
        """Handle deck names loaded from Anki."""
        current_text = self._deck_combo.currentText()
        self._deck_combo.clear()

        for deck in decks:
            self._deck_combo.addItem(deck)

        # Restore last deck or current text
        if self._main.config.last_deck and self._main.config.last_deck in decks:
            self._deck_combo.setCurrentText(self._main.config.last_deck)
        elif current_text:
            self._deck_combo.setCurrentText(current_text)

    def _select_files(self):
        """Open file dialog to select files."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "选择文件" if self._main.config.language == "zh" else "Select Files",
            "",
            "All Supported (*.md *.txt *.docx *.pptx *.pdf *.png *.jpg *.jpeg);;All Files (*.*)"
        )

        if file_paths:
            self._add_files([Path(p) for p in file_paths])

    def _start_convert(self):
        """Start batch conversion and generation."""
        # Validation
        if not self._file_paths:
            QMessageBox.warning(
                self,
                "警告" if self._main.config.language == "zh" else "Warning",
                "请先选择文件" if self._main.config.language == "zh" else "Please select files first"
            )
            return

        # Check if OCR models are ready
        if not self._ensure_ocr_models_ready():
            return

        # Validate provider
        provider = self._main.config.active_provider
        if not provider:
            QMessageBox.warning(
                self,
                "警告" if self._main.config.language == "zh" else "Warning",
                "请先配置 LLM 提供商" if self._main.config.language == "zh" else "Please configure LLM provider first"
            )
            return

        # Check API key (except for Ollama)
        if "Ollama" not in provider.name and not provider.api_key.strip():
            QMessageBox.warning(
                self,
                "警告" if self._main.config.language == "zh" else "Warning",
                "请先配置 API Key" if self._main.config.language == "zh" else "Please configure API Key first"
            )
            return

        # Validate deck name
        deck_name = self._deck_combo.currentText().strip()
        if not deck_name:
            QMessageBox.warning(
                self,
                "警告" if self._main.config.language == "zh" else "Warning",
                "请输入卡片组名称" if self._main.config.language == "zh" else "Please enter deck name"
            )
            return

        # Validate strategy mix
        config = self.build_generation_config()
        if not config["strategy_mix"]:
            QMessageBox.warning(
                self,
                "警告" if self._main.config.language == "zh" else "Warning",
                "请至少选择一个生成策略（占比 > 0）"
                if self._main.config.language == "zh"
                else "Please select at least one strategy (ratio > 0)"
            )
            return

        # Save last used values
        self._main.config.last_deck = deck_name
        self._main.config.last_tags = self._tags_input.text()
        save_config(self._main.config)

        # Start worker
        self._btn_convert.setEnabled(False)
        self._progress.show()
        self._status_label.setText(
            "正在转换文件..." if self._main.config.language == "zh" else "Converting files..."
        )

        self._worker = BatchConvertWorker(self._file_paths, self._main.config)
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.finished.connect(self._on_batch_convert_done)
        self._worker.error.connect(self._on_convert_error)
        self._worker.start()

    def _ensure_ocr_models_ready(self) -> bool:
        """Check if OCR models are ready (placeholder for actual implementation)."""
        # This would check if PaddleOCR models are downloaded
        # For now, return True
        return True

    def build_generation_config(self) -> dict:
        """Build generation configuration from UI state."""
        strategy_mix = []
        for strategy_id, slider, _ in self._strategy_sliders:
            ratio = slider.value()
            if ratio > 0:
                strategy_mix.append({"strategy": strategy_id, "ratio": ratio})

        try:
            target_total = int(self._total_count_input.text())
        except ValueError:
            target_total = 20

        return {
            "mode": "mixed",
            "target_total": target_total,
            "strategy_mix": strategy_mix,
        }

    def _on_file_progress(self, filename: str, current: int, total: int):
        """Handle file conversion progress."""
        self._status_label.setText(
            f"正在转换: {filename} ({current}/{total})"
            if self._main.config.language == "zh"
            else f"Converting: {filename} ({current}/{total})"
        )

    def _on_batch_convert_done(self, result: BatchConvertResult):
        """Handle batch conversion completion."""
        self._progress.hide()
        self._btn_convert.setEnabled(True)

        # Show errors if any
        if result.errors:
            error_msg = "\n".join(result.errors)
            QMessageBox.warning(
                self,
                "转换错误" if self._main.config.language == "zh" else "Conversion Errors",
                f"部分文件转换失败:\n{error_msg}"
                if self._main.config.language == "zh"
                else f"Some files failed to convert:\n{error_msg}"
            )

        # Check if we have any successful conversions
        if not result.documents:
            self._status_label.setText(
                "没有成功转换的文件" if self._main.config.language == "zh" else "No files converted successfully"
            )
            return

        # Store result and switch to preview page
        self._main.batch_result = result
        self._status_label.setText(
            f"转换完成: {len(result.documents)} 个文件"
            if self._main.config.language == "zh"
            else f"Conversion completed: {len(result.documents)} files"
        )

        # Switch to preview page
        self._main.switch_to_preview()

    def _on_convert_error(self, error: str):
        """Handle conversion error."""
        self._progress.hide()
        self._btn_convert.setEnabled(True)
        self._status_label.setText(
            f"转换失败: {error}" if self._main.config.language == "zh" else f"Conversion failed: {error}"
        )
        QMessageBox.critical(
            self,
            "错误" if self._main.config.language == "zh" else "Error",
            error
        )

    def _clear_all(self):
        """Clear all selections and inputs."""
        self._clear_files()
        self._status_label.clear()

        # Reset sliders
        for i, (strategy_id, slider, value_label) in enumerate(self._strategy_sliders):
            if i == 0:  # First strategy (basic)
                slider.setValue(100)
                value_label.setText("100%")
            else:
                slider.setValue(0)
                value_label.setText("0%")
