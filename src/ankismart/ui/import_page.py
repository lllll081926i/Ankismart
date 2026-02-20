from __future__ import annotations

import re
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtWidgets import (
    QMessageBox as _QMessageBox,
)
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    EditableComboBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    MessageBox,
    PrimaryPushButton,
    ProgressBar,
    ProgressRing,
    PushButton,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    SimpleCardWidget,
    Slider,
    StateToolTip,
    SubtitleLabel,
    isDarkTheme,
)

from ankismart.core.config import save_config
from ankismart.core.logging import get_logger
from ankismart.core.models import BatchConvertResult, ConvertedDocument
from ankismart.ui.i18n import get_text
from ankismart.ui.shortcuts import ShortcutKeys, create_shortcut, get_shortcut_text
from ankismart.ui.styles import (
    MARGIN_SMALL,
    MARGIN_STANDARD,
    SPACING_LARGE,
    SPACING_MEDIUM,
    SPACING_SMALL,
)
from ankismart.ui.utils import ProgressMixin, split_tags_text
from ankismart.ui.workers import BatchConvertWorker

logger = get_logger(__name__)
# Backward compatibility for tests patching ankismart.ui.import_page.QMessageBox.
QMessageBox = _QMessageBox

_OCR_FILE_SUFFIXES = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tiff",
    ".webp",
}

_RIGHT_OPTION_CARD_MAX_HEIGHT = 92
_RIGHT_CONFIG_GROUP_MAX_HEIGHT = 360
_RIGHT_STRATEGY_GROUP_MAX_HEIGHT = 640

_OCR_CONVERTER_MODULE = None
_DECK_LOADING_ENABLED = False


class OCRRuntimeUnavailableError(RuntimeError):
    """Raised when OCR runtime modules are not bundled."""


_OCR_PRESET_FALLBACK = {
    "lite": {
        "label_zh": "轻量模型",
        "label_en": "Lite",
        "recommended": "8G 内存 / 无独立显卡",
    },
    "standard": {
        "label_zh": "标准模型",
        "label_en": "Standard",
        "recommended": "16G 内存 / 4 核及以上",
    },
    "accuracy": {
        "label_zh": "高精度模型",
        "label_en": "High Accuracy",
        "recommended": "16G+ 内存 / 独立显卡",
    },
}


def _get_ocr_converter_module():
    """Lazy import OCR converter to avoid startup overhead."""
    global _OCR_CONVERTER_MODULE
    if _OCR_CONVERTER_MODULE is None:
        try:
            from ankismart.converter import ocr_converter as module
        except Exception as exc:
            raise OCRRuntimeUnavailableError("OCR runtime is not bundled in this package") from exc

        _OCR_CONVERTER_MODULE = module
    return _OCR_CONVERTER_MODULE


def is_ocr_runtime_available() -> bool:
    try:
        _get_ocr_converter_module()
        return True
    except OCRRuntimeUnavailableError:
        return False


def configure_ocr_runtime(*, model_tier: str, model_source: str, reset_ocr_instance: bool = False) -> None:
    module = _get_ocr_converter_module()
    try:
        module.configure_ocr_runtime(
            model_tier=model_tier,
            model_source=model_source,
            reset_ocr_instance=reset_ocr_instance,
        )
    except TypeError as exc:
        # Backward compatibility: older runtime doesn't accept reset_ocr_instance.
        if "reset_ocr_instance" not in str(exc):
            raise
        module.configure_ocr_runtime(
            model_tier=model_tier,
            model_source=model_source,
        )


def download_missing_ocr_models(*, model_tier: str, model_source: str):
    return _get_ocr_converter_module().download_missing_ocr_models(
        model_tier=model_tier,
        model_source=model_source,
    )


def get_missing_ocr_models(*, model_tier: str, model_source: str):
    return _get_ocr_converter_module().get_missing_ocr_models(
        model_tier=model_tier,
        model_source=model_source,
    )


def get_ocr_model_presets():
    try:
        return _get_ocr_converter_module().get_ocr_model_presets()
    except OCRRuntimeUnavailableError:
        return _OCR_PRESET_FALLBACK


def is_cuda_available(*, force_refresh: bool = False) -> bool:
    try:
        module = _get_ocr_converter_module()
        try:
            return bool(module.is_cuda_available(force_refresh=force_refresh))
        except TypeError as exc:
            if "force_refresh" not in str(exc):
                raise
            return bool(module.is_cuda_available())
    except OCRRuntimeUnavailableError:
        return False


class OCRDownloadConfigDialog(QDialog):
    """Dialog for selecting OCR model tier and download source."""

    def __init__(self, *, language: str, tier: str, source: str, parent=None) -> None:
        super().__init__(parent)
        self._is_zh = language == "zh"
        self._presets = get_ocr_model_presets()

        self.setWindowTitle("选择 OCR 下载配置" if self._is_zh else "Select OCR Download Options")
        self.setMinimumWidth(580)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MEDIUM)
        layout.setContentsMargins(MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD)

        self._model_title = SubtitleLabel("选择 OCR 模型" if self._is_zh else "Select OCR Model")
        layout.addWidget(self._model_title)

        self._model_combo = ComboBox(self)
        self._model_combo.addItem(self._build_tier_text("lite"), userData="lite")
        self._model_combo.addItem(self._build_tier_text("standard"), userData="standard")
        self._model_combo.addItem(self._build_tier_text("accuracy"), userData="accuracy")
        layout.addWidget(self._model_combo)

        self._recommend_label = BodyLabel(self)
        self._recommend_label.setWordWrap(True)
        layout.addWidget(self._recommend_label)

        self._source_title = SubtitleLabel("选择下载源" if self._is_zh else "Select Download Source")
        layout.addWidget(self._source_title)

        self._source_combo = ComboBox(self)
        self._source_combo.addItem(
            "官方地址（HuggingFace）" if self._is_zh else "Official (HuggingFace)",
            userData="official",
        )
        self._source_combo.addItem(
            "国内镜像（ModelScope）" if self._is_zh else "China Mirror (ModelScope)",
            userData="cn_mirror",
        )
        layout.addWidget(self._source_combo)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._set_tier(tier)
        self._set_source(source)
        self._model_combo.currentIndexChanged.connect(lambda _: self._refresh_recommendation())
        self._refresh_recommendation()

    def _build_tier_text(self, tier: str) -> str:
        preset = self._presets.get(tier)
        if not preset:
            return tier

        label = preset.get("label_zh" if self._is_zh else "label_en", tier)
        det = preset.get("det", "unknown")
        rec = preset.get("rec", "unknown")
        if self._is_zh:
            return f"{label}（det: {det} / rec: {rec}）"
        return f"{label} (det: {det} / rec: {rec})"

    def _set_tier(self, tier: str) -> None:
        for index in range(self._model_combo.count()):
            if self._model_combo.itemData(index) == tier:
                self._model_combo.setCurrentIndex(index)
                return
        self._model_combo.setCurrentIndex(0)

    def _set_source(self, source: str) -> None:
        for index in range(self._source_combo.count()):
            if self._source_combo.itemData(index) == source:
                self._source_combo.setCurrentIndex(index)
                return
        self._source_combo.setCurrentIndex(0)

    def _refresh_recommendation(self) -> None:
        tier = self.selected_tier
        preset = self._presets.get(tier, self._presets["lite"])
        if self._is_zh:
            self._recommend_label.setText(f"推荐配置：{preset['recommended']}")
        else:
            self._recommend_label.setText(f"Recommended: {preset['recommended']}")

    @property
    def selected_tier(self) -> str:
        return str(self._model_combo.currentData())

    @property
    def selected_source(self) -> str:
        return str(self._source_combo.currentData())


