from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankismart.converter.detector import detect_file_type
from ankismart.core.config import save_config
from ankismart.core.models import BatchConvertResult
from ankismart.ui.i18n import t
from ankismart.ui.workers import BatchConvertWorker, DeckListWorker

_SUPPORTED_TYPES = {"markdown", "text", "docx", "pptx", "pdf", "image"}
_OCR_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


def _file_filter() -> str:
    return t("import.file_filter")


class ImportPage(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("page_content")
        self._main = main_window
        self._file_paths: list[Path] = []
        self._worker = None  # Keep reference to prevent GC
        self._strategy_items: list[tuple[str, QCheckBox, QLineEdit]] = []

        # Main layout with padding
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel(t("import.title"))
        title.setProperty("role", "heading")
        layout.addWidget(title)

        # --- File selection ---
        group_file = QVBoxLayout()
        group_file.setSpacing(8)
        group_file.addWidget(QLabel(t("import.select_files")))

        file_row = QHBoxLayout()
        self._file_label = QLabel(t("import.file_placeholder"))
        self._file_label.setStyleSheet("color: #666666;")

        btn_browse = QPushButton(t("import.browse"))
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.clicked.connect(self._browse_files)

        file_row.addWidget(self._file_label, 1)
        file_row.addWidget(btn_browse)
        group_file.addLayout(file_row)
        layout.addLayout(group_file)

        # --- Generation config ---
        form_layout = QVBoxLayout()
        form_layout.setSpacing(15)

        # Deck
        deck_layout = QVBoxLayout()
        deck_layout.setSpacing(5)
        deck_layout.addWidget(QLabel(t("import.deck")))
        self._deck_combo = QComboBox()
        self._deck_combo.setEditable(True)
        self._deck_combo.addItem("Default")
        self._deck_combo.setMinimumHeight(36)
        deck_layout.addWidget(self._deck_combo)
        form_layout.addLayout(deck_layout)

        # Type
        type_layout = QVBoxLayout()
        type_layout.setSpacing(5)
        type_layout.addWidget(QLabel(t("import.card_type")))
        self._type_combo = QComboBox()
        self._type_combo.setMinimumHeight(36)
        self._type_combo.addItem(t("card.basic"), "basic")
        self._type_combo.addItem(t("card.cloze"), "cloze")
        self._type_combo.addItem(t("card.concept"), "concept")
        self._type_combo.addItem(t("card.key_terms"), "key_terms")
        self._type_combo.addItem(t("card.single_choice"), "single_choice")
        self._type_combo.addItem(t("card.multiple_choice"), "multiple_choice")
        self._type_combo.addItem(t("card.image_qa"), "image_qa")
        type_layout.addWidget(self._type_combo)

        self._type_mode_combo = QComboBox()
        self._type_mode_combo.setMinimumHeight(36)
        self._type_mode_combo.addItem(t("import.single_type"), "single")
        self._type_mode_combo.addItem(t("import.mixed_type"), "mixed")
        self._type_mode_combo.currentIndexChanged.connect(self._on_type_mode_changed)
        type_layout.addWidget(self._type_mode_combo)

        self._total_count_input = QLineEdit("20")
        self._total_count_input.setMinimumHeight(36)
        self._total_count_input.setPlaceholderText(t("import.total_count_placeholder"))
        self._total_count_input.hide()
        type_layout.addWidget(self._total_count_input)

        self._mixed_widget = QWidget()
        mixed_layout = QGridLayout(self._mixed_widget)
        mixed_layout.setContentsMargins(0, 0, 0, 0)
        mixed_layout.setHorizontalSpacing(8)
        mixed_layout.setVerticalSpacing(6)
        mixed_layout.addWidget(QLabel(t("import.type_col")), 0, 0)
        mixed_layout.addWidget(QLabel(t("import.ratio_col")), 0, 1)

        strategy_options = [
            ("basic", t("card.basic"), "40"),
            ("cloze", t("card.cloze"), "20"),
            ("concept", t("card.concept"), "15"),
            ("key_terms", t("card.key_terms"), "10"),
            ("single_choice", t("card.single_choice"), "10"),
            ("multiple_choice", t("card.multiple_choice"), "5"),
        ]
        for row, (key, label_text, default_ratio) in enumerate(strategy_options, start=1):
            checkbox = QCheckBox(label_text)
            ratio_input = QLineEdit(default_ratio)
            ratio_input.setMinimumHeight(32)
            ratio_input.setMaximumWidth(100)
            ratio_input.setPlaceholderText("0-100")
            mixed_layout.addWidget(checkbox, row, 0)
            mixed_layout.addWidget(ratio_input, row, 1)
            self._strategy_items.append((key, checkbox, ratio_input))

        self._mixed_widget.hide()
        type_layout.addWidget(self._mixed_widget)
        form_layout.addLayout(type_layout)

        # Tags
        tags_layout = QVBoxLayout()
        tags_layout.setSpacing(5)
        tags_layout.addWidget(QLabel(t("import.tags")))
        self._tags_input = QLineEdit("ankismart")
        self._tags_input.setMinimumHeight(36)
        tags_layout.addWidget(self._tags_input)
        form_layout.addLayout(tags_layout)

        layout.addLayout(form_layout)
        layout.addSpacing(10)
        layout.addStretch()

        # --- Convert button ---
        self._btn_convert = QPushButton(t("import.convert"))
        self._btn_convert.setMinimumHeight(44)
        self._btn_convert.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_convert.setProperty("role", "primary")
        self._btn_convert.setEnabled(False)
        self._btn_convert.clicked.connect(self._start_convert)
        layout.addWidget(self._btn_convert)

        # --- Cancel button ---
        self._btn_cancel = QPushButton(t("import.cancel"))
        self._btn_cancel.setMinimumHeight(44)
        self._btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel.clicked.connect(self._cancel_convert)
        self._btn_cancel.hide()
        layout.addWidget(self._btn_cancel)

        # --- Progress ---
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # Indeterminate
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Load deck list from Anki
        self._load_decks()

        # Restore last-used values
        self._restore_last_values()

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+O"), self, self._browse_files)

    def _restore_last_values(self) -> None:
        config = self._main.config
        if config.last_deck:
            self._deck_combo.setCurrentText(config.last_deck)
        if config.last_tags:
            self._tags_input.setText(config.last_tags)
        if config.last_strategy:
            for i in range(self._type_combo.count()):
                if self._type_combo.itemData(i) == config.last_strategy:
                    self._type_combo.setCurrentIndex(i)
                    break

    @staticmethod
    def _provider_requires_api_key(provider) -> bool:
        if provider is None:
            return True
        provider_name = (provider.name or "").strip().lower()
        return "ollama" not in provider_name

    def _save_last_values(self) -> None:
        config = self._main.config
        config.last_deck = self._deck_combo.currentText()
        config.last_tags = self._tags_input.text()
        config.last_strategy = self._type_combo.currentData() or "basic"
        try:
            save_config(config)
        except Exception:
            pass
        self._main.config = config

    def _on_type_mode_changed(self) -> None:
        is_mixed = (self._type_mode_combo.currentData() == "mixed")
        self._type_combo.setVisible(not is_mixed)
        self._mixed_widget.setVisible(is_mixed)
        self._total_count_input.setVisible(is_mixed)

    def cancel_operation(self) -> None:
        """Cancel the current conversion if running."""
        if self._worker and self._worker.isRunning():
            if hasattr(self._worker, 'cancel'):
                self._worker.cancel()
            self._status_label.setText(t("import.cancelled"))
            self._progress.hide()
            self._btn_convert.setEnabled(True)
            if hasattr(self, '_btn_cancel'):
                self._btn_cancel.hide()

    def build_generation_config(self) -> dict:
        mode = self._type_mode_combo.currentData() or "single"

        if mode != "mixed":
            return {
                "mode": "single",
                "strategy": self._type_combo.currentData() or "basic",
            }

        target_total = 20
        try:
            target_total = max(1, int(self._total_count_input.text().strip() or "20"))
        except ValueError:
            target_total = 20

        ratio_items: list[dict[str, int | str]] = []
        for strategy, checkbox, ratio_input in self._strategy_items:
            if not checkbox.isChecked():
                continue
            try:
                ratio = int(ratio_input.text().strip() or "0")
            except ValueError:
                ratio = 0
            if ratio > 0:
                ratio_items.append({"strategy": strategy, "ratio": ratio})

        if not ratio_items:
            ratio_items = [{"strategy": "basic", "ratio": 100}]

        return {
            "mode": "mixed",
            "target_total": target_total,
            "strategy_mix": ratio_items,
        }

    # ------------------------------------------------------------------
    # File browsing
    # ------------------------------------------------------------------

    def _browse_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, t("import.select_dialog"), "", _file_filter())
        if not paths:
            return

        valid_paths: list[Path] = []
        unsupported: list[str] = []

        for p in paths:
            path = Path(p)
            try:
                file_type = detect_file_type(path)
            except Exception as exc:
                unsupported.append(f"{path.name}: {exc}")
                continue

            if file_type not in _SUPPORTED_TYPES:
                unsupported.append(f"{path.name}: {t('import.unsupported_type')}")
                continue

            valid_paths.append(path)

        if unsupported:
            QMessageBox.warning(
                self, t("error.title"), "\n".join(unsupported)
            )

        if not valid_paths:
            self._btn_convert.setEnabled(False)
            return

        self._file_paths = valid_paths

        if len(valid_paths) == 1:
            self._file_label.setText(valid_paths[0].name)
        else:
            self._file_label.setText(t("import.selected_files", count=len(valid_paths)))
        self._file_label.setStyleSheet("")
        self._btn_convert.setEnabled(True)

    # ------------------------------------------------------------------
    # Deck loading
    # ------------------------------------------------------------------

    def _load_decks(self) -> None:
        config = self._main.config
        worker = DeckListWorker(config.anki_connect_url, config.anki_connect_key, proxy_url=config.proxy_url)
        worker.finished.connect(self._on_decks_loaded)
        worker.error.connect(lambda _: None)  # Silently ignore if Anki not running
        worker.start()
        self._deck_worker = worker

    def _on_decks_loaded(self, decks: list[str]) -> None:
        current_text = self._deck_combo.currentText().strip()
        self._deck_combo.clear()
        for deck in decks:
            self._deck_combo.addItem(deck)
        preferred_deck = self._main.config.last_deck.strip() or current_text
        if preferred_deck:
            self._deck_combo.setCurrentText(preferred_deck)

    # ------------------------------------------------------------------
    # Batch conversion
    # ------------------------------------------------------------------

    def _needs_ocr_models(self) -> bool:
        return any(path.suffix.lower() in _OCR_EXTENSIONS for path in self._file_paths)

    def _ensure_ocr_models_ready(self) -> bool:
        if not self._needs_ocr_models():
            return True

        from ankismart.converter.ocr_converter import (
            download_missing_ocr_models,
            get_missing_ocr_models,
        )

        missing = get_missing_ocr_models()
        if not missing:
            return True

        model_list = "\n".join(f"- {name}" for name in missing)
        answer = QMessageBox.question(
            self,
            t("import.ocr_missing"),
            t("import.ocr_download_prompt", models=model_list),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._status_label.setText(t("import.ocr_cancelled"))
            return False

        dialog = QProgressDialog(t("import.ocr_preparing"), t("import.cancel"), 0, len(missing), self)
        dialog.setWindowTitle(t("import.ocr_download_title"))
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(True)
        dialog.setValue(0)
        dialog.show()
        QApplication.processEvents()

        def _on_progress(done: int, total: int, message: str) -> None:
            if dialog.wasCanceled():
                raise RuntimeError(t("import.ocr_user_cancel"))
            dialog.setMaximum(max(1, total))
            dialog.setValue(min(done, total))
            dialog.setLabelText(message)
            QApplication.processEvents()

        try:
            self._status_label.setText(t("import.ocr_downloading"))
            download_missing_ocr_models(progress_callback=_on_progress)
            dialog.setValue(len(missing))
            self._status_label.setText(t("import.ocr_ready"))
            return True
        except Exception as exc:
            dialog.cancel()
            self._status_label.setText(t("import.ocr_download_failed"))
            QMessageBox.warning(
                self,
                t("import.ocr_download_failed"),
                t("import.ocr_download_failed_detail", error=exc),
            )
            return False

    def _start_convert(self) -> None:
        if not self._file_paths:
            return

        if not self._ensure_ocr_models_ready():
            return

        # Validate configuration
        config = self._main.config
        provider = config.active_provider
        if (
            provider is None
            or (
                self._provider_requires_api_key(provider)
                and not provider.api_key.strip()
            )
        ):
            QMessageBox.warning(self, t("import.config_error"), t("import.no_api_key"))
            return

        deck_name = self._deck_combo.currentText().strip()
        if not deck_name:
            QMessageBox.warning(self, t("import.config_error"), t("import.no_deck"))
            return

        # Validate mixed mode ratios
        if self._type_mode_combo.currentData() == "mixed":
            has_valid = False
            for strategy, checkbox, ratio_input in self._strategy_items:
                if checkbox.isChecked():
                    try:
                        ratio = int(ratio_input.text().strip() or "0")
                        if ratio > 0:
                            has_valid = True
                            break
                    except ValueError:
                        continue
            if not has_valid:
                QMessageBox.warning(self, t("import.config_error"), t("import.mixed_ratio_error"))
                return

        file_count = len(self._file_paths)
        self._btn_convert.setEnabled(False)
        self._progress.setRange(0, file_count)
        self._progress.setValue(0)
        self._progress.show()
        self._status_label.setText(t("import.converting_docs"))

        self._save_last_values()

        worker = BatchConvertWorker(self._file_paths, self._main.config)
        worker.file_progress.connect(self._on_file_progress)
        if hasattr(worker, "ocr_progress"):
            worker.ocr_progress.connect(self._on_ocr_progress)
        worker.finished.connect(self._on_batch_convert_done)
        worker.error.connect(self._on_error)
        worker.start()
        self._worker = worker
        if hasattr(self, '_btn_cancel'):
            self._btn_cancel.show()

    def _cancel_convert(self) -> None:
        if self._worker and hasattr(self._worker, 'cancel'):
            self._worker.cancel()
        if hasattr(self, '_btn_cancel'):
            self._btn_cancel.hide()
        self._status_label.setText(t("import.cancelling"))

    def _on_file_progress(self, current: int, total: int, filename: str) -> None:
        self._progress.setValue(current)
        self._status_label.setText(t("import.converting", current=current, total=total, filename=filename))

    def _on_ocr_progress(self, message: str) -> None:
        self._status_label.setText(message)

    def _on_batch_convert_done(self, result: BatchConvertResult) -> None:
        self._progress.hide()
        self._btn_convert.setEnabled(True)
        if hasattr(self, '_btn_cancel'):
            self._btn_cancel.hide()

        if result.errors:
            QMessageBox.warning(
                self,
                t("import.partial_fail"),
                "\n".join(result.errors),
            )

        if not result.documents:
            self._status_label.setText(t("import.no_docs"))
            return

        self._status_label.setText(
            t("import.converted", count=len(result.documents))
        )
        self._main.batch_result = result
        self._main.switch_to_preview()

    def _on_error(self, msg: str) -> None:
        self._progress.hide()
        self._btn_convert.setEnabled(True)
        if hasattr(self, '_btn_cancel'):
            self._btn_cancel.hide()
        self._status_label.setText("")
        QMessageBox.warning(self, t("error.title"), msg)
