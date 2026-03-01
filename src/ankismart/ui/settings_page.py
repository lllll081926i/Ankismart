from __future__ import annotations

import concurrent.futures
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    ExpandLayout,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PasswordLineEdit,
    PrimaryPushButton,
    PushButton,
    PushSettingCard,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    Slider,
    SmoothMode,
    SpinBox,
    SwitchButton,
    SwitchSettingCard,
    isDarkTheme,
)

from ankismart import __version__
from ankismart.core.config import (
    CONFIG_BACKUP_DIR,
    LLMProviderConfig,
    create_config_backup,
    list_config_backups,
    restore_config_from_backup,
    save_config,
)
from ankismart.core.errors import ErrorCode, get_error_info
from ankismart.ui.shortcuts import ShortcutKeys, create_shortcut, get_shortcut_text
from ankismart.ui.styles import (
    MARGIN_STANDARD,
    SPACING_MEDIUM,
    SPACING_SMALL,
    get_list_widget_palette,
    get_page_background_color,
)

if TYPE_CHECKING:
    from ankismart.ui.main_window import MainWindow


_OCR_MODE_CHOICES = (
    ("local", "本地模型", "Local Model"),
    ("cloud", "云端模型", "Cloud Model"),
)

_OCR_MODEL_TIER_CHOICES = (
    ("lite", "轻量", "Lite"),
    ("standard", "标准", "Standard"),
    ("accuracy", "高精度", "High Accuracy"),
)

_OCR_SOURCE_CHOICES = (
    ("official", "官方地址（HuggingFace）", "Official (HuggingFace)"),
    ("cn_mirror", "国内镜像（ModelScope）", "China Mirror (ModelScope)"),
)

_OCR_CLOUD_PROVIDER_CHOICES = (
    ("mineru", "MinerU 云 OCR", "MinerU Cloud OCR"),
)

_GITHUB_RELEASES_API_URL = "https://api.github.com/repos/lllll081926i/Ankismart/releases/latest"
_GITHUB_TAGS_API_URL = "https://api.github.com/repos/lllll081926i/Ankismart/tags?per_page=1"
_GITHUB_RELEASES_WEB_URL = "https://github.com/lllll081926i/Ankismart/releases"


_OCR_CONVERTER_MODULE = None
_CACHE_STATS_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="settings-cache-stats",
)


class OCRRuntimeUnavailableError(RuntimeError):
    """Raised when OCR runtime modules are not bundled."""


def _get_ocr_converter_module():
    """Lazy import OCR converter to avoid loading OCR stack at startup."""
    global _OCR_CONVERTER_MODULE
    if _OCR_CONVERTER_MODULE is None:
        try:
            from ankismart.converter import ocr_converter as module
        except Exception as exc:
            raise OCRRuntimeUnavailableError("OCR runtime is not bundled in this package") from exc

        _OCR_CONVERTER_MODULE = module
    return _OCR_CONVERTER_MODULE


def configure_ocr_runtime(
    *,
    model_tier: str,
    model_source: str,
    reset_ocr_instance: bool = False,
) -> None:
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


def get_missing_ocr_models(*, model_tier: str, model_source: str):
    return _get_ocr_converter_module().get_missing_ocr_models(
        model_tier=model_tier,
        model_source=model_source,
    )


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


class LLMProviderDialog(QDialog):
    """Dialog for adding/editing LLM provider."""

    saved = pyqtSignal(LLMProviderConfig)

    def __init__(self, provider: LLMProviderConfig | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LLM 提供商配置")
        self.setMinimumWidth(500)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        self._provider = provider or LLMProviderConfig(id=uuid.uuid4().hex[:12])

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MEDIUM)
        layout.setContentsMargins(
            MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD
        )

        # Name
        self._name_edit = LineEdit()
        self._name_edit.setPlaceholderText("提供商名称（例如：OpenAI）")
        self._name_edit.setText(self._provider.name)
        layout.addWidget(self._name_edit)

        # Base URL
        self._base_url_edit = LineEdit()
        self._base_url_edit.setPlaceholderText("基础 URL（例如：https://api.openai.com/v1）")
        self._base_url_edit.setText(self._provider.base_url)
        layout.addWidget(self._base_url_edit)

        # API Key
        self._api_key_edit = PasswordLineEdit()
        self._api_key_edit.setPlaceholderText("API 密钥")
        self._api_key_edit.setText(self._provider.api_key)
        layout.addWidget(self._api_key_edit)

        # Model
        self._model_edit = LineEdit()
        self._model_edit.setPlaceholderText("模型（例如：gpt-4o）")
        self._model_edit.setText(self._provider.model)
        layout.addWidget(self._model_edit)

        # RPM Limit
        rpm_layout = QHBoxLayout()
        self._rpm_spin = SpinBox()
        self._rpm_spin.setRange(0, 9999)
        self._rpm_spin.setValue(self._provider.rpm_limit)
        self._rpm_spin.setPrefix("RPM 限制: ")
        rpm_layout.addWidget(self._rpm_spin)
        layout.addLayout(rpm_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = PushButton("取消")
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)

        save_btn = PrimaryPushButton("保存")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _save(self) -> None:
        self._provider.name = self._name_edit.text().strip()
        self._provider.base_url = self._base_url_edit.text().strip()
        self._provider.api_key = self._api_key_edit.text().strip()
        self._provider.model = self._model_edit.text().strip()
        self._provider.rpm_limit = self._rpm_spin.value()

        if not self._provider.name:
            QMessageBox.warning(self, "错误", "提供商名称为必填项")
            return

        self.saved.emit(self._provider)
        self.close()


