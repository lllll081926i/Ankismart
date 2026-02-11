from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
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
from ankismart.core.models import BatchConvertResult
from ankismart.ui.workers import BatchConvertWorker, DeckListWorker

# File filter for supported formats
_FILE_FILTER = (
    "文档文件 (*.md *.txt *.docx *.pptx *.pdf "
    "*.png *.jpg *.jpeg *.bmp *.tiff *.webp)"
)

_SUPPORTED_TYPES = {"markdown", "text", "docx", "pptx", "pdf", "image"}
_OCR_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}


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
        title = QLabel("导入与生成")
        title.setProperty("role", "heading")
        layout.addWidget(title)

        # --- File selection ---
        group_file = QVBoxLayout()
        group_file.setSpacing(8)
        group_file.addWidget(QLabel("选择文档："))

        file_row = QHBoxLayout()
        self._file_label = QLabel("未选择文件 (支持 .md, .docx, .pptx, .pdf, 图片)")
        self._file_label.setStyleSheet("color: #666666;")

        btn_browse = QPushButton("浏览...")
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
        deck_layout.addWidget(QLabel("目标牌组："))
        self._deck_combo = QComboBox()
        self._deck_combo.setEditable(True)
        self._deck_combo.addItem("Default")
        self._deck_combo.setMinimumHeight(36)
        deck_layout.addWidget(self._deck_combo)
        form_layout.addLayout(deck_layout)

        # Type
        type_layout = QVBoxLayout()
        type_layout.setSpacing(5)
        type_layout.addWidget(QLabel("卡片类型："))
        self._type_combo = QComboBox()
        self._type_combo.setMinimumHeight(36)
        self._type_combo.addItem("基础问答", "basic")
        self._type_combo.addItem("完形填空", "cloze")
        self._type_combo.addItem("概念解释", "concept")
        self._type_combo.addItem("关键术语", "key_terms")
        self._type_combo.addItem("单选题", "single_choice")
        self._type_combo.addItem("多选题", "multiple_choice")
        self._type_combo.addItem("图片问答（附图）", "image_qa")
        type_layout.addWidget(self._type_combo)

        self._type_mode_combo = QComboBox()
        self._type_mode_combo.setMinimumHeight(36)
        self._type_mode_combo.addItem("单一题型", "single")
        self._type_mode_combo.addItem("自定义组合", "mixed")
        self._type_mode_combo.currentIndexChanged.connect(self._on_type_mode_changed)
        type_layout.addWidget(self._type_mode_combo)

        self._total_count_input = QLineEdit("20")
        self._total_count_input.setMinimumHeight(36)
        self._total_count_input.setPlaceholderText("总题数，例如 20")
        self._total_count_input.hide()
        type_layout.addWidget(self._total_count_input)

        self._mixed_widget = QWidget()
        mixed_layout = QGridLayout(self._mixed_widget)
        mixed_layout.setContentsMargins(0, 0, 0, 0)
        mixed_layout.setHorizontalSpacing(8)
        mixed_layout.setVerticalSpacing(6)
        mixed_layout.addWidget(QLabel("题型"), 0, 0)
        mixed_layout.addWidget(QLabel("占比(%)"), 0, 1)

        strategy_options = [
            ("basic", "基础问答", "40"),
            ("cloze", "完形填空", "20"),
            ("concept", "概念解释", "15"),
            ("key_terms", "关键术语", "10"),
            ("single_choice", "单选题", "10"),
            ("multiple_choice", "多选题", "5"),
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
        tags_layout.addWidget(QLabel("标签（逗号分隔）："))
        self._tags_input = QLineEdit("ankismart")
        self._tags_input.setMinimumHeight(36)
        tags_layout.addWidget(self._tags_input)
        form_layout.addLayout(tags_layout)

        layout.addLayout(form_layout)
        layout.addSpacing(10)

        # --- Convert button ---
        self._btn_convert = QPushButton("转换文档")
        self._btn_convert.setMinimumHeight(44)
        self._btn_convert.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_convert.setProperty("role", "primary")
        self._btn_convert.setEnabled(False)
        self._btn_convert.clicked.connect(self._start_convert)
        layout.addWidget(self._btn_convert)

        # --- Progress ---
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # Indeterminate
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Load deck list from Anki
        self._load_decks()

    def _on_type_mode_changed(self) -> None:
        is_mixed = (self._type_mode_combo.currentData() == "mixed")
        self._type_combo.setVisible(not is_mixed)
        self._mixed_widget.setVisible(is_mixed)
        self._total_count_input.setVisible(is_mixed)

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
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文档", "", _FILE_FILTER)
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
                unsupported.append(f"{path.name}: 当前版本不支持该文件类型")
                continue

            valid_paths.append(path)

        if unsupported:
            QMessageBox.warning(
                self, "错误", "\n".join(unsupported)
            )

        if not valid_paths:
            self._btn_convert.setEnabled(False)
            return

        self._file_paths = valid_paths

        if len(valid_paths) == 1:
            self._file_label.setText(valid_paths[0].name)
        else:
            self._file_label.setText(f"已选择 {len(valid_paths)} 个文件")
        self._file_label.setStyleSheet("")
        self._btn_convert.setEnabled(True)

    # ------------------------------------------------------------------
    # Deck loading
    # ------------------------------------------------------------------

    def _load_decks(self) -> None:
        config = self._main.config
        worker = DeckListWorker(config.anki_connect_url, config.anki_connect_key)
        worker.finished.connect(self._on_decks_loaded)
        worker.error.connect(lambda _: None)  # Silently ignore if Anki not running
        worker.start()
        self._deck_worker = worker

    def _on_decks_loaded(self, decks: list[str]) -> None:
        self._deck_combo.clear()
        for deck in decks:
            self._deck_combo.addItem(deck)

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
            "OCR 模型缺失",
            f"检测到以下 OCR 模型缺失：\n{model_list}\n\n是否现在下载？\n（仅在处理 PDF/图片 时需要）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self._status_label.setText("已取消 OCR 模型下载")
            return False

        dialog = QProgressDialog("准备下载 OCR 模型...", "取消", 0, len(missing), self)
        dialog.setWindowTitle("下载 OCR 模型")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(True)

        def _on_progress(done: int, total: int, message: str) -> None:
            if dialog.wasCanceled():
                raise RuntimeError("用户取消下载")
            dialog.setMaximum(max(1, total))
            dialog.setValue(min(done, total))
            dialog.setLabelText(message)
            QApplication.processEvents()

        try:
            download_missing_ocr_models(progress_callback=_on_progress)
            dialog.setValue(len(missing))
            self._status_label.setText("OCR 模型已就绪")
            return True
        except Exception as exc:
            dialog.cancel()
            self._status_label.setText("OCR 模型下载失败")
            QMessageBox.warning(
                self,
                "OCR 模型下载失败",
                f"下载 OCR 模型失败：{exc}",
            )
            return False

    def _start_convert(self) -> None:
        if not self._file_paths:
            return

        if not self._ensure_ocr_models_ready():
            return

        file_count = len(self._file_paths)
        self._btn_convert.setEnabled(False)
        self._progress.setRange(0, file_count)
        self._progress.setValue(0)
        self._progress.show()
        self._status_label.setText("正在转换文档...")

        worker = BatchConvertWorker(self._file_paths, self._main.config)
        worker.file_progress.connect(self._on_file_progress)
        worker.finished.connect(self._on_batch_convert_done)
        worker.error.connect(self._on_error)
        worker.start()
        self._worker = worker

    def _on_file_progress(self, current: int, total: int, filename: str) -> None:
        self._progress.setValue(current)
        self._status_label.setText(f"正在转换 ({current}/{total}): {filename}")

    def _on_batch_convert_done(self, result: BatchConvertResult) -> None:
        self._progress.hide()
        self._btn_convert.setEnabled(True)

        if result.errors:
            QMessageBox.warning(
                self,
                "部分文件转换失败",
                "\n".join(result.errors),
            )

        if not result.documents:
            self._status_label.setText("没有成功转换的文档")
            return

        self._status_label.setText(
            f"已转换 {len(result.documents)} 个文档"
        )
        self._main.batch_result = result
        self._main.switch_to_preview()

    def _on_error(self, msg: str) -> None:
        self._progress.hide()
        self._btn_convert.setEnabled(True)
        self._status_label.setText("")
        QMessageBox.warning(self, "错误", msg)
