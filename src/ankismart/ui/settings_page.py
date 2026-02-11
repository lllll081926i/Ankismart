from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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
    LLMProviderConfig,
    save_config,
)
from ankismart.ui.i18n import set_language, t
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
        title = QLabel(t("settings.title"))
        title.setProperty("role", "heading")
        layout.addWidget(title)

        # ── LLM Provider Section ──
        llm_group = QGroupBox(t("settings.provider_group"))
        llm_layout = QVBoxLayout(llm_group)
        llm_layout.setSpacing(16)
        llm_layout.setContentsMargins(16, 20, 16, 16)

        # Provider Selection Row
        sel_row = QHBoxLayout()
        sel_row.setSpacing(15)
        
        sel_label = QLabel(t("settings.provider"))
        sel_label.setFixedWidth(100)
        sel_row.addWidget(sel_label)

        self._provider_combo = QComboBox()
        self._provider_combo.setMinimumHeight(40) # Taller input
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        sel_row.addWidget(self._provider_combo, 1)

        btn_add = QPushButton(t("settings.add_provider"))
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setFixedWidth(80)
        btn_add.setMinimumHeight(40) # Taller button
        btn_add.clicked.connect(self._add_provider)
        sel_row.addWidget(btn_add)

        self._btn_delete = QPushButton(t("settings.remove_provider"))
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
        form.addRow(t("settings.name"), self._name_combo)

        self._base_url_input = QLineEdit()
        self._base_url_input.setPlaceholderText("https://api.openai.com/v1")
        self._base_url_input.setMinimumHeight(40) # Taller input
        form.addRow(t("settings.base_url"), self._base_url_input)

        self._provider_key_input = QLineEdit()
        self._provider_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._provider_key_input.setPlaceholderText("sk-...")
        self._provider_key_input.setMinimumHeight(40) # Taller input
        form.addRow(t("settings.api_key"), self._provider_key_input)

        self._provider_model_input = QLineEdit()
        self._provider_model_input.setPlaceholderText("gpt-4o")
        self._provider_model_input.setMinimumHeight(40) # Taller input
        form.addRow(t("settings.model"), self._provider_model_input)

        # Ollama model refresh
        ollama_row = QHBoxLayout()
        self._btn_refresh_models = QPushButton(t("settings.refresh_models"))
        self._btn_refresh_models.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh_models.setMinimumHeight(40)
        self._btn_refresh_models.clicked.connect(self._refresh_ollama_models)
        self._btn_refresh_models.hide()  # Only shown for Ollama providers
        ollama_row.addWidget(self._btn_refresh_models)
        ollama_row.addStretch()
        form.addRow("", ollama_row)

        # Rate limit
        rpm_row = QHBoxLayout()
        self._rpm_toggle = QPushButton(t("settings.rpm_off"))
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
        form.addRow(t("settings.rpm"), rpm_row)

        llm_layout.addLayout(form)
        layout.addWidget(llm_group)

        # ── AnkiConnect + Defaults ──
        other_group = QGroupBox(t("settings.other_group"))
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
        other_form.addRow(t("settings.anki_url"), self._anki_url_input)

        self._anki_key_input = QLineEdit()
        self._anki_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._anki_key_input.setPlaceholderText(t("settings.anki_key_placeholder"))
        self._anki_key_input.setMinimumHeight(40) # Taller input
        other_form.addRow(t("settings.anki_key"), self._anki_key_input)

        self._default_deck_input = QLineEdit()
        self._default_deck_input.setMinimumHeight(40) # Taller input
        other_form.addRow(t("settings.default_deck"), self._default_deck_input)

        self._default_tags_input = QLineEdit()
        self._default_tags_input.setMinimumHeight(40) # Taller input
        other_form.addRow(t("settings.default_tags"), self._default_tags_input)

        self._ocr_correction_check = QCheckBox(
            t("settings.ocr_correction")
        )
        self._ocr_correction_check.setMinimumHeight(30)
        other_form.addRow("", self._ocr_correction_check)
        
        other_layout.addLayout(other_form)
        layout.addWidget(other_group)

        # ── Language Settings ──
        lang_group = QGroupBox(t("settings.language_group"))
        lang_layout = QVBoxLayout(lang_group)
        lang_layout.setContentsMargins(16, 20, 16, 16)

        lang_form = QFormLayout()
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("中文", "zh")
        self._lang_combo.addItem("English", "en")
        self._lang_combo.setMinimumHeight(40)
        lang_form.addRow(t("settings.language"), self._lang_combo)
        lang_layout.addLayout(lang_form)
        layout.addWidget(lang_group)

        # ── Generation Parameters ──
        gen_group = QGroupBox(t("settings.gen_group"))
        gen_layout = QVBoxLayout(gen_group)
        gen_layout.setContentsMargins(16, 20, 16, 16)

        gen_form = QFormLayout()
        gen_form.setSpacing(12)
        gen_form.setVerticalSpacing(14)
        gen_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        gen_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self._temperature_spin = QDoubleSpinBox()
        self._temperature_spin.setRange(0.0, 2.0)
        self._temperature_spin.setSingleStep(0.1)
        self._temperature_spin.setDecimals(1)
        self._temperature_spin.setMinimumHeight(40)
        gen_form.addRow(t("settings.temperature"), self._temperature_spin)

        self._max_tokens_spin = QSpinBox()
        self._max_tokens_spin.setRange(0, 128000)
        self._max_tokens_spin.setSpecialValueText(t("settings.max_tokens_default"))
        self._max_tokens_spin.setSingleStep(256)
        self._max_tokens_spin.setMinimumHeight(40)
        gen_form.addRow(t("settings.max_tokens"), self._max_tokens_spin)

        gen_layout.addLayout(gen_form)
        layout.addWidget(gen_group)

        # ── Network Settings ──
        net_group = QGroupBox(t("settings.net_group"))
        net_layout = QVBoxLayout(net_group)
        net_layout.setContentsMargins(16, 20, 16, 16)

        net_form = QFormLayout()
        net_form.setSpacing(12)
        net_form.setVerticalSpacing(14)
        net_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        net_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self._proxy_input = QLineEdit()
        self._proxy_input.setPlaceholderText(t("settings.proxy_placeholder"))
        self._proxy_input.setMinimumHeight(40)
        net_form.addRow(t("settings.proxy"), self._proxy_input)

        net_layout.addLayout(net_form)
        layout.addWidget(net_group)

        # ── OCR Model Management ──
        ocr_group = QGroupBox(t("settings.ocr_group"))
        ocr_layout = QVBoxLayout(ocr_group)
        ocr_layout.setContentsMargins(16, 20, 16, 16)

        self._ocr_status_label = QLabel(t("settings.ocr_checking"))
        ocr_layout.addWidget(self._ocr_status_label)

        ocr_btn_row = QHBoxLayout()
        self._btn_download_ocr = QPushButton(t("settings.ocr_download"))
        self._btn_download_ocr.setMinimumHeight(40)
        self._btn_download_ocr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_download_ocr.clicked.connect(self._download_ocr_models)
        self._btn_download_ocr.hide()
        ocr_btn_row.addWidget(self._btn_download_ocr)

        self._btn_check_ocr = QPushButton(t("settings.ocr_check"))
        self._btn_check_ocr.setMinimumHeight(40)
        self._btn_check_ocr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_check_ocr.clicked.connect(self._check_ocr_status)
        ocr_btn_row.addWidget(self._btn_check_ocr)
        ocr_btn_row.addStretch()

        ocr_layout.addLayout(ocr_btn_row)
        layout.addWidget(ocr_group)

        layout.addSpacing(15)

        # Buttons
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(25) # Increased spacing
        btn_bar.addStretch()

        btn_test = QPushButton(t("settings.test_connection"))
        btn_test.setMinimumHeight(48) # Taller button
        btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test.clicked.connect(self._test_connection)
        btn_bar.addWidget(btn_test)

        btn_save = QPushButton(t("settings.save"))
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
        self._temperature_spin.setValue(config.llm_temperature)
        self._max_tokens_spin.setValue(config.llm_max_tokens)
        self._proxy_input.setText(config.proxy_url)
        lang_idx = self._lang_combo.findData(config.language)
        if lang_idx >= 0:
            self._lang_combo.setCurrentIndex(lang_idx)
        self._check_ocr_status()

    # ── OCR model management ──

    def _check_ocr_status(self) -> None:
        """Check which OCR models are installed."""
        try:
            from ankismart.converter.ocr_converter import get_missing_ocr_models
            missing = get_missing_ocr_models()
            if missing:
                self._ocr_status_label.setText(t("settings.ocr_missing", models=", ".join(missing)))
                self._btn_download_ocr.show()
            else:
                self._ocr_status_label.setText(t("settings.ocr_ready"))
                self._btn_download_ocr.hide()
        except Exception as exc:
            self._ocr_status_label.setText(t("settings.ocr_check_failed", error=exc))

    def _download_ocr_models(self) -> None:
        """Download missing OCR models."""
        self._btn_download_ocr.setEnabled(False)
        self._ocr_status_label.setText(t("settings.ocr_downloading"))

        from PySide6.QtCore import QThread, Signal

        class _DownloadWorker(QThread):
            progress = Signal(str)
            finished = Signal()
            error = Signal(str)

            def run(self):
                try:
                    from ankismart.converter.ocr_converter import download_missing_ocr_models
                    download_missing_ocr_models(progress_callback=lambda msg: self.progress.emit(msg))
                    self.finished.emit()
                except Exception as exc:
                    self.error.emit(str(exc))

        self._ocr_worker = _DownloadWorker()
        self._ocr_worker.progress.connect(lambda msg: self._ocr_status_label.setText(msg))
        self._ocr_worker.finished.connect(self._on_ocr_download_done)
        self._ocr_worker.error.connect(self._on_ocr_download_error)
        self._ocr_worker.start()

    def _on_ocr_download_done(self) -> None:
        self._ocr_status_label.setText(t("settings.ocr_download_done"))
        self._btn_download_ocr.hide()
        self._btn_download_ocr.setEnabled(True)

    def _on_ocr_download_error(self, msg: str) -> None:
        self._ocr_status_label.setText(t("settings.ocr_download_failed", error=msg))
        self._btn_download_ocr.setEnabled(True)

    def _refresh_provider_combo(self) -> None:
        self._updating_ui = True
        
        target_index = 0
        found_index = -1
        
        self._provider_combo.clear()
        for i, p in enumerate(self._providers):
            label = p.name or t("settings.unnamed")
            if p.model:
                label += f" - {p.model}"
            suffix = t("settings.active_suffix") if p.id == self._active_provider_id else ""
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
        self._rpm_toggle.setText(t("settings.rpm_on") if has_rpm else t("settings.rpm_off"))
        self._rpm_spin.setVisible(has_rpm)
        if has_rpm:
            self._rpm_spin.setValue(p.rpm_limit)
        is_ollama = "ollama" in p.name.lower()
        self._btn_refresh_models.setVisible(is_ollama)

        self._updating_ui = False

    def _on_name_edited(self, text: str) -> None:
        if self._updating_ui:
            return
        url = KNOWN_PROVIDERS.get(text, "")
        if url:
            self._base_url_input.setText(url)
        self._save_form_to_provider()
        # Show/hide Ollama model refresh button
        is_ollama = "ollama" in text.lower()
        self._btn_refresh_models.setVisible(is_ollama)

    def _on_rpm_toggled(self, checked: bool) -> None:
        self._rpm_toggle.setText(t("settings.rpm_on") if checked else t("settings.rpm_off"))
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
            QMessageBox.warning(self, t("settings.delete_warning"), t("settings.delete_min"))
            return
            
        if QMessageBox.question(self, t("settings.delete_confirm"), t("settings.delete_confirm_msg")) != QMessageBox.StandardButton.Yes:
            return

        idx = self._provider_combo.currentIndex()
        if idx < 0:
            return

        removed = self._providers.pop(idx)
        if removed.id == self._active_provider_id and self._providers:
            self._active_provider_id = self._providers[0].id
            
        self._refresh_provider_combo()

    # ── Save / test ──

    def _refresh_ollama_models(self) -> None:
        """Fetch model list from Ollama /api/tags endpoint."""
        base_url = self._base_url_input.text().strip()
        if not base_url:
            QMessageBox.warning(self, t("error.title"), t("settings.no_base_url"))
            return

        # Derive Ollama API URL from base_url (remove /v1 suffix if present)
        api_base = base_url.rstrip("/")
        if api_base.endswith("/v1"):
            api_base = api_base[:-3]

        self._btn_refresh_models.setEnabled(False)
        self._btn_refresh_models.setText(t("settings.refreshing"))

        import httpx
        try:
            resp = httpx.get(f"{api_base}/api/tags", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
            if not models:
                QMessageBox.information(self, t("settings.hint"), t("settings.no_models"))
            else:
                from PySide6.QtWidgets import QInputDialog
                model, ok = QInputDialog.getItem(
                    self, t("settings.select_model"), t("settings.available_models"), models, 0, False
                )
                if ok and model:
                    self._provider_model_input.setText(model)
        except Exception as exc:
            QMessageBox.warning(self, t("settings.fetch_failed"), t("settings.ollama_error", error=exc))
        finally:
            self._btn_refresh_models.setEnabled(True)
            self._btn_refresh_models.setText(t("settings.refresh_models"))

    def _save(self) -> None:
        self._save_form_to_provider()
        current_p = self._selected_provider()

        # Validate active provider has API key (skip for Ollama)
        if current_p and current_p.name and "ollama" not in current_p.name.lower():
            if not current_p.api_key.strip():
                QMessageBox.warning(self, t("settings.config_error"), t("settings.no_api_key_error"))
                return

        if current_p:
            self._active_provider_id = current_p.id

        tags = [
            tag.strip()
            for tag in self._default_tags_input.text().split(",")
            if tag.strip()
        ]
        base_config = self._main.config
        config = base_config.model_copy(
            update={
                "llm_providers": self._providers,
                "active_provider_id": self._active_provider_id,
                "anki_connect_url": self._anki_url_input.text()
                or "http://127.0.0.1:8765",
                "anki_connect_key": self._anki_key_input.text(),
                "default_deck": self._default_deck_input.text() or "Default",
                "default_tags": tags or ["ankismart"],
                "ocr_correction": self._ocr_correction_check.isChecked(),
                "llm_temperature": self._temperature_spin.value(),
                "llm_max_tokens": self._max_tokens_spin.value(),
                "proxy_url": self._proxy_input.text().strip(),
                "language": self._lang_combo.currentData() or "zh",
            }
        )
        try:
            save_config(config)
            self._main.config = config
            set_language(self._lang_combo.currentData() or "zh")
            self._status_label.setText(t("settings.saved"))
            self._status_label.setStyleSheet("color: green;")
            self._refresh_provider_combo()
        except Exception as exc:
            QMessageBox.warning(self, t("error.title"), t("settings.save_failed", error=exc))

    def _test_connection(self) -> None:
        url = self._anki_url_input.text() or "http://127.0.0.1:8765"
        key = self._anki_key_input.text()
        self._status_label.setText(t("settings.testing"))
        self._status_label.setStyleSheet("")

        worker = ConnectionCheckWorker(url, key, proxy_url=self._proxy_input.text().strip())
        worker.finished.connect(self._on_test_result)
        worker.start()
        self._worker = worker

    def _on_test_result(self, connected: bool) -> None:
        if connected:
            self._status_label.setText(t("settings.test_ok"))
            self._status_label.setStyleSheet("color: green;")
        else:
            self._status_label.setText(t("settings.test_fail"))
            self._status_label.setStyleSheet("color: red;")
        self._main.set_connection_status(connected)
