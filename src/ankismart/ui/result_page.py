from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.models import CardDraft, PushResult
from ankismart.ui.workers import ExportWorker, PushWorker


class ResultPage(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("page_content")
        self._main = main_window
        self._worker = None
        self._row_to_card_index: list[int] = []

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

        self._select_all = QCheckBox("全选")
        self._select_all.setChecked(True)
        self._select_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self._select_all.stateChanged.connect(self._toggle_select_all)
        title_row.addWidget(self._select_all)

        layout.addLayout(title_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["", "类型", "预览", "标签"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_push = QPushButton("推送到 Anki")
        self._btn_push.setMinimumHeight(40)
        self._btn_push.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_push.setProperty("role", "primary")
        self._btn_push.clicked.connect(self._push_cards)
        btn_row.addWidget(self._btn_push, 2)  # Stretch factor 2

        self._btn_export = QPushButton("导出 APKG")
        self._btn_export.setMinimumHeight(40)
        self._btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_export.clicked.connect(self._export_apkg)
        btn_row.addWidget(self._btn_export, 1) # Stretch factor 1

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
        self._refresh_table()

    def _refresh_table(self) -> None:
        cards = self._main.cards
        self._count_label.setText(f"({len(cards)})")
        self._table.setRowCount(len(cards))
        self._row_to_card_index = list(range(len(cards)))

        for i, card in enumerate(cards):
            # Checkbox
            chk = QTableWidgetItem()
            chk.setCheckState(Qt.CheckState.Checked)
            self._table.setItem(i, 0, chk)

            # Type
            self._table.setItem(i, 1, QTableWidgetItem(card.note_type))

            # Preview (first field value, truncated)
            preview = next(iter(card.fields.values()), "")[:80]
            self._table.setItem(i, 2, QTableWidgetItem(preview))

            # Tags
            self._table.setItem(i, 3, QTableWidgetItem(", ".join(card.tags)))

    def _get_selected_cards(self) -> tuple[list[CardDraft], list[int]]:
        cards = self._main.cards
        selected = []
        selected_rows: list[int] = []
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                card_index = self._row_to_card_index[i]
                selected.append(cards[card_index])
                selected_rows.append(i)
        return selected, selected_rows

    def _toggle_select_all(self, state: int) -> None:
        check = Qt.CheckState.Checked if state else Qt.CheckState.Unchecked
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            if item:
                item.setCheckState(check)

    def _push_cards(self) -> None:
        cards, selected_rows = self._get_selected_cards()
        if not cards:
            QMessageBox.information(self, "提示", "未选择卡片")
            return

        config = self._main.config
        self._btn_push.setEnabled(False)
        self._result_label.setText("正在推送到 Anki...")

        worker = PushWorker(
            cards, config.anki_connect_url, config.anki_connect_key,
            update_mode=self._update_check.isChecked(),
        )
        worker.finished.connect(lambda result, rows=selected_rows: self._on_push_done(result, rows))
        worker.error.connect(self._on_push_error)
        worker.start()
        self._worker = worker

    def _on_push_done(self, result: PushResult, selected_rows: list[int]) -> None:
        self._btn_push.setEnabled(True)
        self._result_label.setText(
            f"推送完成：成功 {result.succeeded}，失败 {result.failed}"
        )

        # Highlight failed rows
        for status in result.results:
            if not status.success:
                if status.index >= len(selected_rows):
                    continue
                table_row = selected_rows[status.index]
                for col in range(self._table.columnCount()):
                    item = self._table.item(table_row, col)
                    if item:
                        item.setBackground(Qt.GlobalColor.red)
                        item.setToolTip(status.error)

    def _on_push_error(self, msg: str) -> None:
        self._btn_push.setEnabled(True)
        self._result_label.setText("")
        QMessageBox.warning(self, "推送错误", msg)

    def _export_apkg(self) -> None:
        cards, _ = self._get_selected_cards()
        if not cards:
            QMessageBox.information(self, "提示", "未选择卡片")
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