class _LegacyBatchConvertWorker(QThread):
    """Worker thread for batch file conversion."""

    file_progress = pyqtSignal(str, int, int)  # filename, current, total
    finished = pyqtSignal(object)  # BatchConvertResult
    error = pyqtSignal(str)  # Error message
    cancelled = pyqtSignal()  # Cancellation signal

    def __init__(self, file_paths: list[Path], config=None) -> None:
        super().__init__()
        self._file_paths = file_paths
        self._config = config
        self._cancelled = False

    def cancel(self) -> None:
        """Cancel the conversion operation."""
        self._cancelled = True

    def run(self) -> None:
        try:
            documents = []
            errors = []

            for i, file_path in enumerate(self._file_paths, 1):
                # Check if cancelled
                if self._cancelled:
                    self.cancelled.emit()
                    return

                self.file_progress.emit(file_path.name, i, len(self._file_paths))
                try:
                    # Create converter with OCR correction if enabled
                    ocr_correction_fn = None
                    if self._config and hasattr(self._config, "ocr_correction") and self._config.ocr_correction:
                        # Get LLM client from active provider
                        provider = self._config.active_provider
                        if provider:
                            from ankismart.card_gen.generator import CardGenerator
                            from ankismart.card_gen.llm_client import LLMClient

                            # Validate provider configuration before creating LLMClient
                            if not provider.api_key and "Ollama" not in provider.name:
                                raise ValueError(f"Provider '{provider.name}' requires an API key but none is configured")
                            if not provider.base_url:
                                raise ValueError(f"Provider '{provider.name}' requires a base URL but none is configured")
                            if not provider.model:
                                raise ValueError(f"Provider '{provider.name}' requires a model but none is configured")

                            llm_client = LLMClient(
                                api_key=provider.api_key,
                                base_url=provider.base_url,
                                model=provider.model,
                            )
                            generator = CardGenerator(llm_client)
                            ocr_correction_fn = generator.correct_ocr_text

                    from ankismart.converter.converter import DocumentConverter

                    converter = DocumentConverter(ocr_correction_fn=ocr_correction_fn)
                    result = converter.convert(file_path)
                    documents.append(
                        ConvertedDocument(result=result, file_name=file_path.name)
                    )
                except Exception as e:
                    errors.append(f"{file_path.name}: {str(e)}")

            # Check if cancelled before emitting finished
            if self._cancelled:
                self.cancelled.emit()
                return

            batch_result = BatchConvertResult(documents=documents, errors=errors)
            self.finished.emit(batch_result)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))


class DeckLoaderWorker(QThread):
    """Worker thread for loading deck names from Anki."""

    finished = pyqtSignal(list)  # list[str]
    error = pyqtSignal(str)  # Error message

    def __init__(self, anki_url: str, anki_key: str = "") -> None:
        super().__init__()
        self._anki_url = anki_url
        self._anki_key = anki_key

    def run(self) -> None:
        try:
            # Product decision: stop loading decks in background from Anki.
            if not _DECK_LOADING_ENABLED:
                self.finished.emit([])
                return

            from ankismart.anki_gateway.client import AnkiConnectClient
            from ankismart.anki_gateway.gateway import AnkiGateway

            client = AnkiConnectClient(url=self._anki_url, key=self._anki_key)
            gateway = AnkiGateway(client)
            self.finished.emit(gateway.get_deck_names())
        except Exception as e:
            self.error.emit(str(e))


class OCRModelDownloadWorker(QThread):
    """Worker thread for downloading OCR models."""

    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(list)  # list[str] - downloaded model names
    error = pyqtSignal(str)  # Error message

    def __init__(self, model_tier: str, model_source: str) -> None:
        super().__init__()
        self._model_tier = model_tier
        self._model_source = model_source

    def run(self) -> None:
        try:
            downloaded = download_missing_ocr_models(
                progress_callback=lambda current, total, msg: self.progress.emit(current, total, msg),
                model_tier=self._model_tier,
                model_source=self._model_source,
            )
            self.finished.emit(downloaded)
        except Exception as e:
            self.error.emit(str(e))


