"""Card preview page for viewing generated Anki cards."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    TitleLabel,
    isDarkTheme,
)
from PyQt6.QtWidgets import QTextBrowser

from ankismart.core.models import CardDraft
from ankismart.ui.i18n import t
from ankismart.ui.styles import (
    MARGIN_SMALL,
    MARGIN_STANDARD,
    SPACING_LARGE,
    SPACING_MEDIUM,
    apply_page_title_style,
)

if TYPE_CHECKING:
    from ankismart.ui.main_window import MainWindow


class CardRenderer:
    """Generates HTML for different Anki note types."""

    @staticmethod
    def render_card(card: CardDraft) -> str:
        """Generate HTML for card preview - always show both question and answer."""
        note_type = card.note_type

        if note_type == "Basic":
            return CardRenderer._render_basic(card)
        elif note_type == "Basic (and reversed card)":
            return CardRenderer._render_basic_reversed(card)
        elif note_type.startswith("Cloze"):
            return CardRenderer._render_cloze(card)
        else:
            return CardRenderer._render_generic(card)

    @staticmethod
    def _render_basic(card: CardDraft) -> str:
        """Render Basic note type - always show both front and back."""
        front = card.fields.get("Front", "")
        back = card.fields.get("Back", "")

        content = f"""
        <div class="question">{front}</div>
        <hr>
        <div class="answer">{back}</div>
        """

        return CardRenderer._wrap_html(content)

    @staticmethod
    def _render_basic_reversed(card: CardDraft) -> str:
        """Render Basic (and reversed card) note type."""
        return CardRenderer._render_basic(card)

    @staticmethod
    def _render_cloze(card: CardDraft) -> str:
        """Render Cloze note type."""
        text = card.fields.get("Text", "")
        # Process cloze deletions: {{c1::text}} -> <span class="cloze">[text]</span>
        processed = re.sub(
            r'\{\{c\d+::([^}]+)\}\}',
            r'<span class="cloze">[\1]</span>',
            text
        )
        return CardRenderer._wrap_html(processed)

    @staticmethod
    def _render_generic(card: CardDraft) -> str:
        """Render generic card with all fields."""
        content = ""
        for field_name, field_value in card.fields.items():
            content += f"""
            <div class="field">
                <strong>{field_name}:</strong>
                <div class="field-content">{field_value}</div>
            </div>
            """
        return CardRenderer._wrap_html(content)

    @staticmethod
    def _wrap_html(content: str) -> str:
        """Wrap content with CSS and card structure."""
        from ankismart.anki_gateway.styling import MODERN_CARD_CSS

        body_class = "night_mode" if isDarkTheme() else ""

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
            {MODERN_CARD_CSS}
            .field {{
                margin-bottom: 1em;
            }}
            .field-content {{
                margin-top: 0.5em;
                padding-left: 1em;
            }}
            </style>
        </head>
        <body class="{body_class}">
            <div class="card">{content}</div>
        </body>
        </html>
        """


