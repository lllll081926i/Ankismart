from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
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
    FluentIcon,
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
)

from ankismart.core.models import CardDraft, CardPushStatus, PushResult
from ankismart.ui.card_edit_widget import CardEditDialog
from ankismart.ui.card_preview_renderer import format_quality_flags
from ankismart.ui.error_handler import build_error_display
from ankismart.ui.i18n import t
from ankismart.ui.styles import (
    MARGIN_SMALL,
    MARGIN_STANDARD,
    SPACING_MEDIUM,
    SPACING_SMALL,
    apply_compact_combo_metrics,
    apply_page_title_style,
)
from ankismart.ui.task_runtime import TaskEvent
from ankismart.ui.workers import ExportWorker, PushWorker

logger = logging.getLogger(__name__)
_REAL_APKG_EXPORTER_CLASS = None
AnkiConnectClient = None
AnkiGateway = None

_STRUCTURE_ERROR_TEXTS = {
    "basic_missing_front": ("缺少问题内容（Front）", "Missing question content (Front)"),
    "basic_missing_answer": ("缺少答案内容（Back）", "Missing answer content (Back)"),
    "choice_missing_question": ("缺少题干", "Missing question text"),
    "invalid_option_count": ("选项数量不合法", "Invalid option count"),
    "choice_missing_answer": ("缺少正确答案", "Missing correct answer"),
    "choice_answer_not_in_options": ("答案不在选项中", "Answer not found in options"),
    "insufficient_correct_options": (
        "多选题正确答案数量不足",
        "Not enough correct options for multiple choice",
    ),
    "unsupported_generic_structure": ("卡片结构暂不支持", "Unsupported card structure"),
    "cloze_syntax_invalid": ("填空语法无效", "Invalid cloze syntax"),
}


def _localized_text(mapping: dict[str, tuple[str, str]], key: str, lang: str) -> str:
    zh_text, en_text = mapping.get(key, (key, key))
    return zh_text if lang == "zh" else en_text
def _format_structure_error(error_key: str, lang: str) -> str:
    return _localized_text(_STRUCTURE_ERROR_TEXTS, str(error_key or "").strip(), lang)


def _format_status_message(message: str, lang: str) -> str:
    text = str(message or "").strip()
    if not text:
        return ""
    if text in _STRUCTURE_ERROR_TEXTS:
        return _format_structure_error(text, lang)
    return text


def _load_gateway_classes():
    client_class = globals().get("AnkiConnectClient")
    gateway_class = globals().get("AnkiGateway")
    if client_class is None or gateway_class is None:
        from ankismart.anki_gateway.client import AnkiConnectClient
        from ankismart.anki_gateway.gateway import AnkiGateway

        client_class = AnkiConnectClient
        gateway_class = AnkiGateway
        globals()["AnkiConnectClient"] = client_class
        globals()["AnkiGateway"] = gateway_class
    return client_class, gateway_class


def _load_apkg_exporter_class():
    exporter_class = globals().get("_REAL_APKG_EXPORTER_CLASS")
    if exporter_class is None:
        from ankismart.anki_gateway.apkg_exporter import ApkgExporter as _ApkgExporter

        exporter_class = _ApkgExporter
        globals()["_REAL_APKG_EXPORTER_CLASS"] = exporter_class
    return exporter_class


class ApkgExporter:
    """Lazy proxy that keeps monkeypatch targets stable for UI tests."""

    def __init__(self) -> None:
        self._exporter = None

    def _get_exporter(self):
        if self._exporter is None:
            self._exporter = _load_apkg_exporter_class()()
        return self._exporter

    def export(self, cards, output_path):
        return self._get_exporter().export(cards, output_path)


def _create_push_gateway(config) -> object:
    client_class, gateway_class = _load_gateway_classes()
    client = client_class(
        url=config.anki_connect_url,
        key=config.anki_connect_key,
        proxy_url=config.proxy_url,
    )
    return gateway_class(client)


def _create_apkg_exporter():
    return ApkgExporter()