class DropAreaWidget(SimpleCardWidget):
    """Widget that accepts drag and drop files using SimpleCardWidget."""

    files_dropped = pyqtSignal(list)  # list[Path]
    clicked = pyqtSignal()  # Signal when clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setBorderRadius(8)

    def dragEnterEvent(self, event: QDragEnterEvent):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.update()  # Trigger repaint

    def dragMoveEvent(self, event):  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):  # noqa: N802
        self.update()  # Trigger repaint

    def dropEvent(self, event: QDropEvent):  # noqa: N802
        if event.mimeData().hasUrls():
            file_paths = []
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_paths.append(Path(url.toLocalFile()))
            if file_paths:
                self.files_dropped.emit(file_paths)
            event.acceptProposedAction()
        self.update()  # Trigger repaint

    def mousePressEvent(self, event):  # noqa: N802
        """Handle mouse click to open file dialog."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def enterEvent(self, event):  # noqa: N802
        """Mouse enter - change border color."""
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        """Mouse leave - restore border color."""
        self.update()
        super().leaveEvent(event)


class ImportPage(ProgressMixin, QWidget):
    """File import and configuration page."""

    def __init__(self, main_window):
        super().__init__()
        self._main = main_window
        self._file_paths: list[Path] = []
        self._file_status: dict[str, str] = {}  # file_name -> status (pending/converting/completed)
        self._worker: BatchConvertWorker | None = None
        self._deck_loader: DeckLoaderWorker | None = None
        self._ocr_download_worker: OCRModelDownloadWorker | None = None
        self._state_tooltip: StateToolTip | None = None
        self._model_check_in_progress = False
        self._auto_generate_after_convert = False  # Flag for auto card generation

        # Lazy-loaded heavy dependencies
        self._converter = None
        self._gateway = None
        self._card_generator = None

        self.setObjectName("importPage")

        self._init_ui()
        self._init_shortcuts()

    def _init_ui(self):
        """Initialize the user interface."""
        # Main horizontal layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD)
        main_layout.setSpacing(SPACING_LARGE)

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

        drop_layout = QVBoxLayout(self._drop_area)
        drop_layout.setContentsMargins(MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD)
        drop_layout.setSpacing(SPACING_MEDIUM)

        # Top row: Title and file count
        top_row = QHBoxLayout()
        top_row.setSpacing(MARGIN_SMALL)

        title = SubtitleLabel()
        title.setText("文件选择" if self._main.config.language == "zh" else "File Selection")
        top_row.addWidget(title)

        top_row.addStretch()

        # File count label - aligned right
        self._file_count_label = BodyLabel()
        self._file_count_label.setText(
            "已选择 0 个文件" if self._main.config.language == "zh" else "0 files selected"
        )
        top_row.addWidget(self._file_count_label)

        drop_layout.addLayout(top_row)

        # Center hint label - shown only when no files
        self._drop_label = SubtitleLabel()
        self._drop_label.setText(
            "拖拽文件到此处或点击选择文件"
            if self._main.config.language == "zh"
            else "Drag files here or click to select"
        )
        self._drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_layout.addStretch()
        drop_layout.addWidget(self._drop_label)
        drop_layout.addStretch()

        # File list - takes remaining space
        self._file_list = ListWidget()
        self._file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._file_list.customContextMenuRequested.connect(self._show_file_context_menu)
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
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Keep right panel adaptive while hiding visible scrollbars
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Remove gray background - make transparent
        scroll.setStyleSheet("""
            ScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                width: 0px;
                height: 0px;
                background: transparent;
                border: none;
            }
            ScrollBar:vertical, ScrollBar:horizontal {
                width: 0px;
                height: 0px;
                background: transparent;
                border: none;
            }
        """)

        self._scroll_widget = QWidget()
        self._scroll_widget.setStyleSheet("background-color: transparent;")
        scroll.setWidget(self._scroll_widget)

        # Use standard vertical layout for right panel content
        # NOTE: ExpandLayout may not handle custom container widgets reliably here.
        self.expand_layout = QVBoxLayout(self._scroll_widget)
        self.expand_layout.setContentsMargins(0, 0, 0, 0)
        self.expand_layout.setSpacing(SPACING_MEDIUM)

        # Configuration area (without LLM provider)
        config_group = self._create_config_group()
        self.expand_layout.addWidget(config_group)

        # Strategy configuration group
        strategy_group = self._create_strategy_group()
        self.expand_layout.addWidget(strategy_group)

        # Progress display
        progress_widget = self._create_progress_display()
        progress_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.expand_layout.addWidget(progress_widget)
        self.expand_layout.addStretch(1)

        return scroll

    def _create_config_group(self) -> QWidget:
        """Create configuration area with custom title bar."""
        is_zh = self._main.config.language == "zh"

        # Container widget
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(SPACING_SMALL)

        # Custom title bar with button
        title_bar = QWidget()
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setSpacing(SPACING_SMALL)

        title_label = SubtitleLabel("生成配置" if is_zh else "Generation Config")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()

        self._btn_generate_cards = PrimaryPushButton(
            "开始生成卡片" if is_zh else "Generate Cards"
        )
        self._btn_generate_cards.setIcon(FluentIcon.SEND)
        self._btn_generate_cards.setFixedHeight(32)
        self._btn_generate_cards.setMinimumWidth(140)
        self._btn_generate_cards.clicked.connect(self._start_generate_cards)
        title_bar_layout.addWidget(self._btn_generate_cards)

        # Keep compatibility with existing generation flow handlers.
        self._btn_convert = self._btn_generate_cards

        container_layout.addWidget(title_bar)

        # Create compact settings container (no extra group title gap)
        group = QWidget(container)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(2)
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        group.setMaximumHeight(_RIGHT_CONFIG_GROUP_MAX_HEIGHT)

        # Target count card
        self._count_card = SettingCard(
            FluentIcon.LABEL,
            "目标卡片数量" if is_zh else "Target Card Count",
            "设置要生成的卡片总数" if is_zh else "Set total number of cards to generate",
            group
        )
        self._total_count_input = LineEdit()
        self._total_count_input.setText("20")
        self._total_count_input.setMinimumWidth(100)
        self._total_count_input.setPlaceholderText(
            get_text("import.card_count_placeholder", self._main.config.language)
        )
        self._total_count_input.setToolTip(
            get_text("import.card_count_tooltip", self._main.config.language)
        )
        self._count_card.hBoxLayout.addWidget(self._total_count_input)
        self._count_card.hBoxLayout.addSpacing(16)
        self._count_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._count_card.setMaximumHeight(_RIGHT_OPTION_CARD_MAX_HEIGHT)
        group_layout.addWidget(self._count_card)

        # Mode combo (for test compatibility)
        self._total_count_mode_combo = ComboBox()
        self._total_count_mode_combo.addItem("custom")
        self._total_count_mode_combo.setCurrentText("custom")
        self._total_count_mode_combo.hide()  # Hidden but accessible for tests

        # Deck name card
        self._deck_card = SettingCard(
            FluentIcon.FOLDER,
            "卡片组名称" if is_zh else "Deck Name",
            "选择或输入 Anki 卡片组名称" if is_zh else "Select or enter Anki deck name",
            group
        )
        self._deck_combo = EditableComboBox()
        initial_deck = self._resolve_initial_deck_name()
        self._deck_combo.addItem(initial_deck)
        self._deck_combo.setCurrentText(initial_deck)
        self._deck_combo.setPlaceholderText(
            get_text("import.deck_name_placeholder", self._main.config.language)
        )
        self._deck_combo.setToolTip(
            get_text("import.deck_name_tooltip", self._main.config.language)
        )
        self._deck_card.hBoxLayout.addWidget(self._deck_combo)
        self._deck_card.hBoxLayout.addSpacing(16)
        self._deck_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._deck_card.setMaximumHeight(_RIGHT_OPTION_CARD_MAX_HEIGHT)
        group_layout.addWidget(self._deck_card)

        # Tags card
        self._tags_card = SettingCard(
            FluentIcon.TAG,
            "标签" if is_zh else "Tags",
            "添加标签，用逗号分隔" if is_zh else "Add tags, separated by commas",
            group
        )
        self._tags_input = LineEdit()
        self._tags_input.setPlaceholderText(
            get_text("import.tags_placeholder", self._main.config.language)
        )
        self._tags_input.setToolTip(
            get_text("import.tags_tooltip", self._main.config.language)
        )
        self._tags_input.setMinimumWidth(320)
        self._tags_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if self._main.config.last_tags:
            self._tags_input.setText(self._main.config.last_tags)
        self._tags_card.hBoxLayout.addWidget(self._tags_input)
        self._tags_card.hBoxLayout.addSpacing(16)
        self._tags_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._tags_card.setMaximumHeight(_RIGHT_OPTION_CARD_MAX_HEIGHT)
        group_layout.addWidget(self._tags_card)

        container_layout.addWidget(group)
        return container

    def _resolve_initial_deck_name(self) -> str:
        last_deck = (self._main.config.last_deck or "").strip()
        if last_deck:
            return last_deck

        default_deck = (self._main.config.default_deck or "").strip()
        if default_deck:
            return default_deck

        return "Default"

    def _create_strategy_group(self) -> SettingCardGroup:
        """Create strategy configuration group with RangeSettingCards."""
        is_zh = self._main.config.language == "zh"

        group = SettingCardGroup(
            "生成策略" if is_zh else "Generation Strategy",
            self._scroll_widget
        )
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        group.setMaximumHeight(_RIGHT_STRATEGY_GROUP_MAX_HEIGHT)

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
                FluentIcon.LABEL,
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
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            card.setMaximumHeight(_RIGHT_OPTION_CARD_MAX_HEIGHT)

            # Store reference
            self._strategy_sliders.append((strategy_id, slider, value_label))

            # Add card to group
            group.addSettingCard(card)

        return group

    def _get_converter(self):
        """获取或创建文档转换器（懒加载）"""
        if self._converter is None:
            from ankismart.converter.converter import DocumentConverter
            self._converter = DocumentConverter(
                ocr_correction_enabled=self._main.config.ocr_correction_enabled,
                ocr_correction_provider=self._main.config.ocr_correction_provider,
                llm_providers=self._main.config.llm_providers,
            )
        return self._converter

    def _get_gateway(self):
        """获取或创建 Anki 网关（懒加载）"""
        if self._gateway is None:
            from ankismart.anki_gateway.client import AnkiConnectClient
            from ankismart.anki_gateway.gateway import AnkiGateway
            client = AnkiConnectClient(
                url=self._main.config.anki_connect_url,
                key=self._main.config.anki_connect_key,
            )
            self._gateway = AnkiGateway(client)
        return self._gateway

    def _get_card_generator(self):
        """获取或创建卡片生成器（懒加载）"""
        if self._card_generator is None:
            from ankismart.card_gen.generator import CardGenerator
            from ankismart.card_gen.llm_client import LLMClient
            llm_client = LLMClient(
                provider=self._main.config.card_gen_provider,
                llm_providers=self._main.config.llm_providers,
            )
            self._card_generator = CardGenerator(llm_client)
        return self._card_generator

    def _init_shortcuts(self):
        """Initialize page-specific keyboard shortcuts."""
        # Ctrl+O: Open files
        create_shortcut(self, ShortcutKeys.OPEN_FILE, self._select_files)

        # Ctrl+G: Start generation
        create_shortcut(self, ShortcutKeys.START_GENERATION, self._start_convert)

    def _create_top_buttons(self) -> QWidget:
        """Create top-right button row."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(MARGIN_SMALL)

        is_zh = self._main.config.language == "zh"

        layout.addStretch()  # Push buttons to right

        self._btn_load_example = PushButton(
            "加载示例" if is_zh else "Load Example"
        )
        self._btn_load_example.setIcon(FluentIcon.DOCUMENT)
        self._btn_load_example.clicked.connect(self._load_example)

        self._btn_recommend = PushButton(
            "推荐策略" if is_zh else "Recommend Strategy"
        )
        self._btn_recommend.setIcon(FluentIcon.ROBOT)
        self._btn_recommend.clicked.connect(self._recommend_strategy)

        layout.addWidget(self._btn_load_example)
        layout.addWidget(self._btn_recommend)

        return widget

    def _create_bottom_buttons(self) -> QWidget:
        """Create bottom action buttons."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(MARGIN_SMALL)

        is_zh = self._main.config.language == "zh"

        # Add shortcut hints to button tooltips
        start_text = "开始生成" if is_zh else "Start Generation"
        start_shortcut = get_shortcut_text(ShortcutKeys.START_GENERATION, self._main.config.language)

        self._btn_convert = PrimaryPushButton(start_text)
        self._btn_convert.setToolTip(f"{start_text} ({start_shortcut})")
        self._btn_convert.clicked.connect(self._start_convert)

        self._btn_clear = PushButton(
            "清除" if is_zh else "Clear"
        )
        self._btn_clear.clicked.connect(self._clear_all)

        layout.addWidget(self._btn_convert)
        layout.addWidget(self._btn_clear)
        layout.addStretch()

        return widget

    def _set_generate_actions_enabled(self, enabled: bool) -> None:
        """Toggle both generation entry buttons together."""
        self._btn_convert.setEnabled(enabled)
        btn_generate_cards = self.__dict__.get("_btn_generate_cards")
        if btn_generate_cards is not None:
            btn_generate_cards.setEnabled(enabled)


    def _create_progress_display(self) -> QWidget:
        """Create progress display area."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(MARGIN_SMALL)

        # Progress bar with percentage
        progress_row = QHBoxLayout()
        progress_row.setSpacing(MARGIN_SMALL)

        self._progress_bar = ProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setValue(0)
        self._progress_bar.hide()

        self._progress_ring = ProgressRing()
        self._progress_ring.setFixedSize(40, 40)
        self._progress_ring.hide()

        progress_row.addWidget(self._progress_ring)
        progress_row.addWidget(self._progress_bar, 1)

        layout.addLayout(progress_row)

        # Status label and cancel button row
        status_row = QHBoxLayout()
        status_row.setSpacing(MARGIN_SMALL)

        self._status_label = BodyLabel()
        self._status_label.setText("")
        self._status_label.setWordWrap(True)

        self._btn_cancel = PushButton(
            "取消" if self._main.config.language == "zh" else "Cancel"
        )
        self._btn_cancel.setIcon(FluentIcon.CLOSE)
        self._btn_cancel.clicked.connect(self._cancel_operation)
        self._btn_cancel.hide()

        status_row.addWidget(self._status_label, 1)
        status_row.addWidget(self._btn_cancel)

        layout.addLayout(status_row)

        return widget

    def _on_files_dropped(self, file_paths: list[Path]):
        """Handle files dropped into the drop area."""
        self._add_files(file_paths)

    def _add_files(self, file_paths: list[Path]):
        """Add files to the file list."""
        for file_path in file_paths:
            if file_path not in self._file_paths:
                self._file_paths.append(file_path)
                self._file_status[file_path.name] = "pending"
                item = QListWidgetItem(file_path.name)
                item.setData(Qt.ItemDataRole.UserRole, str(file_path))
                # Pending items use muted color and must stay theme-aware.
                item.setForeground(self._get_pending_item_color())
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
            from qfluentwidgets import Action, RoundMenu
            menu = RoundMenu(parent=self)
            delete_action = Action(FluentIcon.DELETE, "删除" if self._main.config.language == "zh" else "Delete")
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
        if not _DECK_LOADING_ENABLED:
            self._cleanup_deck_loader_worker()
            return

        if self._deck_loader and self._deck_loader.isRunning():
            return

        self._cleanup_deck_loader_worker()
        self._deck_loader = DeckLoaderWorker(
            self._main.config.anki_connect_url,
            self._main.config.anki_connect_key
        )
        self._deck_loader.finished.connect(self._on_decks_loaded)
        self._deck_loader.error.connect(self._on_decks_load_error)
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
        self._cleanup_deck_loader_worker()

    def _on_decks_load_error(self, error: str):
        """Handle deck loading error and release worker reference."""
        is_zh = self._main.config.language == "zh"
        InfoBar.warning(
            title="牌组加载失败" if is_zh else "Failed to Load Decks",
            content=f"无法从 Anki 读取牌组：{error}" if is_zh else f"Unable to load decks from Anki: {error}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3500,
            parent=self,
        )
        self._cleanup_deck_loader_worker()

    def _cleanup_batch_worker(self) -> None:
        worker = self.__dict__.get("_worker")
        if worker is None:
            return
        if hasattr(worker, "isRunning") and worker.isRunning():
            if hasattr(worker, "cancel"):
                worker.cancel()
            worker.wait(200)
            if worker.isRunning():
                return
        self.__dict__["_worker"] = None
        if hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def _cleanup_ocr_download_worker(self) -> None:
        worker = self.__dict__.get("_ocr_download_worker")
        if worker is None:
            return
        if hasattr(worker, "isRunning") and worker.isRunning():
            worker.wait(200)
            if worker.isRunning():
                return
        self.__dict__["_ocr_download_worker"] = None
        if hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def _cleanup_deck_loader_worker(self) -> None:
        worker = self.__dict__.get("_deck_loader")
        if worker is None:
            return
        if hasattr(worker, "isRunning") and worker.isRunning():
            worker.wait(200)
            if worker.isRunning():
                return
        self.__dict__["_deck_loader"] = None
        if hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def _dispose_state_tooltip(self) -> None:
        tooltip = self.__dict__.get("_state_tooltip")
        self.__dict__["_state_tooltip"] = None
        if tooltip is not None and hasattr(tooltip, "deleteLater"):
            tooltip.deleteLater()

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

    def _validate_card_count(self, count_str: str) -> tuple[bool, int | None, str | None]:
        """Validate target card count input.

        Returns:
            Tuple of (is_valid, value, error_message)
        """
        is_zh = self._main.config.language == "zh"

        # Check if it's a valid integer
        try:
            count = int(count_str)
        except ValueError:
            return (
                False,
                None,
                get_text("import.card_count_must_be_number", is_zh)
            )

        # Check range (1-1000)
        if count < 1 or count > 1000:
            return (
                False,
                None,
                get_text("import.card_count_out_of_range", is_zh)
            )

        return (True, count, None)

    def _validate_tags(self, tags_str: str) -> tuple[bool, str | None]:
        """Validate tags format.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not tags_str.strip():
            return (True, None)  # Empty tags are allowed

        is_zh = self._main.config.language == "zh"

        # Split by comma and validate each tag
        tags = split_tags_text(tags_str)

        # Pattern: letters, numbers, Chinese characters, underscores, hyphens
        tag_pattern = re.compile(r'^[\w\u4e00-\u9fff-]+$')

        for tag in tags:
            if tag and not tag_pattern.match(tag):
                return (
                    False,
                    get_text("import.tags_contain_invalid_chars", is_zh)
                )

        return (True, None)

    def _validate_deck_name(self, deck_name: str) -> tuple[bool, str | None]:
        """Validate deck name.

        Returns:
            Tuple of (is_valid, error_message)
        """
        is_zh = self._main.config.language == "zh"

        # Check if empty
        if not deck_name.strip():
            return (
                False,
                get_text("import.deck_name_empty", is_zh)
            )

        # Check for invalid characters: < > : " / \ | ? *
        invalid_chars = r'[<>:"/\\|?*]'
        if re.search(invalid_chars, deck_name):
            return (
                False,
                get_text("import.deck_name_invalid_chars", is_zh)
            )

        return (True, None)

    @staticmethod
    def _is_ocr_file(file_path: Path) -> bool:
        return file_path.suffix.lower() in _OCR_FILE_SUFFIXES

    def _files_need_ocr(self) -> bool:
        return any(self._is_ocr_file(path) for path in self._file_paths)

    def _persist_ocr_config_updates(self, **updates) -> None:
        config = self._main.config.model_copy(update=updates)
        apply_runtime = getattr(self._main, "apply_runtime_config", None)
        if callable(apply_runtime):
            apply_runtime(config, persist=True)
            return
        self._main.config = config
        save_config(config)

    def _apply_cuda_strategy_once(self) -> None:
        config = self._main.config
        if getattr(config, "ocr_cuda_checked_once", False):
            return

        has_cuda = is_cuda_available(force_refresh=True)
        updates: dict[str, object] = {"ocr_cuda_checked_once": True}

        if (
            has_cuda
            and getattr(config, "ocr_auto_cuda_upgrade", True)
            and not getattr(config, "ocr_model_locked_by_user", False)
            and getattr(config, "ocr_model_tier", "lite") == "lite"
        ):
            updates["ocr_model_tier"] = "standard"
            self._persist_ocr_config_updates(**updates)
            is_zh = self._main.config.language == "zh"
            InfoBar.success(
                title="检测到 CUDA" if is_zh else "CUDA Detected",
                content=(
                    "已检测到 CUDA 环境，OCR 模型已自动切换为「标准」档。"
                    if is_zh
                    else "CUDA detected. OCR model tier is automatically switched to Standard."
                ),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        self._persist_ocr_config_updates(**updates)

    def _prepare_local_ocr_runtime(self) -> bool:
        is_zh = self._main.config.language == "zh"
        if getattr(self._main.config, "ocr_mode", "local") == "cloud":
            InfoBar.info(
                title="云端 OCR 开发中" if is_zh else "Cloud OCR In Development",
                content=(
                    "云端 OCR 仍在开发中，请切换到本地 OCR 后再处理图片/PDF。"
                    if is_zh
                    else "Cloud OCR is still in development. Please switch to local OCR for image/PDF files."
                ),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

        if not is_ocr_runtime_available():
            InfoBar.warning(
                title="OCR 不可用" if is_zh else "OCR Unavailable",
                content=(
                    "当前安装包未包含 OCR 运行时，请使用完整版安装包。"
                    if is_zh
                    else "This package does not include OCR runtime. Please use the full package."
                ),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False

        self._apply_cuda_strategy_once()
        configure_ocr_runtime(
            model_tier=getattr(self._main.config, "ocr_model_tier", "lite"),
            model_source=getattr(self._main.config, "ocr_model_source", "official"),
        )
        return True

    def _start_generate_cards(self):
        """Start the full card generation workflow: convert files then generate cards."""
        # First check if we have files
        if not self._file_paths:
            InfoBar.warning(
                title="警告" if self._main.config.language == "zh" else "Warning",
                content="请先选择要转换的文件" if self._main.config.language == "zh" else "Please select files to convert first",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Set flag to auto-generate cards after conversion
        self._auto_generate_after_convert = True

        # Start conversion
        self._start_convert()

    def _start_convert(self):
        """Start batch conversion and generation."""
        is_zh = self._main.config.language == "zh"

        # Validation: Files
        if not self._file_paths:
            InfoBar.warning(
                title=get_text("import.warning", is_zh),
                content=get_text("import.please_select_files", is_zh),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Validation: Target card count
        is_valid, count_value, error_msg = self._validate_card_count(self._total_count_input.text())
        if not is_valid:
            InfoBar.warning(
                title=get_text("import.invalid_card_count", is_zh),
                content=error_msg,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            if hasattr(self._total_count_input, "setFocus"):
                self._total_count_input.setFocus()
            return

        # Validation: Tags format
        is_valid, error_msg = self._validate_tags(self._tags_input.text())
        if not is_valid:
            InfoBar.warning(
                title=get_text("import.invalid_tags", is_zh),
                content=error_msg,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            if hasattr(self._tags_input, "setFocus"):
                self._tags_input.setFocus()
            return

        # Validation: Deck name
        deck_name = self._deck_combo.currentText().strip()
        is_valid, error_msg = self._validate_deck_name(deck_name)
        if not is_valid:
            InfoBar.warning(
                title=get_text("import.invalid_deck_name", is_zh),
                content=error_msg,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            if hasattr(self._deck_combo, "setFocus"):
                self._deck_combo.setFocus()
            return

        # Check OCR runtime and model availability only when OCR-required files exist
        if self._files_need_ocr():
            if not self._prepare_local_ocr_runtime():
                return

            if not self._ensure_ocr_models_ready():
                return

        # Validate provider
        provider = self._main.config.active_provider
        if not provider:
            InfoBar.warning(
                title=get_text("import.warning", is_zh),
                content=get_text("import.please_configure_provider", is_zh),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Check API key (except for Ollama)
        if "Ollama" not in provider.name and not provider.api_key.strip():
            InfoBar.warning(
                title=get_text("import.warning", is_zh),
                content=get_text("import.please_configure_api_key", is_zh),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Validate strategy mix
        config = self.build_generation_config()
        if not config["strategy_mix"]:
            InfoBar.warning(
                title=get_text("import.warning", is_zh),
                content=get_text("import.please_select_strategy", is_zh),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Save last used values
        self._main.config.last_deck = deck_name
        self._main.config.last_tags = self._tags_input.text()
        save_config(self._main.config)

        # Start worker
        self._set_generate_actions_enabled(False)
        self._progress_ring.show()
        self._progress_bar.show()
        self._progress_bar.setValue(0)
        self._btn_cancel.show()
        self._status_label.setText(
            "正在转换文件..." if self._main.config.language == "zh" else "Converting files..."
        )

        self._cleanup_batch_worker()
        self._worker = BatchConvertWorker(self._file_paths, self._main.config)
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.file_completed.connect(self._on_file_completed)
        self._worker.page_progress.connect(self._on_page_progress)
        self._worker.finished.connect(self._on_batch_convert_done)
        self._worker.error.connect(self._on_convert_error)
        self._worker.cancelled.connect(self._on_operation_cancelled)
        self._worker.start()

    def _ensure_ocr_models_ready(self) -> bool:
        """Check if OCR models are ready and download if necessary."""
        # Prevent multiple simultaneous checks
        if self._model_check_in_progress:
            return False

        current_tier = getattr(self._main.config, "ocr_model_tier", "lite")
        current_source = getattr(self._main.config, "ocr_model_source", "official")

        configure_ocr_runtime(model_tier=current_tier, model_source=current_source)

        # Check if models are missing
        missing_models = get_missing_ocr_models(
            model_tier=current_tier,
            model_source=current_source,
        )
        if not missing_models:
            return True

        # Show model/source selection dialog
        is_zh = self._main.config.language == "zh"
        dialog = OCRDownloadConfigDialog(
            language=self._main.config.language,
            tier=current_tier,
            source=current_source,
            parent=self,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False

        selected_tier = dialog.selected_tier
        selected_source = dialog.selected_source
        updates: dict[str, object] = {}
        if selected_tier != current_tier:
            updates["ocr_model_tier"] = selected_tier
            updates["ocr_model_locked_by_user"] = True
        if selected_source != current_source:
            updates["ocr_model_source"] = selected_source

        if updates:
            self._persist_ocr_config_updates(**updates)

        configure_ocr_runtime(
            model_tier=getattr(self._main.config, "ocr_model_tier", "lite"),
            model_source=getattr(self._main.config, "ocr_model_source", "official"),
        )

        missing_models = get_missing_ocr_models(
            model_tier=getattr(self._main.config, "ocr_model_tier", "lite"),
            model_source=getattr(self._main.config, "ocr_model_source", "official"),
        )
        model_list = ", ".join(missing_models)
        confirm_message = (
            f"检测到缺失的 OCR 模型：{model_list}\n\n是否立即下载？"
            if is_zh
            else f"Missing OCR models detected: {model_list}\n\nDownload now?"
        )

        # For question dialogs, we'll use MessageBox from qfluentwidgets instead
        from qfluentwidgets import MessageBox

        w = MessageBox(
            "下载 OCR 模型" if is_zh else "Download OCR Models",
            confirm_message,
            self
        )
        if w.exec():
            # User clicked Yes/OK
            pass
        else:
            # User clicked No/Cancel
            return False

        # Start download in background thread
        self._model_check_in_progress = True
        self._set_generate_actions_enabled(False)

        # Show progress tooltip
        self._state_tooltip = StateToolTip(
            "正在下载 OCR 模型" if is_zh else "Downloading OCR Models",
            "请稍候..." if is_zh else "Please wait...",
            self.window()
        )
        self._state_tooltip.move(self._state_tooltip.getSuitablePos())
        self._state_tooltip.show()

        # Create and start worker
        self._cleanup_ocr_download_worker()
        self._ocr_download_worker = OCRModelDownloadWorker(
            model_tier=getattr(self._main.config, "ocr_model_tier", "lite"),
            model_source=getattr(self._main.config, "ocr_model_source", "official"),
        )
        self._ocr_download_worker.progress.connect(self._on_ocr_download_progress)
        self._ocr_download_worker.finished.connect(self._on_ocr_download_finished)
        self._ocr_download_worker.error.connect(self._on_ocr_download_error)
        self._ocr_download_worker.start()

        return False  # Return False to prevent immediate conversion start

    def _on_ocr_download_progress(self, current: int, total: int, message: str):
        """Handle OCR model download progress."""
        if self._state_tooltip:
            self._state_tooltip.setContent(message)

    def _on_ocr_download_finished(self, downloaded_models: list[str]):
        """Handle successful OCR model download."""
        self._model_check_in_progress = False
        self._set_generate_actions_enabled(True)
        self._cleanup_ocr_download_worker()

        if self._state_tooltip:
            is_zh = self._main.config.language == "zh"
            success_msg = (
                f"模型下载完成！已下载 {len(downloaded_models)} 个模型"
                if is_zh
                else f"Download complete! {len(downloaded_models)} model(s) downloaded"
            )
            self._state_tooltip.setContent(success_msg)
            self._state_tooltip.setState(True)
            self._dispose_state_tooltip()

        # Show success message
        is_zh = self._main.config.language == "zh"
        InfoBar.success(
            title="下载成功" if is_zh else "Download Successful",
            content="OCR 模型已成功下载，现在可以开始转换文件了。"
            if is_zh
            else "OCR models downloaded successfully. You can now start converting files.",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self
        )

    def _on_ocr_download_error(self, error_message: str):
        """Handle OCR model download error."""
        self._model_check_in_progress = False
        self._set_generate_actions_enabled(True)
        self._cleanup_ocr_download_worker()

        if self._state_tooltip:
            is_zh = self._main.config.language == "zh"
            self._state_tooltip.setContent(
                "下载失败" if is_zh else "Download failed"
            )
            self._state_tooltip.setState(True)
            self._dispose_state_tooltip()

        # Show error message
        is_zh = self._main.config.language == "zh"
        error_detail = (
            f"OCR 模型下载失败：\n\n{error_message}\n\n"
            "请检查网络连接后重试，或手动下载模型文件。"
            if is_zh
            else f"OCR model download failed:\n\n{error_message}\n\n"
            "Please check your network connection and try again, or manually download the model files."
        )

        InfoBar.error(
            title="下载失败" if is_zh else "Download Failed",
            content=error_detail,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

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
        from ankismart.ui.i18n import get_text

        # Update file status to converting
        if filename in self._file_status:
            self._file_status[filename] = "converting"

        percentage = int((current / total) * 100) if total > 0 else 0
        self._progress_bar.setValue(percentage)

        # Store current file info for page progress updates
        self._current_file = filename
        self._current_file_index = current
        self._total_files = total

        # Update status with overall progress
        overall_text = get_text(
            "import.overall_progress",
            self._main.config.language,
            percentage=percentage,
            current=current,
            total=total
        )

        file_text = get_text(
            "import.converting_file",
            self._main.config.language,
            filename=filename,
            current=current,
            total=total
        )

        self._status_label.setText(f"{file_text}\n{overall_text}")

    def _on_file_completed(self, filename: str, document: ConvertedDocument):
        """Handle single file conversion completion."""
        # Update file status to completed
        if filename in self._file_status:
            self._file_status[filename] = "completed"

        # Update file list item color to normal
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item and item.text() == filename:
                item.setForeground(self._get_completed_item_color())
                break

        # Update preview page if it's already showing
        if hasattr(self._main, 'batch_result') and self._main.batch_result:
            # Add document to existing batch result
            self._main.batch_result.documents.append(document)

            # Update preview page if visible
            preview_page = getattr(self._main, 'preview_page', None)
            if preview_page and preview_page.isVisible():
                preview_page.add_converted_document(document)

                # Count remaining pending files
                pending_count = sum(1 for status in self._file_status.values() if status != "completed")
                preview_page.update_converting_status(pending_count)
        else:
            # Create initial batch result with first document
            from ankismart.core.models import BatchConvertResult
            self._main.batch_result = BatchConvertResult(documents=[document], errors=[])

            # Switch to preview page with pending files indicator
            pending_count = sum(1 for status in self._file_status.values() if status != "completed")
            total_files = len(self._file_status)
            self._main.switch_to_preview(pending_files_count=pending_count, total_expected=total_files)

    def _on_page_progress(self, filename: str, current_page: int, total_pages: int):
        """Handle OCR page-by-page progress."""
        from ankismart.ui.i18n import get_text

        # Update status label with detailed page information
        if total_pages > 0:
            file_text = get_text(
                "import.converting_file_with_page",
                self._main.config.language,
                filename=filename,
                page=current_page,
                total_pages=total_pages
            )

            # Calculate overall progress
            if hasattr(self, '_current_file_index') and hasattr(self, '_total_files'):
                percentage = int((self._current_file_index / self._total_files) * 100) if self._total_files > 0 else 0
                overall_text = get_text(
                    "import.overall_progress",
                    self._main.config.language,
                    percentage=percentage,
                    current=self._current_file_index,
                    total=self._total_files
                )
                self._status_label.setText(f"{file_text}\n{overall_text}")
            else:
                self._status_label.setText(file_text)

    def _on_batch_convert_done(self, result: BatchConvertResult):
        """Handle batch conversion completion."""
        self._cleanup_batch_worker()
        self._hide_progress()
        self._set_generate_actions_enabled(True)

        # Show errors if any
        if result.errors:
            error_msg = "\n".join(result.errors)
            InfoBar.warning(
                title="转换错误" if self._main.config.language == "zh" else "Conversion Errors",
                content=f"部分文件转换失败:\n{error_msg}"
                if self._main.config.language == "zh"
                else f"Some files failed to convert:\n{error_msg}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

        # Check if we have any successful conversions
        if not result.documents:
            self._status_label.setText(
                "没有成功转换的文件" if self._main.config.language == "zh" else "No files converted successfully"
            )
            self._auto_generate_after_convert = False
            return

        # Store result and switch to preview page
        self._main.batch_result = result
        self._status_label.setText(
            f"转换完成: {len(result.documents)} 个文件"
            if self._main.config.language == "zh"
            else f"Conversion completed: {len(result.documents)} files"
        )

        # Always just switch to preview page, don't auto-generate
        self._main.switch_to_preview()

    def _on_convert_error(self, error: str):
        """Handle conversion error."""
        self._cleanup_batch_worker()
        self._hide_progress()
        self._set_generate_actions_enabled(True)
        self._status_label.setText(
            f"转换失败: {error}" if self._main.config.language == "zh" else f"Conversion failed: {error}"
        )
        InfoBar.error(
            title="错误" if self._main.config.language == "zh" else "Error",
            content=error,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

    def _cancel_operation(self):
        """Cancel the current operation."""
        if self._worker and self._worker.isRunning():
            from qfluentwidgets import MessageBox

            w = MessageBox(
                "确认取消" if self._main.config.language == "zh" else "Confirm Cancel",
                "确定要取消当前操作吗？" if self._main.config.language == "zh" else "Are you sure you want to cancel?",
                self
            )

            if w.exec():
                self._worker.cancel()
                self._btn_cancel.setEnabled(False)
                self._status_label.setText(
                    "正在取消..." if self._main.config.language == "zh" else "Cancelling..."
                )

    def _on_operation_cancelled(self):
        """Handle operation cancellation."""
        self._cleanup_batch_worker()
        self._hide_progress()
        self._set_generate_actions_enabled(True)
        self._status_label.setText(
            "操作已取消" if self._main.config.language == "zh" else "Operation cancelled"
        )

        from PyQt6.QtCore import Qt
        from qfluentwidgets import InfoBar, InfoBarPosition

        InfoBar.warning(
            title="已取消" if self._main.config.language == "zh" else "Cancelled",
            content="操作已被用户取消" if self._main.config.language == "zh" else "Operation cancelled by user",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

    def closeEvent(self, event):  # noqa: N802
        """Ensure background workers are stopped and references released."""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(3000)
            if self._worker.isRunning():
                self._worker.terminate()
                self._worker.wait()

        if self._ocr_download_worker and self._ocr_download_worker.isRunning():
            self._ocr_download_worker.wait(3000)
            if self._ocr_download_worker.isRunning():
                self._ocr_download_worker.terminate()
                self._ocr_download_worker.wait()

        if self._deck_loader and self._deck_loader.isRunning():
            self._deck_loader.wait(3000)
            if self._deck_loader.isRunning():
                self._deck_loader.terminate()
                self._deck_loader.wait()

        self._cleanup_batch_worker()
        self._cleanup_ocr_download_worker()
        self._cleanup_deck_loader_worker()
        self._dispose_state_tooltip()
        super().closeEvent(event)


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

    def _load_example(self):
        """Show dialog to select and load example documents."""
        is_zh = self._main.config.language == "zh"

        # Create custom dialog
        dialog = MessageBox(
            "选择示例文档" if is_zh else "Select Example Document",
            "",
            self
        )

        # Get examples directory
        import sys
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = Path(sys._MEIPASS)
        else:
            # Running as script
            base_path = Path(__file__).parent.parent.parent.parent

        examples_dir = base_path / "examples"

        # Define examples
        examples = [
            {
                "file": "sample.md",
                "name": "综合知识示例" if is_zh else "Comprehensive Knowledge",
                "desc": "包含数学公式、代码块、列表等多种内容" if is_zh else "Contains math formulas, code blocks, lists, etc.",
                "strategy": {"basic": 40, "cloze": 30, "concept": 30}
            },
            {
                "file": "sample-math.md",
                "name": "数学公式专题" if is_zh else "Mathematics Formulas",
                "desc": "微积分、线性代数、概率论等数学内容" if is_zh else "Calculus, linear algebra, probability, etc.",
                "strategy": {"cloze": 50, "concept": 30, "basic": 20}
            },
            {
                "file": "sample-biology.md",
                "name": "生物学知识" if is_zh else "Biology Knowledge",
                "desc": "细胞、遗传、生态、进化等生物学内容" if is_zh else "Cell biology, genetics, ecology, evolution, etc.",
                "strategy": {"basic": 40, "key_terms": 30, "concept": 30}
            }
        ]

        # Build dialog content
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(SPACING_MEDIUM)

        selected_example = [None]  # Use list to allow modification in nested function

        for example in examples:
            example_path = examples_dir / example["file"]
            if not example_path.exists():
                continue

            # Create example card using CardWidget
            card = CardWidget()
            card.setBorderRadius(8)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(SPACING_SMALL)
            card_layout.setContentsMargins(SPACING_MEDIUM, SPACING_MEDIUM, SPACING_MEDIUM, SPACING_MEDIUM)

            # Title
            title_label = SubtitleLabel(example["name"])
            card_layout.addWidget(title_label)

            # Description
            desc_label = BodyLabel(example["desc"])
            desc_label.setWordWrap(True)
            card_layout.addWidget(desc_label)

            # Select button
            select_btn = PushButton("选择" if is_zh else "Select")
            select_btn.setMinimumWidth(100)

            def make_handler(ex):
                def handler():
                    selected_example[0] = ex
                    dialog.accept()
                return handler

            select_btn.clicked.connect(make_handler(example))
            card_layout.addWidget(select_btn)

            content_layout.addWidget(card)

        dialog.textEdit.hide()
        dialog.yesButton.hide()
        dialog.cancelButton.setText("取消" if is_zh else "Cancel")

        # Add content widget to dialog
        dialog.textLayout.addWidget(content_widget)

        if dialog.exec():
            if selected_example[0]:
                example = selected_example[0]
                example_path = examples_dir / example["file"]

                # Load the example file
                self._add_files([example_path])

                # Apply recommended strategy
                self._apply_strategy_mix(example["strategy"])

                # Show success message
                InfoBar.success(
                    title="示例已加载" if is_zh else "Example Loaded",
                    content=f"已加载示例文档：{example['name']}" if is_zh else f"Example document loaded: {example['name']}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self,
                )

    def _recommend_strategy(self):
        """Analyze files and recommend generation strategy."""
        is_zh = self._main.config.language == "zh"

        if not self._file_paths:
            InfoBar.warning(
                title="警告" if is_zh else "Warning",
                content="请先选择文件" if is_zh else "Please select files first",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Analyze file content to determine type
        content_type = self._analyze_content_type()

        # Get recommended strategy based on content type
        strategy_mix = self._get_recommended_strategy(content_type)

        # Show recommendation dialog
        dialog = MessageBox(
            "策略推荐" if is_zh else "Strategy Recommendation",
            "",
            self
        )

        # Build recommendation content
        type_names = {
            "math_science": ("数学/理科内容", "Math/Science Content"),
            "liberal_arts": ("文科/历史内容", "Liberal Arts/History Content"),
            "programming": ("编程/技术内容", "Programming/Technical Content"),
            "general": ("通用内容", "General Content")
        }

        type_descs = {
            "math_science": ("检测到数学公式、科学概念等内容", "Detected math formulas, scientific concepts, etc."),
            "liberal_arts": ("检测到历史事件、人文知识等内容", "Detected historical events, humanities knowledge, etc."),
            "programming": ("检测到代码块、技术文档等内容", "Detected code blocks, technical documentation, etc."),
            "general": ("混合类型内容，使用平衡策略", "Mixed content type, using balanced strategy")
        }

        type_name = type_names.get(content_type, type_names["general"])
        type_desc = type_descs.get(content_type, type_descs["general"])

        content = f"""