class SettingsPage(ScrollArea):
    """Application settings page using QFluentWidgets components."""

    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self._main = main_window
        self._providers: list[LLMProviderConfig] = []
        self._active_provider_id: str = ""
        self._provider_list_widget: QWidget | None = None
        self._provider_test_worker = None
        self._anki_test_worker = None
        self._ocr_cloud_test_worker = None
        self._cache_stats_seq = 0
        self._cache_stats_future: concurrent.futures.Future | None = None
        self._ocr_card_height_bounds: dict[int, tuple[int, int]] = {}
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(400)
        self._autosave_timer.timeout.connect(self._save_config_silent)

        # Create scroll widget
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # Initialize UI
        self._init_widget()

    def _init_widget(self):
        """Initialize widgets and layout."""
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Improve wheel-following responsiveness for long settings pages.
        self.setSmoothMode(SmoothMode.NO_SMOOTH, Qt.Orientation.Vertical)
        self.setViewportMargins(0, 0, 0, 0)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName("settingsPage")
        self.verticalScrollBar().setSingleStep(64)
        self.verticalScrollBar().setPageStep(360)

        self.scrollWidget.setObjectName("scrollWidget")

        # Apply theme-aware background
        self._apply_background_style()

        # Initialize layout
        self._init_layout()

        # Load current configuration
        self._load_config()
        self._apply_theme_styles()

        # Initialize shortcuts
        self._init_shortcuts()

        # Connect auto-save signals
        self._connect_auto_save_signals()
        self._enforce_scroll_steps()

    def _enforce_scroll_steps(self, *_args) -> None:
        """Keep tuned scroll steps stable after internal scrollbar recalculations."""
        scroll_bar = self.verticalScrollBar()
        if scroll_bar.singleStep() != 64:
            scroll_bar.setSingleStep(64)
        if scroll_bar.pageStep() != 360:
            scroll_bar.setPageStep(360)

    def resizeEvent(self, event):  # noqa: N802
        """Re-apply tuned scroll steps after layout/viewport size changes."""
        super().resizeEvent(event)
        self._enforce_scroll_steps()

    def _init_shortcuts(self):
        """Initialize page-specific keyboard shortcuts."""
        # Ctrl+S: Save configuration
        create_shortcut(self, ShortcutKeys.SAVE_EDIT, self._save_config)

    def _connect_auto_save_signals(self):
        """Connect all control signals to auto-save configuration."""
        # LLM settings
        self._temperature_slider.valueChanged.connect(self._schedule_auto_save)
        self._max_tokens_spin.valueChanged.connect(self._schedule_auto_save)
        self._concurrency_spin.valueChanged.connect(self._schedule_auto_save)
        self._adaptive_concurrency_switch.checkedChanged.connect(self._schedule_auto_save)
        self._concurrency_max_spin.valueChanged.connect(self._schedule_auto_save)

        # Anki settings
        self._anki_url_edit.textChanged.connect(self._schedule_auto_save)
        self._anki_key_edit.textChanged.connect(self._schedule_auto_save)
        self._default_deck_edit.textChanged.connect(self._schedule_auto_save)
        self._default_tags_edit.textChanged.connect(self._schedule_auto_save)

        # Other settings
        self._language_combo.currentIndexChanged.connect(self._schedule_auto_save)
        self._auto_update_card.checkedChanged.connect(self._schedule_auto_save)
        self._proxy_mode_combo.currentIndexChanged.connect(self._schedule_auto_save)
        self._proxy_edit.textChanged.connect(self._schedule_auto_save)
        self._ocr_correction_switch.checkedChanged.connect(self._schedule_auto_save)

        # OCR settings
        self._ocr_mode_combo.currentIndexChanged.connect(self._schedule_auto_save)
        self._ocr_model_tier_combo.currentIndexChanged.connect(self._schedule_auto_save)
        self._ocr_source_combo.currentIndexChanged.connect(self._schedule_auto_save)
        self._ocr_cuda_auto_card.checkedChanged.connect(self._schedule_auto_save)
        self._ocr_cloud_provider_combo.currentIndexChanged.connect(self._schedule_auto_save)
        self._ocr_cloud_endpoint_edit.textChanged.connect(self._schedule_auto_save)
        self._ocr_cloud_api_key_edit.textChanged.connect(self._schedule_auto_save)

        # Experimental features
        self._auto_split_switch.checkedChanged.connect(self._schedule_auto_save)
        self._split_threshold_spinbox.valueChanged.connect(self._schedule_auto_save)

    def _schedule_auto_save(self, *_args) -> None:
        """Debounce auto-save to avoid frequent disk writes while typing."""
        self._autosave_timer.start()

    def _show_info_bar(self, level: str, title: str, content: str, duration: int = 3000) -> None:
        """Show fluent InfoBar notifications consistently."""
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

    def _apply_background_style(self) -> None:
        """Apply theme-aware background color to settings page."""
        bg_color = get_page_background_color(dark=isDarkTheme())

        self.setStyleSheet(
            f"QScrollArea#settingsPage {{ background-color: {bg_color}; border: none; }}"
        )
        self.scrollWidget.setStyleSheet(f"QWidget#scrollWidget {{ background-color: {bg_color}; }}")

    def _apply_theme_styles(self) -> None:
        """Apply theme-aware styles for non-Fluent labels in settings page."""
        self._apply_background_style()
        self._apply_provider_table_style()
        if hasattr(self, "_ocr_model_recommend_label"):
            self._ocr_model_recommend_label.setStyleSheet("")
        if hasattr(self, "_provider_list_widget") and self._provider_list_widget:
            self._provider_list_widget.update_theme()

    def _apply_provider_table_style(self) -> None:
        """Keep provider table border consistent with current light/dark theme."""
        if not hasattr(self, "_provider_table"):
            return
        palette = get_list_widget_palette(dark=isDarkTheme())
        self._provider_table.setStyleSheet(
            "QTableWidget {"
            f"border: 1px solid {palette.border};"
            "border-radius: 8px;"
            "}"
            "QTableWidget::item:selected {"
            "background: transparent;"
            "color: inherit;"
            "}"
        )

    def _init_layout(self):
        """Initialize layout and add all setting cards."""
        self.expandLayout.setSpacing(SPACING_MEDIUM)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)

        # ── LLM Configuration Group ──
        self._llm_group = SettingCardGroup("LLM 配置", self.scrollWidget)

        # Provider management card with add button
        self._provider_mgmt_card = PushSettingCard(
            "添加提供商",
            FluentIcon.ADD,
            "LLM 提供商",
            "管理 LLM 服务提供商配置",
        )
        self._provider_mgmt_card.clicked.connect(self._add_provider)
        self._llm_group.addSettingCard(self._provider_mgmt_card)

        self.expandLayout.addWidget(self._llm_group)

        # Provider table (standalone widget below the group, reduced spacing)
        self._provider_table = QTableWidget(self.scrollWidget)
        self._apply_provider_table_style()
        self._provider_table.setWordWrap(False)
        self._provider_table.setColumnCount(5)
        self._provider_table.setHorizontalHeaderLabels(["名称", "模型", "地址", "RPM", "操作"])
        self._provider_table.verticalHeader().hide()
        self._provider_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._provider_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._provider_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._provider_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._provider_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Set fixed row height (36px per row)
        self._provider_table.verticalHeader().setDefaultSectionSize(36)

        # Set fixed height for 2 rows + header
        header_height = self._provider_table.horizontalHeader().height()
        self._provider_table.setFixedHeight(header_height + 36 * 2 + 2)  # 2 rows + border

        # Use adaptive widths to avoid horizontal scrolling.
        header = self._provider_table.horizontalHeader()
        header.setMinimumSectionSize(56)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        # Reduce top margin for table
        self.expandLayout.setSpacing(8)  # Reduce spacing between widgets
        self.expandLayout.addWidget(self._provider_table)
        self.expandLayout.setSpacing(SPACING_SMALL)  # Restore normal spacing for rest

        # Temperature
        self._temperature_card = SettingCard(
            FluentIcon.FRIGID,
            "温度",
            "控制生成的随机性（0.0 = 确定性，2.0 = 创造性）",
            self.scrollWidget,
        )
        self._temperature_slider = Slider(Qt.Orientation.Horizontal, self._temperature_card)
        self._temperature_slider.setRange(0, 20)
        self._temperature_slider.setSingleStep(1)
        self._temperature_slider.setValue(3)
        self._temperature_slider.setMinimumWidth(200)

        self._temperature_label = BodyLabel()
        self._temperature_label.setText("0.3")
        self._temperature_label.setFixedWidth(50)

        self._temperature_slider.valueChanged.connect(
            lambda v: self._temperature_label.setText(f"{v / 10:.1f}")
        )

        self._temperature_card.hBoxLayout.addWidget(self._temperature_slider)
        self._temperature_card.hBoxLayout.addWidget(self._temperature_label)
        self._temperature_card.hBoxLayout.addSpacing(16)
        self._llm_group.addSettingCard(self._temperature_card)

        # Max Tokens
        self._max_tokens_card = SettingCard(
            FluentIcon.FONT,
            "最大令牌数",
            "生成的最大令牌数（0 = 使用提供商默认值）",
            self.scrollWidget,
        )
        self._max_tokens_spin = SpinBox(self._max_tokens_card)
        self._max_tokens_spin.setRange(0, 128000)
        self._max_tokens_spin.setSingleStep(256)
        self._max_tokens_spin.setSpecialValueText("默认")
        self._max_tokens_spin.setMinimumWidth(200)
        self._max_tokens_card.hBoxLayout.addWidget(self._max_tokens_spin)
        self._max_tokens_card.hBoxLayout.addSpacing(16)
        self._llm_group.addSettingCard(self._max_tokens_card)

        # LLM Concurrency
        self._concurrency_card = SettingCard(
            FluentIcon.SPEED_HIGH,
            "并发限制",
            "同时处理的最大文件数（0 = 按文档数自动）",
            self.scrollWidget,
        )
        self._concurrency_spin = SpinBox(self._concurrency_card)
        self._concurrency_spin.setRange(0, 10)
        self._concurrency_spin.setSingleStep(1)
        self._concurrency_spin.setValue(2)
        self._concurrency_spin.setSpecialValueText("自动")
        self._concurrency_spin.setMinimumWidth(200)
        self._concurrency_card.hBoxLayout.addWidget(self._concurrency_spin)
        self._concurrency_card.hBoxLayout.addSpacing(16)
        self._llm_group.addSettingCard(self._concurrency_card)

        self._adaptive_concurrency_card = SettingCard(
            FluentIcon.ROBOT,
            "自适应并发",
            "根据限流/超时自动调低并发，稳定后自动回升",
            self.scrollWidget,
        )
        self._adaptive_concurrency_switch = SwitchButton(self._adaptive_concurrency_card)
        self._adaptive_concurrency_card.hBoxLayout.addWidget(self._adaptive_concurrency_switch)
        self._adaptive_concurrency_card.hBoxLayout.addSpacing(16)
        self._llm_group.addSettingCard(self._adaptive_concurrency_card)

        self._concurrency_max_card = SettingCard(
            FluentIcon.SPEED_HIGH,
            "并发上限",
            "自适应回升时可达到的最大并发",
            self.scrollWidget,
        )
        self._concurrency_max_spin = SpinBox(self._concurrency_max_card)
        self._concurrency_max_spin.setRange(1, 20)
        self._concurrency_max_spin.setSingleStep(1)
        self._concurrency_max_spin.setValue(6)
        self._concurrency_max_spin.setMinimumWidth(200)
        self._concurrency_max_card.hBoxLayout.addWidget(self._concurrency_max_spin)
        self._concurrency_max_card.hBoxLayout.addSpacing(16)
        self._llm_group.addSettingCard(self._concurrency_max_card)

        # ── Anki Configuration Group ──
        self._anki_group = SettingCardGroup("Anki 配置", self.scrollWidget)

        # AnkiConnect URL
        self._anki_url_card = SettingCard(
            FluentIcon.LINK,
            "AnkiConnect URL",
            "AnkiConnect API 的 URL 地址",
            self.scrollWidget,
        )
        self._anki_url_edit = LineEdit(self._anki_url_card)
        self._anki_url_edit.setPlaceholderText("http://127.0.0.1:8765")
        self._anki_url_edit.setMinimumWidth(300)
        self._anki_url_card.hBoxLayout.addWidget(self._anki_url_edit)
        self._anki_url_card.hBoxLayout.addSpacing(16)
        self._anki_group.addSettingCard(self._anki_url_card)

        # AnkiConnect Key
        self._anki_key_card = SettingCard(
            FluentIcon.FINGERPRINT,
            "AnkiConnect 密钥",
            "AnkiConnect 的可选 API 密钥",
            self.scrollWidget,
        )
        self._anki_key_edit = PasswordLineEdit(self._anki_key_card)
        self._anki_key_edit.setPlaceholderText("可选的 API 密钥")
        self._anki_key_edit.setMinimumWidth(300)
        self._anki_key_card.hBoxLayout.addWidget(self._anki_key_edit)
        self._anki_key_card.hBoxLayout.addSpacing(16)
        self._anki_group.addSettingCard(self._anki_key_card)

        # Default Deck
        self._default_deck_card = SettingCard(
            FluentIcon.BOOK_SHELF,
            "默认牌组",
            "新卡片的默认 Anki 牌组",
            self.scrollWidget,
        )
        self._default_deck_edit = LineEdit(self._default_deck_card)
        self._default_deck_edit.setPlaceholderText("默认")
        self._default_deck_edit.setMinimumWidth(300)
        self._default_deck_card.hBoxLayout.addWidget(self._default_deck_edit)
        self._default_deck_card.hBoxLayout.addSpacing(16)
        self._anki_group.addSettingCard(self._default_deck_card)

        # Default Tags
        self._default_tags_card = SettingCard(
            FluentIcon.TAG,
            "默认标签",
            "新卡片的默认标签（逗号分隔）",
            self.scrollWidget,
        )
        self._default_tags_edit = LineEdit(self._default_tags_card)
        self._default_tags_edit.setPlaceholderText("ankismart, imported")
        self._default_tags_edit.setMinimumWidth(300)
        self._default_tags_card.hBoxLayout.addWidget(self._default_tags_edit)
        self._default_tags_card.hBoxLayout.addSpacing(16)
        self._anki_group.addSettingCard(self._default_tags_card)

        # Test Connection
        self._test_connection_card = PushSettingCard(
            "测试连接",
            FluentIcon.SYNC,
            "测试连接",
            "测试与 AnkiConnect 的连接",
        )
        self._test_connection_card.clicked.connect(self._test_connection)
        self._anki_group.addSettingCard(self._test_connection_card)

        self.expandLayout.addWidget(self._anki_group)

        # ── Other Configuration Group ──
        self._other_group = SettingCardGroup("其他设置", self.scrollWidget)

        # Theme
        self._theme_card = SettingCard(
            FluentIcon.BRUSH,
            "主题",
            "应用程序主题",
            self.scrollWidget,
        )
        self._theme_combo = ComboBox(self._theme_card)
        self._theme_combo.addItems(["浅色", "深色", "跟随系统"])
        self._theme_combo.setMinimumWidth(200)
        self._theme_card.hBoxLayout.addWidget(self._theme_combo)
        self._theme_card.hBoxLayout.addSpacing(16)
        # Theme switching is handled by sidebar button, keep this control hidden.
        self._theme_card.setVisible(False)

        # Language
        self._language_card = SettingCard(
            FluentIcon.LANGUAGE,
            "语言",
            "应用程序语言",
            self.scrollWidget,
        )
        self._language_combo = ComboBox(self._language_card)
        self._language_combo.addItems(["中文", "English"])
        self._language_combo.setMinimumWidth(200)
        self._language_card.hBoxLayout.addWidget(self._language_combo)
        self._language_card.hBoxLayout.addSpacing(16)
        self._other_group.addSettingCard(self._language_card)

        # Proxy Settings
        self._proxy_card = SettingCard(
            FluentIcon.GLOBE,
            "代理设置",
            "配置网络代理（默认使用系统代理）",
            self.scrollWidget,
        )

        # Proxy row: manual URL input on the left, mode selector on the right.
        proxy_container = QWidget(self._proxy_card)
        proxy_layout = QHBoxLayout(proxy_container)
        proxy_layout.setContentsMargins(0, 0, 0, 0)
        proxy_layout.setSpacing(8)

        # Manual proxy input (hidden by default)
        self._proxy_edit = LineEdit(proxy_container)
        self._proxy_edit.setPlaceholderText("http://proxy.example.com:8080")
        self._proxy_edit.setMinimumWidth(300)
        self._proxy_edit.setVisible(False)

        self._proxy_mode_combo = ComboBox(proxy_container)
        self._proxy_mode_combo.addItems(["系统代理", "手动配置", "不使用代理"])
        self._proxy_mode_combo.setMinimumWidth(150)
        self._proxy_mode_combo.currentIndexChanged.connect(self._on_proxy_mode_changed)

        proxy_layout.addWidget(self._proxy_edit, 1)
        proxy_layout.addWidget(self._proxy_mode_combo, 0)

        self._proxy_card.hBoxLayout.addWidget(proxy_container)
        self._proxy_card.hBoxLayout.addSpacing(16)
        self._other_group.addSettingCard(self._proxy_card)

        # OCR Correction
        self._ocr_correction_card = SettingCard(
            FluentIcon.EDIT,
            "OCR 校正",
            "启用基于 LLM 的 OCR 文本校正",
            self.scrollWidget,
        )
        self._ocr_correction_switch = SwitchButton(self._ocr_correction_card)
        self._ocr_correction_card.hBoxLayout.addWidget(self._ocr_correction_switch)
        self._ocr_correction_card.hBoxLayout.addSpacing(16)
        self._other_group.addSettingCard(self._ocr_correction_card)

        # Log Level - Create custom setting card with ComboBox
        from ankismart.ui.i18n import t

        is_zh = self._main.config.language == "zh"

        log_level_texts = [
            t("log.level_debug", self._main.config.language),
            t("log.level_info", self._main.config.language),
            t("log.level_warning", self._main.config.language),
            t("log.level_error", self._main.config.language),
        ]

        # Create a custom SettingCard with ComboBox
        self._log_level_card = SettingCard(
            FluentIcon.DOCUMENT,
            t("log.level", self._main.config.language),
            t("log.level_desc", self._main.config.language),
            parent=self._other_group,
        )

        # Add ComboBox to the card
        self._log_level_combobox = ComboBox(self._log_level_card)
        self._log_level_combobox.addItems(log_level_texts)
        self._log_level_combobox.setCurrentIndex(
            ["DEBUG", "INFO", "WARNING", "ERROR"].index(self._main.config.log_level)
        )
        self._log_level_combobox.currentIndexChanged.connect(self._on_log_level_changed)

        # Add ComboBox to card layout
        self._log_level_card.hBoxLayout.addWidget(
            self._log_level_combobox, 0, Qt.AlignmentFlag.AlignRight
        )
        self._log_level_card.hBoxLayout.addSpacing(16)

        self._other_group.addSettingCard(self._log_level_card)

        # View Logs
        self._view_logs_card = PushSettingCard(
            t("log.open_folder", self._main.config.language),
            FluentIcon.FOLDER,
            t("log.view_logs", self._main.config.language),
            t("log.view_logs_desc", self._main.config.language),
        )
        self._view_logs_card.clicked.connect(self._open_log_directory)
        self._other_group.addSettingCard(self._view_logs_card)

        # ── OCR Settings Group ──
        self._ocr_group = SettingCardGroup("OCR 设置", self.scrollWidget)

        self._ocr_mode_card = SettingCard(
            FluentIcon.ROBOT,
            "OCR 模式",
            "切换使用本地模型或云端模型（MinerU）",
            self.scrollWidget,
        )
        self._ocr_mode_combo = ComboBox(self._ocr_mode_card)
        for key, zh_text, en_text in _OCR_MODE_CHOICES:
            self._ocr_mode_combo.addItem(zh_text if is_zh else en_text, userData=key)
        self._ocr_mode_combo.currentIndexChanged.connect(self._on_ocr_mode_changed)
        self._ocr_mode_card.hBoxLayout.addWidget(self._ocr_mode_combo)
        self._ocr_mode_card.hBoxLayout.addSpacing(16)
        self._ocr_group.addSettingCard(self._ocr_mode_card)

        self._ocr_cloud_provider_card = SettingCard(
            FluentIcon.CLOUD,
            "云 OCR 提供商",
            "当前支持 MinerU 云 OCR",
            self.scrollWidget,
        )
        self._ocr_cloud_provider_combo = ComboBox(self._ocr_cloud_provider_card)
        for key, zh_text, en_text in _OCR_CLOUD_PROVIDER_CHOICES:
            self._ocr_cloud_provider_combo.addItem(zh_text if is_zh else en_text, userData=key)
        self._ocr_cloud_provider_card.hBoxLayout.addWidget(self._ocr_cloud_provider_combo)
        self._ocr_cloud_provider_card.hBoxLayout.addSpacing(16)
        self._ocr_group.addSettingCard(self._ocr_cloud_provider_card)

        self._ocr_cloud_endpoint_card = SettingCard(
            FluentIcon.GLOBE,
            "云 OCR Endpoint",
            "MinerU API 地址（示例：https://mineru.net）",
            self.scrollWidget,
        )
        self._ocr_cloud_endpoint_edit = LineEdit(self._ocr_cloud_endpoint_card)
        self._ocr_cloud_endpoint_edit.setPlaceholderText("https://mineru.net")
        self._ocr_cloud_endpoint_edit.setMinimumWidth(300)
        self._ocr_cloud_endpoint_card.hBoxLayout.addWidget(self._ocr_cloud_endpoint_edit)
        self._ocr_cloud_endpoint_card.hBoxLayout.addSpacing(16)
        self._ocr_group.addSettingCard(self._ocr_cloud_endpoint_card)

        self._ocr_cloud_api_key_card = SettingCard(
            FluentIcon.FINGERPRINT,
            "云 OCR API Key",
            "MinerU 用户令牌（将加密保存）",
            self.scrollWidget,
        )
        self._ocr_cloud_api_key_edit = PasswordLineEdit(self._ocr_cloud_api_key_card)
        self._ocr_cloud_api_key_edit.setPlaceholderText("sk-...")
        self._ocr_cloud_api_key_edit.setMinimumWidth(460)
        self._ocr_cloud_api_key_card.hBoxLayout.addWidget(self._ocr_cloud_api_key_edit)
        self._ocr_cloud_api_key_card.hBoxLayout.addSpacing(16)
        self._ocr_group.addSettingCard(self._ocr_cloud_api_key_card)

        self._ocr_cloud_limit_card = SettingCard(
            FluentIcon.INFO,
            "云 OCR 官方限制" if is_zh else "Cloud OCR Official Limits",
            (
                "单文件<=200MB，PDF<=600页；每天2000页为最高优先级，超出后优先级降低；"
                "需 Authorization: Bearer <Token>；MinerU 专业版还需额外 token 头；"
                "且先申请上传地址再上传文件。"
            )
            if is_zh
            else (
                "Single file <=200MB and PDF <=600 pages; first 2000 pages/day are "
                "high-priority, then lower priority; requires Authorization: Bearer <Token>; "
                "MinerU Pro additionally requires `token` header; file must be uploaded via "
                "pre-signed URL."
            ),
            self.scrollWidget,
        )
        self._ocr_group.addSettingCard(self._ocr_cloud_limit_card)

        self._ocr_cuda_auto_card = SwitchSettingCard(
            FluentIcon.POWER_BUTTON,
            "CUDA 自动升档",
            "首次 OCR 前检测到 CUDA 时，自动将模型从轻量档升至标准档",
            parent=self._ocr_group,
        )
        self._ocr_group.addSettingCard(self._ocr_cuda_auto_card)

        self._ocr_connectivity_card = PushSettingCard(
            "测试",
            FluentIcon.HELP,
            "OCR 模型连通性测试",
            "本地模式检查模型完整性，云端模式检查 API 与鉴权",
        )
        self._ocr_connectivity_card.clicked.connect(self._test_ocr_connectivity)
        self._ocr_group.addSettingCard(self._ocr_connectivity_card)

        self._ocr_model_tier_card = SettingCard(
            FluentIcon.GLOBE,
            "OCR 模型",
            "切换 OCR 模型档位",
            self.scrollWidget,
        )
        self._ocr_model_tier_combo = ComboBox(self._ocr_model_tier_card)
        for key, zh_text, en_text in _OCR_MODEL_TIER_CHOICES:
            self._ocr_model_tier_combo.addItem(zh_text if is_zh else en_text, userData=key)
        self._ocr_model_tier_combo.currentIndexChanged.connect(
            lambda _: self._refresh_ocr_recommendation()
        )

        self._ocr_model_recommend_label = BodyLabel(self._ocr_model_tier_card)
        self._ocr_model_recommend_label.setWordWrap(False)
        self._ocr_model_recommend_label.setMinimumWidth(260)
        self._ocr_model_tier_card.hBoxLayout.addWidget(self._ocr_model_recommend_label)
        self._ocr_model_tier_card.hBoxLayout.addStretch(1)
        self._ocr_model_tier_card.hBoxLayout.addWidget(self._ocr_model_tier_combo)
        self._ocr_model_tier_card.hBoxLayout.addSpacing(16)
        self._ocr_group.addSettingCard(self._ocr_model_tier_card)

        self._ocr_source_card = SettingCard(
            FluentIcon.CLOUD_DOWNLOAD,
            "模型下载源",
            "首次下载和切换模型时可选择官方地址或国内镜像",
            self.scrollWidget,
        )
        self._ocr_source_combo = ComboBox(self._ocr_source_card)
        for key, zh_text, en_text in _OCR_SOURCE_CHOICES:
            self._ocr_source_combo.addItem(zh_text if is_zh else en_text, userData=key)
        self._ocr_source_card.hBoxLayout.addWidget(self._ocr_source_combo)
        self._ocr_source_card.hBoxLayout.addSpacing(16)
        self._ocr_group.addSettingCard(self._ocr_source_card)

        self._ocr_cuda_detect_card = PushSettingCard(
            "检测",
            FluentIcon.VPN,
            "检测 CUDA 环境",
            "检测是否可使用 GPU，并给出 OCR 模型建议",
        )
        self._ocr_cuda_detect_card.clicked.connect(self._manual_detect_cuda)
        self._ocr_group.addSettingCard(self._ocr_cuda_detect_card)

        self.expandLayout.addWidget(self._ocr_group)

        # ── Cache Management Group ──
        self._cache_group = SettingCardGroup("缓存管理", self.scrollWidget)

        # Cache size card
        self._cache_size_card = PushSettingCard(
            "清空缓存",
            FluentIcon.DELETE,
            "缓存大小",
            "计算中...",
        )
        self._cache_size_card.clicked.connect(self._clear_cache)
        self._cache_group.addSettingCard(self._cache_size_card)

        # Cache count card
        self._cache_count_card = PushSettingCard(
            "刷新",
            FluentIcon.SYNC,
            "缓存文件数",
            "计算中...",
        )
        self._cache_count_card.clicked.connect(self._refresh_cache_stats)
        self._cache_group.addSettingCard(self._cache_count_card)

        self.expandLayout.addWidget(self._cache_group)

        # ── Experimental Features Group ──
        self._experimental_group = SettingCardGroup("实验性功能", self.scrollWidget)

        # Auto-split enable
        self._auto_split_card = SettingCard(
            FluentIcon.CUT,
            "启用长文档自动分割",
            "当文档超过阈值时自动分割为多个片段处理",
            parent=self._experimental_group,
        )
        self._auto_split_switch = SwitchButton(self._auto_split_card)
        self._auto_split_switch.setChecked(self._main.config.enable_auto_split)
        self._auto_split_card.hBoxLayout.addWidget(
            self._auto_split_switch, 0, Qt.AlignmentFlag.AlignRight
        )
        self._auto_split_card.hBoxLayout.addSpacing(16)
        self._experimental_group.addSettingCard(self._auto_split_card)

        # Split threshold
        self._split_threshold_card = SettingCard(
            FluentIcon.ALIGNMENT,
            "分割阈值",
            "触发自动分割的字符数阈值",
            parent=self._experimental_group,
        )
        self._split_threshold_spinbox = SpinBox(self._split_threshold_card)
        self._split_threshold_spinbox.setRange(10000, 200000)
        self._split_threshold_spinbox.setSingleStep(10000)
        self._split_threshold_spinbox.setValue(self._main.config.split_threshold)
        self._split_threshold_card.hBoxLayout.addWidget(
            self._split_threshold_spinbox, 0, Qt.AlignmentFlag.AlignRight
        )
        self._split_threshold_card.hBoxLayout.addSpacing(16)
        self._experimental_group.addSettingCard(self._split_threshold_card)

        # Warning label
        self._warning_card = SettingCard(
            FluentIcon.INFO,
            "注意事项",
            "⚠️ 警告：这是实验性功能，可能影响卡片质量和生成时间。建议仅在处理超长文档时启用。",
            self.scrollWidget,
        )
        self._experimental_group.addSettingCard(self._warning_card)

        self.expandLayout.addWidget(self._experimental_group)

        # Action cards are merged into "Other Settings" and moved to bottom.
        is_zh = self._main.config.language == "zh"
        self._export_logs_card = PushSettingCard(
            "导出日志" if is_zh else "Export Logs",
            FluentIcon.DOCUMENT,
            "导出日志" if is_zh else "Export Logs",
            "导出应用日志文件用于问题排查"
            if is_zh
            else "Export application logs for troubleshooting",
        )
        self._export_logs_card.clicked.connect(self._export_logs)
        self._other_group.addSettingCard(self._export_logs_card)

        self._auto_update_card = SwitchSettingCard(
            FluentIcon.SYNC,
            "自动检查更新" if is_zh else "Auto Check Updates",
            "启动时自动检查新版本（仅查询，不自动安装）"
            if is_zh
            else "Check for new versions at startup (check only, no auto install)",
            parent=self._other_group,
        )
        self._other_group.addSettingCard(self._auto_update_card)

        self._check_update_card = PushSettingCard(
            "立即检查" if is_zh else "Check Now",
            FluentIcon.INFO,
            "版本更新" if is_zh else "Version Update",
            "查询 GitHub Releases 最新版本"
            if is_zh
            else "Query latest version from GitHub Releases",
        )
        self._check_update_card.clicked.connect(self._check_for_updates)
        self._other_group.addSettingCard(self._check_update_card)

        self._backup_config_card = PushSettingCard(
            "创建备份" if is_zh else "Create Backup",
            FluentIcon.DOCUMENT,
            "配置备份" if is_zh else "Config Backup",
            "保存当前加密配置快照，便于回滚" if is_zh else "Create encrypted config snapshot",
        )
        self._backup_config_card.clicked.connect(self._backup_current_config)
        self._other_group.addSettingCard(self._backup_config_card)

        self._restore_config_card = PushSettingCard(
            "从备份恢复" if is_zh else "Restore Backup",
            FluentIcon.RETURN,
            "配置回滚" if is_zh else "Config Rollback",
            "选择备份文件并恢复配置（即时生效）"
            if is_zh
            else "Select backup file and restore config immediately",
        )
        self._restore_config_card.clicked.connect(self._restore_config_backup)
        self._other_group.addSettingCard(self._restore_config_card)

        self._reset_card = PushSettingCard(
            "恢复默认",
            FluentIcon.RETURN,
            "重置设置",
            "将所有设置恢复为默认值",
        )
        self._reset_card.clicked.connect(self._reset_to_default)
        self._other_group.addSettingCard(self._reset_card)

        # Keep "Other Settings" at the very bottom.
        self.expandLayout.addWidget(self._other_group)

    def _load_config(self) -> None:
        """Load configuration from main window."""
        config = self._main.config
        self._providers = [p.model_copy() for p in config.llm_providers]
        self._active_provider_id = config.active_provider_id

        # Update provider list
        self._update_provider_list()

        # LLM settings
        temp_value = int(config.llm_temperature * 10)
        self._temperature_slider.setValue(temp_value)
        self._max_tokens_spin.setValue(config.llm_max_tokens)
        self._concurrency_spin.setValue(getattr(config, "llm_concurrency", 2))
        self._adaptive_concurrency_switch.setChecked(
            getattr(config, "llm_adaptive_concurrency", True)
        )
        self._concurrency_max_spin.setValue(getattr(config, "llm_concurrency_max", 6))

        # Anki settings
        self._anki_url_edit.setText(config.anki_connect_url)
        self._anki_key_edit.setText(config.anki_connect_key)
        self._default_deck_edit.setText(config.default_deck)
        self._default_tags_edit.setText(", ".join(config.default_tags))

        # Other settings
        theme_map = {"light": 0, "dark": 1, "auto": 2}
        self._theme_combo.setCurrentIndex(theme_map.get(config.theme, 0))

        lang_map = {"zh": 0, "en": 1}
        self._language_combo.setCurrentIndex(lang_map.get(config.language, 0))
        self._auto_update_card.setChecked(getattr(config, "auto_check_updates", True))

        # Proxy settings - load mode and manual URL
        proxy_mode = getattr(config, "proxy_mode", "system")
        proxy_mode_map = {"system": 0, "manual": 1, "none": 2}
        self._proxy_mode_combo.blockSignals(True)
        self._proxy_mode_combo.setCurrentIndex(proxy_mode_map.get(proxy_mode, 0))
        self._proxy_mode_combo.blockSignals(False)
        self._proxy_edit.setText(config.proxy_url)
        # Show/hide manual input based on mode
        self._proxy_edit.setVisible(proxy_mode == "manual")

        self._ocr_correction_switch.setChecked(config.ocr_correction)

        self._set_combo_current_data(self._ocr_mode_combo, getattr(config, "ocr_mode", "local"))
        self._set_combo_current_data(
            self._ocr_model_tier_combo, getattr(config, "ocr_model_tier", "lite")
        )
        self._set_combo_current_data(
            self._ocr_source_combo, getattr(config, "ocr_model_source", "official")
        )
        self._set_combo_current_data(
            self._ocr_cloud_provider_combo, getattr(config, "ocr_cloud_provider", "mineru")
        )
        self._ocr_cloud_endpoint_edit.setText(
            getattr(config, "ocr_cloud_endpoint", "https://mineru.net")
        )
        self._ocr_cloud_api_key_edit.setText(getattr(config, "ocr_cloud_api_key", ""))
        self._ocr_cuda_auto_card.setChecked(getattr(config, "ocr_auto_cuda_upgrade", True))
        self._refresh_ocr_recommendation()
        self._update_ocr_mode_ui()

        # Experimental features
        self._auto_split_switch.setChecked(config.enable_auto_split)
        self._split_threshold_spinbox.setValue(config.split_threshold)

        # Cache statistics
        self._refresh_cache_stats_deferred()

        # Log level
        log_level_map = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        self._log_level_combobox.setCurrentIndex(log_level_map.get(config.log_level, 1))

    def _update_provider_list(self) -> None:
        """Update provider table display."""
        self._provider_table.setRowCount(len(self._providers))

        can_delete = len(self._providers) > 1

        for row, provider in enumerate(self._providers):
            is_active = provider.id == self._active_provider_id

            # Column 0: Name
            name_item = QTableWidgetItem(provider.name)
            self._provider_table.setItem(row, 0, name_item)

            # Column 1: Model
            model_text = provider.model.strip() if provider.model else "未设置"
            model_item = QTableWidgetItem(model_text)
            self._provider_table.setItem(row, 1, model_item)

            # Column 2: Base URL
            url_text = provider.base_url.strip() if provider.base_url else "未设置"
            url_item = QTableWidgetItem(url_text)
            self._provider_table.setItem(row, 2, url_item)

            # Column 3: RPM
            rpm_text = str(provider.rpm_limit) if provider.rpm_limit > 0 else "无限制"
            rpm_item = QTableWidgetItem(rpm_text)
            rpm_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._provider_table.setItem(row, 3, rpm_item)

            # Column 4: Action buttons
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(2, 2, 2, 2)
            action_layout.setSpacing(2)

            # Active state button: active=primary(强调色), inactive=flat(no color).
            if is_active:
                activate_btn = PrimaryPushButton("当前")
                activate_btn.setFixedSize(64, 28)
            else:
                activate_btn = PushButton("激活")
                activate_btn.setFixedSize(64, 28)
                activate_btn.clicked.connect(lambda checked, p=provider: self._activate_provider(p))
            action_layout.addWidget(activate_btn)

            # Edit button
            edit_btn = PushButton("编辑")
            edit_btn.setFixedSize(52, 28)
            edit_btn.clicked.connect(lambda checked, p=provider: self._edit_provider(p))
            action_layout.addWidget(edit_btn)

            # Test button
            test_btn = PushButton("测试")
            test_btn.setFixedSize(52, 28)
            test_btn.clicked.connect(lambda checked, p=provider: self._test_provider_connection(p))
            action_layout.addWidget(test_btn)

            # Delete button
            delete_btn = PushButton("删除")
            delete_btn.setFixedSize(52, 28)
            delete_btn.setEnabled(can_delete)
            delete_btn.clicked.connect(lambda checked, p=provider: self._delete_provider(p))
            action_layout.addWidget(delete_btn)
            self._provider_table.setCellWidget(row, 4, action_widget)

    @staticmethod
    def _set_combo_current_data(combo: ComboBox, target_value: str) -> None:
        for index in range(combo.count()):
            if combo.itemData(index) == target_value:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    @staticmethod
    def _get_combo_current_data(combo: ComboBox, fallback: str) -> str:
        current = combo.currentData()
        if current is None:
            return fallback
        return str(current)

    def _current_proxy_url(self) -> str:
        """Return effective proxy URL consistent with runtime config save logic."""
        proxy_mode_values = ["system", "manual", "none"]
        index = self._proxy_mode_combo.currentIndex()
        if index < 0 or index >= len(proxy_mode_values):
            return ""
        mode = proxy_mode_values[index]
        if mode != "manual":
            return ""
        return self._proxy_edit.text().strip()

    def _current_ocr_cloud_proxy_url(self, provider: str) -> str:
        normalized = str(provider or "").strip().lower()
        if normalized == "mineru":
            return ""
        return self._current_proxy_url()

    def _refresh_ocr_recommendation(self) -> None:
        tier = self._get_combo_current_data(self._ocr_model_tier_combo, "lite")
        is_zh = self._main.config.language == "zh"
        short_recommendations = {
            "lite": (
                "推荐：8G / 无独显",
                "Rec: 8G / iGPU",
            ),
            "standard": (
                "推荐：16G / 4核+",
                "Rec: 16G / 4+ cores",
            ),
            "accuracy": (
                "推荐：16G+ / 独显",
                "Rec: 16G+ / dGPU",
            ),
        }
        zh_text, en_text = short_recommendations.get(tier, short_recommendations["lite"])
        text = zh_text if is_zh else en_text
        self._ocr_model_recommend_label.setText(text)

    def _on_ocr_mode_changed(self, *_args) -> None:
        self._update_ocr_mode_ui()

    def _set_ocr_card_collapsed(self, card: QWidget, *, collapsed: bool) -> None:
        key = id(card)
        if key not in self._ocr_card_height_bounds:
            self._ocr_card_height_bounds[key] = (card.minimumHeight(), card.maximumHeight())

        if collapsed:
            card.setMinimumHeight(0)
            card.setMaximumHeight(0)
            card.hide()
        else:
            min_height, max_height = self._ocr_card_height_bounds[key]
            card.setMinimumHeight(min_height)
            card.setMaximumHeight(max_height)
            card.show()

        card.updateGeometry()

    def _update_ocr_mode_ui(self) -> None:
        mode = self._get_combo_current_data(self._ocr_mode_combo, "local")
        is_cloud = mode == "cloud"

        local_cards = (
            self._ocr_cuda_auto_card,
            self._ocr_model_tier_card,
            self._ocr_source_card,
            self._ocr_cuda_detect_card,
        )
        cloud_cards = (
            self._ocr_cloud_provider_card,
            self._ocr_cloud_endpoint_card,
            self._ocr_cloud_api_key_card,
            self._ocr_cloud_limit_card,
        )

        for card in local_cards:
            self._set_ocr_card_collapsed(card, collapsed=is_cloud)
        for card in cloud_cards:
            self._set_ocr_card_collapsed(card, collapsed=not is_cloud)

        self._ocr_group.adjustSize()
        self._cache_group.adjustSize()
        self.scrollWidget.adjustSize()
        self.expandLayout.activate()
        self.scrollWidget.updateGeometry()

    def _test_ocr_connectivity(self) -> None:
        is_zh = self._main.config.language == "zh"
        mode = self._get_combo_current_data(self._ocr_mode_combo, "local")

        if mode == "cloud":
            provider = self._get_combo_current_data(self._ocr_cloud_provider_combo, "mineru")
            endpoint = self._ocr_cloud_endpoint_edit.text().strip()
            api_key = self._ocr_cloud_api_key_edit.text().strip()
            if not endpoint:
                self._show_info_bar(
                    "warning",
                    "配置不完整" if is_zh else "Incomplete Config",
                    "请先填写云 OCR Endpoint。"
                    if is_zh
                    else "Please fill cloud OCR endpoint first.",
                    duration=3500,
                )
                return
            if not api_key:
                self._show_info_bar(
                    "warning",
                    "配置不完整" if is_zh else "Incomplete Config",
                    "请先填写云 OCR API Key。"
                    if is_zh
                    else "Please fill cloud OCR API key first.",
                    duration=3500,
                )
                return

            from ankismart.ui.workers import OCRCloudConnectionWorker

            self._cleanup_ocr_cloud_test_worker()
            worker = OCRCloudConnectionWorker(
                provider=provider,
                endpoint=endpoint,
                api_key=api_key,
                proxy_url=self._current_ocr_cloud_proxy_url(provider),
            )
            self._ocr_cloud_test_worker = worker

            self._show_info_bar(
                "info",
                "测试中" if is_zh else "Testing",
                "正在测试云 OCR 连通性..."
                if is_zh
                else "Testing cloud OCR connectivity...",
                duration=1800,
            )

            def _on_finished(ok: bool, detail: str) -> None:
                try:
                    if ok:
                        self._show_info_bar(
                            "success",
                            "连接成功" if is_zh else "Connected",
                            "云 OCR 连通正常。"
                            if is_zh
                            else "Cloud OCR connectivity is OK.",
                            duration=3000,
                        )
                    else:
                        self._show_info_bar(
                            "error",
                            "连接失败" if is_zh else "Connection Failed",
                            detail
                            or (
                                "云 OCR 连通性测试失败"
                                if is_zh
                                else "Cloud OCR test failed"
                            ),
                            duration=5000,
                        )
                finally:
                    self._cleanup_ocr_cloud_test_worker()

            worker.finished.connect(_on_finished)
            worker.start()
            return

        tier = self._get_combo_current_data(self._ocr_model_tier_combo, "lite")
        source = self._get_combo_current_data(self._ocr_source_combo, "official")
        try:
            configure_ocr_runtime(model_tier=tier, model_source=source)
            missing = get_missing_ocr_models(model_tier=tier, model_source=source)
        except OCRRuntimeUnavailableError:
            self._show_info_bar(
                "warning",
                "OCR 不可用" if is_zh else "OCR Unavailable",
                (
                    "当前安装包未包含 OCR 运行时。"
                    if is_zh
                    else "This package does not include OCR runtime."
                ),
                duration=4500,
            )
            return

        if not missing:
            self._show_info_bar(
                "success",
                "OCR 连通正常" if is_zh else "OCR Connection OK",
                "本地 OCR 模型已就绪。" if is_zh else "Local OCR models are ready.",
                duration=3000,
            )
            return

        missing_text = ", ".join(missing)
        self._show_info_bar(
            "warning",
            "OCR 模型缺失" if is_zh else "OCR Models Missing",
            (
                f"检测到缺失模型：{missing_text}"
                if is_zh
                else f"Missing models detected: {missing_text}"
            ),
            duration=5000,
        )

    def _manual_detect_cuda(self) -> None:
        is_zh = self._main.config.language == "zh"
        has_cuda = is_cuda_available(force_refresh=True)
        tier = self._get_combo_current_data(self._ocr_model_tier_combo, "lite")

        if has_cuda:
            content = (
                "检测到 CUDA 环境。建议至少使用“标准”模型档位。"
                if is_zh
                else "CUDA detected. Standard model tier or above is recommended."
            )
            if tier == "lite":
                content += "（当前为轻量档）" if is_zh else " (Current: Lite tier)"
            self._show_info_bar(
                "success",
                "CUDA 可用" if is_zh else "CUDA Available",
                content,
                duration=4000,
            )
            return

        self._show_info_bar(
            "info",
            "CUDA 不可用" if is_zh else "CUDA Unavailable",
            "未检测到可用 CUDA，建议使用轻量模型档位。"
            if is_zh
            else "No CUDA detected, Lite model tier is recommended.",
            duration=4000,
        )

    def _add_provider(self) -> None:
        """Open dialog to add a new provider."""
        dialog = LLMProviderDialog(parent=self)
        dialog.saved.connect(self._on_provider_saved)
        dialog.exec()

    def _edit_provider(self, provider: LLMProviderConfig) -> None:
        """Open dialog to edit a provider."""
        dialog = LLMProviderDialog(provider, parent=self)
        dialog.saved.connect(self._on_provider_saved)
        dialog.exec()

    def _on_provider_saved(self, provider: LLMProviderConfig) -> None:
        """Handle provider save from dialog."""
        # Check if provider exists
        existing = next((p for p in self._providers if p.id == provider.id), None)
        if existing:
            # Update existing
            idx = self._providers.index(existing)
            self._providers[idx] = provider
        else:
            # Add new
            self._providers.append(provider)
            if not self._active_provider_id:
                self._active_provider_id = provider.id

        self._update_provider_list()
        self._save_config_silent(show_feedback=False)

    def _delete_provider(self, provider: LLMProviderConfig) -> None:
        """Delete a provider."""
        if len(self._providers) <= 1:
            QMessageBox.warning(self, "无法删除", "至少需要保留一个提供商配置")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除提供商 '{provider.name}' 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._providers.remove(provider)
            if provider.id == self._active_provider_id and self._providers:
                self._active_provider_id = self._providers[0].id
            self._update_provider_list()
            self._save_config_silent(show_feedback=False)

    def _activate_provider(self, provider: LLMProviderConfig) -> None:
        """Set a provider as active."""
        self._active_provider_id = provider.id
        self._update_provider_list()
        self._save_config_silent(show_feedback=False)

    def _test_provider_connection(self, provider: LLMProviderConfig) -> None:
        """Test connection to a specific LLM provider."""
        from ankismart.ui.workers import ProviderConnectionWorker

        self._cleanup_provider_test_worker()
        self._show_info_bar(
            "info",
            "测试中",
            f"正在测试提供商「{provider.name}」连通性...",
            duration=1500,
        )

        worker = ProviderConnectionWorker(
            provider,
            proxy_url=self._current_proxy_url(),
            temperature=self._temperature_slider.value() / 10,
            max_tokens=self._max_tokens_spin.value(),
        )
        self._provider_test_worker = worker

        def _on_finished(ok: bool, err: str) -> None:
            try:
                self._on_provider_test_result(provider.name, ok, err)
            finally:
                self._cleanup_provider_test_worker()

        worker.finished.connect(_on_finished)
        worker.start()

    def _on_provider_test_result(self, provider_name: str, connected: bool, error: str) -> None:
        """Handle provider connection test result."""
        if connected:
            self._show_info_bar(
                "success", "连接成功", f"提供商「{provider_name}」连通正常", duration=3500
            )
            return

        if error:
            code, detail = self._parse_error_payload(error)
            if code is not None:
                info = get_error_info(code, self._main.config.language)
                message = info["message"] if not detail else f"{info['message']} ({detail})"
                self._show_info_bar("error", info["title"], message, duration=5000)
                return

            self._show_info_bar(
                "error",
                "连接失败",
                f"提供商「{provider_name}」连接失败：{error}",
                duration=5000,
            )
            return

        self._show_info_bar(
            "warning", "连接失败", f"提供商「{provider_name}」未通过连通性测试", duration=4000
        )

    @staticmethod
    def _parse_error_payload(error: str) -> tuple[ErrorCode | None, str]:
        text = str(error).strip()
        if not (text.startswith("[") and "]" in text):
            return None, text

        code_token, _, remainder = text.partition("]")
        code_str = code_token.lstrip("[").strip()
        try:
            return ErrorCode(code_str), remainder.strip()
        except ValueError:
            return None, text

    def _test_connection(self) -> None:
        """Test connection to AnkiConnect."""
        from ankismart.ui.workers import ConnectionCheckWorker

        self._cleanup_anki_test_worker()
        url = self._anki_url_edit.text() or "http://127.0.0.1:8765"
        key = self._anki_key_edit.text()
        proxy = self._current_proxy_url()

        self._test_connection_card.setContent("测试中...")
        self._show_info_bar("info", "测试中", "正在检测 AnkiConnect 连接...", duration=1500)

        worker = ConnectionCheckWorker(url, key, proxy_url=proxy)
        self._anki_test_worker = worker

        def _on_finished(connected: bool) -> None:
            try:
                self._on_test_result(connected)
            finally:
                self._cleanup_anki_test_worker()

        worker.finished.connect(_on_finished)
        worker.start()

    def _on_test_result(self, connected: bool) -> None:
        """Handle test connection result."""
        if connected:
            self._test_connection_card.setContent("连接成功！")
            self._show_info_bar("success", "连接成功", "AnkiConnect 连通正常", duration=3500)
        else:
            self._test_connection_card.setContent("连接失败")
            self._show_info_bar(
                "error",
                "连接失败",
                "无法连接到 AnkiConnect，请检查 URL/密钥与代理设置",
                duration=5000,
            )
        self._main.set_connection_status(connected)

    def _refresh_cache_stats(self) -> None:
        """Refresh cache statistics display."""
        from ankismart.converter.cache import get_cache_stats

        stats = get_cache_stats()
        self._apply_cache_stats(stats)

    def _refresh_cache_stats_deferred(self) -> None:
        """Refresh cache statistics in a background thread to avoid UI stalls."""
        self._cache_stats_seq += 1
        seq = self._cache_stats_seq
        is_zh = self._main.config.language == "zh"
        pending_text = "统计中..." if is_zh else "Loading..."
        self._cache_size_card.setContent(pending_text)
        self._cache_count_card.setContent(pending_text)
        self._cache_stats_future = _CACHE_STATS_EXECUTOR.submit(self._compute_cache_stats)
        QTimer.singleShot(10, lambda token=seq: self._poll_cache_stats_future(token))

    @staticmethod
    def _compute_cache_stats() -> dict[str, float | int]:
        from ankismart.converter.cache import get_cache_stats

        return get_cache_stats()

    def _poll_cache_stats_future(self, token: int) -> None:
        if token != self._cache_stats_seq:
            return
        future = self._cache_stats_future
        if future is None:
            return
        if not future.done():
            QTimer.singleShot(30, lambda token=token: self._poll_cache_stats_future(token))
            return

        self._cache_stats_future = None
        is_zh = self._main.config.language == "zh"
        try:
            stats = future.result()
        except Exception:
            failed_text = "统计失败" if is_zh else "Failed to load"
            self._cache_size_card.setContent(failed_text)
            self._cache_count_card.setContent(failed_text)
            return
        self._apply_cache_stats(stats)

    def _apply_cache_stats(self, stats: dict[str, float | int]) -> None:
        from ankismart.ui.i18n import t

        size_mb = stats["size_mb"]
        count = stats["count"]

        # Update cache size card
        if size_mb < 0.01 and count == 0:
            size_text = t("settings.cache_empty_msg", self._main.config.language)
        else:
            size_text = t("settings.cache_size_value", self._main.config.language, size=size_mb)
        self._cache_size_card.setContent(size_text)

        # Update cache count card
        if count == 0:
            count_text = t("settings.cache_empty_msg", self._main.config.language)
        else:
            count_text = t("settings.cache_count_value", self._main.config.language, count=count)
        self._cache_count_card.setContent(count_text)

    def _clear_cache(self) -> None:
        """Clear all cache files."""
        from ankismart.converter.cache import clear_cache, get_cache_stats
        from ankismart.ui.i18n import t

        stats = get_cache_stats()
        size_mb = stats["size_mb"]
        count = stats["count"]

        # Check if cache is empty
        if count == 0:
            self._show_info_bar(
                "info",
                t("settings.cache_empty", self._main.config.language),
                t("settings.cache_empty_msg", self._main.config.language),
                duration=3000,
            )
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            t("settings.confirm_clear_cache", self._main.config.language),
            t(
                "settings.confirm_clear_cache_msg",
                self._main.config.language,
                count=count,
                size=size_mb,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = clear_cache()
            if success:
                self._show_info_bar(
                    "success",
                    t("settings.cache_cleared", self._main.config.language),
                    t("settings.cache_cleared_msg", self._main.config.language, size=size_mb),
                    duration=3500,
                )
                # Refresh stats display
                self._refresh_cache_stats()
            else:
                self._show_info_bar(
                    "error",
                    t("settings.cache_clear_failed", self._main.config.language),
                    t("settings.cache_clear_failed_msg", self._main.config.language),
                    duration=5000,
                )

    def _on_log_level_changed(self, index: int) -> None:
        """Handle log level change."""
        from ankismart.core.logging import set_log_level
        from ankismart.ui.i18n import t

        log_level_values = ["DEBUG", "INFO", "WARNING", "ERROR"]
        log_level = log_level_values[index]

        # Apply log level immediately
        set_log_level(log_level)

        # Show notification
        self._show_info_bar(
            "success",
            t("log.level_changed", self._main.config.language),
            t("log.level_changed_msg", self._main.config.language, level=log_level),
            duration=2000,
        )

    def _on_proxy_mode_changed(self, index: int) -> None:
        """Handle proxy mode change - show/hide manual input."""
        from ankismart.ui.i18n import t

        # 0: System, 1: Manual, 2: None
        is_manual = index == 1
        self._proxy_edit.setVisible(is_manual)
        if not self.isVisible():
            return

        if index == 0:
            mode_text = "系统代理" if self._main.config.language == "zh" else "System Proxy"
        elif index == 1:
            mode_text = "手动配置" if self._main.config.language == "zh" else "Manual Proxy"
        else:
            mode_text = "不使用代理" if self._main.config.language == "zh" else "No Proxy"

        self._show_info_bar(
            "info",
            t("settings.proxy", self._main.config.language),
            f"{mode_text}",
            duration=1500,
        )

    def _open_log_directory(self) -> None:
        """Open the log directory in file explorer."""
        from ankismart.core.logging import get_log_directory

        log_dir = get_log_directory()
        if log_dir.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))
        else:
            from ankismart.ui.i18n import t

            self._show_info_bar(
                "warning",
                t("log.no_logs_found", self._main.config.language),
                "",
                duration=3000,
            )

    @staticmethod
    def _parse_version_tuple(version_text: str) -> tuple[int, ...]:
        cleaned = (version_text or "").strip().lstrip("vV")
        parts = []
        for chunk in cleaned.split("."):
            match = re.match(r"^(\d+)", chunk)
            parts.append(int(match.group(1)) if match else 0)
        return tuple(parts) if parts else (0,)

    @staticmethod
    def _github_update_headers() -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Ankismart/{__version__}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _fetch_latest_github_release(self) -> tuple[str, str]:
        latest_url = _GITHUB_RELEASES_WEB_URL
        proxy_url = self._current_proxy_url()
        client_kwargs: dict[str, object] = {"timeout": 8.0}
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        with httpx.Client(**client_kwargs) as client:
            headers = self._github_update_headers()

            latest_response = client.get(_GITHUB_RELEASES_API_URL, headers=headers)
            if latest_response.status_code < 400:
                payload = latest_response.json() if latest_response.content else {}
                if isinstance(payload, dict):
                    latest_version = str(payload.get("tag_name", "")).strip().lstrip("vV")
                    latest_url = str(payload.get("html_url", latest_url)).strip() or latest_url
                    if latest_version:
                        return latest_version, latest_url

            tags_response = client.get(_GITHUB_TAGS_API_URL, headers=headers)
            tags_response.raise_for_status()
            payload = tags_response.json() if tags_response.content else []
            if isinstance(payload, list) and payload:
                first = payload[0]
                if isinstance(first, dict):
                    latest_version = str(first.get("name", "")).strip().lstrip("vV")
                    if latest_version:
                        return latest_version, latest_url

        raise RuntimeError("GitHub did not return a valid latest version tag")

    def _check_for_updates(self) -> None:
        """Check latest version from GitHub releases."""
        is_zh = self._main.config.language == "zh"
        latest_version = ""
        latest_url = _GITHUB_RELEASES_WEB_URL
        error = ""

        try:
            latest_version, latest_url = self._fetch_latest_github_release()
        except Exception as exc:
            error = str(exc)

        now = datetime.now().isoformat(timespec="seconds")
        config = self._main.config.model_copy(
            update={
                "last_update_check_at": now,
                "last_update_version_seen": (
                    latest_version or self._main.config.last_update_version_seen
                ),
            }
        )
        self._main.apply_runtime_config(
            config,
            persist=True,
            changed_fields={"last_update_check_at", "last_update_version_seen"},
        )

        if error:
            self._show_info_bar(
                "warning",
                "检查更新失败" if is_zh else "Update Check Failed",
                error,
                duration=3500,
            )
            return

        current_tuple = self._parse_version_tuple(__version__)
        latest_tuple = self._parse_version_tuple(latest_version)
        if latest_tuple > current_tuple:
            reply = QMessageBox.question(
                self,
                "发现新版本" if is_zh else "Update Available",
                (
                    f"当前版本 {__version__}，最新版本 {latest_version}。\n是否打开发布页面？"
                    if is_zh
                    else (
                        f"Current version {__version__}, latest {latest_version}.\n"
                        "Open release page now?"
                    )
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(latest_url))
            return

        self._show_info_bar(
            "success",
            "已是最新版本" if is_zh else "Up to Date",
            f"当前版本 {__version__}" if is_zh else f"Current version {__version__}",
            duration=2500,
        )

    def _backup_current_config(self) -> None:
        is_zh = self._main.config.language == "zh"
        try:
            backup = create_config_backup(self._main.config, reason="manual")
        except Exception as exc:
            self._show_info_bar(
                "error",
                "备份失败" if is_zh else "Backup Failed",
                str(exc),
                duration=4000,
            )
            return

        self._show_info_bar(
            "success",
            "备份成功" if is_zh else "Backup Created",
            str(backup),
            duration=3200,
        )

    def _restore_config_backup(self) -> None:
        is_zh = self._main.config.language == "zh"
        backups = list_config_backups(limit=30)
        initial_dir = str(CONFIG_BACKUP_DIR if CONFIG_BACKUP_DIR.exists() else Path.home())
        initial_file = str(backups[0]) if backups else initial_dir
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置备份文件" if is_zh else "Select Config Backup",
            initial_file,
            "YAML Files (*.yaml *.yml)",
        )
        if not selected_path:
            return

        confirm = QMessageBox.question(
            self,
            "确认恢复" if is_zh else "Confirm Restore",
            "恢复后将立即覆盖当前配置，是否继续？"
            if is_zh
            else "Current config will be overwritten immediately. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            restored = restore_config_from_backup(Path(selected_path))
            self._main.apply_runtime_config(restored, persist=False)
            self._load_config()
        except Exception as exc:
            self._show_info_bar(
                "error",
                "恢复失败" if is_zh else "Restore Failed",
                str(exc),
                duration=4000,
            )
            return

        self._show_info_bar(
            "success",
            "恢复成功" if is_zh else "Restore Succeeded",
            "配置已从备份恢复并生效" if is_zh else "Config restored from backup",
            duration=3000,
        )

    def _save_config(self) -> None:
        """Save configuration."""
        from ankismart.ui.i18n import t

        # Validate active provider
        if not self._providers:
            QMessageBox.warning(
                self,
                t("settings.error", self._main.config.language),
                t("settings.must_have_provider", self._main.config.language),
            )
            return

        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        self._save_config_silent(show_feedback=True)

    @staticmethod
    def _should_reset_ocr_runtime(old_config, new_config) -> bool:
        tracked_fields = (
            "ocr_mode",
            "ocr_model_tier",
            "ocr_model_source",
        )
        return any(
            getattr(old_config, name, None) != getattr(new_config, name, None)
            for name in tracked_fields
        )

    def _save_config_silent(self, *, show_feedback: bool = False) -> None:
        """Save configuration without showing success message (for auto-save)."""
        # Validate active provider
        if not self._providers:
            return

        # Parse tags
        tags = [tag.strip() for tag in self._default_tags_edit.text().split(",") if tag.strip()]
        if not tags:
            tags = ["ankismart"]

        # Theme switching is controlled in sidebar, settings page does not override it.
        lang_values = ["zh", "en"]
        language = lang_values[self._language_combo.currentIndex()]

        # Get temperature (convert from 0-20 to 0.0-2.0)
        temperature = self._temperature_slider.value() / 10.0
        concurrency_cap = self._concurrency_max_spin.value()
        concurrency_value = self._concurrency_spin.value()
        if concurrency_value > 0:
            concurrency_value = min(concurrency_value, concurrency_cap)

        # Get log level
        log_level_values = ["DEBUG", "INFO", "WARNING", "ERROR"]
        log_level = log_level_values[self._log_level_combobox.currentIndex()]

        # Get proxy settings
        proxy_mode_values = ["system", "manual", "none"]
        proxy_mode = proxy_mode_values[self._proxy_mode_combo.currentIndex()]
        proxy_url = self._proxy_edit.text().strip() if proxy_mode == "manual" else ""

        ocr_mode = self._get_combo_current_data(self._ocr_mode_combo, "local")
        ocr_model_tier = self._get_combo_current_data(self._ocr_model_tier_combo, "lite")
        ocr_model_source = self._get_combo_current_data(self._ocr_source_combo, "official")
        ocr_cloud_provider = self._get_combo_current_data(self._ocr_cloud_provider_combo, "mineru")
        ocr_cloud_endpoint = self._ocr_cloud_endpoint_edit.text().strip() or "https://mineru.net"
        ocr_cloud_api_key = self._ocr_cloud_api_key_edit.text().strip()
        ocr_model_locked_by_user = getattr(
            self._main.config, "ocr_model_locked_by_user", False
        ) or ocr_model_tier != getattr(self._main.config, "ocr_model_tier", "lite")

        # Update config
        config = self._main.config.model_copy(
            update={
                "llm_providers": self._providers,
                "active_provider_id": self._active_provider_id,
                "anki_connect_url": self._anki_url_edit.text() or "http://127.0.0.1:8765",
                "anki_connect_key": self._anki_key_edit.text(),
                "default_deck": self._default_deck_edit.text() or "Default",
                "default_tags": tags,
                "ocr_correction": self._ocr_correction_switch.isChecked(),
                "ocr_mode": ocr_mode,
                "ocr_model_tier": ocr_model_tier,
                "ocr_model_source": ocr_model_source,
                "ocr_cloud_provider": ocr_cloud_provider,
                "ocr_cloud_endpoint": ocr_cloud_endpoint,
                "ocr_cloud_api_key": ocr_cloud_api_key,
                "ocr_auto_cuda_upgrade": self._ocr_cuda_auto_card.isChecked(),
                "ocr_model_locked_by_user": ocr_model_locked_by_user,
                "llm_temperature": temperature,
                "llm_max_tokens": self._max_tokens_spin.value(),
                "llm_concurrency": concurrency_value,
                "llm_adaptive_concurrency": self._adaptive_concurrency_switch.isChecked(),
                "llm_concurrency_max": concurrency_cap,
                "proxy_mode": proxy_mode,
                "proxy_url": proxy_url,
                "language": language,
                "auto_check_updates": self._auto_update_card.isChecked(),
                "log_level": log_level,
                "enable_auto_split": self._auto_split_switch.isChecked(),
                "split_threshold": self._split_threshold_spinbox.value(),
            }
        )

        old_config = self._main.config
        should_reset_ocr_runtime = self._should_reset_ocr_runtime(old_config, config)

        try:
            apply_runtime = getattr(self._main, "apply_runtime_config", None)
            if callable(apply_runtime):
                apply_runtime(config, persist=True)
            else:
                self._main.config = config
                save_config(config)

            # Configure OCR runtime only when OCR settings are changed.
            if should_reset_ocr_runtime and getattr(config, "ocr_mode", "local") == "local":
                try:
                    configure_ocr_runtime(
                        model_tier=config.ocr_model_tier,
                        model_source=config.ocr_model_source,
                        reset_ocr_instance=True,
                    )
                except OCRRuntimeUnavailableError:
                    pass

            if show_feedback:
                from ankismart.ui.i18n import t

                self._show_info_bar(
                    "success",
                    t("settings.success", self._main.config.language),
                    t("settings.save_success", self._main.config.language),
                    duration=2000,
                )
        except Exception as exc:
            if show_feedback:
                from ankismart.ui.i18n import t

                QMessageBox.critical(
                    self,
                    t("settings.error", self._main.config.language),
                    t("settings.save_failed", self._main.config.language, error=str(exc)),
                )

    def _reset_to_default(self) -> None:
        """Reset configuration to default values."""
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要将所有设置恢复为默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            from ankismart.core.config import AppConfig

            default_config = AppConfig()
            apply_runtime = getattr(self._main, "apply_runtime_config", None)
            if callable(apply_runtime):
                apply_runtime(default_config, persist=True)
            else:
                self._main.config = default_config
                save_config(default_config)
            self._load_config()
            QMessageBox.information(self, "重置完成", "设置已恢复为默认值")

    def _export_logs(self) -> None:
        """Export application logs to a zip file."""
        from datetime import datetime
        from pathlib import Path

        from ankismart.ui.i18n import t
        from ankismart.ui.log_exporter import LogExporter

        try:
            exporter = LogExporter()

            # Check if logs exist
            log_count = exporter.get_log_count()
            if log_count == 0:
                self._show_info_bar(
                    "warning",
                    t("log.no_logs_found", self._main.config.language),
                    "",
                    duration=3000,
                )
                return

            # Show file dialog
            default_filename = f"ankismart_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                t("log.select_location", self._main.config.language),
                default_filename,
                t("log.zip_file", self._main.config.language),
            )

            if not file_path:
                return

            # Show progress
            self._show_info_bar(
                "info",
                t("log.exporting", self._main.config.language),
                "",
                duration=2000,
            )

            # Export logs
            exporter.export_logs(Path(file_path))

            # Show success message
            self._show_info_bar(
                "success",
                t("log.export_success", self._main.config.language),
                t("log.export_success_msg", self._main.config.language, path=file_path),
                duration=5000,
            )

        except FileNotFoundError:
            self._show_info_bar(
                "warning",
                t("log.no_logs_found", self._main.config.language),
                "",
                duration=3000,
            )
        except Exception as e:
            self._show_info_bar(
                "error",
                t("log.export_failed", self._main.config.language),
                t("log.export_failed_msg", self._main.config.language, error=str(e)),
                duration=5000,
            )

    def _cleanup_provider_test_worker(self, *_args) -> None:
        worker = self.__dict__.get("_provider_test_worker")
        if worker is None:
            return
        if hasattr(worker, "isRunning") and worker.isRunning():
            worker.wait(200)
            if worker.isRunning():
                return
        self.__dict__["_provider_test_worker"] = None
        if hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def _cleanup_anki_test_worker(self, *_args) -> None:
        worker = self.__dict__.get("_anki_test_worker")
        if worker is None:
            return
        if hasattr(worker, "isRunning") and worker.isRunning():
            worker.wait(200)
            if worker.isRunning():
                return
        self.__dict__["_anki_test_worker"] = None
        if hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def _cleanup_ocr_cloud_test_worker(self, *_args) -> None:
        worker = self.__dict__.get("_ocr_cloud_test_worker")
        if worker is None:
            return
        if hasattr(worker, "isRunning") and worker.isRunning():
            worker.wait(200)
            if worker.isRunning():
                return
        self.__dict__["_ocr_cloud_test_worker"] = None
        if hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def closeEvent(self, event):  # noqa: N802
        """Stop test workers gracefully during application shutdown."""
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        if self._provider_test_worker and self._provider_test_worker.isRunning():
            self._provider_test_worker.requestInterruption()
            self._provider_test_worker.wait(300)
        if self._anki_test_worker and self._anki_test_worker.isRunning():
            self._anki_test_worker.requestInterruption()
            self._anki_test_worker.wait(300)
        if self._ocr_cloud_test_worker and self._ocr_cloud_test_worker.isRunning():
            self._ocr_cloud_test_worker.requestInterruption()
            self._ocr_cloud_test_worker.wait(300)
        self._cleanup_provider_test_worker()
        self._cleanup_anki_test_worker()
        self._cleanup_ocr_cloud_test_worker()
        super().closeEvent(event)

    def retranslate_ui(self):
        """Retranslate UI elements when language changes."""
        is_zh = self._main.config.language == "zh"

        # Update save card tooltip with shortcut
        save_shortcut = get_shortcut_text(ShortcutKeys.SAVE_EDIT, self._main.config.language)
        if hasattr(self, "_save_card"):
            self._save_card.setContent(
                f"保存所有配置更改 ({save_shortcut})"
                if is_zh
                else f"Save all configuration changes ({save_shortcut})"
            )

    def update_theme(self):
        """Update theme-dependent components when theme changes."""
        self._apply_theme_styles()
        if self._provider_list_widget:
            self._provider_list_widget.update_theme()