class ResultPage(QWidget):
    """推送结果展示页面，显示卡片推送统计和详细结果列表。"""

    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("resultPage")
        self._main = main_window
        self._language = getattr(self._main.config, "language", "zh")
        self._worker = None
        self._export_worker = None
        self._export_button_states: dict[str, bool] | None = None
        self._push_result: PushResult | None = None
        self._cards: list[CardDraft] = []
        self._selected_indices: set[int] = set()  # Track selected card indices
        self._result_feedback_key: tuple[str, int, int, int] | None = None
        self._current_task_id: str = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_SMALL)
        layout.setContentsMargins(
            MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD
        )

        # Title
        self._title_label = TitleLabel(t("result.title"))
        apply_page_title_style(self._title_label)
        layout.addWidget(self._title_label)

        # Statistics cards row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(SPACING_MEDIUM)

        lang = getattr(self._main.config, "language", "zh")
        self._card_total = self._create_stat_card(t("result.total_cards", lang), "0", "#409EFF")
        self._card_success = self._create_stat_card(
            t("result.success_pushed", lang), "0", "#67C23A"
        )
        self._card_failed = self._create_stat_card(t("result.failed", lang), "0", "#F56C6C")
        self._card_skipped = self._create_stat_card(t("result.skipped", lang), "0", "#E6A23C")

        stats_row.addWidget(self._card_total)
        stats_row.addWidget(self._card_success)
        stats_row.addWidget(self._card_failed)
        stats_row.addWidget(self._card_skipped)

        layout.addLayout(stats_row)

        # Unified settings card (merged push and duplicate settings)
        settings_card = self._create_unified_settings_card()
        settings_card.setMaximumHeight(86)
        layout.addWidget(settings_card)

        # Results table
        self._table_label = SubtitleLabel(t("result.detail_results", lang))
        apply_page_title_style(self._table_label)
        layout.addWidget(self._table_label)

        self._table = TableWidget()
        self._table.setBorderVisible(True)
        self._table.setBorderRadius(8)
        self._table.setWordWrap(False)
        self._table.setColumnCount(5)
        self._table.setMinimumHeight(420)
        self._table.verticalHeader().setDefaultSectionSize(38)

        # Create header with checkbox
        self._header_checkbox = CheckBox()
        self._header_checkbox.stateChanged.connect(self._on_select_all_changed)

        self._table.setHorizontalHeaderLabels(
            [
                "",
                t("result.card_title", lang),
                t("result.status", lang),
                t("result.error_message", lang),
                "操作" if lang == "zh" else "Action",
            ]
        )
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setSortingEnabled(False)  # Disable sorting to keep checkbox alignment
        self._table.setEditTriggers(TableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(TableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self._table, 5)

        # Bottom operation row (dedicated line)
        bottom_actions = CardWidget()
        bottom_actions.setBorderRadius(8)
        all_buttons_row = QHBoxLayout(bottom_actions)
        all_buttons_row.setContentsMargins(
            MARGIN_STANDARD, MARGIN_SMALL, MARGIN_STANDARD, MARGIN_SMALL
        )
        all_buttons_row.setSpacing(MARGIN_SMALL)

        self._status_label = CaptionLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        all_buttons_row.addWidget(self._status_label, 1)
        all_buttons_row.addStretch()

        self._btn_batch_edit_tags = PrimaryPushButton(t("result.batch_edit_tags"))
        self._btn_batch_edit_tags.setMinimumHeight(34)
        self._btn_batch_edit_tags.clicked.connect(self._batch_edit_tags)
        self._btn_batch_edit_tags.setEnabled(False)
        all_buttons_row.addWidget(self._btn_batch_edit_tags)

        self._btn_batch_edit_deck = PushButton(t("result.batch_edit_deck"))
        self._btn_batch_edit_deck.setMinimumHeight(34)
        self._btn_batch_edit_deck.clicked.connect(self._batch_edit_deck)
        self._btn_batch_edit_deck.setEnabled(False)
        all_buttons_row.addWidget(self._btn_batch_edit_deck)

        self._btn_export_selected = PushButton("导出所选" if lang == "zh" else "Export Selected")
        self._btn_export_selected.setMinimumHeight(34)
        self._btn_export_selected.clicked.connect(self._export_selected_apkg)
        self._btn_export_selected.setEnabled(False)
        all_buttons_row.addWidget(self._btn_export_selected)

        self._btn_retry = PushButton(t("result.retry_failed", lang))
        self._btn_retry.setMinimumHeight(34)
        self._btn_retry.clicked.connect(self._retry_failed)
        self._btn_retry.setEnabled(False)
        all_buttons_row.addWidget(self._btn_retry)

        self._btn_repush_all = PushButton("推送所有卡片" if lang == "zh" else "Push All Cards")
        self._btn_repush_all.setMinimumHeight(34)
        self._btn_repush_all.clicked.connect(self._repush_all_cards)
        self._btn_repush_all.setEnabled(False)
        all_buttons_row.addWidget(self._btn_repush_all)

        self._btn_export_apkg = PushButton("导出为 APKG" if lang == "zh" else "Export as APKG")
        self._btn_export_apkg.setMinimumHeight(34)
        self._btn_export_apkg.clicked.connect(self._export_apkg)
        self._btn_export_apkg.setEnabled(False)
        all_buttons_row.addWidget(self._btn_export_apkg)

        layout.addWidget(bottom_actions)

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
        self._update_combo.setMinimumWidth(170)
        self._update_combo.setFixedHeight(30)
        apply_compact_combo_metrics(self._update_combo)

        default_mode = getattr(self._main.config, "last_update_mode", None) or "create_or_update"
        for idx in range(self._update_combo.count()):
            if self._update_combo.itemData(idx) == default_mode:
                self._update_combo.setCurrentIndex(idx)
                break
        self._update_combo.currentIndexChanged.connect(self._on_update_mode_changed)
        update_row.addWidget(update_label, 0, Qt.AlignmentFlag.AlignVCenter)
        update_row.addWidget(self._update_combo, 0, Qt.AlignmentFlag.AlignVCenter)
        update_row.addStretch(1)

        # Duplicate scope
        scope_row = QHBoxLayout()
        scope_row.setSpacing(SPACING_SMALL)
        scope_label = BodyLabel(t("result.duplicate_scope"))
        self._duplicate_scope_combo = ComboBox()
        self._duplicate_scope_combo.addItem(t("result.duplicate_scope_deck"), userData="deck")
        self._duplicate_scope_combo.addItem(
            t("result.duplicate_scope_collection"), userData="collection"
        )
        self._duplicate_scope_combo.setMinimumWidth(170)
        self._duplicate_scope_combo.setFixedHeight(30)
        apply_compact_combo_metrics(self._duplicate_scope_combo)
        duplicate_scope = getattr(self._main.config, "duplicate_scope", "deck")
        self._duplicate_scope_combo.setCurrentIndex(0 if duplicate_scope == "deck" else 1)
        self._duplicate_scope_combo.currentIndexChanged.connect(self._on_duplicate_scope_changed)
        scope_row.addWidget(scope_label, 0, Qt.AlignmentFlag.AlignVCenter)
        scope_row.addWidget(self._duplicate_scope_combo, 0, Qt.AlignmentFlag.AlignVCenter)
        scope_row.addStretch(1)

        # Check model switch
        model_row = QHBoxLayout()
        model_row.setSpacing(SPACING_SMALL)
        model_label = BodyLabel(t("result.duplicate_check_model"))
        self._check_model_switch = SwitchButton()
        self._check_model_switch.setChecked(
            getattr(self._main.config, "duplicate_check_model", True)
        )
        self._check_model_switch.checkedChanged.connect(self._on_check_model_changed)
        model_row.addWidget(model_label)
        model_row.addStretch(1)
        model_row.addWidget(self._check_model_switch)

        # Allow duplicate switch
        allow_row = QHBoxLayout()
        allow_row.setSpacing(SPACING_SMALL)
        allow_label = BodyLabel(t("result.allow_duplicate"))
        self._allow_duplicate_switch = SwitchButton()
        self._allow_duplicate_switch.setChecked(
            getattr(self._main.config, "allow_duplicate", False)
        )
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
        card_layout.setContentsMargins(
            MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD
        )

        # Title
        title_label = SubtitleLabel(t("result.duplicate_check_settings"))
        card_layout.addWidget(title_label)

        # Duplicate scope setting
        scope_row = QHBoxLayout()
        scope_row.setSpacing(SPACING_MEDIUM)

        scope_label = BodyLabel(t("result.duplicate_scope"))
        scope_label.setMinimumWidth(100)
        scope_row.addWidget(scope_label)

        self._duplicate_scope_combo = ComboBox()
        self._duplicate_scope_combo.addItem(t("result.duplicate_scope_deck"), userData="deck")
        self._duplicate_scope_combo.addItem(
            t("result.duplicate_scope_collection"), userData="collection"
        )
        duplicate_scope = getattr(self._main.config, "duplicate_scope", "deck")
        self._duplicate_scope_combo.setCurrentIndex(0 if duplicate_scope == "deck" else 1)
        self._duplicate_scope_combo.currentIndexChanged.connect(self._on_duplicate_scope_changed)
        self._duplicate_scope_combo.setMinimumWidth(150)
        apply_compact_combo_metrics(self._duplicate_scope_combo)
        scope_row.addWidget(self._duplicate_scope_combo)

        scope_desc = CaptionLabel(t("result.duplicate_scope_desc"))
        scope_row.addWidget(scope_desc)
        scope_row.addStretch()

        card_layout.addLayout(scope_row)

        # Check model setting
        model_row = QHBoxLayout()
        model_row.setSpacing(SPACING_MEDIUM)

        model_label = BodyLabel(t("result.duplicate_check_model"))
        model_label.setMinimumWidth(100)
        model_row.addWidget(model_label)

        self._check_model_switch = SwitchButton()
        self._check_model_switch.setChecked(
            getattr(self._main.config, "duplicate_check_model", True)
        )
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
        allow_label.setMinimumWidth(100)
        allow_row.addWidget(allow_label)

        self._allow_duplicate_switch = SwitchButton()
        self._allow_duplicate_switch.setChecked(
            getattr(self._main.config, "allow_duplicate", False)
        )
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

    def _show_info_bar(
        self,
        level: str,
        title: str,
        content: str,
        *,
        duration: int = 3000,
        is_closable: bool = True,
    ) -> None:
        """Show fluent InfoBar notifications consistently."""
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
            isClosable=is_closable,
            position=InfoBarPosition.TOP,
            duration=duration,
            parent=self,
        )

    def _export_apkg(self) -> None:
        """导出所有卡片为 APKG。"""
        if not self._cards:
            self._show_info_bar("info", "提示", "没有卡片需要导出", duration=2000)
            return
        if self._export_worker and self._export_worker.isRunning():
            wait_title = (
                "请稍候" if getattr(self._main.config, "language", "zh") == "zh" else "Please Wait"
            )
            self._show_info_bar(
                "info",
                wait_title,
                "已有导出任务进行中"
                if getattr(self._main.config, "language", "zh") == "zh"
                else "Another export task is already running.",
                duration=2000,
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

        self._current_task_id = str(
            getattr(self._main, "active_task_id", "") or self._current_task_id
        )
        self._publish_task_event(
            TaskEvent(
                task_id=self._current_task_id,
                stage="export",
                kind="started",
                message="export started",
            )
        )
        worker = ExportWorker(_create_apkg_exporter(), self._cards, Path(path))
        self._export_worker = worker
        self._export_button_states = {
            "retry": self._btn_retry.isEnabled(),
            "repush_all": self._btn_repush_all.isEnabled(),
            "export": self._btn_export_apkg.isEnabled(),
        }
        self._btn_export_apkg.setEnabled(False)
        self._btn_retry.setEnabled(False)
        self._btn_repush_all.setEnabled(False)
        self._set_status_label(
            f"正在导出 {len(self._cards)} 张卡片到 APKG"
            if is_zh
            else f"Exporting {len(self._cards)} cards to APKG"
        )
        worker.progress.connect(self._on_export_progress)
        worker.finished.connect(self._on_export_done)
        worker.error.connect(self._on_export_error)
        worker.cancelled.connect(self._on_export_cancelled)
        worker.start()

    def _export_selected_apkg(self) -> None:
        """导出选中的卡片为 APKG。"""
        is_zh = getattr(self._main.config, "language", "zh") == "zh"

        if not self._selected_indices:
            self._show_info_bar(
                "info",
                "提示" if is_zh else "Info",
                "请先选择要导出的卡片" if is_zh else "Please select cards to export",
                duration=2000,
            )
            return

        selected_cards = [
            self._cards[i] for i in self._selected_indices if 0 <= i < len(self._cards)
        ]
        if not selected_cards:
            return

        if self._export_worker and self._export_worker.isRunning():
            self._show_info_bar(
                "info",
                "请稍候" if is_zh else "Please Wait",
                "已有导出任务进行中" if is_zh else "Another export task is already running.",
                duration=2000,
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出所选为 APKG" if is_zh else "Export Selected as APKG",
            "ankismart_selected.apkg",
            "Anki Package (*.apkg)",
        )
        if not path:
            return

        self._current_task_id = str(
            getattr(self._main, "active_task_id", "") or self._current_task_id
        )
        self._publish_task_event(
            TaskEvent(
                task_id=self._current_task_id,
                stage="export",
                kind="started",
                message="export selected started",
            )
        )
        worker = ExportWorker(_create_apkg_exporter(), selected_cards, Path(path))
        self._export_worker = worker
        self._export_button_states = {
            "retry": self._btn_retry.isEnabled(),
            "repush_all": self._btn_repush_all.isEnabled(),
            "export": self._btn_export_apkg.isEnabled(),
        }
        self._btn_export_apkg.setEnabled(False)
        self._btn_export_selected.setEnabled(False)
        self._btn_retry.setEnabled(False)
        self._btn_repush_all.setEnabled(False)
        self._set_status_label(
            f"正在导出 {len(selected_cards)} 张所选卡片到 APKG"
            if is_zh
            else f"Exporting {len(selected_cards)} selected cards to APKG"
        )
        worker.progress.connect(self._on_export_progress)
        worker.finished.connect(self._on_export_done)
        worker.error.connect(self._on_export_error)
        worker.cancelled.connect(self._on_export_cancelled)
        worker.start()

    def _create_stat_card(self, title: str, value: str, color: str) -> CardWidget:
        """创建统计卡片。"""
        card = CardWidget()
        card.setMinimumHeight(78)
        card.setBorderRadius(8)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(4)
        card_layout.setContentsMargins(MARGIN_STANDARD, 8, MARGIN_STANDARD, 8)

        title_label = CaptionLabel(title)
        title_label.setObjectName("stat_title")
        card_layout.addWidget(title_label)

        value_label = TitleLabel(value)
        value_label.setStyleSheet(f"color: {color};")
        value_label.setObjectName("stat_value")
        card_layout.addWidget(value_label)

        card_layout.addStretch()

        return card

    def _update_stat_card(self, card: CardWidget, value: str) -> None:
        """更新统计卡片的值。"""
        value_label = card.findChild(TitleLabel, "stat_value")
        if value_label:
            value_label.setText(value)

    def _set_stat_card_title(self, card: CardWidget, title: str) -> None:
        """更新统计卡片的标题。"""
        title_label = card.findChild(CaptionLabel, "stat_title")
        if title_label:
            title_label.setText(title)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        """页面显示时刷新数据。"""
        super().showEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        """刷新页面数据。"""
        if self._push_result:
            self._display_result(self._push_result, self._cards, show_feedback=False)
        else:
            self._clear_display()

    def load_result(self, result: PushResult, cards: list[CardDraft]) -> None:
        """加载推送结果数据。"""
        self._push_result = result
        self._cards = cards
        self._display_result(result, cards, show_feedback=True)

    def _display_result(
        self,
        result: PushResult,
        cards: list[CardDraft],
        *,
        show_feedback: bool = False,
    ) -> None:
        """显示推送结果。"""
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
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
        self._btn_export_apkg.setEnabled(bool(cards))

        # Show top feedback only on fresh result load.
        feedback_key = (result.trace_id or "", result.total, result.succeeded, result.failed)
        should_show_feedback = show_feedback and self._result_feedback_key != feedback_key
        if should_show_feedback and result.succeeded == result.total:
            self._show_info_bar(
                "success",
                "推送成功" if is_zh else "Push Success",
                f"成功推送 {result.succeeded} 张卡片"
                if is_zh
                else f"Successfully pushed {result.succeeded} cards",
                duration=3000,
            )
            self._result_feedback_key = feedback_key
        elif should_show_feedback and result.failed > 0:
            self._show_info_bar(
                "warning",
                "部分失败" if is_zh else "Partial Failure",
                f"成功 {result.succeeded} 张，失败 {result.failed} 张"
                if is_zh
                else f"Success {result.succeeded}, Failed {result.failed}",
                duration=5000,
            )
            self._result_feedback_key = feedback_key

    def _add_table_row(self, status: CardPushStatus, cards: list[CardDraft]) -> None:
        """添加表格行。"""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Checkbox for selection
        checkbox = CheckBox()
        checkbox.setProperty("card_index", status.index)
        checkbox.stateChanged.connect(
            lambda state, idx=status.index: self._on_row_checkbox_changed(idx, state)
        )
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self._table.setCellWidget(row, 0, checkbox_widget)

        # Card title (from first field)
        lang = getattr(self._main.config, "language", "zh")
        card_title = t("result.unknown_card", lang)
        quality_text = ""
        if 0 <= status.index < len(cards):
            card = cards[status.index]
            card_title = self._extract_question_title(card, lang=lang)
            quality_text = format_quality_flags(
                list(getattr(card.metadata, "quality_flags", []) or []),
                lang,
            )

        title_item = QTableWidgetItem(card_title)
        self._table.setItem(row, 1, title_item)

        # Status with color
        if status.success and quality_text:
            status_text = "需关注" if lang == "zh" else "Needs Review"
            status_color = "#E6A23C"
        elif status.success:
            status_text = t("result.status_success", lang)
            status_color = "#67C23A"
        elif status.error:
            status_text = t("result.status_failed", lang)
            status_color = "#F56C6C"
        else:
            status_text = t("result.status_skipped", lang)
            status_color = "#E6A23C"

        status_item = QTableWidgetItem(status_text)
        status_item.setForeground(Qt.GlobalColor.white)
        status_item.setBackground(self._hex_to_qcolor(status_color))
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 2, status_item)

        # Error message
        error_text = _format_status_message(status.error or "", lang) or quality_text
        error_item = QTableWidgetItem(error_text)
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

    @staticmethod
    def _extract_question_title(card: CardDraft, *, lang: str) -> str:
        """Extract display title from question field only."""

        def _compact(value: str) -> str:
            plain = " ".join(value.replace("\r", " ").replace("\n", " ").split())
            return plain if len(plain) <= 56 else f"{plain[:55]}…"

        for key in ("Front", "Text", "Question"):
            value = card.fields.get(key, "")
            if value and value.strip():
                return _compact(value)
        return t("result.unknown_card", lang)

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
        self._result_feedback_key = None
        if self._worker is None and self._export_worker is None:
            self._set_status_label("")

    def _set_status_label(self, text: str) -> None:
        message = str(text or "").strip()
        self._status_label.setText(message)
        self._status_label.setVisible(bool(message))

    def _restore_export_buttons(self) -> None:
        if self._export_button_states is not None:
            self._btn_retry.setEnabled(self._export_button_states.get("retry", False))
            self._btn_repush_all.setEnabled(self._export_button_states.get("repush_all", False))
            self._btn_export_apkg.setEnabled(
                self._export_button_states.get("export", bool(self._cards))
            )
            self._export_button_states = None
            return

        self._btn_retry.setEnabled(bool(self._push_result and self._push_result.failed > 0))
        self._btn_repush_all.setEnabled(self._btn_repush_all.isEnabled())
        self._btn_export_apkg.setEnabled(bool(self._cards))

    def _on_push_progress(self, message: str) -> None:
        self._set_status_label(message)

    def _on_push_card_progress(self, current: int, total: int) -> None:
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
        self._set_status_label(
            f"已完成 {current}/{total} 张卡片推送" if is_zh else f"Pushed {current}/{total} cards"
        )

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
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
        if not self._push_result or not self._cards:
            return
        if self._worker and self._worker.isRunning():
            self._show_info_bar(
                "info",
                "请稍候" if is_zh else "Please Wait",
                "已有推送任务进行中" if is_zh else "Another push task is already running.",
                duration=2000,
            )
            return

        # Collect failed cards
        failed_cards = []
        for status in self._push_result.results:
            if not status.success and 0 <= status.index < len(self._cards):
                failed_cards.append(self._cards[status.index])

        if not failed_cards:
            self._show_info_bar(
                "info",
                "提示" if is_zh else "Info",
                "没有失败的卡片需要重试" if is_zh else "No failed cards to retry",
                duration=2000,
            )
            return

        # Apply duplicate check settings
        self._apply_duplicate_settings(failed_cards)

        # Disable buttons during push
        self._btn_retry.setEnabled(False)
        self._btn_export_apkg.setEnabled(False)

        # Start push worker
        config = self._main.config
        gateway = _create_push_gateway(config)
        worker = PushWorker(
            gateway=gateway,
            cards=failed_cards,
            update_mode=config.last_update_mode or "create_or_update",
        )
        self._worker = worker
        worker.progress.connect(self._on_push_progress)
        worker.card_progress.connect(self._on_push_card_progress)
        worker.finished.connect(self._on_retry_done)
        worker.error.connect(self._on_retry_error)
        self._set_status_label(
            f"正在重试 {len(failed_cards)} 张失败卡片"
            if is_zh
            else f"Retrying {len(failed_cards)} failed cards"
        )
        worker.start()

        self._show_info_bar(
            "info",
            "重试中" if is_zh else "Retrying",
            f"正在重试 {len(failed_cards)} 张失败卡片..."
            if is_zh
            else f"Retrying {len(failed_cards)} failed cards...",
            duration=2000,
        )

    def _on_retry_done(self, result: PushResult) -> None:
        """重试完成回调。"""
        self._cleanup_push_worker()
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
        self._set_status_label(
            f"重试完成：成功 {result.succeeded} 张，失败 {result.failed} 张"
            if is_zh
            else f"Retry finished: {result.succeeded} succeeded, {result.failed} failed"
        )
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
            self._show_info_bar(
                "success",
                "重试成功" if is_zh else "Retry Succeeded",
                f"成功推送 {result.succeeded} 张卡片"
                if is_zh
                else f"Successfully pushed {result.succeeded} cards",
            )
        else:
            self._show_info_bar(
                "error",
                "重试失败" if is_zh else "Retry Failed",
                "所有卡片重试失败" if is_zh else "All retries failed",
            )

    def _on_retry_error(self, msg: str) -> None:
        """重试错误回调。"""
        self._cleanup_push_worker()
        error_display = build_error_display(msg, getattr(self._main.config, "language", "zh"))
        self._btn_retry.setEnabled(True)
        self._btn_export_apkg.setEnabled(True)
        self._set_status_label(error_display["content"])

        self._show_info_bar(
            "error",
            error_display["title"],
            error_display["content"],
            duration=5000,
        )

    def _on_export_progress(self, message: str) -> None:
        self._set_status_label(message)
        self._publish_task_event(
            TaskEvent(
                task_id=self._current_task_id,
                stage="export",
                kind="progress",
                message=message,
            )
        )

    def _on_export_done(self, path: str) -> None:
        """导出完成回调。"""
        self._cleanup_export_worker()
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
        self._restore_export_buttons()
        self._set_status_label(f"导出完成：{path}" if is_zh else f"Export completed: {path}")

        self._show_info_bar(
            "success",
            "导出成功" if is_zh else "Export Succeeded",
            f"已导出到 {path}" if is_zh else f"Exported to {path}",
        )
        self._publish_task_event(
            TaskEvent(
                task_id=self._current_task_id,
                stage="export",
                kind="completed",
                progress=100,
                message=path,
            )
        )

    def _on_export_error(self, msg: str) -> None:
        """导出错误回调。"""
        self._cleanup_export_worker()
        lang = getattr(self._main.config, "language", "zh")
        friendly_message = _format_status_message(msg, lang)
        if friendly_message != str(msg or "").strip():
            error_display = {
                "title": "导出失败" if lang == "zh" else "Export Failed",
                "content": friendly_message,
            }
        else:
            error_display = build_error_display(msg, lang)
        self._restore_export_buttons()
        self._set_status_label(error_display["content"])

        self._show_info_bar(
            "error",
            error_display["title"],
            error_display["content"],
            duration=5000,
        )
        self._publish_task_event(
            TaskEvent(
                task_id=self._current_task_id,
                stage="export",
                kind="failed",
                message=error_display["content"],
            )
        )

    def _on_export_cancelled(self) -> None:
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
        self._cleanup_export_worker()
        self._restore_export_buttons()
        self._set_status_label("导出已取消" if is_zh else "Export cancelled")
        self._publish_task_event(
            TaskEvent(
                task_id=self._current_task_id,
                stage="export",
                kind="cancelled",
                message="export cancelled",
            )
        )

    def _publish_task_event(self, event: TaskEvent) -> None:
        if not event.task_id:
            return
        publish = getattr(self._main, "publish_task_event", None)
        if callable(publish):
            publish(event)

    def _back_to_preview(self) -> None:
        """返回预览页面。"""
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
        reply = QMessageBox.question(
            self,
            "确认返回" if is_zh else "Confirm Back",
            "返回预览页面将丢失当前结果，是否继续？"
            if is_zh
            else "Going back to preview will lose current results. Continue?",
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
            quality_text = format_quality_flags(
                list(getattr(edited_card.metadata, "quality_flags", []) or []),
                lang,
            )
            if quality_text:
                self._show_info_bar(
                    "warning",
                    t("card_edit.save_success", lang),
                    quality_text,
                    duration=2500,
                )
            else:
                self._show_info_bar("success", t("card_edit.save_success", lang), "", duration=2000)

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
        self._btn_export_selected.setEnabled(has_selection)

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
        self._show_info_bar(
            "success",
            t("result.batch_edit_success", lang),
            t("result.batch_tags_updated", lang, count=len(self._selected_indices)),
            duration=2000,
        )

    def _apply_batch_deck(self, new_deck: str) -> None:
        """Apply new deck to selected cards."""
        if not new_deck.strip():
            return

        for card_index in self._selected_indices:
            if 0 <= card_index < len(self._cards):
                self._cards[card_index].deck_name = new_deck.strip()

        lang = getattr(self._main.config, "language", "zh")
        self._show_info_bar(
            "success",
            t("result.batch_edit_success", lang),
            t("result.batch_deck_updated", lang, count=len(self._selected_indices)),
            duration=2000,
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
                card_title = self._extract_question_title(
                    card,
                    lang=getattr(self._main.config, "language", "zh"),
                )
                title_item = self._table.item(row_idx, 1)
                if title_item:
                    title_item.setText(card_title)
                break

    def _repush_all_cards(self) -> None:
        """Repush all cards to Anki."""
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
        if not self._cards:
            self._show_info_bar(
                "info",
                "提示" if is_zh else "Info",
                "没有卡片需要推送" if is_zh else "No cards to push",
                duration=2000,
            )
            return
        if self._worker and self._worker.isRunning():
            self._show_info_bar(
                "info",
                "请稍候" if is_zh else "Please Wait",
                "已有推送任务进行中" if is_zh else "Another push task is already running.",
                duration=2000,
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
        gateway = _create_push_gateway(config)
        worker = PushWorker(
            gateway=gateway,
            cards=self._cards,
            update_mode=config.last_update_mode or "create_or_update",
        )
        self._worker = worker
        worker.progress.connect(self._on_push_progress)
        worker.card_progress.connect(self._on_push_card_progress)
        worker.finished.connect(self._on_repush_done)
        worker.error.connect(self._on_repush_error)
        self._set_status_label(
            f"正在推送 {len(self._cards)} 张卡片" if is_zh else f"Pushing {len(self._cards)} cards"
        )
        worker.start()

        self._show_info_bar(
            "info",
            "推送中" if is_zh else "Pushing",
            f"正在推送 {len(self._cards)} 张卡片..."
            if is_zh
            else f"Pushing {len(self._cards)} cards...",
            duration=2000,
        )

    def _on_repush_done(self, result: PushResult) -> None:
        """Callback when repush is complete."""
        self._cleanup_push_worker()
        is_zh = getattr(self._main.config, "language", "zh") == "zh"
        self._set_status_label(
            f"推送完成：成功 {result.succeeded} 张，失败 {result.failed} 张"
            if is_zh
            else f"Push finished: {result.succeeded} succeeded, {result.failed} failed"
        )
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
            self._push_result.failed = sum(
                1 for s in self._push_result.results if not s.success and s.error
            )

            # Clear edited indices
            self._edited_card_indices.clear()

            # Refresh display
            self._display_result(self._push_result, self._cards)

        if result.succeeded > 0:
            self._show_info_bar(
                "success",
                "推送成功" if is_zh else "Push Success",
                f"成功推送 {result.succeeded} 张已编辑卡片"
                if is_zh
                else f"Successfully pushed {result.succeeded} edited cards",
            )
        else:
            self._show_info_bar(
                "error",
                "推送失败" if is_zh else "Push Failed",
                "所有卡片推送失败" if is_zh else "All cards failed to push",
            )

    def _on_repush_error(self, msg: str) -> None:
        """Callback when repush encounters an error."""
        self._cleanup_push_worker()
        lang = getattr(self._main.config, "language", "zh")
        friendly_message = _format_status_message(msg, lang)
        if friendly_message != str(msg or "").strip():
            error_display = {
                "title": "推送失败" if lang == "zh" else "Push Failed",
                "content": friendly_message,
            }
        else:
            error_display = build_error_display(msg, lang)
        self._btn_repush_all.setEnabled(True)
        self._btn_retry.setEnabled(True)
        self._btn_export_apkg.setEnabled(True)
        self._set_status_label(error_display["content"])

        self._show_info_bar(
            "error",
            error_display["title"],
            error_display["content"],
            duration=5000,
        )

    def retranslate_ui(self):
        """Retranslate UI elements when language changes."""
        lang = getattr(self._main.config, "language", "zh")
        is_zh = lang == "zh"

        self._title_label.setText(t("result.title", lang))
        self._table_label.setText(t("result.detail_results", lang))
        self._table.setHorizontalHeaderLabels(
            [
                "",
                t("result.card_title", lang),
                t("result.status", lang),
                t("result.error_message", lang),
                "操作" if is_zh else "Action",
            ]
        )

        self._set_stat_card_title(self._card_total, t("result.total_cards", lang))
        self._set_stat_card_title(self._card_success, t("result.success_pushed", lang))
        self._set_stat_card_title(self._card_failed, t("result.failed", lang))
        self._set_stat_card_title(self._card_skipped, t("result.skipped", lang))

        self._btn_batch_edit_tags.setText(t("result.batch_edit_tags", lang))
        self._btn_batch_edit_deck.setText(t("result.batch_edit_deck", lang))
        self._btn_retry.setText(t("result.retry_failed", lang))
        self._btn_repush_all.setText("推送所有卡片" if is_zh else "Push All Cards")
        self._btn_export_apkg.setText("导出为 APKG" if is_zh else "Export as APKG")

        self._update_combo.setItemText(0, t("result.create_only", lang))
        self._update_combo.setItemText(1, t("result.update_only", lang))
        self._update_combo.setItemText(2, t("result.create_or_update", lang))

        self._duplicate_scope_combo.setItemText(0, t("result.duplicate_scope_deck", lang))
        self._duplicate_scope_combo.setItemText(1, t("result.duplicate_scope_collection", lang))

        # Refresh row content (status/error/action texts) with the active language.
        if self._push_result:
            self._display_result(self._push_result, self._cards, show_feedback=False)

    def _cleanup_push_worker(self) -> None:
        worker = self.__dict__.get("_worker")
        if worker is None:
            return
        if hasattr(worker, "isRunning") and worker.isRunning():
            if hasattr(worker, "cancel"):
                worker.cancel()
            worker.wait(200)
            if worker.isRunning():
                return
        self.__dict__["_worker"] = None
        if hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def _cleanup_export_worker(self) -> None:
        worker = self.__dict__.get("_export_worker")
        if worker is None:
            return
        if hasattr(worker, "isRunning") and worker.isRunning():
            if hasattr(worker, "cancel"):
                worker.cancel()
            worker.wait(200)
            if worker.isRunning():
                return
        self.__dict__["_export_worker"] = None
        if hasattr(worker, "deleteLater"):
            worker.deleteLater()

    def closeEvent(self, event):  # noqa: N802
        """Request cooperative worker cancellation during application shutdown."""
        self._cleanup_push_worker()
        self._cleanup_export_worker()
        if self._worker and self._worker.isRunning():
            logger.warning(
                "Push worker is still running during close event; "
                "skip force terminate to avoid inconsistent shutdown state"
            )
        super().closeEvent(event)

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
        self.countLabel = CaptionLabel(
            t("result.selected_cards_count", lang, count=selected_count), self
        )

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
        self.countLabel = CaptionLabel(
            t("result.selected_cards_count", lang, count=selected_count), self
        )

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