<h3>{type_name[0] if is_zh else type_name[1]}</h3>
<p>{type_desc[0] if is_zh else type_desc[1]}</p>
<br>
<h4>{"推荐策略配置：" if is_zh else "Recommended Strategy:"}</h4>
<ul>
"""

        strategy_names = {
            "basic": ("基础问答", "Basic Q&A"),
            "cloze": ("填空题", "Cloze"),
            "concept": ("概念解释", "Concept"),
            "key_terms": ("关键术语", "Key Terms"),
            "single_choice": ("单选题", "Single Choice"),
            "multiple_choice": ("多选题", "Multiple Choice")
        }

        for strategy_id, ratio in strategy_mix.items():
            if ratio > 0:
                name = strategy_names.get(strategy_id, (strategy_id, strategy_id))
                content += f"<li>{name[0] if is_zh else name[1]}: {ratio}%</li>"

        content += "</ul>"

        dialog.setText(content)
        dialog.yesButton.setText("应用推荐" if is_zh else "Apply Recommendation")
        dialog.cancelButton.setText("取消" if is_zh else "Cancel")

        if dialog.exec():
            # Apply recommended strategy
            self._apply_strategy_mix(strategy_mix)

            InfoBar.success(
                title="已应用推荐策略" if is_zh else "Recommendation Applied",
                content="已根据文档类型应用推荐的生成策略" if is_zh else "Applied recommended strategy based on document type",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )

    def _analyze_content_type(self) -> str:
        """Analyze file content to determine content type."""
        # Simple heuristic based on file content
        math_keywords = ["$$", "\\frac", "\\int", "\\sum", "\\lim", "公式", "定理", "证明"]
        programming_keywords = ["```", "def ", "class ", "function", "import", "代码", "函数"]
        history_keywords = ["年", "世纪", "朝代", "历史", "事件", "人物"]

        math_score = 0
        programming_score = 0
        history_score = 0

        for file_path in self._file_paths[:3]:  # Check first 3 files
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")[:5000]  # First 5000 chars

                for keyword in math_keywords:
                    math_score += content.count(keyword)

                for keyword in programming_keywords:
                    programming_score += content.count(keyword)

                for keyword in history_keywords:
                    history_score += content.count(keyword)
            except (OSError, UnicodeDecodeError) as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
                pass

        # Determine content type based on scores
        if math_score > programming_score and math_score > history_score and math_score > 3:
            return "math_science"
        elif programming_score > math_score and programming_score > history_score and programming_score > 2:
            return "programming"
        elif history_score > math_score and history_score > programming_score and history_score > 5:
            return "liberal_arts"
        else:
            return "general"

    def _get_recommended_strategy(self, content_type: str) -> dict:
        """Get recommended strategy mix based on content type."""
        strategies = {
            "math_science": {"cloze": 50, "concept": 30, "basic": 20},
            "liberal_arts": {"basic": 40, "key_terms": 30, "concept": 30},
            "programming": {"basic": 40, "cloze": 30, "concept": 30},
            "general": {"basic": 35, "cloze": 25, "concept": 25, "key_terms": 15}
        }
        return strategies.get(content_type, strategies["general"])

    def _apply_strategy_mix(self, strategy_mix: dict):
        """Apply strategy mix to sliders."""
        # Reset all sliders first
        for strategy_id, slider, value_label in self._strategy_sliders:
            slider.setValue(0)
            value_label.setText("0%")

        # Apply recommended values
        for strategy_id, slider, value_label in self._strategy_sliders:
            if strategy_id in strategy_mix:
                ratio = strategy_mix[strategy_id]
                slider.setValue(ratio)
                value_label.setText(f"{ratio}%")

    def retranslate_ui(self):
        """Retranslate UI elements when language changes."""
        is_zh = self._main.config.language == "zh"

        # Update button text and tooltips
        start_text = "开始生成" if is_zh else "Start Generation"
        start_shortcut = get_shortcut_text(ShortcutKeys.START_GENERATION, self._main.config.language)
        self._btn_convert.setText(start_text)
        self._btn_convert.setToolTip(f"{start_text} ({start_shortcut})")

        self._btn_clear.setText("清除" if is_zh else "Clear")

    def update_theme(self):
        """Update theme-dependent components when theme changes."""
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item is None:
                continue
            status = self._file_status.get(item.text(), "pending")
            if status == "completed":
                item.setForeground(self._get_completed_item_color())
            else:
                item.setForeground(self._get_pending_item_color())

    @staticmethod
    def _get_pending_item_color() -> QColor:
        """Muted color for pending/converting items in current theme."""
        if isDarkTheme():
            return QColor(160, 160, 160)
        return QColor(150, 150, 150)

    @staticmethod
    def _get_completed_item_color() -> QColor:
        """Readable normal text color for completed items in current theme."""
        if isDarkTheme():
            return QColor(255, 255, 255)
        return QColor(0, 0, 0)