class CardPreviewPage(QWidget):
    """Page for previewing generated Anki cards."""

    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.setObjectName("cardPreviewPage")  # Required by QFluentWidgets
        self._main = main_window
        self._all_cards: list[CardDraft] = []
        self._filtered_cards: list[CardDraft] = []
        self._current_index = -1

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_LARGE)
        layout.setContentsMargins(MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD, MARGIN_STANDARD)

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
        self._apply_theme_styles()

    def _create_top_bar(self) -> QHBoxLayout:
        """Create top bar with title and filters."""
        layout = QHBoxLayout()
        layout.setSpacing(SPACING_MEDIUM)

        # Title
        title = TitleLabel("卡片预览" if self._main.config.language == "zh" else "Card Preview")
        apply_page_title_style(title)
        layout.addWidget(title)

        layout.addStretch()

        # Filter by note type
        filter_label = BodyLabel("筛选:" if self._main.config.language == "zh" else "Filter:")
        layout.addWidget(filter_label)

        self._note_type_combo = ComboBox()
        self._note_type_combo.addItem("全部" if self._main.config.language == "zh" else "All", userData="all")
        self._note_type_combo.addItem("Basic", userData="Basic")
        self._note_type_combo.addItem("Cloze", userData="Cloze")
        self._note_type_combo.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self._note_type_combo)

        # Search box
        self._search_input = LineEdit()
        self._search_input.setPlaceholderText("搜索卡片内容..." if self._main.config.language == "zh" else "Search card content...")
        self._search_input.setFixedWidth(200)
        self._search_input.textChanged.connect(self._apply_filters)
        layout.addWidget(self._search_input)

        return layout

    def _create_left_panel(self) -> QWidget:
        """Create left panel with card list."""
        panel = CardWidget()
        panel.setBorderRadius(8)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL)
        layout.setSpacing(MARGIN_SMALL)

        # List title
        list_title = BodyLabel("卡片列表" if self._main.config.language == "zh" else "Card List")
        layout.addWidget(list_title)

        # Card list
        self._card_list = QListWidget()
        self._card_list.currentRowChanged.connect(self._on_card_selected)
        layout.addWidget(self._card_list, 1)

        return panel

    def _create_right_panel(self) -> QWidget:
        """Create right panel with card preview."""
        panel = CardWidget()
        panel.setBorderRadius(8)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL, MARGIN_SMALL)
        layout.setSpacing(MARGIN_SMALL)

        # Card info bar
        info_bar = QHBoxLayout()
        info_bar.setSpacing(SPACING_MEDIUM)

        self._note_type_label = CaptionLabel("类型: -")
        info_bar.addWidget(self._note_type_label)

        self._deck_label = CaptionLabel("牌组: -")
        info_bar.addWidget(self._deck_label)

        self._tags_label = CaptionLabel("标签: -")
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
        self._btn_prev.setIcon(FIF.LEFT_ARROW)
        self._btn_prev.clicked.connect(self._show_previous)
        self._btn_prev.setEnabled(False)
        layout.addWidget(self._btn_prev)

        self._btn_next = PushButton("下一张" if self._main.config.language == "zh" else "Next")
        self._btn_next.setIcon(FIF.RIGHT_ARROW)
        self._btn_next.clicked.connect(self._show_next)
        self._btn_next.setEnabled(False)
        layout.addWidget(self._btn_next)

        # Close button
        self._btn_close = PrimaryPushButton("关闭" if self._main.config.language == "zh" else "Close")
        self._btn_close.clicked.connect(self._close_preview)
        layout.addWidget(self._btn_close)

        return layout

    def load_cards(self, cards: list[CardDraft]):
        """Load cards for preview."""
        self._all_cards = cards
        self._apply_filters()
        if self._filtered_cards:
            self._show_card(0)

    def _apply_filters(self):
        """Apply current filter settings to card list."""
        filtered = self._all_cards

        # Filter by note type
        note_type_filter = self._note_type_combo.currentData()
        if note_type_filter and note_type_filter != "all":
            filtered = [c for c in filtered if c.note_type == note_type_filter]

        # Filter by search text
        search_text = self._search_input.text().strip().lower()
        if search_text:
            filtered = [
                c for c in filtered
                if any(search_text in v.lower() for v in c.fields.values())
            ]

        self._filtered_cards = filtered
        self._refresh_card_list()

    def _refresh_card_list(self):
        """Refresh the card list widget."""
        self._card_list.clear()

        for i, card in enumerate(self._filtered_cards):
            # Get first field value as title
            title = ""
            if card.fields:
                first_value = next(iter(card.fields.values()))
                title = first_value if len(first_value) <= 50 else f"{first_value[:47]}..."

            item = QListWidgetItem(f"{i + 1}. {title}")
            self._card_list.addItem(item)

        # Update count label
        self._count_label.setText(f"{len(self._filtered_cards)} 张卡片")

        # Select first card if available
        if self._filtered_cards:
            self._card_list.setCurrentRow(0)

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
        self._note_type_label.setText(f"类型: {card.note_type}")
        self._deck_label.setText(f"牌组: {card.deck_name}")
        self._tags_label.setText(f"标签: {', '.join(card.tags) if card.tags else '-'}")

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
        border_color = "rgba(255, 255, 255, 0.12)" if isDarkTheme() else "rgba(0, 0, 0, 0.08)"
        self._card_browser.setStyleSheet(
            "QTextBrowser {"
            "background-color: transparent;"
            f"border: 1px solid {border_color};"
            "border-radius: 8px;"
            "}"
        )

    def _apply_theme_styles(self) -> None:
        """Apply theme-aware styles for non-Fluent Qt widgets."""
        border_color = "rgba(255, 255, 255, 0.12)" if isDarkTheme() else "rgba(0, 0, 0, 0.08)"
        hover_color = "rgba(255, 255, 255, 0.06)" if isDarkTheme() else "rgba(0, 0, 0, 0.04)"
        selected_color = "rgba(59, 130, 246, 0.26)" if isDarkTheme() else "rgba(37, 99, 235, 0.14)"
        self._card_list.setStyleSheet(
            "QListWidget {"
            "background-color: transparent;"
            f"border: 1px solid {border_color};"
            "border-radius: 8px;"
            "}"
            "QListWidget::item {"
            "padding: 8px 10px;"
            "border-radius: 6px;"
            "}"
            f"QListWidget::item:selected {{background-color: {selected_color};}}"
            f"QListWidget::item:hover {{background-color: {hover_color};}}"
        )

    def update_theme(self) -> None:
        """Update card preview when global theme changes."""
        self._apply_theme_styles()
        self._apply_browser_theme()
        if 0 <= self._current_index < len(self._filtered_cards):
            self._show_card(self._current_index)
