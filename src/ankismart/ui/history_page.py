from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CaptionLabel,
    CardWidget,
    CheckBox,
    ComboBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    TableWidget,
    TitleLabel,
)
from qfluentwidgets import (
    MessageBox as FluentMessageBox,
)

from ankismart.core.history_export import (
    export_cards_to_csv,
    export_cards_to_json,
    export_cards_to_markdown,
)
from ankismart.core.history_store import (
    GenerationBatchSummary,
    SQLiteHistoryStore,
    get_default_history_store,
)
from ankismart.core.models import CardDraft
from ankismart.ui.styles import (
    MARGIN_SMALL,
    MARGIN_STANDARD,
    SPACING_MEDIUM,
    SPACING_SMALL,
    apply_compact_combo_metrics,
    apply_page_title_style,
    get_theme_accent_text_hex,
)


class HistoryPage(QWidget):
    """历史结果页面，展示并导出之前生成的卡片批次。"""

    _PAGE_SIZE = 50

    def __init__(self, main_window, *, history_store: SQLiteHistoryStore | None = None) -> None:
        super().__init__()
        self.setObjectName("historyPage")
        self._main = main_window
        self._history_store = history_store or get_default_history_store()
        self._summaries: list[GenerationBatchSummary] = []
        self._filtered_summaries: list[GenerationBatchSummary] = []
        self._selected_batch_ids: set[str] = set()
        self._export_worker = None
        self._current_page = 0

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_SMALL)
        layout.setContentsMargins(
            MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD
        )

        self._title_label = TitleLabel("历史结果")
        apply_page_title_style(self._title_label)
        layout.addWidget(self._title_label)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(SPACING_MEDIUM)
        self._total_records_card, self._total_records_value = self._create_stat_card(
            "历史批次", "0", get_theme_accent_text_hex()
        )
        self._total_cards_card, self._total_cards_value = self._create_stat_card(
            "卡片总数", "0", "#67C23A"
        )
        self._cache_size_card, self._cache_size_value = self._create_stat_card(
            "缓存占用", "0 MB", "#E6A23C"
        )
        stats_row.addWidget(self._total_records_card)
        stats_row.addWidget(self._total_cards_card)
        stats_row.addWidget(self._cache_size_card)
        layout.addLayout(stats_row)

        toolbar = CardWidget()
        toolbar.setBorderRadius(8)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(
            MARGIN_STANDARD, MARGIN_SMALL, MARGIN_STANDARD, MARGIN_SMALL
        )
        toolbar_layout.setSpacing(MARGIN_SMALL)

        self._search_edit = LineEdit()
        self._search_edit.setPlaceholderText("筛选来源文件、标题或策略")
        self._search_edit.setMinimumWidth(260)
        self._search_edit.textChanged.connect(self.refresh_history)
        toolbar_layout.addWidget(self._search_edit, 1)

        self._select_all_checkbox = CheckBox("全选")
        self._select_all_checkbox.stateChanged.connect(self._on_select_all_changed)
        toolbar_layout.addWidget(self._select_all_checkbox)

        self._export_format_combo = ComboBox()
        self._export_format_combo.addItem("APKG", userData="apkg")
        self._export_format_combo.addItem("JSON", userData="json")
        self._export_format_combo.addItem("CSV", userData="csv")
        self._export_format_combo.addItem("Markdown", userData="markdown")
        self._export_format_combo.setMinimumWidth(128)
        apply_compact_combo_metrics(self._export_format_combo)
        toolbar_layout.addWidget(self._export_format_combo)

        self._btn_refresh = PushButton("刷新")
        self._btn_refresh.setIcon(FluentIcon.SYNC)
        self._btn_refresh.clicked.connect(self.refresh_history)
        toolbar_layout.addWidget(self._btn_refresh)

        self._btn_export_selected = PrimaryPushButton("导出所选")
        self._btn_export_selected.setIcon(FluentIcon.DOWNLOAD)
        self._btn_export_selected.clicked.connect(self._export_selected)
        self._btn_export_selected.setEnabled(False)
        toolbar_layout.addWidget(self._btn_export_selected)

        self._btn_export_all = PushButton("导出全部")
        self._btn_export_all.setIcon(FluentIcon.SAVE)
        self._btn_export_all.clicked.connect(self._export_all)
        toolbar_layout.addWidget(self._btn_export_all)

        self._btn_load_selected = PushButton("载入预览")
        self._btn_load_selected.setIcon(FluentIcon.VIEW)
        self._btn_load_selected.clicked.connect(self._load_selected_to_preview)
        self._btn_load_selected.setEnabled(False)
        toolbar_layout.addWidget(self._btn_load_selected)

        self._btn_delete_selected = PushButton("删除所选")
        self._btn_delete_selected.setIcon(FluentIcon.DELETE)
        self._btn_delete_selected.clicked.connect(self._delete_selected)
        self._btn_delete_selected.setEnabled(False)
        toolbar_layout.addWidget(self._btn_delete_selected)

        self._btn_prune_cache = PushButton("清理超额")
        self._btn_prune_cache.setIcon(FluentIcon.BROOM)
        self._btn_prune_cache.clicked.connect(self._prune_cache)
        toolbar_layout.addWidget(self._btn_prune_cache)

        layout.addWidget(toolbar)

        self._table = TableWidget()
        self._table.setBorderVisible(True)
        self._table.setBorderRadius(8)
        self._table.setWordWrap(False)
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["", "生成时间", "来源文件", "卡片数", "策略", "状态", "标题"]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setDefaultSectionSize(38)
        layout.addWidget(self._table, 1)

        bottom_bar = CardWidget()
        bottom_bar.setBorderRadius(8)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(
            MARGIN_STANDARD, MARGIN_SMALL, MARGIN_STANDARD, MARGIN_SMALL
        )
        self._status_label = CaptionLabel("")
        bottom_layout.addWidget(self._status_label)
        bottom_layout.addStretch(1)
        self._btn_prev_page = PushButton("上一页")
        self._btn_prev_page.clicked.connect(self._go_prev_page)
        bottom_layout.addWidget(self._btn_prev_page)
        self._pagination_label = CaptionLabel("第 1/1 页，共 0 条")
        bottom_layout.addWidget(self._pagination_label)
        self._btn_next_page = PushButton("下一页")
        self._btn_next_page.clicked.connect(self._go_next_page)
        bottom_layout.addWidget(self._btn_next_page)
        layout.addWidget(bottom_bar)

        self.refresh_history()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh_history()

    def refresh_history(self) -> None:
        stats = self._history_store.get_cache_stats()
        limit = max(500, int(getattr(self._main.config, "history_cache_max_records", 500)))
        self._summaries = self._history_store.list_generation_batches(limit=limit)
        query = self._search_edit.text().strip().lower() if hasattr(self, "_search_edit") else ""
        visible = [summary for summary in self._summaries if self._matches_query(summary, query)]

        self._total_records_value.setText(str(stats["batch_count"]))
        self._total_cards_value.setText(str(stats["card_count"]))
        self._cache_size_value.setText(_format_size_mb(float(stats["size_mb"])))
        self._render_table(visible)
        self._update_actions()

    def _render_table(self, summaries: list[GenerationBatchSummary]) -> None:
        self._filtered_summaries = summaries
        self._clamp_current_page()
        self._render_current_page()

    def _render_current_page(self) -> None:
        self._table.setUpdatesEnabled(False)
        try:
            self._table.setRowCount(0)
            visible_ids = {summary.batch_id for summary in self._filtered_summaries}
            self._selected_batch_ids &= visible_ids
            for summary in self._current_page_summaries():
                self._add_summary_row(summary)
        finally:
            self._table.setUpdatesEnabled(True)
        self._update_pagination_controls()

    def _add_summary_row(self, summary: GenerationBatchSummary) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        checkbox = CheckBox()
        checkbox.setChecked(summary.batch_id in self._selected_batch_ids)
        checkbox.stateChanged.connect(
            lambda state, batch_id=summary.batch_id: self._on_row_selection_changed(batch_id, state)
        )
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self._table.setCellWidget(row, 0, checkbox_widget)

        values = [
            _format_time(summary.created_at),
            _source_documents_text(summary),
            str(summary.card_count),
            _strategy_text(summary),
            _status_text(summary.status),
            summary.title,
        ]
        for column, value in enumerate(values, start=1):
            item = QTableWidgetItem(value)
            if column == 3:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, column, item)

    def _on_row_selection_changed(self, batch_id: str, state: int) -> None:
        if state:
            self._selected_batch_ids.add(batch_id)
        else:
            self._selected_batch_ids.discard(batch_id)
        self._sync_select_all_checkbox()
        self._update_actions()

    def _on_select_all_changed(self, state: int) -> None:
        if state:
            self._selected_batch_ids = {summary.batch_id for summary in self._visible_summaries()}
        else:
            self._selected_batch_ids.clear()
        self._render_current_page()
        self._update_actions()

    def _sync_select_all_checkbox(self) -> None:
        visible_ids = {summary.batch_id for summary in self._visible_summaries()}
        checked = bool(visible_ids) and visible_ids <= self._selected_batch_ids
        self._select_all_checkbox.blockSignals(True)
        self._select_all_checkbox.setChecked(checked)
        self._select_all_checkbox.blockSignals(False)
        self._update_pagination_controls()

    def _visible_summaries(self) -> list[GenerationBatchSummary]:
        query = self._search_edit.text().strip().lower()
        if self._filtered_summaries and not query:
            return list(self._filtered_summaries)
        return [summary for summary in self._summaries if self._matches_query(summary, query)]

    def _update_actions(self) -> None:
        has_rows = bool(self._summaries)
        has_selection = bool(self._selected_batch_ids)
        self._btn_export_all.setEnabled(has_rows)
        self._btn_export_selected.setEnabled(has_selection)
        self._btn_load_selected.setEnabled(has_selection)
        self._btn_delete_selected.setEnabled(has_selection)
        self._sync_select_all_checkbox()

    def _total_pages(self) -> int:
        if not self._filtered_summaries:
            return 1
        return (len(self._filtered_summaries) + self._PAGE_SIZE - 1) // self._PAGE_SIZE

    def _clamp_current_page(self) -> None:
        self._current_page = max(0, min(self._current_page, self._total_pages() - 1))

    def _current_page_summaries(self) -> list[GenerationBatchSummary]:
        start = self._current_page * self._PAGE_SIZE
        end = start + self._PAGE_SIZE
        return self._filtered_summaries[start:end]

    def _update_pagination_controls(self) -> None:
        total = len(self._filtered_summaries)
        total_pages = self._total_pages()
        self._pagination_label.setText(
            f"第 {self._current_page + 1}/{total_pages} 页，共 {total} 条"
        )
        self._btn_prev_page.setEnabled(self._current_page > 0)
        self._btn_next_page.setEnabled(self._current_page < total_pages - 1)
        if total:
            start = self._current_page * self._PAGE_SIZE + 1
            end = min(total, start + len(self._current_page_summaries()) - 1)
            self._status_label.setText(
                f"显示 {start}-{end}/{total} 条记录，已选择 {len(self._selected_batch_ids)} 条"
            )
        else:
            self._status_label.setText("显示 0 条记录，已选择 0 条")

    def _go_prev_page(self) -> None:
        if self._current_page <= 0:
            return
        self._current_page -= 1
        self._render_current_page()
        self._update_actions()

    def _go_next_page(self) -> None:
        if self._current_page >= self._total_pages() - 1:
            return
        self._current_page += 1
        self._render_current_page()
        self._update_actions()

    def _export_selected(self) -> None:
        if not self._selected_batch_ids:
            self._show_info_bar("info", "提示", "请先选择要导出的历史记录")
            return
        self._export_batch_ids(sorted(self._selected_batch_ids))

    def _export_all(self) -> None:
        batch_ids = [summary.batch_id for summary in self._summaries]
        if not batch_ids:
            self._show_info_bar("info", "提示", "暂无历史记录可导出")
            return
        self._export_batch_ids(batch_ids)

    def _export_batch_ids(self, batch_ids: list[str]) -> None:
        cards = self._load_cards_for_batches(batch_ids)
        if not cards:
            self._show_info_bar("warning", "导出失败", "选中的历史记录没有可导出的卡片")
            return

        format_id = str(self._export_format_combo.currentData() or "apkg")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出历史结果",
            self._default_export_name(format_id),
            self._file_dialog_filter(format_id),
        )
        if not path:
            return

        output_path = Path(path)
        try:
            if format_id == "json":
                export_cards_to_json(cards, output_path)
            elif format_id == "csv":
                export_cards_to_csv(cards, output_path)
            elif format_id == "markdown":
                export_cards_to_markdown(cards, output_path)
            else:
                from ankismart.anki_gateway.apkg_exporter import ApkgExporter

                ApkgExporter().export(cards, output_path)
        except Exception as exc:
            self._show_info_bar("error", "导出失败", str(exc), duration=5000)
            return

        self._show_info_bar("success", "导出完成", f"已导出 {len(cards)} 张卡片")

    def _delete_selected(self) -> None:
        if not self._selected_batch_ids:
            self._show_info_bar("info", "提示", "请先选择要删除的历史记录")
            return
        count = len(self._selected_batch_ids)
        dialog = FluentMessageBox(
            "确认删除",
            f"确定要删除选中的 {count} 条历史记录吗？此操作不可撤销。",
            self,
        )
        dialog.yesButton.setText("是")
        dialog.cancelButton.setText("否")
        if not dialog.exec():
            return

        deleted = self._history_store.delete_generation_batches(sorted(self._selected_batch_ids))
        self._selected_batch_ids.clear()
        self.refresh_history()
        self._show_info_bar("success", "删除完成", f"已删除 {deleted} 条历史记录")

    def _prune_cache(self) -> None:
        result = self._history_store.prune_cache(
            max_size_mb=getattr(self._main.config, "history_cache_max_mb", 500),
            max_records=getattr(self._main.config, "history_cache_max_records", 500),
        )
        self.refresh_history()
        if result.deleted_batches:
            self._show_info_bar("success", "清理完成", f"已清理 {result.deleted_batches} 条记录")
        else:
            self._show_info_bar("info", "无需清理", "历史缓存当前未超过设置上限")

    def _load_selected_to_preview(self) -> None:
        cards = self._load_cards_for_batches(sorted(self._selected_batch_ids))
        if not cards:
            self._show_info_bar("info", "提示", "请先选择要载入的历史记录")
            return
        self._main.cards = cards
        preview_page = getattr(self._main, "card_preview_page", None)
        if preview_page is not None and hasattr(preview_page, "load_cards"):
            preview_page.load_cards(cards)
        switch_page = getattr(self._main, "_switch_page", None)
        if callable(switch_page):
            switch_page(2)
        self._show_info_bar("success", "已载入", f"已载入 {len(cards)} 张卡片到预览页")

    def _load_cards_for_batches(self, batch_ids: list[str]) -> list[CardDraft]:
        cards: list[CardDraft] = []
        for batch_id in batch_ids:
            cards.extend(self._history_store.load_generation_cards(batch_id))
        return cards

    def _matches_query(self, summary: GenerationBatchSummary, query: str) -> bool:
        if not query:
            return True
        haystack = " ".join(
            [
                summary.title,
                _source_documents_text(summary),
                _strategy_text(summary),
                summary.status,
            ]
        ).lower()
        return query in haystack

    def _show_info_bar(
        self,
        level: str,
        title: str,
        content: str,
        *,
        duration: int = 3000,
    ) -> None:
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

    @staticmethod
    def _create_stat_card(title: str, value: str, color: str) -> tuple[CardWidget, TitleLabel]:
        card = CardWidget()
        card.setMinimumHeight(78)
        card.setBorderRadius(8)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(4)
        card_layout.setContentsMargins(MARGIN_STANDARD, 8, MARGIN_STANDARD, 8)

        title_label = CaptionLabel(title)
        card_layout.addWidget(title_label)

        value_label = TitleLabel(value)
        value_label.setStyleSheet(f"color: {color};")
        card_layout.addWidget(value_label)
        card_layout.addStretch()
        return card, value_label

    @staticmethod
    def _file_dialog_filter(format_id: str) -> str:
        return {
            "json": "JSON Files (*.json)",
            "csv": "CSV Files (*.csv)",
            "markdown": "Markdown Files (*.md)",
        }.get(format_id, "Anki Package (*.apkg)")

    @staticmethod
    def _default_export_name(format_id: str) -> str:
        suffix = {
            "json": "json",
            "csv": "csv",
            "markdown": "md",
        }.get(format_id, "apkg")
        return f"ankismart_history.{suffix}"


def _format_size_mb(size_mb: float) -> str:
    if size_mb < 0.01:
        return "0 MB"
    if size_mb < 1024:
        return f"{size_mb:.2f} MB"
    return f"{size_mb / 1024:.2f} GB"


def _format_time(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value.replace("T", " ")[:19]
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone()
    return parsed.strftime("%Y-%m-%d %H:%M")


def _source_documents_text(summary: GenerationBatchSummary) -> str:
    return _metadata_list_text(summary.metadata.get("source_documents")) or "未记录"


def _strategy_text(summary: GenerationBatchSummary) -> str:
    return _metadata_list_text(summary.metadata.get("strategy_ids")) or "未记录"


def _metadata_list_text(value: Any) -> str:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        items = [item.strip() for item in value.split(",") if item.strip()]
    else:
        items = []
    if len(items) <= 3:
        return ", ".join(items)
    return f"{', '.join(items[:3])} 等 {len(items)} 个"


def _status_text(status: str) -> str:
    status_map = {"success": "成功", "partial": "部分完成", "failed": "失败"}
    return status_map.get(status, status or "未记录")
