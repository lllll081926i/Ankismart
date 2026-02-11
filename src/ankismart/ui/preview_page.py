from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.models import BatchConvertResult, ConvertedDocument
from ankismart.ui.workers import BatchGenerateWorker


class PreviewPage(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("page_content")
        self._main = main_window
        self._documents: list[ConvertedDocument] = []
        self._edited_contents: dict[int, str] = {}
        self._current_index: int = -1
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title row
        title_row = QHBoxLayout()
        title = QLabel("预览与编辑")
        title.setProperty("role", "heading")
        title_row.addWidget(title)
        title_row.addStretch()

        self._btn_generate = QPushButton("生成卡片")
        self._btn_generate.setMinimumHeight(40)
        self._btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_generate.setProperty("role", "primary")
        self._btn_generate.clicked.connect(self._start_generate)
        title_row.addWidget(self._btn_generate)

        layout.addLayout(title_row)

        # Content area: file list + editor
        content_row = QHBoxLayout()

        self._file_list = QListWidget()
        self._file_list.setMaximumWidth(200)
        self._file_list.currentRowChanged.connect(self._on_file_switched)
        content_row.addWidget(self._file_list)

        self._editor = QPlainTextEdit()
        self._editor.setPlaceholderText("Markdown 内容将显示在这里...")
        content_row.addWidget(self._editor, 1)

        layout.addLayout(content_row, 1)

        # Progress bar + status
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: red;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

    def load_documents(self, batch_result: BatchConvertResult) -> None:
        """Load converted documents into the preview page."""
        self._documents = list(batch_result.documents)
        self._edited_contents.clear()
        self._current_index = -1

        self._file_list.clear()
        self._editor.clear()
        self._error_label.hide()
        self._status_label.setText("")

        for doc in self._documents:
            self._file_list.addItem(doc.file_name)

        # Hide file list when there is only one document
        self._file_list.setVisible(len(self._documents) > 1)

        # Show errors if any
        if batch_result.errors:
            self._error_label.setText(
                "转换失败：\n" + "\n".join(batch_result.errors)
            )
            self._error_label.show()

        # Select the first file
        if self._documents:
            self._file_list.setCurrentRow(0)

    def _on_file_switched(self, new_index: int) -> None:
        """Save current edits and load the newly selected file."""
        if new_index < 0:
            return

        # Save current editor content
        if 0 <= self._current_index < len(self._documents):
            self._edited_contents[self._current_index] = (
                self._editor.toPlainText()
            )

        # Load new file content
        self._current_index = new_index
        content = self._edited_contents.get(
            new_index, self._documents[new_index].result.content
        )
        self._editor.setPlainText(content)

    def _save_current_edit(self) -> None:
        """Persist the editor text for the current index."""
        if 0 <= self._current_index < len(self._documents):
            self._edited_contents[self._current_index] = (
                self._editor.toPlainText()
            )

    def _build_documents(self) -> list[ConvertedDocument]:
        """Return documents with edited markdown content applied."""
        result: list[ConvertedDocument] = []
        for i, doc in enumerate(self._documents):
            content = self._edited_contents.get(i, doc.result.content)
            updated_result = doc.result.model_copy(
                update={"content": content}
            )
            result.append(
                ConvertedDocument(
                    result=updated_result, file_name=doc.file_name
                )
            )
        return result

    def _start_generate(self) -> None:
        if not self._documents:
            QMessageBox.information(self, "提示", "没有可用的文档")
            return

        self._save_current_edit()

        # Read config from import_page
        import_page = self._main.import_page
        strategy = import_page._type_combo.currentData() or "basic"
        deck_name = import_page._deck_combo.currentText()
        tags = [
            t.strip()
            for t in import_page._tags_input.text().split(",")
            if t.strip()
        ]

        documents = self._build_documents()
        config = self._main.config
        requests_config = {
            "strategy": strategy,
            "deck_name": deck_name,
            "tags": tags,
        }

        self._btn_generate.setEnabled(False)
        self._progress.show()
        self._status_label.setText("正在生成卡片...")

        worker = BatchGenerateWorker(
            documents, requests_config, config.openai_api_key, config.openai_model
        )
        worker.file_progress.connect(self._on_file_progress)
        worker.finished.connect(self._on_generate_done)
        worker.error.connect(self._on_error)
        worker.start()
        self._worker = worker

    def _on_file_progress(
        self, current: int, total: int, filename: str
    ) -> None:
        self._status_label.setText(
            f"正在生成卡片 ({current}/{total})：{filename}"
        )

    def _on_generate_done(self, cards: list) -> None:
        self._progress.hide()
        self._btn_generate.setEnabled(True)
        self._status_label.setText(f"已生成 {len(cards)} 张卡片")

        self._main.cards = cards
        self._main.switch_to_results()

    def _on_error(self, msg: str) -> None:
        self._progress.hide()
        self._btn_generate.setEnabled(True)
        self._status_label.setText("")
        QMessageBox.warning(self, "错误", msg)
