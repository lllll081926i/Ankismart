from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.config import (
    KNOWN_PROVIDERS,
    AppConfig,
    LLMProviderConfig,
    save_config,
)
from ankismart.ui.workers import ConnectionCheckWorker


class SettingsPage(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("page_content")
        self._main = main_window
        self._worker = None
        self._providers: list[LLMProviderConfig] = []
        self._active_provider_id: str = ""
        self._updating_ui = False

        # Root layout with scroll area to avoid controls being compressed together
        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(0)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(20)
        layout.setContentsMargins(16, 16, 16, 16)

        # Title
        title = QLabel("设置")
        title.setProperty("role", "heading")
        layout.addWidget(title)

        # ── LLM Provider Section ──
        llm_group = QGroupBox("LLM 服务商设置")
        llm_layout = QVBoxLayout(llm_group)
        llm_layout.setSpacing(16)
        llm_layout.setContentsMargins(16, 20, 16, 16)

        # Provider Selection Row
        sel_row = QHBoxLayout()
        sel_row.setSpacing(15)
        
        sel_label = QLabel("选择服务商：")
        sel_label.setFixedWidth(100)
        sel_row.addWidget(sel_label)

        self._provider_combo = QComboBox()
        self._provider_combo.setMinimumHeight(40) # Taller input
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        sel_row.addWidget(self._provider_combo, 1)

        btn_add = QPushButton("新建")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setFixedWidth(80)
        btn_add.setMinimumHeight(40) # Taller button
        btn_add.clicked.connect(self._add_provider)
        sel_row.addWidget(btn_add)

        self._btn_delete = QPushButton("删除")
        self._btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_delete.setFixedWidth(80)
        self._btn_delete.setMinimumHeight(40) # Taller button
        self._btn_delete.clicked.connect(self._delete_provider)
        sel_row.addWidget(self._btn_delete)
        
        llm_layout.addLayout(sel_row)

        # Divider
        line = QWidget()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #E0E0E0;")
        llm_layout.addWidget(line)

        # Provider Details Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setVerticalSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self._name_combo = QComboBox()
        self._name_combo.setEditable(True)
        self._name_combo.setMinimumHeight(40) # Taller input
        for name in KNOWN_PROVIDERS:
            self._name_combo.addItem(name)
        self._name_combo.currentTextChanged.connect(self._on_name_edited)
        form.addRow("服务商名称：", self._name_combo)

        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText("https://api.openai.com/v1")
        self._base_url_input.setMinimumHeight(40) # Taller input
        form.addRow("API 地址：", self._base_url_input)

        self._provider_key_input = QLineEdit()
        self._provider_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._provider_key_input.setPlaceholderText("sk-...")
        self._provider_key_input.setMinimumHeight(40) # Taller input
        form.addRow("API Key：", self._provider_key_input)

        self._provider_model_input = QLineEdit()
        self._provider_model_input.setPlaceholderText("gpt-4o")
        self._provider_model_input.setMinimumHeight(40) # Taller input
        form.addRow("模型名称：", self._provider_model_input)

        # Rate limit
        rpm_row = QHBoxLayout()
        self._rpm_toggle = QPushButton("关")
        self._rpm_toggle.setCheckable(True)
        self._rpm_toggle.setFixedWidth(70)
        self._rpm_toggle.setMinimumHeight(40) # Taller input
        self._rpm_toggle.toggled.connect(self._on_rpm_toggled)
        rpm_row.addWidget(self._rpm_toggle)

        self._rpm_spin = QSpinBox()
        self._rpm_spin.setRange(1, 9999)
        self._rpm_spin.setValue(60)
        self._rpm_spin.setSuffix(" RPM")
        self._rpm_spin.setMinimumHeight(40) # Taller input
        self._rpm_spin.hide()
        rpm_row.addWidget(self._rpm_spin)
        rpm_row.addStretch()
        form.addRow("速率限制：", rpm_row)

        llm_layout.addLayout(form)
        layout.addWidget(llm_group)

        # ── AnkiConnect + Defaults ──
        other_group = QGroupBox("通用设置")
        other_layout = QVBoxLayout(other_group)
        other_layout.setContentsMargins(16, 20, 16, 16)

        other_form = QFormLayout()
        other_form.setSpacing(12)
        other_form.setVerticalSpacing(14)
        other_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        other_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self._anki_url_input = QLineEdit()
        self._anki_url_input.setPlaceholderText("http://127.0.0.1:8765")
        self._anki_url_input.setMinimumHeight(40) # Taller input
        other_form.addRow("AnkiConnect 地址：", self._anki_url_input)

        self._anki_key_input = QLineEdit()
        self._anki_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._anki_key_input.setPlaceholderText("可选")
        self._anki_key_input.setMinimumHeight(40) # Taller input
        other_form.addRow("AnkiConnect Key：", self._anki_key_input)

        self._default_deck_input = QLineEdit()
        self._default_deck_input.setMinimumHeight(40) # Taller input
        other_form.addRow("默认牌组：", self._default_deck_input)

        self._default_tags_input = QLineEdit()
        self._default_tags_input.setMinimumHeight(40) # Taller input
        other_form.addRow("默认标签：", self._default_tags_input)

        self._ocr_correction_check = QCheckBox(
            "启用 OCR 文本纠错（使用 LLM 自动修正 OCR 错误）"
        )
        self._ocr_correction_check.setMinimumHeight(30)
        other_form.addRow("", self._ocr_correction_check)
        
        other_layout.addLayout(other_form)
        layout.addWidget(other_group)

        layout.addSpacing(15)

        # Buttons
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(25) # Increased spacing
        btn_bar.addStretch()

        btn_test = QPushButton("测试连接")
        btn_test.setMinimumHeight(48) # Taller button
        btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test.clicked.connect(self._test_connection)
        btn_bar.addWidget(btn_test)

        btn_save = QPushButton("保存设置")
        btn_save.setMinimumHeight(48) # Taller button
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setProperty("role", "primary")
        btn_save.clicked.connect(self._save)
        btn_bar.addWidget(btn_save)

        layout.addLayout(btn_bar)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setMinimumHeight(30)
        layout.addWidget(self._status_label)

        layout.addStretch()
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        self._load_config()

    # ── Config load / save ──

    def _load_config(self) -> None:
        config = self._main.config
        self._providers = [p.model_copy() for p in config.llm_providers]
        self._active_provider_id = config.active_provider_id
        self._refresh_provider_combo()

        self._anki_url_input.setText(config.anki_connect_url)
        self._anki_key_input.setText(config.anki_connect_key)
        self._default_deck_input.setText(config.default_deck)
        self._default_tags_input.setText(", ".join(config.default_tags))
        self._ocr_correction_check.setChecked(config.ocr_correction)

    def _refresh_provider_combo(self) -> None:
        self._updating_ui = True
        
        target_index = 0
        found_index = -1
        
        self._provider_combo.clear()
        for i, p in enumerate(self._providers):
            label = p.name or "(未命名)"
            if p.model:
                label += f" - {p.model}"
            suffix = " [当前使用]" if p.id == self._active_provider_id else ""
            self._provider_combo.addItem(label + suffix, userData=p.id)
            
            if p.id == self._active_provider_id:
                found_index = i

        if found_index >= 0:
            target_index = found_index
        elif self._provider_combo.count() > 0:
            target_index = 0
            
        self._provider_combo.setCurrentIndex(target_index)
        self._btn_delete.setEnabled(len(self._providers) > 1)
        self._updating_ui = False
        
        self._on_provider_changed(target_index)

    def _selected_provider(self) -> LLMProviderConfig | None:
        idx = self._provider_combo.currentIndex()
        if 0 <= idx < len(self._providers):
            return self._providers[idx]
        return None

    def _save_form_to_provider(self) -> None:
        p = self._selected_provider()
        if p is None:
            return
        p.name = self._name_combo.currentText().strip()
        p.base_url = self._base_url_input.text().strip()
        p.api_key = self._provider_key_input.text().strip()
        p.model = self._provider_model_input.text().strip()
        if self._rpm_toggle.isChecked():
            p.rpm_limit = self._rpm_spin.value()
        else:
            p.rpm_limit = 0

    # ── Provider interactions ──

    def _on_provider_changed(self, index: int) -> None:
        if self._updating_ui:
            return
            
        p = self._selected_provider()
        if p is None:
            self._updating_ui = True
            self._name_combo.setCurrentText("")
            self._base_url_input.clear()
            self._provider_key_input.clear()
            self._provider_model_input.clear()
            self._rpm_toggle.setChecked(False)
            self._updating_ui = False
            return
            
        self._updating_ui = True
        self._name_combo.setCurrentText(p.name)
        self._base_url_input.setText(p.base_url)
        self._provider_key_input.setText(p.api_key)
        self._provider_model_input.setText(p.model)
        has_rpm = p.rpm_limit > 0
        self._rpm_toggle.setChecked(has_rpm)
        self._rpm_toggle.setText("开" if has_rpm else "关")
        self._rpm_spin.setVisible(has_rpm)
        if has_rpm:
            self._rpm_spin.setValue(p.rpm_limit)
        
        self._updating_ui = False

    def _on_name_edited(self, text: str) -> None:
        if self._updating_ui:
            return
        url = KNOWN_PROVIDERS.get(text, "")
        if url:
            self._base_url_input.setText(url)
        self._save_form_to_provider()

    def _on_rpm_toggled(self, checked: bool) -> None:
        self._rpm_toggle.setText("开" if checked else "关")
        self._rpm_spin.setVisible(checked)
        self._save_form_to_provider()

    def _add_provider(self) -> None:
        self._save_form_to_provider()
        new_p = LLMProviderConfig(id=uuid.uuid4().hex[:12], name="New Provider")
        self._providers.append(new_p)
        self._refresh_provider_combo()
        self._provider_combo.setCurrentIndex(len(self._providers) - 1)
        self._name_combo.setFocus()

    def _delete_provider(self) -> None:
        if len(self._providers) <= 1:
            QMessageBox.warning(self, "警告", "至少需要保留一个服务商配置。")
            return
            
        if QMessageBox.question(self, "确认", "确定要删除当前选中的服务商配置吗？") != QMessageBox.StandardButton.Yes:
            return

        idx = self._provider_combo.currentIndex()
        if idx < 0:
            return

        removed = self._providers.pop(idx)
        if removed.id == self._active_provider_id and self._providers:
            self._active_provider_id = self._providers[0].id
            
        self._refresh_provider_combo()

    # ── Save / test ──

    def _save(self) -> None:
        self._save_form_to_provider()
        current_p = self._selected_provider()
        if current_p:
            self._active_provider_id = current_p.id
            
        tags = [
            t.strip()
            for t in self._default_tags_input.text().split(",")
            if t.strip()
        ]
        config = AppConfig(
            llm_providers=self._providers,
            active_provider_id=self._active_provider_id,
            anki_connect_url=self._anki_url_input.text()
            or "http://127.0.0.1:8765",
            anki_connect_key=self._anki_key_input.text(),
            default_deck=self._default_deck_input.text() or "Default",
            default_tags=tags or ["ankismart"],
            ocr_correction=self._ocr_correction_check.isChecked(),
        )
        try:
            save_config(config)
            self._main.config = config
            self._status_label.setText("设置已保存")
            self._status_label.setStyleSheet("color: green;")
            self._refresh_provider_combo()
        except Exception as exc:
            QMessageBox.warning(self, "错误", f"保存失败：{exc}")

    def _test_connection(self) -> None:
        url = self._anki_url_input.text() or "http://127.0.0.1:8765"
        key = self._anki_key_input.text()
        self._status_label.setText("正在测试连接...")
        self._status_label.setStyleSheet("")

        worker = ConnectionCheckWorker(url, key)
        worker.finished.connect(self._on_test_result)
        worker.start()
        self._worker = worker

    def _on_test_result(self, connected: bool) -> None:
        if connected:
            self._status_label.setText("AnkiConnect：连接成功！")
            self._status_label.setStyleSheet("color: green;")
        else:
            self._status_label.setText("AnkiConnect：连接失败")
            self._status_label.setStyleSheet("color: red;")
        self._main.set_connection_status(connected)
