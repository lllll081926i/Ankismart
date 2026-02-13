from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
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
    CheckBox,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SimpleCardWidget,
    SubtitleLabel,
    SwitchButton,
    TableWidget,
    TitleLabel,
    ToolButton,
    FluentIcon,
)

from ankismart.anki_gateway.apkg_exporter import ApkgExporter
from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.anki_gateway.gateway import AnkiGateway
from ankismart.core.models import CardDraft, CardPushStatus, PushResult
from ankismart.ui.card_edit_widget import CardEditDialog
from ankismart.ui.i18n import t
from ankismart.ui.workers import ExportWorker, PushWorker
from ankismart.ui.shortcuts import ShortcutKeys, create_shortcut, get_shortcut_text
from ankismart.ui.styles import (
    SPACING_LARGE,
    SPACING_MEDIUM,
    SPACING_SMALL,
    MARGIN_STANDARD,
    MARGIN_SMALL,
    apply_page_title_style,
)

logger = logging.getLogger(__name__)


class ResultPage(QWidget):
    """推送结果展示页面，显示卡片推送统计和详细结果列表。"""

    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("resultPage")
        self._main = main_window
        self._language = getattr(self._main.config, "language", "zh")
        self._worker = None
        self._push_result: PushResult | None = None
        self._cards: list[CardDraft] = []
        self._selected_indices: set[int] = set()  # Track selected card indices

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MEDIUM)  # Reduced from SPACING_LARGE
        layout.setContentsMargins(MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD)

        # Title
        title = TitleLabel(t("result.title"))
        apply_page_title_style(title)
        layout.addWidget(title)

        # Statistics cards row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(SPACING_MEDIUM)

        self._card_total = self._create_stat_card("总卡片数", "0", "#409EFF")
        self._card_success = self._create_stat_card("成功推送", "0", "#67C23A")
        self._card_failed = self._create_stat_card("失败", "0", "#F56C6C")
        self._card_skipped = self._create_stat_card("跳过", "0", "#E6A23C")

        stats_row.addWidget(self._card_total)
        stats_row.addWidget(self._card_success)
        stats_row.addWidget(self._card_failed)
        stats_row.addWidget(self._card_skipped)

        layout.addLayout(stats_row)

        # Unified settings card (merged push and duplicate settings)
        settings_card = self._create_unified_settings_card()
        settings_card.setMaximumHeight(92)
        layout.addWidget(settings_card)

        # Results table
        table_label = SubtitleLabel("详细结果")
        layout.addWidget(table_label)

        self._table = TableWidget()
        self._table.setBorderVisible(True)
        self._table.setBorderRadius(8)
        self._table.setWordWrap(False)
        self._table.setColumnCount(5)
        self._table.setMinimumHeight(520)

        # Create header with checkbox
        self._header_checkbox = CheckBox()
        self._header_checkbox.stateChanged.connect(self._on_select_all_changed)

        self._table.setHorizontalHeaderLabels(["", "卡片标题", "状态", "错误信息", "操作"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 50)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(4, 80)
        self._table.setSortingEnabled(False)  # Disable sorting to keep checkbox alignment
        self._table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table, 5)

        # All buttons in one row at the bottom, right-aligned
        all_buttons_row = QHBoxLayout()
        all_buttons_row.setSpacing(MARGIN_SMALL)
        all_buttons_row.addStretch()

        self._btn_batch_edit_tags = PrimaryPushButton(t("result.batch_edit_tags"))
        self._btn_batch_edit_tags.setMinimumHeight(40)
        self._btn_batch_edit_tags.clicked.connect(self._batch_edit_tags)
        self._btn_batch_edit_tags.setEnabled(False)
        all_buttons_row.addWidget(self._btn_batch_edit_tags)

        self._btn_batch_edit_deck = PushButton(t("result.batch_edit_deck"))
        self._btn_batch_edit_deck.setMinimumHeight(40)
        self._btn_batch_edit_deck.clicked.connect(self._batch_edit_deck)
        self._btn_batch_edit_deck.setEnabled(False)
        all_buttons_row.addWidget(self._btn_batch_edit_deck)

        self._btn_retry = PushButton("重试失败卡片" if self._language == "zh" else "Retry Failed")
        self._btn_retry.setMinimumHeight(40)
        self._btn_retry.clicked.connect(self._retry_failed)
        self._btn_retry.setEnabled(False)
        all_buttons_row.addWidget(self._btn_retry)

        self._btn_repush_all = PushButton("推送所有卡片" if self._language == "zh" else "Push All Cards")
        self._btn_repush_all.setMinimumHeight(40)
        self._btn_repush_all.clicked.connect(self._repush_all_cards)
        self._btn_repush_all.setEnabled(False)
        all_buttons_row.addWidget(self._btn_repush_all)

        self._btn_export_apkg = PushButton("导出为 APKG" if self._language == "zh" else "Export as APKG")
        self._btn_export_apkg.setMinimumHeight(40)
        self._btn_export_apkg.clicked.connect(self._export_apkg)
        self._btn_export_apkg.setEnabled(False)
        all_buttons_row.addWidget(self._btn_export_apkg)

        layout.addLayout(all_buttons_row)

        # Track edited cards
        self._edited_card_indices: set[int] = set()

        # Initialize shortcuts
        self._init_shortcuts()

    def _init_shortcuts(self):
        """Initialize page-specific keyboard shortcuts."""
        # Removed Ctrl+E shortcut for export failed cards
        pass

    def _on_update_mode_changed(self) -> None:
        """Persist selected update mode in runtime config."""
        mode = self._update_combo.currentData()
        if mode:
            setattr(self._main.config, "last_update_mode", mode)

    def _create_unified_settings_card(self) -> SimpleCardWidget:
        """Create unified settings card with push and duplicate settings."""
        card = SimpleCardWidget()
        card.setBorderRadius(8)

        card_layout = QHBoxLayout(card)
        card_layout.setSpacing(SPACING_MEDIUM)
        card_layout.setContentsMargins(MARGIN_STANDARD, MARGIN_SMALL, MARGIN_STANDARD, MARGIN_SMALL)

        # Update strategy
        update_row = QHBoxLayout()
        update_row.setSpacing(SPACING_SMALL)
        update_label = BodyLabel(t("result.update_strategy"))
        self._update_combo = ComboBox()
        self._update_combo.addItem(t("result.create_only"), userData="create_only")
        self._update_combo.addItem(t("result.update_only"), userData="update_only")
        self._update_combo.addItem(t("result.create_or_update"), userData="create_or_update")
        self._update_combo.setFixedWidth(170)

        default_mode = getattr(self._main.config, "last_update_mode", None) or "create_only"
        for idx in range(self._update_combo.count()):
            if self._update_combo.itemData(idx) == default_mode:
                self._update_combo.setCurrentIndex(idx)
                break
        self._update_combo.currentIndexChanged.connect(self._on_update_mode_changed)
        update_row.addWidget(update_label)
        update_row.addWidget(self._update_combo)
        update_row.addStretch(1)

        # Duplicate scope
        scope_row = QHBoxLayout()
        scope_row.setSpacing(SPACING_SMALL)
        scope_label = BodyLabel(t("result.duplicate_scope"))
        self._duplicate_scope_combo = ComboBox()
        self._duplicate_scope_combo.addItem(t("result.duplicate_scope_deck"), userData="deck")
        self._duplicate_scope_combo.addItem(t("result.duplicate_scope_collection"), userData="collection")
        self._duplicate_scope_combo.setFixedWidth(170)
        duplicate_scope = getattr(self._main.config, "duplicate_scope", "deck")
        self._duplicate_scope_combo.setCurrentIndex(
            0 if duplicate_scope == "deck" else 1
        )
        self._duplicate_scope_combo.currentIndexChanged.connect(self._on_duplicate_scope_changed)
        scope_row.addWidget(scope_label)
        scope_row.addWidget(self._duplicate_scope_combo)
        scope_row.addStretch(1)

        # Check model switch
        model_row = QHBoxLayout()
        model_row.setSpacing(SPACING_SMALL)
        model_label = BodyLabel(t("result.duplicate_check_model"))
        self._check_model_switch = SwitchButton()
        self._check_model_switch.setChecked(getattr(self._main.config, "duplicate_check_model", True))
        self._check_model_switch.checkedChanged.connect(self._on_check_model_changed)
        model_row.addWidget(model_label)
        model_row.addStretch(1)
        model_row.addWidget(self._check_model_switch)

        # Allow duplicate switch
        allow_row = QHBoxLayout()
        allow_row.setSpacing(SPACING_SMALL)
        allow_label = BodyLabel(t("result.allow_duplicate"))
        self._allow_duplicate_switch = SwitchButton()
        self._allow_duplicate_switch.setChecked(getattr(self._main.config, "allow_duplicate", False))
        self._allow_duplicate_switch.checkedChanged.connect(self._on_allow_duplicate_changed)
        allow_row.addWidget(allow_label)
        allow_row.addStretch(1)
        allow_row.addWidget(self._allow_duplicate_switch)

        card_layout.addLayout(update_row, 1)
        card_layout.addLayout(scope_row, 1)
        card_layout.addLayout(model_row, 1)
        card_layout.addLayout(allow_row, 1)

        return card

    def _create_duplicate_settings_card(self) -> SimpleCardWidget:
        """Create duplicate check settings card following QFluentWidgets official style."""
        card = SimpleCardWidget()
        card.setBorderRadius(8)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(SPACING_MEDIUM)
        card_layout.setContentsMargins(MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD)

        # Title
        title_label = SubtitleLabel(t("result.duplicate_check_settings"))
        card_layout.addWidget(title_label)

        # Duplicate scope setting
        scope_row = QHBoxLayout()
        scope_row.setSpacing(SPACING_MEDIUM)

        scope_label = BodyLabel(t("result.duplicate_scope"))
        scope_label.setFixedWidth(100)
        scope_row.addWidget(scope_label)

        self._duplicate_scope_combo = ComboBox()
        self._duplicate_scope_combo.addItem(t("result.duplicate_scope_deck"), userData="deck")
        self._duplicate_scope_combo.addItem(t("result.duplicate_scope_collection"), userData="collection")
        duplicate_scope = getattr(self._main.config, "duplicate_scope", "deck")
        self._duplicate_scope_combo.setCurrentIndex(
            0 if duplicate_scope == "deck" else 1
        )
        self._duplicate_scope_combo.currentIndexChanged.connect(self._on_duplicate_scope_changed)
        self._duplicate_scope_combo.setFixedWidth(150)
        scope_row.addWidget(self._duplicate_scope_combo)

        scope_desc = CaptionLabel(t("result.duplicate_scope_desc"))
        scope_row.addWidget(scope_desc)
        scope_row.addStretch()

        card_layout.addLayout(scope_row)

        # Check model setting
        model_row = QHBoxLayout()
        model_row.setSpacing(SPACING_MEDIUM)

        model_label = BodyLabel(t("result.duplicate_check_model"))
        model_label.setFixedWidth(100)
        model_row.addWidget(model_label)

        self._check_model_switch = SwitchButton()
        self._check_model_switch.setChecked(getattr(self._main.config, "duplicate_check_model", True))
        self._check_model_switch.checkedChanged.connect(self._on_check_model_changed)
        model_row.addWidget(self._check_model_switch)

        model_desc = CaptionLabel(t("result.duplicate_check_model_desc"))
        model_row.addWidget(model_desc)
        model_row.addStretch()

        card_layout.addLayout(model_row)

        # Allow duplicate setting
        allow_row = QHBoxLayout()
        allow_row.setSpacing(SPACING_MEDIUM)

        allow_label = BodyLabel(t("result.allow_duplicate"))
        allow_label.setFixedWidth(100)
        allow_row.addWidget(allow_label)

        self._allow_duplicate_switch = SwitchButton()
        self._allow_duplicate_switch.setChecked(getattr(self._main.config, "allow_duplicate", False))
        self._allow_duplicate_switch.checkedChanged.connect(self._on_allow_duplicate_changed)
        allow_row.addWidget(self._allow_duplicate_switch)

        allow_desc = CaptionLabel(t("result.allow_duplicate_desc"))
        allow_row.addWidget(allow_desc)
        allow_row.addStretch()

        card_layout.addLayout(allow_row)

        return card

    def _on_duplicate_scope_changed(self) -> None:
        """Handle duplicate scope change."""
        scope = self._duplicate_scope_combo.currentData()
        if scope:
            self._main.config.duplicate_scope = scope

    def _on_check_model_changed(self, checked: bool) -> None:
        """Handle check model switch change."""
        self._main.config.duplicate_check_model = checked

    def _on_allow_duplicate_changed(self, checked: bool) -> None:
        """Handle allow duplicate switch change."""
        self._main.config.allow_duplicate = checked

    def _export_apkg(self) -> None:
        """导出所有卡片为 APKG。"""
        if not self._cards:
            InfoBar.info(
                title="提示",
                content="没有卡片需要导出",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )
            return

        # Show save dialog
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出为 APKG" if is_zh else "Export as APKG",
            "ankismart_cards.apkg",
            "Anki Package (*.apkg)",
        )

        if not path:
            return

        try:
            from ankismart.anki_gateway.apkg_exporter import ApkgExporter

            exporter = ApkgExporter()
            exporter.export(self._cards, path)

            InfoBar.success(
                title="成功" if is_zh else "Success",
                content=f"已导出 {len(self._cards)} 张卡片到 {path}" if is_zh else f"Exported {len(self._cards)} cards to {path}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        except Exception as e:
            logger.error(f"Failed to export APKG: {e}")
            InfoBar.error(
                title="导出失败" if is_zh else "Export Failed",
                content=str(e),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )

    def _create_stat_card(self, title: str, value: str, color: str) -> CardWidget:
        """创建统计卡片。"""
        card = CardWidget()
        card.setMinimumHeight(100)
        card.setBorderRadius(8)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(MARGIN_SMALL)
        card_layout.setContentsMargins(MARGIN_STANDARD, SPACING_MEDIUM, MARGIN_STANDARD, SPACING_MEDIUM)

        title_label = CaptionLabel(title)
        card_layout.addWidget(title_label)

        value_label = TitleLabel(value)
        value_label.setStyleSheet(f"color: {color};")
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
        self._btn_export_apkg.setEnabled(has_failed)

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

        # Checkbox for selection
        checkbox = CheckBox()
        checkbox.setProperty("card_index", status.index)
        checkbox.stateChanged.connect(lambda state, idx=status.index: self._on_row_checkbox_changed(idx, state))
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self._table.setCellWidget(row, 0, checkbox_widget)

        # Card title (from first field)
        card_title = "未知卡片"
        if 0 <= status.index < len(cards):
            card = cards[status.index]
            if card.fields:
                first_field = next(iter(card.fields.values()))
                card_title = first_field[:50] + "..." if len(first_field) > 50 else first_field

        title_item = QTableWidgetItem(card_title)
        self._table.setItem(row, 1, title_item)

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
        self._table.setItem(row, 2, status_item)

        # Error message
        error_item = QTableWidgetItem(status.error or "")
        self._table.setItem(row, 3, error_item)

        # Edit button
        edit_btn = ToolButton(FluentIcon.EDIT, self)
        edit_btn.setToolTip(t("card_edit.edit_button"))
        edit_btn.clicked.connect(lambda: self._edit_card(status.index))

        # Create a container widget for the button
        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.addWidget(edit_btn)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self._table.setCellWidget(row, 4, btn_widget)

    def _hex_to_qcolor(self, hex_color: str):
        """将十六进制颜色转换为 QColor。"""
        from PyQt6.QtGui import QColor

        return QColor(hex_color)

    def _clear_display(self) -> None:
        """清空显示。"""
        self._update_stat_card(self._card_total, "0")
        self._update_stat_card(self._card_success, "0")
        self._update_stat_card(self._card_failed, "0")
        self._update_stat_card(self._card_skipped, "0")
        self._table.setRowCount(0)
        self._btn_retry.setEnabled(False)
        self._btn_export_apkg.setEnabled(False)

    def _apply_duplicate_settings(self, cards: list[CardDraft]) -> None:
        """Apply duplicate check settings to cards."""
        config = self._main.config
        for card in cards:
            if card.options is None:
                from ankismart.core.models import CardOptions
                card.options = CardOptions()
            card.options.allow_duplicate = config.allow_duplicate
            card.options.duplicate_scope = config.duplicate_scope
            card.options.duplicate_scope_options.deck_name = card.deck_name
            card.options.duplicate_scope_options.check_children = False
            card.options.duplicate_scope_options.check_all_models = not config.duplicate_check_model

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

        # Apply duplicate check settings
        self._apply_duplicate_settings(failed_cards)

        # Disable buttons during push
        self._btn_retry.setEnabled(False)
        self._btn_export_apkg.setEnabled(False)

        # Start push worker
        config = self._main.config
        client = AnkiConnectClient(
            url=config.anki_connect_url,
            key=config.anki_connect_key,
            proxy_url=config.proxy_url,
        )
        gateway = AnkiGateway(client)
        worker = PushWorker(
            gateway=gateway,
            cards=failed_cards,
            update_mode=config.last_update_mode or "create_only",
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
        self._btn_export_apkg.setEnabled(True)

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
        self._btn_export_apkg.setEnabled(False)

        # Start export worker
        exporter = ApkgExporter()
        worker = ExportWorker(
            exporter=exporter,
            cards=failed_cards,
            output_path=Path(path),
        )
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
        self._btn_export_apkg.setEnabled(True)

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
        self._btn_export_apkg.setEnabled(True)

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

    def _edit_card(self, card_index: int) -> None:
        """Edit a card at the given index."""
        if not (0 <= card_index < len(self._cards)):
            return

        card = self._cards[card_index]
        lang = getattr(self._main.config, "language", "zh")

        # Show edit dialog
        dialog = CardEditDialog(card, lang, self.window())
        if dialog.exec():
            # Save edited card
            edited_card = dialog.get_edited_card()
            self._cards[card_index] = edited_card

            # Mark as edited
            self._edited_card_indices.add(card_index)

            # Update table display
            self._refresh_table_row(card_index)

            # Enable repush button if there are edited cards
            self._btn_repush_all.setEnabled(True)

            InfoBar.success(
                title=t("card_edit.save_success", lang),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )

    def _on_select_all_changed(self, state: int) -> None:
        """Handle select all checkbox state change."""
        is_checked = state == Qt.CheckState.Checked.value

        # Update all row checkboxes
        for row in range(self._table.rowCount()):
            checkbox_widget = self._table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(CheckBox)
                if checkbox:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(is_checked)
                    checkbox.blockSignals(False)

                    # Update selected indices
                    card_index = checkbox.property("card_index")
                    if is_checked:
                        self._selected_indices.add(card_index)
                    else:
                        self._selected_indices.discard(card_index)

        # Update batch button states
        self._update_batch_button_states()

    def _on_row_checkbox_changed(self, card_index: int, state: int) -> None:
        """Handle individual row checkbox state change."""
        is_checked = state == Qt.CheckState.Checked.value

        if is_checked:
            self._selected_indices.add(card_index)
        else:
            self._selected_indices.discard(card_index)

        # Update header checkbox state
        total_rows = self._table.rowCount()
        if len(self._selected_indices) == 0:
            self._header_checkbox.setCheckState(Qt.CheckState.Unchecked)
        elif len(self._selected_indices) == total_rows:
            self._header_checkbox.setCheckState(Qt.CheckState.Checked)
        else:
            self._header_checkbox.setCheckState(Qt.CheckState.PartiallyChecked)

        # Update batch button states
        self._update_batch_button_states()

    def _update_batch_button_states(self) -> None:
        """Update batch operation button enabled states."""
        has_selection = len(self._selected_indices) > 0
        self._btn_batch_edit_tags.setEnabled(has_selection)
        self._btn_batch_edit_deck.setEnabled(has_selection)

    def _batch_edit_tags(self) -> None:
        """Open batch edit tags dialog."""
        if not self._selected_indices:
            return

        lang = getattr(self._main.config, "language", "zh")
        dialog = BatchEditTagsDialog(len(self._selected_indices), lang, self.window())

        if dialog.exec():
            new_tags = dialog.get_tags()
            self._apply_batch_tags(new_tags)

    def _batch_edit_deck(self) -> None:
        """Open batch edit deck dialog."""
        if not self._selected_indices:
            return

        lang = getattr(self._main.config, "language", "zh")
        dialog = BatchEditDeckDialog(len(self._selected_indices), lang, self.window())

        if dialog.exec():
            new_deck = dialog.get_deck()
            self._apply_batch_deck(new_deck)

    def _apply_batch_tags(self, new_tags: str) -> None:
        """Apply new tags to selected cards."""
        tags_list = [tag.strip() for tag in new_tags.split(",") if tag.strip()]

        for card_index in self._selected_indices:
            if 0 <= card_index < len(self._cards):
                self._cards[card_index].tags = tags_list

        lang = getattr(self._main.config, "language", "zh")
        InfoBar.success(
            title=t("result.batch_edit_success", lang),
            content=t("result.batch_tags_updated", lang, count=len(self._selected_indices)),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )

    def _apply_batch_deck(self, new_deck: str) -> None:
        """Apply new deck to selected cards."""
        if not new_deck.strip():
            return

        for card_index in self._selected_indices:
            if 0 <= card_index < len(self._cards):
                self._cards[card_index].deck_name = new_deck.strip()

        lang = getattr(self._main.config, "language", "zh")
        InfoBar.success(
            title=t("result.batch_edit_success", lang),
            content=t("result.batch_deck_updated", lang, count=len(self._selected_indices)),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )

    def _refresh_table_row(self, card_index: int) -> None:
        """Refresh a specific table row after card edit."""
        if not self._push_result:
            return

        # Find the row corresponding to this card index
        for row_idx, status in enumerate(self._push_result.results):
            if status.index == card_index:
                # Update card title
                card = self._cards[card_index]
                if card.fields:
                    first_field = next(iter(card.fields.values()))
                    card_title = first_field[:50] + "..." if len(first_field) > 50 else first_field
                    title_item = self._table.item(row_idx, 1)
                    if title_item:
                        title_item.setText(card_title)
                break

    def _repush_all_cards(self) -> None:
        """Repush all cards to Anki."""
        if not self._cards:
            InfoBar.info(
                title="提示",
                content="没有卡片需要推送",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )
            return

        # Apply duplicate check settings to all cards
        self._apply_duplicate_settings(self._cards)

        # Disable buttons during push
        self._btn_repush_all.setEnabled(False)
        self._btn_retry.setEnabled(False)
        self._btn_export_apkg.setEnabled(False)

        # Start push worker
        config = self._main.config
        client = AnkiConnectClient(
            url=config.anki_connect_url,
            key=config.anki_connect_key,
            proxy_url=config.proxy_url,
        )
        gateway = AnkiGateway(client)
        worker = PushWorker(
            gateway=gateway,
            cards=self._cards,
            update_mode=config.last_update_mode or "create_or_update",
        )
        worker.finished.connect(self._on_repush_done)
        worker.error.connect(self._on_repush_error)
        worker.start()
        self._worker = worker

        InfoBar.info(
            title="推送中",
            content=f"正在推送 {len(self._cards)} 张卡片...",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self,
        )

    def _on_repush_done(self, result: PushResult) -> None:
        """Callback when repush is complete."""
        # Update status for repushed cards
        if self._push_result:
            repush_indices = sorted(self._edited_card_indices)
            for i, status in enumerate(result.results):
                if i < len(repush_indices):
                    card_idx = repush_indices[i]
                    # Find and update the status in original results
                    for j, orig_status in enumerate(self._push_result.results):
                        if orig_status.index == card_idx:
                            self._push_result.results[j] = CardPushStatus(
                                index=card_idx,
                                note_id=status.note_id,
                                success=status.success,
                                error=status.error,
                            )
                            break

            # Recalculate statistics
            self._push_result.succeeded = sum(1 for s in self._push_result.results if s.success)
            self._push_result.failed = sum(1 for s in self._push_result.results if not s.success and s.error)

            # Clear edited indices
            self._edited_card_indices.clear()

            # Refresh display
            self._display_result(self._push_result, self._cards)

        if result.succeeded > 0:
            InfoBar.success(
                title="推送成功",
                content=f"成功推送 {result.succeeded} 张已编辑卡片",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        else:
            InfoBar.error(
                title="推送失败",
                content="所有卡片推送失败",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )

    def _on_repush_error(self, msg: str) -> None:
        """Callback when repush encounters an error."""
        self._btn_repush_all.setEnabled(True)
        self._btn_retry.setEnabled(True)
        self._btn_export_apkg.setEnabled(True)

        InfoBar.error(
            title="推送错误",
            content=msg,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )

    def retranslate_ui(self):
        """Retranslate UI elements when language changes."""
        is_zh = getattr(self._main.config, "language", "zh") == "zh"

        # Update button text and tooltips
        export_text = "导出失败卡片" if is_zh else "Export Failed Cards"
        export_shortcut = get_shortcut_text(
            ShortcutKeys.EXPORT_CARDS,
            getattr(self._main.config, "language", "zh"),
        )
        self._btn_export_failed.setText(export_text)
        self._btn_export_failed.setToolTip(f"{export_text} ({export_shortcut})")

        self._btn_retry.setText("重试失败卡片" if is_zh else "Retry Failed Cards")
        self._btn_repush_all.setText("推送所有卡片" if is_zh else "Push All Cards")
        self._btn_back.setText("返回预览" if is_zh else "Back to Preview")

    def update_theme(self):
        """Update theme-dependent components when theme changes."""
        # ResultPage uses QFluentWidgets components that handle theme automatically
        # No custom styling that needs manual updates
        pass


class BatchEditTagsDialog(MessageBoxBase):
    """Batch edit tags dialog following QFluentWidgets official style."""

    def __init__(self, selected_count: int, lang: str = "zh", parent=None):
        super().__init__(parent)
        self._lang = lang

        self.titleLabel = SubtitleLabel(t("result.batch_edit_tags_title", lang), self)
        self.countLabel = CaptionLabel(t("result.selected_cards_count", lang, count=selected_count), self)

        self.tagsLineEdit = LineEdit(self)
        self.tagsLineEdit.setPlaceholderText(t("result.tags_placeholder", lang))
        self.tagsLineEdit.setClearButtonEnabled(True)

        self.hintLabel = CaptionLabel(t("result.tags_hint", lang))

        # Add widgets to view layout
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.countLabel)
        self.viewLayout.addSpacing(MARGIN_SMALL)
        self.viewLayout.addWidget(self.tagsLineEdit)
        self.viewLayout.addWidget(self.hintLabel)

        # Change button text
        self.yesButton.setText(t("common.apply", lang))
        self.cancelButton.setText(t("common.cancel", lang))

        self.widget.setMinimumWidth(400)

    def get_tags(self) -> str:
        """Get the entered tags."""
        return self.tagsLineEdit.text()


class BatchEditDeckDialog(MessageBoxBase):
    """Batch edit deck dialog following QFluentWidgets official style."""

    def __init__(self, selected_count: int, lang: str = "zh", parent=None):
        super().__init__(parent)
        self._lang = lang

        self.titleLabel = SubtitleLabel(t("result.batch_edit_deck_title", lang), self)
        self.countLabel = CaptionLabel(t("result.selected_cards_count", lang, count=selected_count), self)

        self.deckLineEdit = LineEdit(self)
        self.deckLineEdit.setPlaceholderText(t("result.deck_placeholder", lang))
        self.deckLineEdit.setClearButtonEnabled(True)

        self.hintLabel = CaptionLabel(t("result.deck_hint", lang))

        # Add widgets to view layout
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.countLabel)
        self.viewLayout.addSpacing(MARGIN_SMALL)
        self.viewLayout.addWidget(self.deckLineEdit)
        self.viewLayout.addWidget(self.hintLabel)

        # Change button text
        self.yesButton.setText(t("common.apply", lang))
        self.cancelButton.setText(t("common.cancel", lang))

        self.widget.setMinimumWidth(400)

    def validate(self):
        """Validate deck name is not empty."""
        is_valid = bool(self.deckLineEdit.text().strip())
        return is_valid

    def get_deck(self) -> str:
        """Get the entered deck name."""
        return self.deckLineEdit.text()
