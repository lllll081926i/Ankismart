from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
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


class ImportPage(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("page_content")
        self._main = main_window
        self._file_paths: list[Path] = []
        self._worker = None  # Keep reference to prevent GC

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
        self._type_combo.addItem("图片问答（附图）", "image_qa")
        type_layout.addWidget(self._type_combo)
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

    def _start_convert(self) -> None:
        if not self._file_paths:
            return

        file_count = len(self._file_paths)
        self._btn_convert.setEnabled(False)
        self._progress.setRange(0, file_count)
        self._progress.setValue(0)
        self._progress.show()
        self._status_label.setText("正在转换文档...")

        worker = BatchConvertWorker(self._file_paths)
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
