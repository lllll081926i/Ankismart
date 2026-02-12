from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
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
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    Slider,
    SmoothMode,
    SpinBox,
    SwitchButton,
)

from ankismart.core.config import KNOWN_PROVIDERS, LLMProviderConfig, save_config

if TYPE_CHECKING:
    from ankismart.ui.main_window import MainWindow


class LLMProviderDialog(QDialog):
    """Dialog for adding/editing LLM provider."""

    saved = Signal(LLMProviderConfig)

    def __init__(self, provider: LLMProviderConfig | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LLM 提供商配置")
        self.setMinimumWidth(500)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        self._provider = provider or LLMProviderConfig(id=uuid.uuid4().hex[:12])

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

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

    editClicked = Signal(LLMProviderConfig)
    testClicked = Signal(LLMProviderConfig)
    deleteClicked = Signal(LLMProviderConfig)
    activateClicked = Signal(LLMProviderConfig)

    def __init__(self, provider: LLMProviderConfig, is_active: bool, can_delete: bool, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._is_active = is_active
        self.setObjectName("providerListItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Use transparent row background so parent white panel is visually dominant
        self.setStyleSheet("""
            QWidget#providerListItem {
                background-color: transparent;
                border-bottom: 1px solid #ECECEC;
            }
            QWidget#providerListItem:hover {
                background-color: #F7F7F7;
            }
        """)
        self.setAutoFillBackground(False)

        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 12, 12, 12)  # Reduced left margin to 8px
        layout.setSpacing(4)  # Reduced spacing to 4px

        # Active indicator placeholder (always reserve space for green dot at the front)
        indicator_container = QWidget()
        indicator_container.setFixedWidth(16)  # Reduced width to 16px
        indicator_layout = QHBoxLayout(indicator_container)
        indicator_layout.setContentsMargins(0, 0, 0, 0)
        indicator_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)  # Align to left

        if is_active:
            active_label = BodyLabel("●")
            active_label.setStyleSheet("color: #10b981; font-size: 20px; background: transparent;")  # Larger dot
            indicator_layout.addWidget(active_label)

        layout.addWidget(indicator_container)

        # Provider info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(3)

        name_label = BodyLabel(provider.name)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px; background: transparent;")
        name_label.setToolTip(provider.name)
        info_layout.addWidget(name_label)

        model_text = provider.model.strip() if provider.model else "未设置"
        model_label = BodyLabel(f"模型：{model_text}")
        model_label.setObjectName("providerModelLabel")
        model_label.setStyleSheet("color: #606060; font-size: 12px; background: transparent;")
        model_label.setToolTip(provider.model or "")
        info_layout.addWidget(model_label)

        base_url_text = provider.base_url.strip() if provider.base_url else "未设置"
        base_url_label = BodyLabel(f"地址：{base_url_text}")
        base_url_label.setObjectName("providerUrlLabel")
        base_url_label.setStyleSheet("color: #606060; font-size: 12px; background: transparent;")
        base_url_label.setWordWrap(True)
        base_url_label.setToolTip(provider.base_url or "")
        info_layout.addWidget(base_url_label)

        rpm_text = str(provider.rpm_limit) if provider.rpm_limit > 0 else "默认"
        rpm_label = BodyLabel(f"RPM：{rpm_text}")
        rpm_label.setObjectName("providerRpmLabel")
        rpm_label.setStyleSheet("color: #808080; font-size: 11px; background: transparent;")
        info_layout.addWidget(rpm_label)

        layout.addLayout(info_layout, 1)
        layout.addStretch()

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

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


class ProviderListWidget(QWidget):
    """Standalone widget for displaying provider list."""

    editClicked = Signal(LLMProviderConfig)
    testClicked = Signal(LLMProviderConfig)
    deleteClicked = Signal(LLMProviderConfig)
    activateClicked = Signal(LLMProviderConfig)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("providerListPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # High-contrast pure white panel for provider list block
        self.setStyleSheet("""
            QWidget#providerListPanel {
                background-color: #FFFFFF;
                border: 1px solid #D9D9D9;
                border-radius: 10px;
            }
        """)
        self.setAutoFillBackground(True)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        # Create list widget
        self._list_widget = ListWidget()
        # Set minimum and maximum height (auto-adjust based on content)
        self._list_widget.setMinimumHeight(72)  # At least 1 row
        self._list_widget.setMaximumHeight(288)  # Maximum 4 rows (4 * 72px)
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
        if num_providers <= 4:
            # Show exact height for 1-4 providers
            target_height = num_providers * 72
            self._list_widget.setFixedHeight(target_height)
            self.setFixedHeight(target_height + 2)  # +2 for borders
        else:
            # Show maximum 4 rows with scrollbar
            self._list_widget.setFixedHeight(288)
            self.setFixedHeight(290)  # +2 for borders


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
        self.expandLayout.setSpacing(6)  # Reduced spacing
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
        self._theme_combo.addItems(["浅色", "深色", "自动"])
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

        self.expandLayout.addWidget(self._other_group)

        # ── Action Buttons Group ──
        self._action_group = SettingCardGroup("操作", self.scrollWidget)

        self._reset_card = PushSettingCard(
            "恢复默认",
            FIF.RETURN,
            "重置设置",
            "将所有设置恢复为默认值",
        )
        self._reset_card.clicked.connect(self._reset_to_default)
        self._action_group.addSettingCard(self._reset_card)

        self._save_card = PrimaryPushSettingCard(
            "保存配置",
            FIF.SAVE,
            "保存设置",
            "保存所有配置更改",
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

    def _update_provider_list(self) -> None:
        """Update provider list display."""
        if self._provider_list_widget:
            self._provider_list_widget.update_providers(self._providers, self._active_provider_id)

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
                "llm_temperature": temperature,
                "llm_max_tokens": self._max_tokens_spin.value(),
                "proxy_url": self._proxy_edit.text().strip(),
                "theme": theme,
                "language": language,
            }
        )

        try:
            save_config(config)
            self._main.config = config
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
