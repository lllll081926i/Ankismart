from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.models import CardDraft, PushResult
from ankismart.ui.card_edit_widget import CardEditWidget
from ankismart.ui.workers import ExportWorker, PushWorker


class ResultPage(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("page_content")
        self._main = main_window
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_row = QHBoxLayout()
        title = QLabel("生成结果")
        title.setProperty("role", "heading")
        title_row.addWidget(title)

        self._count_label = QLabel("(0)")
        self._count_label.setStyleSheet("color: #666666;")
        title_row.addWidget(self._count_label)

        title_row.addStretch()
        layout.addLayout(title_row)

        # Card editor widget
        self._card_editor = CardEditWidget()
        self._card_editor.cards_changed.connect(self._on_cards_changed)
        layout.addWidget(self._card_editor, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_push = QPushButton("推送到 Anki")
        self._btn_push.setMinimumHeight(40)
        self._btn_push.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_push.setProperty("role", "primary")
        self._btn_push.clicked.connect(self._push_cards)
        btn_row.addWidget(self._btn_push, 2)

        self._btn_export = QPushButton("导出 APKG")
        self._btn_export.setMinimumHeight(40)
        self._btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_export.clicked.connect(self._export_apkg)
        btn_row.addWidget(self._btn_export, 1)

        layout.addLayout(btn_row)

        # Update mode option
        self._update_check = QCheckBox("更新模式（已有相同卡片时更新而非新建）")
        self._update_check.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._update_check)

        # Result summary
        self._result_label = QLabel("")
        layout.addWidget(self._result_label)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        cards = self._main.cards
        self._count_label.setText(f"({len(cards)})")
        self._card_editor.set_cards(cards)

    def _on_cards_changed(self) -> None:
        """Sync edited cards back to main window."""
        cards = self._card_editor.get_cards()
        self._main.cards = cards
        self._count_label.setText(f"({len(cards)})")

    def _get_cards(self) -> list[CardDraft]:
        """Return the current (edited) card list."""
        return self._card_editor.get_cards()

    def _push_cards(self) -> None:
        cards = self._get_cards()
        if not cards:
            QMessageBox.information(self, "提示", "没有卡片可推送")
            return

        config = self._main.config
        self._btn_push.setEnabled(False)
        self._result_label.setText("正在推送到 Anki...")

        worker = PushWorker(
            cards, config.anki_connect_url, config.anki_connect_key,
            update_mode=self._update_check.isChecked(),
        )
        worker.finished.connect(self._on_push_done)
        worker.error.connect(self._on_push_error)
        worker.start()
        self._worker = worker

    def _on_push_done(self, result: PushResult) -> None:
        self._btn_push.setEnabled(True)
        self._result_label.setText(
            f"推送完成：成功 {result.succeeded}，失败 {result.failed}"
        )

    def _on_push_error(self, msg: str) -> None:
        self._btn_push.setEnabled(True)
        self._result_label.setText("")
        QMessageBox.warning(self, "推送错误", msg)

    def _export_apkg(self) -> None:
        cards = self._get_cards()
        if not cards:
            QMessageBox.information(self, "提示", "没有卡片可导出")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 APKG",
            "ankismart_export.apkg",
            "Anki 牌组包 (*.apkg)",
        )
        if not path:
            return

        self._btn_export.setEnabled(False)
        self._result_label.setText("正在导出...")

        worker = ExportWorker(cards, Path(path))
        worker.finished.connect(self._on_export_done)
        worker.error.connect(self._on_export_error)
        worker.start()
        self._worker = worker

    def _on_export_done(self, path: Path) -> None:
        self._btn_export.setEnabled(True)
        self._result_label.setText(f"已导出到：{path}")

    def _on_export_error(self, msg: str) -> None:
        self._btn_export.setEnabled(True)
        self._result_label.setText("")
        QMessageBox.warning(self, "导出错误", msg)
