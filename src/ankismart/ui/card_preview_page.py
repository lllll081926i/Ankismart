"""Card preview page for viewing generated Anki cards."""

from __future__ import annotations

import csv
import json
import re
import time
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    TitleLabel,
    isDarkTheme,
)

from ankismart.core.config import append_task_history, record_operation_metric, save_config
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft, RegenerateRequest
from ankismart.ui.card_preview_renderer import CARD_KIND_LABELS, CardRenderer, format_quality_flags
from ankismart.ui.error_handler import build_error_display
from ankismart.ui.styles import (
    MARGIN_SMALL,
    MARGIN_STANDARD,
    SPACING_LARGE,
    SPACING_MEDIUM,
    SPACING_SMALL,
    apply_compact_combo_metrics,
    apply_page_title_style,
    get_list_widget_palette,
)

if TYPE_CHECKING:
    from ankismart.ui.main_window import MainWindow

logger = get_logger(__name__)


class CardPreviewPage(QWidget):
    """Page for previewing generated Anki cards."""

    _NOTE_TYPE_FILTERS: tuple[tuple[str, str, str], ...] = (
        ("all", "全部类型", "All Types"),
        ("basic", "基础问答", "Basic Q&A"),
        ("basic_reversed", "双向卡片", "Reversed"),
        ("cloze", "填空题", "Cloze"),
        ("concept", "概念解释", "Concept"),
        ("key_terms", "关键术语", "Key Terms"),
        ("single_choice", "单选题", "Single Choice"),
        ("multiple_choice", "多选题", "Multiple Choice"),
        ("image_qa", "图片问答", "Image Q&A"),
        ("generic", "其他", "Other"),
    )

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.setObjectName("cardPreviewPage")  # Required by QFluentWidgets
        self._main = main_window
        self._all_cards: list[CardDraft] = []
        self._filtered_cards: list[CardDraft] = []
        self._current_index = -1
        self._quality_low_only = False
        self._duplicate_risk_only = False
        self._duplicate_risk_card_ids: set[int] = set()
        self._push_worker = None
        self._export_worker = None
        self._push_start_ts = 0.0
        self._export_start_ts = 0.0

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_SMALL)
        layout.setContentsMargins(MARGIN_STANDARD, MARGIN_SMALL, MARGIN_STANDARD, MARGIN_SMALL)

        # Top bar
        top_bar = self._create_top_bar()
        layout.addLayout(top_bar)

        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(SPACING_LARGE)

        # Left panel: Card list (30% width)
        left_panel = self._create_left_panel()
        content_layout.addWidget(left_panel, 3)

        # Right panel: Card preview (70% width)
        right_panel = self._create_right_panel()
        content_layout.addWidget(right_panel, 7)

        layout.addLayout(content_layout, 1)

        # Bottom bar
        bottom_bar = self._create_bottom_bar()
        layout.addLayout(bottom_bar)

        # Progress bar
        self._progress_bar = ProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(0)  # Indeterminate progress
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        self._apply_theme_styles()
        self._set_total_count_text(0)
        self._set_card_meta_labels(None)

    def _create_top_bar(self) -> QHBoxLayout:
        """Create top bar with title and filters."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_SMALL)

        # Title
        self._title_label = TitleLabel(
            "卡片预览" if self._main.config.language == "zh" else "Card Preview"
        )
        apply_page_title_style(self._title_label)
        layout.addWidget(self._title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addStretch()

        # Filter by note type
        self._filter_label = BodyLabel("筛选:" if self._main.config.language == "zh" else "Filter:")
        layout.addWidget(self._filter_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._note_type_combo = ComboBox()
        for key, zh_text, en_text in self._NOTE_TYPE_FILTERS:
            self._note_type_combo.addItem(
                zh_text if self._main.config.language == "zh" else en_text, userData=key
            )
        apply_compact_combo_metrics(self._note_type_combo)
        self._note_type_combo.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self._note_type_combo, 0, Qt.AlignmentFlag.AlignVCenter)

        # Search box
        self._search_input = LineEdit()
        self._search_input.setPlaceholderText(
            "搜索卡片内容..." if self._main.config.language == "zh" else "Search card content..."
        )
        self._search_input.setFixedHeight(self._note_type_combo.height())
        self._search_input.setMinimumWidth(200)
        self._search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._search_input.textChanged.connect(self._apply_filters)
        layout.addWidget(self._search_input, 0, Qt.AlignmentFlag.AlignVCenter)

        self._quality_overview_label = BodyLabel(
            "质量: -" if self._main.config.language == "zh" else "Quality: -"
        )
        layout.addWidget(self._quality_overview_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._btn_low_quality = PushButton(
            "仅低分" if self._main.config.language == "zh" else "Low Quality"
        )
        self._btn_low_quality.setCheckable(True)
        self._btn_low_quality.clicked.connect(self._on_toggle_low_quality_filter)
        layout.addWidget(self._btn_low_quality, 0, Qt.AlignmentFlag.AlignVCenter)

        self._btn_duplicate_risk = PushButton(
            "仅近重复" if self._main.config.language == "zh" else "Near Duplicates"
        )
        self._btn_duplicate_risk.setCheckable(True)
        self._btn_duplicate_risk.clicked.connect(self._on_toggle_duplicate_risk_filter)
        layout.addWidget(self._btn_duplicate_risk, 0, Qt.AlignmentFlag.AlignVCenter)

        return layout

    def _create_left_panel(self) -> QWidget:
        """Create left panel with card list."""
        panel = CardWidget()
        panel.setObjectName("cardPreviewLeftPanel")
        panel.setBorderRadius(8)
        self._left_panel = panel
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL)
        layout.setSpacing(MARGIN_SMALL)

        # List title
        self._list_title_label = BodyLabel(
            "问题列表" if self._main.config.language == "zh" else "Questions"
        )
        layout.addWidget(self._list_title_label)

        # Card list
        self._card_list = QListWidget()
        self._card_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._card_list.currentRowChanged.connect(self._on_card_selected)
        layout.addWidget(self._card_list, 1)

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create right panel with card preview."""
        panel = CardWidget()
        panel.setObjectName("cardPreviewRightPanel")
        panel.setBorderRadius(8)
        self._right_panel = panel
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL)
        layout.setSpacing(MARGIN_SMALL)

        # Card info bar
        info_bar = QHBoxLayout()
        info_bar.setSpacing(SPACING_MEDIUM)

        self._note_type_label = BodyLabel("类型: -")
        info_bar.addWidget(self._note_type_label)

        self._deck_label = BodyLabel("牌组: -")
        info_bar.addWidget(self._deck_label)

        self._tags_label = BodyLabel("标签: -")
        self._tags_label.setWordWrap(False)
        info_bar.addWidget(self._tags_label)

        info_bar.addStretch()

        layout.addLayout(info_bar)

        # Card renderer
        self._card_browser = QTextBrowser()
        self._card_browser.setOpenExternalLinks(False)
        self._card_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._apply_browser_theme()
        layout.addWidget(self._card_browser, 1)

        return panel

    def _create_bottom_bar(self) -> QHBoxLayout:
        """Create bottom bar with navigation and actions."""
        layout = QHBoxLayout()
        layout.setSpacing(SPACING_MEDIUM)

        # Card count
        self._count_label = BodyLabel("0 / 0")
        layout.addWidget(self._count_label)

        layout.addStretch()

        # Navigation buttons
        self._btn_prev = PushButton("上一张" if self._main.config.language == "zh" else "Previous")
        self._btn_prev.setIcon(FluentIcon.LEFT_ARROW)
        self._btn_prev.clicked.connect(self._show_previous)
        self._btn_prev.setEnabled(False)
        layout.addWidget(self._btn_prev)

        self._btn_next = PushButton("下一张" if self._main.config.language == "zh" else "Next")
        self._btn_next.setIcon(FluentIcon.RIGHT_ARROW)
        self._btn_next.clicked.connect(self._show_next)
        self._btn_next.setEnabled(False)
        layout.addWidget(self._btn_next)

        self._btn_regenerate_current = PushButton(
            "重生成当前卡" if self._main.config.language == "zh" else "Regenerate Current"
        )
        self._btn_regenerate_current.clicked.connect(self._regenerate_current_card)
        layout.addWidget(self._btn_regenerate_current)

        self._btn_regenerate_selected = PushButton(
            "重生成所选" if self._main.config.language == "zh" else "Regenerate Selected"
        )
        self._btn_regenerate_selected.clicked.connect(self._regenerate_selected_cards)
        layout.addWidget(self._btn_regenerate_selected)

        self._btn_regenerate_source = PushButton(
            "重生成来源文档" if self._main.config.language == "zh" else "Regenerate Source"
        )
        self._btn_regenerate_source.clicked.connect(self._regenerate_source_document)
        layout.addWidget(self._btn_regenerate_source)

        self._btn_export_apkg = PushButton(
            "导出为 APKG" if self._main.config.language == "zh" else "Export as APKG"
        )
        self._btn_export_apkg.setIcon(FluentIcon.DOWNLOAD)
        self._btn_export_apkg.clicked.connect(self._export_apkg)
        layout.addWidget(self._btn_export_apkg)

        self._btn_export_csv = PushButton(
            "导出为 CSV" if self._main.config.language == "zh" else "Export CSV"
        )
        self._btn_export_csv.setIcon(FluentIcon.DOCUMENT)
        self._btn_export_csv.clicked.connect(self._export_csv)
        layout.addWidget(self._btn_export_csv)

        # Push to Anki button
        self._btn_push = PrimaryPushButton(
            "推送到 Anki" if self._main.config.language == "zh" else "Push to Anki"
        )
        self._btn_push.setIcon(FluentIcon.SEND)
        self._btn_push.clicked.connect(self._push_to_anki)
        layout.addWidget(self._btn_push)

        return layout

    def load_cards(self, cards: list[CardDraft]):
        """Load cards for preview."""
        self._all_cards = cards
        self._rebuild_duplicate_risk_cache()
        self._apply_filters()
        if self._filtered_cards:
            self._show_card(0)

    def _set_total_count_text(self, count: int) -> None:
        """Update total count text based on current language."""
        is_zh = self._main.config.language == "zh"
        self._count_label.setText(f"{count} 张卡片" if is_zh else f"{count} cards")

    def _set_card_meta_labels(self, card: CardDraft | None = None) -> None:
        """Update card metadata labels with localization."""
        is_zh = self._main.config.language == "zh"
        if card is None:
            self._note_type_label.setText("类型: -" if is_zh else "Type: -")
            self._deck_label.setText("牌组: -" if is_zh else "Deck: -")
            self._tags_label.setText("标签: -" if is_zh else "Tags: -")
            self._deck_label.setToolTip("")
            self._tags_label.setToolTip("")
            return

        card_kind = CardRenderer.detect_card_kind(card)
        kind_zh, kind_en = CARD_KIND_LABELS.get(card_kind, CARD_KIND_LABELS["generic"])
        kind_text = kind_zh if is_zh else kind_en
        deck_name = card.deck_name or "-"
        tags_text = self._format_tags_summary(card.tags)
        quality_score = self._compute_card_quality_score(card)
        quality_flags = list(getattr(card.metadata, "quality_flags", []) or [])
        quality_suffix = ""
        if quality_flags:
            quality_text = format_quality_flags(quality_flags, "zh" if is_zh else "en")
            quality_suffix = (
                f"  风险: {quality_text}"
                if is_zh
                else f"  Flags: {quality_text}"
            )
        self._note_type_label.setText(
            f"类型: {kind_text}  质量: {quality_score}{quality_suffix}"
            if is_zh
            else f"Type: {kind_text}  Quality: {quality_score}{quality_suffix}"
        )
        self._deck_label.setText(f"牌组: {deck_name}" if is_zh else f"Deck: {deck_name}")
        self._tags_label.setText(f"标签: {tags_text}" if is_zh else f"Tags: {tags_text}")
        self._deck_label.setToolTip(deck_name if deck_name != "-" else "")
        self._tags_label.setToolTip(", ".join(card.tags) if card.tags else "")

    def _format_tags_summary(self, tags: list[str] | None, *, max_tags: int = 3) -> str:
        is_zh = self._main.config.language == "zh"
        if not tags:
            return "-"

        visible = [tag for tag in tags[:max_tags] if tag]
        if not visible:
            return "-"

        if len(tags) <= max_tags:
            return ", ".join(visible)

        remain = len(tags) - max_tags
        suffix = f" 等{remain}个" if is_zh else f" +{remain}"
        return f"{', '.join(visible)}{suffix}"

    def _apply_filters(self):
        """Apply current filter settings to card list."""
        filtered = self._all_cards

        # Filter by note type
        note_type_filter = self._note_type_combo.currentData()
        if note_type_filter and note_type_filter != "all":
            filtered = [c for c in filtered if CardRenderer.detect_card_kind(c) == note_type_filter]

        # Filter by search text
        search_text = self._search_input.text().strip().lower()
        if search_text:
            filtered = [
                c for c in filtered if any(search_text in v.lower() for v in c.fields.values())
            ]

        if self._quality_low_only:
            filtered = [
                c
                for c in filtered
                if (getattr(c.metadata, "quality_flags", None) or [])
                or self._compute_card_quality_score(c) < 60
            ]

        if self._duplicate_risk_only:
            filtered = [c for c in filtered if self._is_duplicate_risk_card(c)]

        self._filtered_cards = filtered
        self._refresh_card_list()

    def _refresh_card_list(self):
        """Refresh the card list widget."""
        self._card_list.clear()

        for card in self._filtered_cards:
            question = self._build_card_list_item_text(card)
            item = QListWidgetItem(question)
            self._card_list.addItem(item)

        self._update_quality_overview()

        # Update count label
        self._set_total_count_text(len(self._filtered_cards))

        # Select first card if available
        if self._filtered_cards:
            self._card_list.setCurrentRow(0)
        else:
            self._set_card_meta_labels(None)

    def _compact_plain_text(self, text: str, *, max_len: int = 72) -> str:
        plain = re.sub(r"<[^>]+>", "", text or "")
        plain = re.sub(r"\s+", " ", plain).strip()
        if not plain:
            return "（空问题）" if self._main.config.language == "zh" else "(Empty question)"
        return plain if len(plain) <= max_len else f"{plain[: max_len - 1]}…"

    @staticmethod
    def _normalize_quality_text(text: str) -> str:
        plain = re.sub(r"<[^>]+>", " ", text or "")
        return re.sub(r"\s+", " ", plain).strip()

    def _get_card_answer_text(self, card: CardDraft) -> str:
        for key in ("Back", "Answer", "Extra"):
            value = str(card.fields.get(key, "") or "")
            normalized = self._normalize_quality_text(value)
            if normalized:
                return normalized
        if str(card.note_type or "").startswith("Cloze"):
            return self._normalize_quality_text(str(card.fields.get("Text", "") or ""))
        return ""

    def _compute_card_quality_score(self, card: CardDraft) -> int:
        question = self._normalize_quality_text(self._get_card_question_text(card))
        answer = self._get_card_answer_text(card)
        score = 100
        if len(question) < 8:
            score -= 35
        elif len(question) < 15:
            score -= 15
        if len(answer) < 4:
            score -= 40
        elif len(answer) < 10:
            score -= 20
        if (
            not str(card.note_type or "").startswith("Cloze")
            and question
            and answer
            and question == answer
        ):
            score -= 35
        if getattr(card.metadata, "quality_flags", None):
            score = min(score, 55)
        return max(0, min(100, score))

    def _update_quality_overview(self) -> None:
        is_zh = self._main.config.language == "zh"
        if not self._all_cards:
            self._quality_overview_label.setText("质量: -" if is_zh else "Quality: -")
            return

        scores = [self._compute_card_quality_score(card) for card in self._all_cards]
        avg = sum(scores) / max(1, len(scores))
        low = sum(1 for score in scores if score < 60)
        duplicate_risk = len(self._duplicate_risk_card_ids)
        if is_zh:
            self._quality_overview_label.setText(
                "质量均分 "
                f"{avg:.1f}，低分 {low}/{len(scores)}，近重复 {duplicate_risk}/{len(scores)}"
            )
        else:
            self._quality_overview_label.setText(
                "Quality avg "
                f"{avg:.1f}, low {low}/{len(scores)}, "
                f"near-duplicate {duplicate_risk}/{len(scores)}"
            )

    def _on_toggle_low_quality_filter(self, checked: bool) -> None:
        self._quality_low_only = bool(checked)
        self._apply_filters()

    def _on_toggle_duplicate_risk_filter(self, checked: bool) -> None:
        self._duplicate_risk_only = bool(checked)
        self._apply_filters()

    def _get_card_question_text(self, card: CardDraft) -> str:
        kind = CardRenderer.detect_card_kind(card)
        if kind in {"single_choice", "multiple_choice"}:
            question, _ = CardRenderer._parse_choice_front(card.fields.get("Front", ""))
            return self._compact_plain_text(question)

        for key in ("Front", "Text", "Question"):
            value = card.fields.get(key, "")
            if value and value.strip():
                return self._compact_plain_text(value)

        if card.fields:
            first_value = next(iter(card.fields.values()))
            return self._compact_plain_text(first_value)
        return "（空问题）" if self._main.config.language == "zh" else "(Empty question)"

    def _build_card_list_item_text(self, card: CardDraft) -> str:
        question = self._get_card_question_text(card)
        badges: list[str] = []
        if (
            getattr(card.metadata, "quality_flags", None)
            or self._compute_card_quality_score(card) < 60
        ):
            badges.append("[低分]" if self._main.config.language == "zh" else "[Low]")
        if self._is_duplicate_risk_card(card):
            badges.append("[近重复]" if self._main.config.language == "zh" else "[Near Duplicate]")
        if not badges:
            return question
        return f"{question} {' '.join(badges)}"

    def _on_card_selected(self, index: int):
        """Handle card selection from list."""
        if index >= 0:
            self._show_card(index)

    def _show_card(self, index: int):
        """Display card at given index."""
        if not (0 <= index < len(self._filtered_cards)):
            return

        self._current_index = index
        card = self._filtered_cards[index]

        # Update card list selection
        self._card_list.setCurrentRow(index)

        # Update info bar
        self._set_card_meta_labels(card)

        # Render card - always show both question and answer
        html = CardRenderer.render_card(card)
        self._card_browser.setHtml(html)

        # Update navigation buttons
        self._btn_prev.setEnabled(index > 0)
        self._btn_next.setEnabled(index < len(self._filtered_cards) - 1)

        # Update count label
        self._count_label.setText(f"{index + 1} / {len(self._filtered_cards)}")

    def _show_previous(self):
        """Show previous card."""
        if self._current_index > 0:
            self._show_card(self._current_index - 1)

    def _show_next(self):
        """Show next card."""
        if self._current_index < len(self._filtered_cards) - 1:
            self._show_card(self._current_index + 1)

    def _close_preview(self):
        """Close preview and return to previous page."""
        # Navigate back to result page
        self._main.switchTo(self._main.result_page)

    def _apply_browser_theme(self) -> None:
        """Apply theme-aware stylesheet to embedded HTML preview browser."""
        palette = get_list_widget_palette(dark=isDarkTheme())
        self._card_browser.setStyleSheet(
            "QTextBrowser {"
            f"background-color: {palette.background};"
            f"border: 1px solid {palette.border};"
            f"color: {palette.text};"
            "border-radius: 8px;"
            "font-size: 18px;"
            "}"
        )

    def _apply_theme_styles(self) -> None:
        """Apply theme-aware styles for non-Fluent Qt widgets."""
        palette = get_list_widget_palette(dark=isDarkTheme())

        panel_style = (
            f"QWidget#cardPreviewLeftPanel, QWidget#cardPreviewRightPanel {{"
            f"background-color: {palette.background};"
            f"border: 1px solid {palette.border};"
            "border-radius: 8px;"
            "}"
        )
        if hasattr(self, "_left_panel"):
            self._left_panel.setStyleSheet(panel_style)
        if hasattr(self, "_right_panel"):
            self._right_panel.setStyleSheet(panel_style)

        self._card_list.setStyleSheet(
            "QListWidget {"
            f"background-color: {palette.background};"
            f"border: 1px solid {palette.border};"
            "border-radius: 8px;"
            "padding: 8px;"
            "outline: none;"
            "}"
            "QListWidget::item {"
            f"color: {palette.text};"
            "font-size: 15px;"
            "padding: 10px 14px;"
            "border-radius: 6px;"
            "border: none;"
            "margin: 2px 0px;"
            "}"
            "QListWidget::item:hover {"
            f"background-color: {palette.hover};"
            "}"
            "QListWidget::item:selected {"
            f"background-color: {palette.selected_background};"
            f"color: {palette.selected_text};"
            "font-weight: 500;"
            "}"
            "QListWidget::item:selected:hover {"
            f"background-color: {palette.selected_background};"
            "}"
        )

    def update_theme(self) -> None:
        """Update card preview when global theme changes."""
        self._apply_theme_styles()
        self._apply_browser_theme()
        if 0 <= self._current_index < len(self._filtered_cards):
            self._show_card(self._current_index)

    def retranslate_ui(self) -> None:
        """Retranslate UI text when language changes."""
        is_zh = self._main.config.language == "zh"
        self._title_label.setText("卡片预览" if is_zh else "Card Preview")
        self._filter_label.setText("筛选:" if is_zh else "Filter:")
        for idx, (_key, zh_text, en_text) in enumerate(self._NOTE_TYPE_FILTERS):
            self._note_type_combo.setItemText(idx, zh_text if is_zh else en_text)
        self._search_input.setPlaceholderText(
            "搜索卡片内容..." if is_zh else "Search card content..."
        )
        self._btn_low_quality.setText("仅低分" if is_zh else "Low Quality")
        self._btn_duplicate_risk.setText("仅近重复" if is_zh else "Near Duplicates")
        self._list_title_label.setText("问题列表" if is_zh else "Questions")
        self._btn_prev.setText("上一张" if is_zh else "Previous")
        self._btn_next.setText("下一张" if is_zh else "Next")
        self._btn_export_apkg.setText("导出为 APKG" if is_zh else "Export as APKG")
        self._btn_export_csv.setText("导出为 CSV" if is_zh else "Export CSV")
        self._btn_push.setText("推送到 Anki" if is_zh else "Push to Anki")

        if 0 <= self._current_index < len(self._filtered_cards):
            self._show_card(self._current_index)
        else:
            self._set_total_count_text(len(self._filtered_cards))
            self._set_card_meta_labels(None)
            self._update_quality_overview()

    def _push_to_anki(self):
        """Push all cards to Anki."""
        if not self._all_cards:
            InfoBar.warning(
                title="警告" if self._main.config.language == "zh" else "Warning",
                content="没有卡片需要推送"
                if self._main.config.language == "zh"
                else "No cards to push",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        if self._export_worker and self._export_worker.isRunning():
            InfoBar.info(
                title="请稍候" if self._main.config.language == "zh" else "Please Wait",
                content="导出任务进行中，请稍后再推送。"
                if self._main.config.language == "zh"
                else "Export is running. Please push after it finishes.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2500,
                parent=self,
            )
            return

        # Disable push button during push
        is_zh = self._main.config.language == "zh"
        self._set_action_buttons_enabled(False)
        self._progress_bar.show()
        self._push_start_ts = time.monotonic()
        self._count_label.setText("正在推送到 Anki..." if is_zh else "Pushing to Anki...")
        logger.info(
            "push started",
            extra={"event": "ui.push.started", "cards_count": len(self._all_cards)},
        )

        # Apply duplicate check settings to cards
        config = self._main.config
        for card in self._all_cards:
            if card.options is None:
                from ankismart.core.models import CardOptions

                card.options = CardOptions()
            card.options.allow_duplicate = config.allow_duplicate
            card.options.duplicate_scope = config.duplicate_scope
            card.options.duplicate_scope_options.deck_name = card.deck_name
            card.options.duplicate_scope_options.check_children = False
            card.options.duplicate_scope_options.check_all_models = not config.duplicate_check_model

        # Create gateway
        from ankismart.anki_gateway.client import AnkiConnectClient
        from ankismart.anki_gateway.gateway import AnkiGateway
        from ankismart.ui.workers import PushWorker

        client = AnkiConnectClient(
            url=config.anki_connect_url,
            key=config.anki_connect_key,
            proxy_url=config.proxy_url,
        )
        gateway = AnkiGateway(client)

        # Start push worker
        self._push_worker = PushWorker(
            gateway=gateway,
            cards=self._all_cards,
            update_mode=config.last_update_mode or "create_or_update",
        )
        self._push_worker.progress.connect(self._on_push_progress)
        self._push_worker.finished.connect(self._on_push_finished)
        self._push_worker.error.connect(self._on_push_error)
        self._push_worker.cancelled.connect(self._on_push_cancelled)
        self._push_worker.start()

    def _on_push_progress(self, message: str):
        """Handle push progress message."""
        is_zh = self._main.config.language == "zh"
        self._count_label.setText(f"推送中：{message}" if is_zh else f"Pushing: {message}")

    def _on_push_finished(self, result):
        """Handle push completion."""
        self._cleanup_push_worker()
        self._progress_bar.hide()
        self._set_action_buttons_enabled(True)
        elapsed = max(0.0, time.monotonic() - self._push_start_ts) if self._push_start_ts else 0.0
        succeeded = self._safe_int(getattr(result, "succeeded", 0))
        failed = self._safe_int(getattr(result, "failed", 0))

        self._main.result_page.load_result(result, self._all_cards)
        self._main.switchTo(self._main.result_page)
        logger.info(
            "push finished",
            extra={"event": "ui.push.finished", "cards_count": len(self._all_cards)},
        )
        append_task_history(
            self._main.config,
            event="batch_push",
            status="success" if failed == 0 else "partial",
            summary=(f"推送成功 {succeeded} 张，失败 {failed} 张"),
            payload={
                "cards_total": len(self._all_cards),
                "cards_succeeded": succeeded,
                "cards_failed": failed,
                "duration_seconds": round(elapsed, 2),
            },
        )
        record_operation_metric(
            self._main.config,
            event="push",
            duration_seconds=elapsed,
            success=failed == 0,
            error_code="partial_failure" if failed else "",
        )
        save_config(self._main.config)

    def _on_push_error(self, error: str):
        """Handle push error."""
        self._cleanup_push_worker()
        is_zh = self._main.config.language == "zh"
        error_display = build_error_display(error, self._main.config.language)
        elapsed = max(0.0, time.monotonic() - self._push_start_ts) if self._push_start_ts else 0.0
        self._progress_bar.hide()
        self._set_action_buttons_enabled(True)
        self._count_label.setText("推送失败" if is_zh else "Push failed")
        InfoBar.error(
            title=error_display["title"],
            content=error_display["content"],
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )
        logger.error(
            "push failed",
            extra={"event": "ui.push.failed", "error_detail": error},
        )
        append_task_history(
            self._main.config,
            event="batch_push",
            status="failed",
            summary=f"推送失败: {error}",
            payload={
                "cards_total": len(self._all_cards),
                "duration_seconds": round(elapsed, 2),
            },
        )
        record_operation_metric(
            self._main.config,
            event="push",
            duration_seconds=elapsed,
            success=False,
            error_code="push_error",
        )
        save_config(self._main.config)

    def _on_push_cancelled(self):
        """Handle push cancellation."""
        self._cleanup_push_worker()
        is_zh = self._main.config.language == "zh"
        elapsed = max(0.0, time.monotonic() - self._push_start_ts) if self._push_start_ts else 0.0
        self._progress_bar.hide()
        self._set_action_buttons_enabled(True)
        self._count_label.setText("推送已取消" if is_zh else "Push cancelled")
        InfoBar.warning(
            title="已取消" if is_zh else "Cancelled",
            content="卡片推送已被用户取消" if is_zh else "Card push cancelled by user",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
        append_task_history(
            self._main.config,
            event="batch_push",
            status="cancelled",
            summary="用户取消推送",
            payload={
                "cards_total": len(self._all_cards),
                "duration_seconds": round(elapsed, 2),
            },
        )
        record_operation_metric(
            self._main.config,
            event="push",
            duration_seconds=elapsed,
            success=False,
            error_code="cancelled",
        )
        save_config(self._main.config)

    def _export_apkg(self) -> None:
        """Export cards to APKG from card preview page."""
        is_zh = self._main.config.language == "zh"
        if not self._all_cards:
            InfoBar.warning(
                title="警告" if is_zh else "Warning",
                content="没有卡片需要导出" if is_zh else "No cards to export",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        if self._push_worker and self._push_worker.isRunning():
            InfoBar.info(
                title="请稍候" if is_zh else "Please Wait",
                content="推送任务进行中，请稍后导出。"
                if is_zh
                else "Push is running. Please export after it finishes.",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2500,
                parent=self,
            )
            return

        if self._export_worker and self._export_worker.isRunning():
            InfoBar.info(
                title="请稍候" if is_zh else "Please Wait",
                content="已有导出任务进行中" if is_zh else "Another export task is running",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2500,
                parent=self,
            )
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出为 APKG" if is_zh else "Export as APKG",
            "ankismart_cards.apkg",
            "Anki Package (*.apkg)",
        )
        if not output_path:
            return

        from ankismart.anki_gateway.apkg_exporter import ApkgExporter
        from ankismart.ui.workers import ExportWorker

        self._set_action_buttons_enabled(False)
        self._progress_bar.show()
        self._export_start_ts = time.monotonic()
        self._count_label.setText(
            f"正在导出 {len(self._all_cards)} 张卡片..."
            if is_zh
            else f"Exporting {len(self._all_cards)} cards..."
        )

        self._cleanup_export_worker()
        worker = ExportWorker(
            exporter=ApkgExporter(),
            cards=self._all_cards,
            output_path=Path(output_path),
        )
        self._export_worker = worker
        worker.progress.connect(self._on_export_progress)
        worker.finished.connect(self._on_export_finished)
        worker.error.connect(self._on_export_error)
        worker.cancelled.connect(self._on_export_cancelled)
        worker.start()

    def _on_export_progress(self, message: str) -> None:
        is_zh = self._main.config.language == "zh"
        self._count_label.setText(f"导出中：{message}" if is_zh else f"Exporting: {message}")

    def _on_export_finished(self, output_path: str) -> None:
        is_zh = self._main.config.language == "zh"
        elapsed = (
            max(0.0, time.monotonic() - self._export_start_ts) if self._export_start_ts else 0.0
        )
        self._cleanup_export_worker()
        self._progress_bar.hide()
        self._set_action_buttons_enabled(True)
        self._set_count_label_for_current_state()

        InfoBar.success(
            title="导出成功" if is_zh else "Export Succeeded",
            content=f"已导出到 {output_path}" if is_zh else f"Exported to {output_path}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3200,
            parent=self,
        )
        append_task_history(
            self._main.config,
            event="export_apkg",
            status="success",
            summary=f"导出 APKG: {Path(output_path).name}",
            payload={
                "cards_total": len(self._all_cards),
                "duration_seconds": round(elapsed, 2),
                "output_path": output_path,
            },
        )
        record_operation_metric(
            self._main.config,
            event="export",
            duration_seconds=elapsed,
            success=True,
        )
        save_config(self._main.config)

    def _on_export_error(self, error: str) -> None:
        is_zh = self._main.config.language == "zh"
        error_display = build_error_display(error, self._main.config.language)
        elapsed = (
            max(0.0, time.monotonic() - self._export_start_ts) if self._export_start_ts else 0.0
        )
        self._cleanup_export_worker()
        self._progress_bar.hide()
        self._set_action_buttons_enabled(True)
        self._count_label.setText("导出失败" if is_zh else "Export failed")

        InfoBar.error(
            title=error_display["title"],
            content=error_display["content"],
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self,
        )
        append_task_history(
            self._main.config,
            event="export_apkg",
            status="failed",
            summary=f"导出 APKG 失败: {error}",
            payload={
                "cards_total": len(self._all_cards),
                "duration_seconds": round(elapsed, 2),
            },
        )
        record_operation_metric(
            self._main.config,
            event="export",
            duration_seconds=elapsed,
            success=False,
            error_code="export_error",
        )
        save_config(self._main.config)

    def _on_export_cancelled(self) -> None:
        """Handle export cancellation."""
        self._cleanup_export_worker()
        is_zh = self._main.config.language == "zh"
        elapsed = (
            max(0.0, time.monotonic() - self._export_start_ts) if self._export_start_ts else 0.0
        )
        self._progress_bar.hide()
        self._set_action_buttons_enabled(True)
        self._count_label.setText("导出已取消" if is_zh else "Export cancelled")
        InfoBar.warning(
            title="已取消" if is_zh else "Cancelled",
            content="APKG 导出已被用户取消" if is_zh else "APKG export cancelled by user",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3000,
            parent=self,
        )
        append_task_history(
            self._main.config,
            event="export_apkg",
            status="cancelled",
            summary="用户取消导出 APKG",
            payload={
                "cards_total": len(self._all_cards),
                "duration_seconds": round(elapsed, 2),
            },
        )
        record_operation_metric(
            self._main.config,
            event="export",
            duration_seconds=elapsed,
            success=False,
            error_code="cancelled",
        )
        save_config(self._main.config)

    def _set_count_label_for_current_state(self) -> None:
        if 0 <= self._current_index < len(self._filtered_cards):
            self._count_label.setText(f"{self._current_index + 1} / {len(self._filtered_cards)}")
            return
        self._set_total_count_text(len(self._filtered_cards))

    @staticmethod
    def _safe_int(value: object, default: int = 0) -> int:
        try:
            return int(value)  # type: ignore[arg-type]
        except Exception:
            return default

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        self._btn_push.setEnabled(enabled)
        self._btn_export_apkg.setEnabled(enabled)
        self._btn_export_csv.setEnabled(enabled)
        self._btn_regenerate_current.setEnabled(enabled)
        self._btn_regenerate_selected.setEnabled(enabled)
        self._btn_regenerate_source.setEnabled(enabled)

    def _selected_filtered_indices(self) -> list[int]:
        selected_rows = sorted(index.row() for index in self._card_list.selectedIndexes())
        if selected_rows:
            return selected_rows
        if 0 <= self._current_index < len(self._filtered_cards):
            return [self._current_index]
        return []

    def _build_regenerate_request(self, scope: str, indices: list[int]) -> RegenerateRequest | None:
        cards = [
            self._filtered_cards[index]
            for index in indices
            if 0 <= index < len(self._filtered_cards)
        ]
        if not cards:
            return None

        source_documents: list[str] = []
        strategy_ids: list[str] = []
        for card in cards:
            source_document = str(getattr(card.metadata, "source_document", "") or "").strip()
            strategy_id = str(getattr(card.metadata, "strategy_id", "") or "").strip()
            if source_document and source_document not in source_documents:
                source_documents.append(source_document)
            if strategy_id and strategy_id not in strategy_ids:
                strategy_ids.append(strategy_id)

        return RegenerateRequest(
            scope=scope,
            card_indices=indices,
            source_documents=source_documents,
            strategy_ids=strategy_ids,
        )

    def _dispatch_regenerate_request(self, request: RegenerateRequest) -> None:
        switch = getattr(self._main, "switch_to_preview", None)
        if callable(switch):
            switch()
        preview_page = getattr(self._main, "preview_page", None)
        starter = getattr(preview_page, "start_regenerate_request", None)
        if callable(starter):
            starter(request)

    def _regenerate_current_card(self) -> None:
        if not (0 <= self._current_index < len(self._filtered_cards)):
            return
        request = self._build_regenerate_request("current_card", [self._current_index])
        if request is not None:
            self._dispatch_regenerate_request(request)

    def _regenerate_selected_cards(self) -> None:
        request = self._build_regenerate_request(
            "selected_cards",
            self._selected_filtered_indices(),
        )
        if request is not None:
            self._dispatch_regenerate_request(request)

    def _regenerate_source_document(self) -> None:
        request = self._build_regenerate_request(
            "source_document",
            self._selected_filtered_indices(),
        )
        if request is not None:
            self._dispatch_regenerate_request(request)

    def _build_export_rows(self) -> tuple[list[str], list[dict[str, str]]]:
        rows: list[dict[str, str]] = []
        field_keys: set[str] = set()
        for card in self._all_cards:
            field_keys.update(card.fields.keys())

        ordered_field_keys = sorted(field_keys)
        headers = [
            "index",
            "deck_name",
            "note_type",
            "tags",
            "trace_id",
            "source_format",
            "source_path",
            "source_document",
            "strategy_id",
            "quality_flags",
            *[f"field_{name}" for name in ordered_field_keys],
        ]

        for idx, card in enumerate(self._all_cards, 1):
            row: dict[str, str] = {
                "index": str(idx),
                "deck_name": card.deck_name or "",
                "note_type": card.note_type or "",
                "tags": ",".join(card.tags or []),
                "trace_id": card.trace_id or "",
                "source_format": card.metadata.source_format or "",
                "source_path": card.metadata.source_path or "",
                "source_document": card.metadata.source_document or "",
                "strategy_id": card.metadata.strategy_id or "",
                "quality_flags": ",".join(card.metadata.quality_flags or []),
            }
            for key in ordered_field_keys:
                row[f"field_{key}"] = str(card.fields.get(key, "") or "")
            rows.append(row)

        return headers, rows

    def _export_csv(self) -> None:
        is_zh = self._main.config.language == "zh"
        if not self._all_cards:
            InfoBar.warning(
                title="警告" if is_zh else "Warning",
                content="没有卡片需要导出" if is_zh else "No cards to export",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出为 CSV" if is_zh else "Export CSV",
            "ankismart_cards.csv",
            "CSV Files (*.csv)",
        )
        if not output_path:
            return

        headers, rows = self._build_export_rows()
        try:
            with Path(output_path).open("w", encoding="utf-8-sig", newline="") as fp:
                writer = csv.DictWriter(fp, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
        except Exception as exc:
            InfoBar.error(
                title="导出失败" if is_zh else "Export Failed",
                content=str(exc),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
            append_task_history(
                self._main.config,
                event="export_csv",
                status="failed",
                summary=f"导出 CSV 失败: {exc}",
                payload={"cards_total": len(self._all_cards)},
            )
            save_config(self._main.config)
            return

        InfoBar.success(
            title="导出成功" if is_zh else "Export Succeeded",
            content=f"已导出到 {output_path}" if is_zh else f"Exported to {output_path}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2800,
            parent=self,
        )
        append_task_history(
            self._main.config,
            event="export_csv",
            status="success",
            summary=f"导出 CSV: {Path(output_path).name}",
            payload={"cards_total": len(self._all_cards), "output_path": output_path},
        )
        save_config(self._main.config)

    def _export_json(self) -> None:
        is_zh = self._main.config.language == "zh"
        if not self._all_cards:
            InfoBar.warning(
                title="警告" if is_zh else "Warning",
                content="没有卡片需要导出" if is_zh else "No cards to export",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出为 JSON" if is_zh else "Export JSON",
            "ankismart_cards.json",
            "JSON Files (*.json)",
        )
        if not output_path:
            return

        headers, rows = self._build_export_rows()
        payload = {
            "count": len(rows),
            "columns": headers,
            "cards": rows,
        }
        try:
            Path(output_path).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            InfoBar.error(
                title="导出失败" if is_zh else "Export Failed",
                content=str(exc),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
            append_task_history(
                self._main.config,
                event="export_json",
                status="failed",
                summary=f"导出 JSON 失败: {exc}",
                payload={"cards_total": len(self._all_cards)},
            )
            save_config(self._main.config)
            return

        InfoBar.success(
            title="导出成功" if is_zh else "Export Succeeded",
            content=f"已导出到 {output_path}" if is_zh else f"Exported to {output_path}",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2800,
            parent=self,
        )
        append_task_history(
            self._main.config,
            event="export_json",
            status="success",
            summary=f"导出 JSON: {Path(output_path).name}",
            payload={"cards_total": len(self._all_cards), "output_path": output_path},
        )
        save_config(self._main.config)

    @staticmethod
    def _normalize_similarity_text(text: str) -> str:
        plain = re.sub(r"<[^>]+>", " ", text or "")
        plain = re.sub(r"\s+", " ", plain).strip().lower()
        return plain

    def _extract_card_question_for_similarity(self, card: CardDraft) -> str:
        for key in ("Front", "Text", "Question"):
            value = card.fields.get(key, "")
            if value and str(value).strip():
                return self._normalize_similarity_text(str(value))
        if card.fields:
            return self._normalize_similarity_text(str(next(iter(card.fields.values()))))
        return ""

    def _estimate_duplicate_risk(
        self, cards: list[CardDraft], threshold: float
    ) -> tuple[int, list[tuple[int, int, float]], bool]:
        if len(cards) < 2:
            return 0, [], False

        texts = [self._extract_card_question_for_similarity(card) for card in cards]
        suspicious_pairs: list[tuple[int, int, float]] = []
        risky_indices: set[int] = set()
        max_comparisons = 15000
        comparisons = 0
        truncated = False

        for i in range(len(texts)):
            if comparisons >= max_comparisons:
                truncated = True
                break
            left = texts[i]
            if not left:
                continue
            for j in range(i + 1, len(texts)):
                comparisons += 1
                if comparisons > max_comparisons:
                    truncated = True
                    break
                right = texts[j]
                if not right:
                    continue
                ratio = SequenceMatcher(None, left, right).ratio()
                if ratio >= threshold:
                    risky_indices.add(i)
                    risky_indices.add(j)
                    if len(suspicious_pairs) < 8:
                        suspicious_pairs.append((i, j, ratio))
            if truncated:
                break

        return len(risky_indices), suspicious_pairs, truncated

    def _collect_duplicate_risk_indices(self, cards: list[CardDraft], threshold: float) -> set[int]:
        if len(cards) < 2:
            return set()

        texts = [self._extract_card_question_for_similarity(card) for card in cards]
        risky_indices: set[int] = set()
        max_comparisons = 15000
        comparisons = 0

        for i in range(len(texts)):
            if comparisons >= max_comparisons:
                break
            left = texts[i]
            if not left:
                continue
            for j in range(i + 1, len(texts)):
                comparisons += 1
                if comparisons > max_comparisons:
                    break
                right = texts[j]
                if not right:
                    continue
                ratio = SequenceMatcher(None, left, right).ratio()
                if ratio >= threshold:
                    risky_indices.add(i)
                    risky_indices.add(j)
            if comparisons > max_comparisons:
                break

        return risky_indices

    def _rebuild_duplicate_risk_cache(self) -> None:
        threshold = float(getattr(self._main.config, "semantic_duplicate_threshold", 0.9))
        risky_indices = self._collect_duplicate_risk_indices(self._all_cards, threshold)
        self._duplicate_risk_card_ids = {id(self._all_cards[index]) for index in risky_indices}

    def _is_duplicate_risk_card(self, card: CardDraft) -> bool:
        return id(card) in self._duplicate_risk_card_ids

    def _show_push_preview(self) -> None:
        is_zh = self._main.config.language == "zh"
        if not self._all_cards:
            InfoBar.warning(
                title="警告" if is_zh else "Warning",
                content="没有卡片可预演" if is_zh else "No cards for preview",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2800,
                parent=self,
            )
            return

        threshold = float(getattr(self._main.config, "semantic_duplicate_threshold", 0.9))
        risk_count, pairs, truncated = self._estimate_duplicate_risk(self._all_cards, threshold)

        deck_counter = Counter((card.deck_name or "Default") for card in self._all_cards)
        top_decks = sorted(deck_counter.items(), key=lambda item: item[1], reverse=True)[:5]
        mode = (
            getattr(self._main.config, "last_update_mode", "create_or_update") or "create_or_update"
        )

        lines: list[str] = []
        if is_zh:
            lines.append(f"卡片总数：{len(self._all_cards)}")
            lines.append(f"推送模式：{mode}")
            lines.append(
                f"近重复风险：{risk_count} 张（阈值 {threshold:.2f}）"
                + ("，已触发比较上限，结果为近似值" if truncated else "")
            )
            lines.append("牌组分布（Top 5）：")
            lines.extend([f"- {deck}: {count}" for deck, count in top_decks])
            if pairs:
                lines.append("高相似样例：")
                for left, right, score in pairs[:5]:
                    lines.append(f"- #{left + 1} vs #{right + 1}: {score:.2f}")
        else:
            lines.append(f"Total cards: {len(self._all_cards)}")
            lines.append(f"Update mode: {mode}")
            lines.append(
                f"Near-duplicate risk: {risk_count} cards (threshold {threshold:.2f})"
                + (", comparison capped so this is approximate" if truncated else "")
            )
            lines.append("Deck distribution (Top 5):")
            lines.extend([f"- {deck}: {count}" for deck, count in top_decks])
            if pairs:
                lines.append("High-similarity samples:")
                for left, right, score in pairs[:5]:
                    lines.append(f"- #{left + 1} vs #{right + 1}: {score:.2f}")

        dialog = MessageBox(
            "推送预演" if is_zh else "Push Preview",
            "\n".join(lines),
            self,
        )
        dialog.yesButton.setText("确认推送" if is_zh else "Push Now")
        dialog.cancelButton.setText("取消" if is_zh else "Cancel")
        if dialog.exec():
            self._push_to_anki()

    def _cleanup_push_worker(self) -> None:
        worker = self.__dict__.get("_push_worker")
        if worker is None:
            return
        if hasattr(worker, "isRunning") and worker.isRunning():
            if hasattr(worker, "cancel"):
                worker.cancel()
            worker.wait(200)
            if worker.isRunning():
                return
        self.__dict__["_push_worker"] = None
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
        """Stop workers cooperatively during application shutdown."""
        if self._push_worker and self._push_worker.isRunning():
            if hasattr(self._push_worker, "cancel"):
                self._push_worker.cancel()
            self._push_worker.requestInterruption()
            self._push_worker.wait(300)
        if self._export_worker and self._export_worker.isRunning():
            if hasattr(self._export_worker, "cancel"):
                self._export_worker.cancel()
            self._export_worker.requestInterruption()
            self._export_worker.wait(300)
        self._cleanup_push_worker()
        self._cleanup_export_worker()
        super().closeEvent(event)
