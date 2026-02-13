from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QWheelEvent, QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    ComboBoxSettingCard,
    ExpandLayout,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    ListWidget,
    PasswordLineEdit,
    PrimaryPushButton,
    PrimaryPushSettingCard,
    PushButton,
    PushSettingCard,
    RangeSettingCard,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    Slider,
    SmoothMode,
    SpinBox,
    SubtitleLabel,
    SwitchButton,
    SwitchSettingCard,
    isDarkTheme,
)

from ankismart.core.config import KNOWN_PROVIDERS, LLMProviderConfig, save_config
from ankismart.ui.shortcuts import ShortcutKeys, create_shortcut, get_shortcut_text
from ankismart.ui.styles import (
    PROVIDER_ITEM_HEIGHT,
    MAX_VISIBLE_PROVIDERS,
    SPACING_MEDIUM,
    SPACING_LARGE,
    SPACING_SMALL,
    MARGIN_STANDARD,
    MARGIN_SMALL,
)

if TYPE_CHECKING:
    from ankismart.ui.main_window import MainWindow


_OCR_MODE_CHOICES = (
    ("local", "本地模型", "Local Model"),
    ("cloud", "云端模型（开发中）", "Cloud Model (In Development)"),
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


_OCR_CONVERTER_MODULE = None


def _get_ocr_converter_module():
    """Lazy import OCR converter to avoid loading OCR stack at startup."""
    global _OCR_CONVERTER_MODULE
    if _OCR_CONVERTER_MODULE is None:
        from ankismart.converter import ocr_converter as module

        _OCR_CONVERTER_MODULE = module
    return _OCR_CONVERTER_MODULE


def configure_ocr_runtime(*, model_tier: str, model_source: str) -> None:
    _get_ocr_converter_module().configure_ocr_runtime(
        model_tier=model_tier,
        model_source=model_source,
    )


def get_missing_ocr_models(*, model_tier: str, model_source: str):
    return _get_ocr_converter_module().get_missing_ocr_models(
        model_tier=model_tier,
        model_source=model_source,
    )


def is_cuda_available() -> bool:
    return bool(_get_ocr_converter_module().is_cuda_available())


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
        layout.setContentsMargins(MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD)

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


class ProviderListItemWidget(QWidget):
    """Custom widget for provider list item."""

    editClicked = pyqtSignal(LLMProviderConfig)
    testClicked = pyqtSignal(LLMProviderConfig)
    deleteClicked = pyqtSignal(LLMProviderConfig)
    activateClicked = pyqtSignal(LLMProviderConfig)

    def __init__(self, provider: LLMProviderConfig, is_active: bool, can_delete: bool, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._is_active = is_active
        self.setObjectName("providerListItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._update_style()
        self.setAutoFillBackground(False)
        self._init_ui(is_active, can_delete)

    def _init_ui(self, is_active: bool, can_delete: bool):
        """Initialize UI components."""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 12, 12, 12)
        layout.setSpacing(4)

        # Active indicator placeholder (always reserve space for green dot at the front)
        indicator_container = QWidget()
        indicator_container.setFixedWidth(16)
        indicator_layout = QHBoxLayout(indicator_container)
        indicator_layout.setContentsMargins(0, 0, 0, 0)
        indicator_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        if is_active:
            self._active_label = SubtitleLabel("●")
            self._active_label.setStyleSheet("color: #10b981;")
            indicator_layout.addWidget(self._active_label)
        else:
            self._active_label = None

        layout.addWidget(indicator_container)

        # Provider info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        self._name_label = SubtitleLabel(self._provider.name)
        self._name_label.setToolTip(self._provider.name)
        info_layout.addWidget(self._name_label)

        model_text_inline = self._provider.model.strip() if self._provider.model else "未设置"
        base_url_text_inline = self._provider.base_url.strip() if self._provider.base_url else "未设置"

        self._model_label = BodyLabel(f"模型：{model_text_inline}")
        self._model_label.setObjectName("providerModelLabel")
        info_layout.addWidget(self._model_label)

        self._url_label = BodyLabel(f"地址：{base_url_text_inline}")
        self._url_label.setObjectName("providerUrlLabel")
        info_layout.addWidget(self._url_label)

        rpm_text_inline = f"RPM：{self._provider.rpm_limit}" if self._provider.rpm_limit > 0 else "RPM：未设置"
        self._rpm_label = BodyLabel(rpm_text_inline)
        self._rpm_label.setObjectName("providerRpmLabel")
        info_layout.addWidget(self._rpm_label)

        layout.addLayout(info_layout, 1)
        layout.addStretch()

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(SPACING_SMALL)

        self._activate_btn = PrimaryPushButton("激活", self) if not is_active else PushButton("当前使用", self)
        self._activate_btn.setFixedWidth(80)
        self._activate_btn.setEnabled(not is_active)
        self._activate_btn.clicked.connect(lambda: self.activateClicked.emit(self._provider))
        button_layout.addWidget(self._activate_btn)

        self._edit_btn = PushButton("修改", self)
        self._edit_btn.setFixedWidth(70)
        self._edit_btn.clicked.connect(lambda: self.editClicked.emit(self._provider))
        button_layout.addWidget(self._edit_btn)

        self._test_btn = PushButton("测试", self)
        self._test_btn.setFixedWidth(70)
        self._test_btn.clicked.connect(lambda: self.testClicked.emit(self._provider))
        button_layout.addWidget(self._test_btn)

        self._delete_btn = PushButton("删除", self)
        self._delete_btn.setFixedWidth(70)
        self._delete_btn.setEnabled(can_delete)
        self._delete_btn.clicked.connect(lambda: self.deleteClicked.emit(self._provider))
        button_layout.addWidget(self._delete_btn)

        layout.addLayout(button_layout)

    def _update_style(self):
        """Update style based on current theme - using QFluentWidgets theme system."""
        # Use QFluentWidgets theme colors instead of hardcoded values
        is_dark = isDarkTheme()
        if is_dark:
            self.setStyleSheet("""
                QWidget#providerListItem {
                    background-color: transparent;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                }
                QWidget#providerListItem:hover {
                    background-color: rgba(255, 255, 255, 0.03);
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget#providerListItem {
                    background-color: transparent;
                    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
                }
                QWidget#providerListItem:hover {
                    background-color: rgba(0, 0, 0, 0.03);
                }
            """)

    def update_theme(self):
        """Update theme-dependent styles when theme changes."""
        self._update_style()


class ProviderListWidget(QWidget):
    """Standalone widget for displaying provider list."""

    editClicked = pyqtSignal(LLMProviderConfig)
    testClicked = pyqtSignal(LLMProviderConfig)
    deleteClicked = pyqtSignal(LLMProviderConfig)
    activateClicked = pyqtSignal(LLMProviderConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("providerListPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._init_panel_ui()
        self._update_panel_style()
        self.setAutoFillBackground(True)

    def _init_panel_ui(self) -> None:
        """Initialize static UI structure for provider panel."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self._list_widget = ListWidget()
        self._list_widget.setMinimumHeight(PROVIDER_ITEM_HEIGHT)
        self._list_widget.setMaximumHeight(PROVIDER_ITEM_HEIGHT * MAX_VISIBLE_PROVIDERS)
        self._list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list_widget.setSpacing(0)
        self._list_widget.setStyleSheet("""
            ListWidget {
                background-color: transparent;
                border: none;
            }
            QListView {
                background-color: transparent;
                border: none;
            }
        """)
        self._list_widget.installEventFilter(self)
        self._list_widget.viewport().installEventFilter(self)

        layout.addWidget(self._list_widget)

    def _update_panel_style(self):
        """Update panel style based on current theme - using QFluentWidgets theme system."""
        is_dark = isDarkTheme()
        if is_dark:
            self.setStyleSheet("""
                QWidget#providerListPanel {
                    background-color: rgba(45, 45, 45, 1);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget#providerListPanel {
                    background-color: #FFFFFF;
                    border: 1px solid rgba(0, 0, 0, 0.08);
                    border-radius: 10px;
                }
            """)

    def _forward_wheel_to_parent(self, event: QWheelEvent) -> None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, ScrollArea):
                parent.wheelEvent(event)
                return
            parent = parent.parentWidget()

    def _should_forward_from_list(self, event: QWheelEvent) -> bool:
        bar = self._list_widget.verticalScrollBar()
        if not bar.isVisible():
            return True

        delta = event.angleDelta().y()
        if delta > 0 and bar.value() <= bar.minimum():
            return True
        if delta < 0 and bar.value() >= bar.maximum():
            return True
        return False

    def eventFilter(self, watched, event):
        if watched in {self._list_widget, self._list_widget.viewport()} and event.type() == QEvent.Type.Wheel:
            if self._should_forward_from_list(event):
                self._forward_wheel_to_parent(event)
                return True
        return super().eventFilter(watched, event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Forward wheel events to parent settings scroll area when needed."""
        if not isinstance(event, QWheelEvent):
            self._forward_wheel_to_parent(event)
            return

        if self._list_widget.verticalScrollBar().isVisible():
            super().wheelEvent(event)
            if event.isAccepted():
                return

        self._forward_wheel_to_parent(event)

    def update_providers(self, providers: list[LLMProviderConfig], active_provider_id: str):
        """Update the provider list display."""
        self._list_widget.clear()

        can_delete = len(providers) > 1
        for provider in providers:
            is_active = provider.id == active_provider_id

            # Create list item
            item = QListWidgetItem(self._list_widget)

            # Create custom widget
            widget = ProviderListItemWidget(provider, is_active, can_delete)
            widget.editClicked.connect(self.editClicked.emit)
            widget.testClicked.connect(self.testClicked.emit)
            widget.deleteClicked.connect(self.deleteClicked.emit)
            widget.activateClicked.connect(self.activateClicked.emit)

            # Set item size hint (height 72px per item)
            item.setSizeHint(widget.sizeHint())

            # Add item and widget
            self._list_widget.addItem(item)
            self._list_widget.setItemWidget(item, widget)

        # Auto-adjust height based on number of providers
        num_providers = len(providers)
        if num_providers <= MAX_VISIBLE_PROVIDERS:
            # Show exact height for 1-4 providers
            target_height = num_providers * PROVIDER_ITEM_HEIGHT
            self._list_widget.setFixedHeight(target_height)
            self.setFixedHeight(target_height + 2)  # +2 for borders
        else:
            # Show maximum 4 rows with scrollbar
            self._list_widget.setFixedHeight(PROVIDER_ITEM_HEIGHT * MAX_VISIBLE_PROVIDERS)
            self.setFixedHeight(PROVIDER_ITEM_HEIGHT * MAX_VISIBLE_PROVIDERS + 2)  # +2 for borders

    def update_theme(self):
        """Update theme-dependent styles when theme changes."""
        self._update_panel_style()
        # Update all item widgets
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            widget = self._list_widget.itemWidget(item)
            if widget and hasattr(widget, 'update_theme'):
                widget.update_theme()


class SettingsPage(ScrollArea):
    """Application settings page using QFluentWidgets components."""

    def __init__(self, main_window: MainWindow) -> None:
        super().__init__()
        self._main = main_window
        self._providers: list[LLMProviderConfig] = []
        self._active_provider_id: str = ""
        self._provider_list_widget: ProviderListWidget | None = None
        self._provider_test_worker = None
        self._anki_test_worker = None

        # Create scroll widget
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # Initialize UI
        self.__initWidget()

    def __initWidget(self):
        """Initialize widgets and layout."""
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSmoothMode(SmoothMode.LINEAR, Qt.Orientation.Vertical)
        self.setViewportMargins(0, 0, 0, 0)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName("settingsPage")

        self.scrollWidget.setObjectName("scrollWidget")

        # Initialize layout
        self.__initLayout()

        # Load current configuration
        self._load_config()

        # Initialize shortcuts
        self._init_shortcuts()

    def _init_shortcuts(self):
        """Initialize page-specific keyboard shortcuts."""
        # Ctrl+S: Save configuration
        create_shortcut(self, ShortcutKeys.SAVE_EDIT, self._save_config)

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

    def __initLayout(self):
        """Initialize layout and add all setting cards."""
        self.expandLayout.setSpacing(SPACING_MEDIUM)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)

        # ── LLM Configuration Group ──
        self._llm_group = SettingCardGroup("LLM 配置", self.scrollWidget)

        # Add provider button
        self._add_provider_card = PushSettingCard(
            "添加提供商",
            FIF.ADD,
            "添加 LLM 提供商",
            "添加新的 LLM 提供商配置",
        )
        self._add_provider_card.clicked.connect(self._add_provider)
        self._llm_group.addSettingCard(self._add_provider_card)

        self.expandLayout.addWidget(self._llm_group)

        # ── Provider List (Standalone Widget) ──
        self._provider_list_widget = ProviderListWidget(self.scrollWidget)
        self._provider_list_widget.editClicked.connect(self._edit_provider)
        self._provider_list_widget.testClicked.connect(self._test_provider_connection)
        self._provider_list_widget.deleteClicked.connect(self._delete_provider)
        self._provider_list_widget.activateClicked.connect(self._activate_provider)
        self.expandLayout.addWidget(self._provider_list_widget)

        # ── LLM Parameters Group ──
        self._llm_params_group = SettingCardGroup("LLM 参数", self.scrollWidget)

        # Temperature - using custom card with Slider
        self._temperature_card = SettingCard(
            FIF.FRIGID,
            "温度",
            "控制生成的随机性（0.0 = 确定性，2.0 = 创造性）",
            self.scrollWidget,
        )
        self._temperature_slider = Slider(Qt.Orientation.Horizontal, self._temperature_card)
        self._temperature_slider.setRange(0, 20)
        self._temperature_slider.setSingleStep(1)
        self._temperature_slider.setValue(3)  # Default 0.3
        self._temperature_slider.setMinimumWidth(200)

        self._temperature_label = BodyLabel()
        self._temperature_label.setText("0.3")
        self._temperature_label.setFixedWidth(50)

        self._temperature_slider.valueChanged.connect(
            lambda v: self._temperature_label.setText(f"{v/10:.1f}")
        )

        self._temperature_card.hBoxLayout.addWidget(self._temperature_slider)
        self._temperature_card.hBoxLayout.addWidget(self._temperature_label)
        self._temperature_card.hBoxLayout.addSpacing(16)
        self._llm_params_group.addSettingCard(self._temperature_card)

        # Max Tokens - using custom card with SpinBox
        self._max_tokens_card = SettingCard(
            FIF.FONT,
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
        self._llm_params_group.addSettingCard(self._max_tokens_card)

        self.expandLayout.addWidget(self._llm_params_group)

        # ── Anki Configuration Group ──
        self._anki_group = SettingCardGroup("Anki 配置", self.scrollWidget)

        # AnkiConnect URL
        self._anki_url_card = SettingCard(
            FIF.LINK,
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
            FIF.FINGERPRINT,
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
            FIF.BOOK_SHELF,
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
            FIF.TAG,
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
            FIF.SYNC,
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
            FIF.BRUSH,
            "主题",
            "应用程序主题",
            self.scrollWidget,
        )
        self._theme_combo = ComboBox(self._theme_card)
        self._theme_combo.addItems(["浅色", "深色", "跟随系统"])
        self._theme_combo.setMinimumWidth(200)
        self._theme_card.hBoxLayout.addWidget(self._theme_combo)
        self._theme_card.hBoxLayout.addSpacing(16)
        self._other_group.addSettingCard(self._theme_card)

        # Language
        self._language_card = SettingCard(
            FIF.LANGUAGE,
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

        # Proxy
        self._proxy_card = SettingCard(
            FIF.GLOBE,
            "代理设置",
            "HTTP/HTTPS 代理 URL（可选）",
            self.scrollWidget,
        )
        self._proxy_edit = LineEdit(self._proxy_card)
        self._proxy_edit.setPlaceholderText("http://proxy.example.com:8080")
        self._proxy_edit.setMinimumWidth(300)
        self._proxy_card.hBoxLayout.addWidget(self._proxy_edit)
        self._proxy_card.hBoxLayout.addSpacing(16)
        self._other_group.addSettingCard(self._proxy_card)

        # OCR Correction
        self._ocr_correction_card = SettingCard(
            FIF.EDIT,
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
            FIF.DOCUMENT,
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
        self._log_level_card.hBoxLayout.addWidget(self._log_level_combobox, 0, Qt.AlignmentFlag.AlignRight)
        self._log_level_card.hBoxLayout.addSpacing(16)

        self._other_group.addSettingCard(self._log_level_card)

        # View Logs
        self._view_logs_card = PushSettingCard(
            t("log.open_folder", self._main.config.language),
            FIF.FOLDER,
            t("log.view_logs", self._main.config.language),
            t("log.view_logs_desc", self._main.config.language),
        )
        self._view_logs_card.clicked.connect(self._open_log_directory)
        self._other_group.addSettingCard(self._view_logs_card)

        self.expandLayout.addWidget(self._other_group)

        # ── OCR Settings Group ──
        self._ocr_group = SettingCardGroup("OCR 设置", self.scrollWidget)

        self._ocr_mode_card = SettingCard(
            FIF.ROBOT,
            "OCR 模式",
            "切换使用本地模型或云端模型（云端功能开发中）",
            self.scrollWidget,
        )
        self._ocr_mode_combo = ComboBox(self._ocr_mode_card)
        for key, zh_text, en_text in _OCR_MODE_CHOICES:
            self._ocr_mode_combo.addItem(zh_text if is_zh else en_text, userData=key)
        self._ocr_mode_card.hBoxLayout.addWidget(self._ocr_mode_combo)
        self._ocr_mode_card.hBoxLayout.addSpacing(16)
        self._ocr_group.addSettingCard(self._ocr_mode_card)

        self._ocr_cuda_auto_card = SwitchSettingCard(
            FIF.POWER_BUTTON,
            "CUDA 自动升档",
            "首次 OCR 前检测到 CUDA 时，自动将模型从轻量档升至标准档",
            parent=self._ocr_group,
        )
        self._ocr_group.addSettingCard(self._ocr_cuda_auto_card)

        self._ocr_connectivity_card = PushSettingCard(
            "测试",
            FIF.HELP,
            "OCR 模型连通性测试",
            "本地模式检查模型完整性，云端模式显示开发中状态",
        )
        self._ocr_connectivity_card.clicked.connect(self._test_ocr_connectivity)
        self._ocr_group.addSettingCard(self._ocr_connectivity_card)

        self._ocr_model_tier_card = SettingCard(
            FIF.GLOBE,
            "OCR 模型",
            "切换 OCR 模型档位",
            self.scrollWidget,
        )
        self._ocr_model_tier_combo = ComboBox(self._ocr_model_tier_card)
        for key, zh_text, en_text in _OCR_MODEL_TIER_CHOICES:
            self._ocr_model_tier_combo.addItem(zh_text if is_zh else en_text, userData=key)
        self._ocr_model_tier_combo.currentIndexChanged.connect(lambda _: self._refresh_ocr_recommendation())

        self._ocr_model_recommend_label = BodyLabel(self._ocr_model_tier_card)
        self._ocr_model_recommend_label.setWordWrap(False)
        self._ocr_model_recommend_label.setMinimumWidth(260)
        self._ocr_model_tier_card.hBoxLayout.addWidget(self._ocr_model_recommend_label)
        self._ocr_model_tier_card.hBoxLayout.addStretch(1)
        self._ocr_model_tier_card.hBoxLayout.addWidget(self._ocr_model_tier_combo)
        self._ocr_model_tier_card.hBoxLayout.addSpacing(16)
        self._ocr_group.addSettingCard(self._ocr_model_tier_card)

        self._ocr_source_card = SettingCard(
            FIF.CLOUD_DOWNLOAD,
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
            FIF.VPN,
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
            FIF.DELETE,
            "缓存大小",
            "计算中...",
        )
        self._cache_size_card.clicked.connect(self._clear_cache)
        self._cache_group.addSettingCard(self._cache_size_card)

        # Cache count card
        self._cache_count_card = PushSettingCard(
            "刷新",
            FIF.SYNC,
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
            FIF.CUT,
            "启用长文档自动分割",
            "当文档超过阈值时自动分割为多个片段处理",
            parent=self._experimental_group,
        )
        self._auto_split_switch = SwitchButton(self._auto_split_card)
        self._auto_split_switch.setChecked(self._main.config.enable_auto_split)
        self._auto_split_card.hBoxLayout.addWidget(self._auto_split_switch, 0, Qt.AlignmentFlag.AlignRight)
        self._auto_split_card.hBoxLayout.addSpacing(16)
        self._experimental_group.addSettingCard(self._auto_split_card)

        # Split threshold
        self._split_threshold_card = SettingCard(
            FIF.ALIGNMENT,
            "分割阈值",
            "触发自动分割的字符数阈值",
            parent=self._experimental_group,
        )
        self._split_threshold_spinbox = SpinBox(self._split_threshold_card)
        self._split_threshold_spinbox.setRange(10000, 200000)
        self._split_threshold_spinbox.setSingleStep(10000)
        self._split_threshold_spinbox.setValue(self._main.config.split_threshold)
        self._split_threshold_card.hBoxLayout.addWidget(self._split_threshold_spinbox, 0, Qt.AlignmentFlag.AlignRight)
        self._split_threshold_card.hBoxLayout.addSpacing(16)
        self._experimental_group.addSettingCard(self._split_threshold_card)

        # Warning label
        self._warning_card = SettingCard(
            FIF.INFO,
            "注意事项",
            "⚠️ 警告：这是实验性功能，可能影响卡片质量和生成时间。建议仅在处理超长文档时启用。",
            self.scrollWidget,
        )
        self._experimental_group.addSettingCard(self._warning_card)

        self.expandLayout.addWidget(self._experimental_group)

        # ── Action Buttons Group ──
        self._action_group = SettingCardGroup("操作", self.scrollWidget)

        # Export logs button
        is_zh = self._main.config.language == "zh"
        self._export_logs_card = PushSettingCard(
            "导出日志" if is_zh else "Export Logs",
            FIF.DOCUMENT,
            "导出日志" if is_zh else "Export Logs",
            "导出应用日志文件用于问题排查" if is_zh else "Export application logs for troubleshooting",
        )
        self._export_logs_card.clicked.connect(self._export_logs)
        self._action_group.addSettingCard(self._export_logs_card)

        self._reset_card = PushSettingCard(
            "恢复默认",
            FIF.RETURN,
            "重置设置",
            "将所有设置恢复为默认值",
        )
        self._reset_card.clicked.connect(self._reset_to_default)
        self._action_group.addSettingCard(self._reset_card)

        save_text = "保存配置" if is_zh else "Save Configuration"
        save_shortcut = get_shortcut_text(ShortcutKeys.SAVE_EDIT, self._main.config.language)

        self._save_card = PrimaryPushSettingCard(
            save_text,
            FIF.SAVE,
            "保存设置" if is_zh else "Save Settings",
            f"保存所有配置更改 ({save_shortcut})" if is_zh else f"Save all configuration changes ({save_shortcut})",
        )
        self._save_card.clicked.connect(self._save_config)
        self._action_group.addSettingCard(self._save_card)

        self.expandLayout.addWidget(self._action_group)

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

        self._proxy_edit.setText(config.proxy_url)
        self._ocr_correction_switch.setChecked(config.ocr_correction)

        self._set_combo_current_data(self._ocr_mode_combo, getattr(config, "ocr_mode", "local"))
        self._set_combo_current_data(self._ocr_model_tier_combo, getattr(config, "ocr_model_tier", "lite"))
        self._set_combo_current_data(self._ocr_source_combo, getattr(config, "ocr_model_source", "official"))
        self._ocr_cuda_auto_card.setChecked(getattr(config, "ocr_auto_cuda_upgrade", True))
        self._refresh_ocr_recommendation()

        # Experimental features
        self._auto_split_switch.setChecked(config.enable_auto_split)
        self._split_threshold_spinbox.setValue(config.split_threshold)

        # Cache statistics
        self._refresh_cache_stats()

        # Log level
        log_level_map = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        self._log_level_combobox.setCurrentIndex(log_level_map.get(config.log_level, 1))

    def _update_provider_list(self) -> None:
        """Update provider list display."""
        if self._provider_list_widget:
            self._provider_list_widget.update_providers(self._providers, self._active_provider_id)

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

    def _test_ocr_connectivity(self) -> None:
        is_zh = self._main.config.language == "zh"
        mode = self._get_combo_current_data(self._ocr_mode_combo, "local")

        if mode == "cloud":
            self._show_info_bar(
                "info",
                "云端 OCR 开发中" if is_zh else "Cloud OCR In Development",
                "云端 OCR 连通性测试暂未开放。" if is_zh else "Cloud OCR connectivity test is not available yet.",
                duration=3500,
            )
            return

        tier = self._get_combo_current_data(self._ocr_model_tier_combo, "lite")
        source = self._get_combo_current_data(self._ocr_source_combo, "official")
        configure_ocr_runtime(model_tier=tier, model_source=source)
        missing = get_missing_ocr_models(model_tier=tier, model_source=source)

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
        has_cuda = is_cuda_available()
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
            "未检测到可用 CUDA，建议使用轻量模型档位。" if is_zh else "No CUDA detected, Lite model tier is recommended.",
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

    def _delete_provider(self, provider: LLMProviderConfig) -> None:
        """Delete a provider."""
        if len(self._providers) <= 1:
            QMessageBox.warning(
                self, "无法删除", "至少需要保留一个提供商配置"
            )
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

    def _activate_provider(self, provider: LLMProviderConfig) -> None:
        """Set a provider as active."""
        self._active_provider_id = provider.id
        self._update_provider_list()

    def _test_provider_connection(self, provider: LLMProviderConfig) -> None:
        """Test connection to a specific LLM provider."""
        from ankismart.ui.workers import ProviderConnectionWorker

        self._show_info_bar(
            "info",
            "测试中",
            f"正在测试提供商「{provider.name}」连通性...",
            duration=1500,
        )

        worker = ProviderConnectionWorker(
            provider,
            proxy_url=self._proxy_edit.text().strip(),
            temperature=self._temperature_slider.value() / 10,
            max_tokens=self._max_tokens_spin.value(),
        )
        worker.finished.connect(lambda ok, err: self._on_provider_test_result(provider.name, ok, err))
        worker.start()
        self._provider_test_worker = worker

    def _on_provider_test_result(self, provider_name: str, connected: bool, error: str) -> None:
        """Handle provider connection test result."""
        if connected:
            self._show_info_bar("success", "连接成功", f"提供商「{provider_name}」连通正常", duration=3500)
            return

        if error:
            self._show_info_bar(
                "error",
                "连接失败",
                f"提供商「{provider_name}」连接失败：{error}",
                duration=5000,
            )
            return

        self._show_info_bar("warning", "连接失败", f"提供商「{provider_name}」未通过连通性测试", duration=4000)

    def _test_connection(self) -> None:
        """Test connection to AnkiConnect."""
        from ankismart.ui.workers import ConnectionCheckWorker

        url = self._anki_url_edit.text() or "http://127.0.0.1:8765"
        key = self._anki_key_edit.text()
        proxy = self._proxy_edit.text()

        self._test_connection_card.setContent("测试中...")
        self._show_info_bar("info", "测试中", "正在检测 AnkiConnect 连接...", duration=1500)

        worker = ConnectionCheckWorker(url, key, proxy_url=proxy)
        worker.finished.connect(self._on_test_result)
        worker.start()
        self._anki_test_worker = worker

    def _on_test_result(self, connected: bool) -> None:
        """Handle test connection result."""
        if connected:
            self._test_connection_card.setContent("连接成功！")
            self._show_info_bar("success", "连接成功", "AnkiConnect 连通正常", duration=3500)
        else:
            self._test_connection_card.setContent("连接失败")
            self._show_info_bar("error", "连接失败", "无法连接到 AnkiConnect，请检查 URL/密钥与代理设置", duration=5000)
        self._main.set_connection_status(connected)

    def _refresh_cache_stats(self) -> None:
        """Refresh cache statistics display."""
        from ankismart.converter.cache import get_cache_stats
        from ankismart.ui.i18n import t

        stats = get_cache_stats()
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
        from ankismart.converter.cache import get_cache_stats, clear_cache
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
            t("settings.confirm_clear_cache_msg", self._main.config.language, count=count, size=size_mb),
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

    def _save_config(self) -> None:
        """Save configuration."""
        # Validate active provider
        if not self._providers:
            QMessageBox.warning(self, "错误", "至少需要配置一个 LLM 提供商")
            return

        # Parse tags
        tags = [tag.strip() for tag in self._default_tags_edit.text().split(",") if tag.strip()]
        if not tags:
            tags = ["ankismart"]

        # Get theme and language
        theme_values = ["light", "dark", "auto"]
        theme = theme_values[self._theme_combo.currentIndex()]

        lang_values = ["zh", "en"]
        language = lang_values[self._language_combo.currentIndex()]

        # Get temperature (convert from 0-20 to 0.0-2.0)
        temperature = self._temperature_slider.value() / 10.0

        # Get log level
        log_level_values = ["DEBUG", "INFO", "WARNING", "ERROR"]
        log_level = log_level_values[self._log_level_combobox.currentIndex()]

        ocr_mode = self._get_combo_current_data(self._ocr_mode_combo, "local")
        ocr_model_tier = self._get_combo_current_data(self._ocr_model_tier_combo, "lite")
        ocr_model_source = self._get_combo_current_data(self._ocr_source_combo, "official")
        ocr_model_locked_by_user = (
            getattr(self._main.config, "ocr_model_locked_by_user", False)
            or ocr_model_tier != getattr(self._main.config, "ocr_model_tier", "lite")
        )

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
                "ocr_auto_cuda_upgrade": self._ocr_cuda_auto_card.isChecked(),
                "ocr_model_locked_by_user": ocr_model_locked_by_user,
                "llm_temperature": temperature,
                "llm_max_tokens": self._max_tokens_spin.value(),
                "proxy_url": self._proxy_edit.text().strip(),
                "theme": theme,
                "language": language,
                "log_level": log_level,
                "enable_auto_split": self._auto_split_switch.isChecked(),
                "split_threshold": self._split_threshold_spinbox.value(),
            }
        )

        old_theme = self._main.config.theme
        old_language = self._main.config.language

        try:
            save_config(config)
            self._main.config = config
            configure_ocr_runtime(
                model_tier=config.ocr_model_tier,
                model_source=config.ocr_model_source,
                reset_ocr_instance=True,
            )

            # Apply theme change immediately
            if old_theme != theme and hasattr(self._main, "switch_theme"):
                self._main.switch_theme(theme)

            # Apply language change if needed
            if old_language != language and hasattr(self._main, "switch_language"):
                self._main.switch_language(language)

            QMessageBox.information(self, "成功", "配置保存成功")
        except Exception as exc:
            QMessageBox.critical(self, "错误", f"保存配置失败：{exc}")

    def _reset_to_default(self) -> None:
        """Reset configuration to default values."""
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要将所有设置恢复为默认值吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            from ankismart.core.config import AppConfig

            default_config = AppConfig()
            self._main.config = default_config
            self._load_config()
            QMessageBox.information(self, "重置完成", "设置已恢复为默认值")

    def _export_logs(self) -> None:
        """Export application logs to a zip file."""
        from ankismart.ui.log_exporter import LogExporter
        from ankismart.ui.i18n import t
        from pathlib import Path
        from datetime import datetime

        is_zh = self._main.config.language == "zh"

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

    def retranslate_ui(self):
        """Retranslate UI elements when language changes."""
        is_zh = self._main.config.language == "zh"

        # Update save card tooltip with shortcut
        save_text = "保存配置" if is_zh else "Save Configuration"
        save_shortcut = get_shortcut_text(ShortcutKeys.SAVE_EDIT, self._main.config.language)
        self._save_card.setContent(
            f"保存所有配置更改 ({save_shortcut})" if is_zh else f"Save all configuration changes ({save_shortcut})"
        )

    def update_theme(self):
        """Update theme-dependent components when theme changes."""
        if self._provider_list_widget:
            self._provider_list_widget.update_theme()
