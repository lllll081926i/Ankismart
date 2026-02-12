from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    InfoBar,
    InfoBarPosition,
    PrimaryPushButton,
    PushButton,
    TableWidget,
)

from ankismart.core.models import CardDraft, CardPushStatus, PushResult
from ankismart.ui.i18n import t
from ankismart.ui.workers import ExportWorker, PushWorker


class ResultPage(QWidget):
    """推送结果展示页面，显示卡片推送统计和详细结果列表。"""

    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("resultPage")
        self._main = main_window
        self._worker = None
        self._push_result: PushResult | None = None
        self._cards: list[CardDraft] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = BodyLabel(t("result.title"))
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Statistics cards row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(15)

        self._card_total = self._create_stat_card("总卡片数", "0", "#409EFF")
        self._card_success = self._create_stat_card("成功推送", "0", "#67C23A")
        self._card_failed = self._create_stat_card("失败", "0", "#F56C6C")
        self._card_skipped = self._create_stat_card("跳过", "0", "#E6A23C")

        stats_row.addWidget(self._card_total)
        stats_row.addWidget(self._card_success)
        stats_row.addWidget(self._card_failed)
        stats_row.addWidget(self._card_skipped)

        layout.addLayout(stats_row)

        # Results table
        table_label = BodyLabel("详细结果")
        table_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(table_label)

        self._table = TableWidget()
        self._table.setBorderVisible(True)
        self._table.setBorderRadius(8)
        self._table.setWordWrap(False)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["卡片标题", "状态", "错误信息"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 100)
        self._table.setSortingEnabled(True)
        self._table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_retry = PrimaryPushButton("重试失败卡片")
        self._btn_retry.setMinimumHeight(40)
        self._btn_retry.clicked.connect(self._retry_failed)
        self._btn_retry.setEnabled(False)
        btn_row.addWidget(self._btn_retry)

        self._btn_export_failed = PushButton("导出失败卡片")
        self._btn_export_failed.setMinimumHeight(40)
        self._btn_export_failed.clicked.connect(self._export_failed)
        self._btn_export_failed.setEnabled(False)
        btn_row.addWidget(self._btn_export_failed)

        self._btn_back = PushButton("返回预览")
        self._btn_back.setMinimumHeight(40)
        self._btn_back.clicked.connect(self._back_to_preview)
        btn_row.addWidget(self._btn_back)

        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _create_stat_card(self, title: str, value: str, color: str) -> CardWidget:
        """创建统计卡片。"""
        card = CardWidget()
        card.setMinimumHeight(100)
        card.setBorderRadius(8)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)
        card_layout.setContentsMargins(20, 15, 20, 15)

        title_label = CaptionLabel(title)
        title_label.setStyleSheet("font-size: 13px; color: #666666;")
        card_layout.addWidget(title_label)

        value_label = BodyLabel(value)
        value_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {color};")
        value_label.setObjectName("stat_value")
        card_layout.addWidget(value_label)

        card_layout.addStretch()

        return card

    def _update_stat_card(self, card: CardWidget, value: str) -> None:
        """更新统计卡片的值。"""
        value_label = card.findChild(BodyLabel, "stat_value")
        if value_label:
            value_label.setText(value)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        """页面显示时刷新数据。"""
        super().showEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        """刷新页面数据。"""
        if self._push_result:
            self._display_result(self._push_result, self._cards)
        else:
            self._clear_display()

    def load_result(self, result: PushResult, cards: list[CardDraft]) -> None:
        """加载推送结果数据。"""
        self._push_result = result
        self._cards = cards
        self._display_result(result, cards)

    def _display_result(self, result: PushResult, cards: list[CardDraft]) -> None:
        """显示推送结果。"""
        # Update statistics
        self._update_stat_card(self._card_total, str(result.total))
        self._update_stat_card(self._card_success, str(result.succeeded))
        self._update_stat_card(self._card_failed, str(result.failed))
        skipped = result.total - result.succeeded - result.failed
        self._update_stat_card(self._card_skipped, str(skipped))

        # Update table
        self._table.setRowCount(0)
        for status in result.results:
            self._add_table_row(status, cards)

        # Enable/disable buttons
        has_failed = result.failed > 0
        self._btn_retry.setEnabled(has_failed)
        self._btn_export_failed.setEnabled(has_failed)

        # Show info bar
        if result.succeeded == result.total:
            InfoBar.success(
                title="推送成功",
                content=f"成功推送 {result.succeeded} 张卡片",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        elif result.failed > 0:
            InfoBar.warning(
                title="部分失败",
                content=f"成功 {result.succeeded} 张，失败 {result.failed} 张",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )

    def _add_table_row(self, status: CardPushStatus, cards: list[CardDraft]) -> None:
        """添加表格行。"""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Card title (from first field)
        card_title = "未知卡片"
        if 0 <= status.index < len(cards):
            card = cards[status.index]
            if card.fields:
                first_field = next(iter(card.fields.values()))
                card_title = first_field[:50] + "..." if len(first_field) > 50 else first_field

        title_item = QTableWidgetItem(card_title)
        self._table.setItem(row, 0, title_item)

        # Status with color
        if status.success:
            status_text = "成功"
            status_color = "#67C23A"
        elif status.error:
            status_text = "失败"
            status_color = "#F56C6C"
        else:
            status_text = "跳过"
            status_color = "#E6A23C"

        status_item = QTableWidgetItem(status_text)
        status_item.setForeground(Qt.GlobalColor.white)
        status_item.setBackground(self._hex_to_qcolor(status_color))
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 1, status_item)

        # Error message
        error_item = QTableWidgetItem(status.error or "")
        self._table.setItem(row, 2, error_item)

    def _hex_to_qcolor(self, hex_color: str):
        """将十六进制颜色转换为 QColor。"""
        from PySide6.QtGui import QColor

        return QColor(hex_color)

    def _clear_display(self) -> None:
        """清空显示。"""
        self._update_stat_card(self._card_total, "0")
        self._update_stat_card(self._card_success, "0")
        self._update_stat_card(self._card_failed, "0")
        self._update_stat_card(self._card_skipped, "0")
        self._table.setRowCount(0)
        self._btn_retry.setEnabled(False)
        self._btn_export_failed.setEnabled(False)

    def _retry_failed(self) -> None:
        """重试失败的卡片。"""
        if not self._push_result or not self._cards:
            return

        # Collect failed cards
        failed_cards = []
        for status in self._push_result.results:
            if not status.success and 0 <= status.index < len(self._cards):
                failed_cards.append(self._cards[status.index])

        if not failed_cards:
            InfoBar.info(
                title="提示",
                content="没有失败的卡片需要重试",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )
            return

        # Disable buttons during push
        self._btn_retry.setEnabled(False)
        self._btn_export_failed.setEnabled(False)

        # Start push worker
        config = self._main.config
        worker = PushWorker(
            failed_cards,
            config.anki_connect_url,
            config.anki_connect_key,
            update_mode=config.last_update_mode or "create_only",
            proxy_url=config.proxy_url,
        )
        worker.finished.connect(self._on_retry_done)
        worker.error.connect(self._on_retry_error)
        worker.start()
        self._worker = worker

        InfoBar.info(
            title="重试中",
            content=f"正在重试 {len(failed_cards)} 张失败卡片...",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )

    def _on_retry_done(self, result: PushResult) -> None:
        """重试完成回调。"""
        # Merge retry result with original result
        if self._push_result:
            # Update original result statistics
            self._push_result.succeeded += result.succeeded
            self._push_result.failed = result.failed

            # Update status for retried cards
            retry_index = 0
            for i, status in enumerate(self._push_result.results):
                if not status.success and retry_index < len(result.results):
                    self._push_result.results[i] = result.results[retry_index]
                    retry_index += 1

            self._display_result(self._push_result, self._cards)

        if result.succeeded > 0:
            InfoBar.success(
                title="重试成功",
                content=f"成功推送 {result.succeeded} 张卡片",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        else:
            InfoBar.error(
                title="重试失败",
                content="所有卡片重试失败",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )

    def _on_retry_error(self, msg: str) -> None:
        """重试错误回调。"""
        self._btn_retry.setEnabled(True)
        self._btn_export_failed.setEnabled(True)

        InfoBar.error(
            title="重试错误",
            content=msg,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )

    def _export_failed(self) -> None:
        """导出失败的卡片为 APKG。"""
        if not self._push_result or not self._cards:
            return

        # Collect failed cards
        failed_cards = []
        for status in self._push_result.results:
            if not status.success and 0 <= status.index < len(self._cards):
                failed_cards.append(self._cards[status.index])

        if not failed_cards:
            InfoBar.info(
                title="提示",
                content="没有失败的卡片需要导出",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )
            return

        # Show save dialog
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出失败卡片",
            "ankismart_failed.apkg",
            "Anki Package (*.apkg)",
        )
        if not path:
            return

        # Disable buttons during export
        self._btn_export_failed.setEnabled(False)

        # Start export worker
        worker = ExportWorker(failed_cards, Path(path))
        worker.finished.connect(self._on_export_done)
        worker.error.connect(self._on_export_error)
        worker.start()
        self._worker = worker

        InfoBar.info(
            title="导出中",
            content=f"正在导出 {len(failed_cards)} 张失败卡片...",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )

    def _on_export_done(self, path: Path) -> None:
        """导出完成回调。"""
        self._btn_export_failed.setEnabled(True)

        InfoBar.success(
            title="导出成功",
            content=f"已导出到 {path}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )

    def _on_export_error(self, msg: str) -> None:
        """导出错误回调。"""
        self._btn_export_failed.setEnabled(True)

        InfoBar.error(
            title="导出错误",
            content=msg,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )

    def _back_to_preview(self) -> None:
        """返回预览页面。"""
        reply = QMessageBox.question(
            self,
            "确认返回",
            "返回预览页面将丢失当前结果，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._main.switch_to_preview()
