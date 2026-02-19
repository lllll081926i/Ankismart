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
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    TitleLabel,
    isDarkTheme,
)
from PyQt6.QtWidgets import QTextBrowser

from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft
from ankismart.ui.styles import (
    MARGIN_SMALL,
    MARGIN_STANDARD,
    SPACING_LARGE,
    SPACING_MEDIUM,
    apply_page_title_style,
    get_list_widget_palette,
)

if TYPE_CHECKING:
    from ankismart.ui.main_window import MainWindow

logger = get_logger(__name__)


class CardRenderer:
    """Generates HTML for different Anki note types."""

    @staticmethod
    def render_card(card: CardDraft) -> str:
        """Generate HTML for card preview - always show both question and answer."""
        note_type = card.note_type

        # Detect card strategy from tags or content
        tags = card.tags or []

        # Check for specific strategies
        if "concept" in tags or "概念" in str(card.fields.get("Front", "")).lower()[:50]:
            return CardRenderer._render_concept(card)
        elif "key_terms" in tags or "术语" in tags:
            return CardRenderer._render_key_terms(card)
        elif "single_choice" in tags or "单选" in tags:
            return CardRenderer._render_single_choice(card)
        elif "multiple_choice" in tags or "多选" in tags:
            return CardRenderer._render_multiple_choice(card)
        elif "image" in tags:
            return CardRenderer._render_image_qa(card)
        elif note_type == "Basic":
            return CardRenderer._render_basic(card)
        elif note_type == "Basic (and reversed card)":
            return CardRenderer._render_basic_reversed(card)
        elif note_type.startswith("Cloze"):
            return CardRenderer._render_cloze(card)
        else:
            return CardRenderer._render_generic(card)

    @staticmethod
    def _render_basic(card: CardDraft) -> str:
        """Render Basic note type - standard Q&A format."""
        front = card.fields.get("Front", "")
        back = card.fields.get("Back", "")

        content = f"""
        <div class="card-basic">
            <div class="question-section">
                <div class="section-label">
                    <span class="label-icon">Q</span>
                    <span class="label-text">问题</span>
                </div>
                <div class="section-content">{front}</div>
            </div>
            <div class="divider"></div>
            <div class="answer-section">
                <div class="section-label">
                    <span class="label-icon">A</span>
                    <span class="label-text">答案</span>
                </div>
                <div class="section-content">{back}</div>
            </div>
        </div>
        """

        return CardRenderer._wrap_html(content, "basic")

    @staticmethod
    def _render_basic_reversed(card: CardDraft) -> str:
        """Render Basic (and reversed card) note type."""
        front = card.fields.get("Front", "")
        back = card.fields.get("Back", "")

        content = f"""
        <div class="card-reversed">
            <div class="reversed-notice">
                <span class="notice-icon">⇄</span>
                <span class="notice-text">双向卡片</span>
            </div>
            <div class="question-section">
                <div class="section-label">
                    <span class="label-icon">Q</span>
                    <span class="label-text">正面</span>
                </div>
                <div class="section-content">{front}</div>
            </div>
            <div class="divider"></div>
            <div class="answer-section">
                <div class="section-label">
                    <span class="label-icon">A</span>
                    <span class="label-text">背面</span>
                </div>
                <div class="section-content">{back}</div>
            </div>
        </div>
        """

        return CardRenderer._wrap_html(content, "reversed")

    @staticmethod
    def _render_cloze(card: CardDraft) -> str:
        """Render Cloze note type with highlighted deletions."""
        text = card.fields.get("Text", "")

        # Process cloze deletions: {{c1::text}} -> highlighted spans
        processed = re.sub(
            r'\{\{c(\d+)::([^}]+)\}\}',
            r'<span class="cloze" data-cloze="\1"><span class="cloze-bracket">[</span><span class="cloze-content">\2</span><span class="cloze-bracket">]</span></span>',
            text
        )

        content = f"""
        <div class="card-cloze">
            <div class="cloze-notice">
                <span class="notice-icon">●●●</span>
                <span class="notice-text">填空题</span>
            </div>
            <div class="cloze-content-wrapper">
                {processed}
            </div>
        </div>
        """

        return CardRenderer._wrap_html(content, "cloze")

    @staticmethod
    def _render_concept(card: CardDraft) -> str:
        """Render concept explanation cards."""
        front = card.fields.get("Front", "")
        back = card.fields.get("Back", "")

        content = f"""
        <div class="card-concept">
            <div class="concept-notice">
                <span class="notice-icon">📖</span>
                <span class="notice-text">概念解释</span>
            </div>
            <div class="concept-term">
                <div class="section-label">概念</div>
                <div class="section-content concept-name">{front}</div>
            </div>
            <div class="divider"></div>
            <div class="concept-explanation">
                <div class="section-label">解释</div>
                <div class="section-content">{back}</div>
            </div>
        </div>
        """

        return CardRenderer._wrap_html(content, "concept")

    @staticmethod
    def _render_key_terms(card: CardDraft) -> str:
        """Render key terms cards."""
        front = card.fields.get("Front", "")
        back = card.fields.get("Back", "")

        content = f"""
        <div class="card-keyterm">
            <div class="keyterm-notice">
                <span class="notice-icon">🔑</span>
                <span class="notice-text">关键术语</span>
            </div>
            <div class="keyterm-term">
                <div class="section-label">术语</div>
                <div class="section-content keyterm-name">{front}</div>
            </div>
            <div class="divider"></div>
            <div class="keyterm-definition">
                <div class="section-label">定义</div>
                <div class="section-content">{back}</div>
            </div>
        </div>
        """

        return CardRenderer._wrap_html(content, "keyterm")

    @staticmethod
    def _render_single_choice(card: CardDraft) -> str:
        """Render single choice question cards."""
        front = card.fields.get("Front", "")
        back = card.fields.get("Back", "")

        content = f"""
        <div class="card-choice">
            <div class="choice-notice">
                <span class="notice-icon">◉</span>
                <span class="notice-text">单选题</span>
            </div>
            <div class="choice-question">
                <div class="section-label">题目</div>
                <div class="section-content">{front}</div>
            </div>
            <div class="divider"></div>
            <div class="choice-answer">
                <div class="section-label">答案</div>
                <div class="section-content">{back}</div>
            </div>
        </div>
        """

        return CardRenderer._wrap_html(content, "choice")

    @staticmethod
    def _render_multiple_choice(card: CardDraft) -> str:
        """Render multiple choice question cards."""
        front = card.fields.get("Front", "")
        back = card.fields.get("Back", "")

        content = f"""
        <div class="card-choice">
            <div class="choice-notice">
                <span class="notice-icon">☑</span>
                <span class="notice-text">多选题</span>
            </div>
            <div class="choice-question">
                <div class="section-label">题目</div>
                <div class="section-content">{front}</div>
            </div>
            <div class="divider"></div>
            <div class="choice-answer">
                <div class="section-label">答案</div>
                <div class="section-content">{back}</div>
            </div>
        </div>
        """

        return CardRenderer._wrap_html(content, "choice")

    @staticmethod
    def _render_image_qa(card: CardDraft) -> str:
        """Render image-based Q&A cards."""
        front = card.fields.get("Front", "")
        back = card.fields.get("Back", "")

        content = f"""
        <div class="card-image">
            <div class="image-notice">
                <span class="notice-icon">🖼️</span>
                <span class="notice-text">图片问答</span>
            </div>
            <div class="image-question">
                <div class="section-label">问题</div>
                <div class="section-content">{front}</div>
            </div>
            <div class="divider"></div>
            <div class="image-answer">
                <div class="section-label">答案</div>
                <div class="section-content">{back}</div>
            </div>
        </div>
        """

        return CardRenderer._wrap_html(content, "image")

    @staticmethod
    def _render_generic(card: CardDraft) -> str:
        """Render generic card with all fields."""
        content = '<div class="card-generic">'
        for field_name, field_value in card.fields.items():
            content += f"""
            <div class="field">
                <div class="field-name">{field_name}</div>
                <div class="field-content">{field_value}</div>
            </div>
            """
        content += '</div>'
        return CardRenderer._wrap_html(content, "generic")

    @staticmethod
    def _wrap_html(content: str, card_type: str = "basic") -> str:
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

            /* Card Type Specific Styles */
            .card-basic, .card-reversed, .card-cloze, .card-concept,
            .card-keyterm, .card-choice, .card-image, .card-generic {{
                padding: 32px;
                min-height: 400px;
            }}

            /* Notice Badges */
            .reversed-notice, .cloze-notice, .concept-notice,
            .keyterm-notice, .choice-notice, .image-notice {{
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 16px;
                background: linear-gradient(135deg, #0078d4 0%, #005a9e 100%);
                color: white;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 24px;
                box-shadow: 0 2px 8px rgba(0, 120, 212, 0.3);
            }}

            .night_mode .reversed-notice,
            .night_mode .cloze-notice,
            .night_mode .concept-notice,
            .night_mode .keyterm-notice,
            .night_mode .choice-notice,
            .night_mode .image-notice {{
                background: linear-gradient(135deg, #4db8ff 0%, #0078d4 100%);
                box-shadow: 0 2px 8px rgba(77, 184, 255, 0.3);
            }}

            .notice-icon {{
                font-size: 18px;
            }}

            .notice-text {{
                font-size: 14px;
                letter-spacing: 0.5px;
            }}

            /* Section Styles */
            .question-section, .answer-section,
            .concept-term, .concept-explanation,
            .keyterm-term, .keyterm-definition,
            .choice-question, .choice-answer,
            .image-question, .image-answer {{
                margin: 32px 0;
            }}

            .section-label {{
                display: flex;
                align-items: center;
                gap: 10px;
                font-size: 16px;
                font-weight: 700;
                color: #0078d4;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 16px;
            }}

            .night_mode .section-label {{
                color: #4db8ff;
            }}

            .label-icon {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 32px;
                height: 32px;
                background: #0078d4;
                color: white;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 700;
            }}

            .night_mode .label-icon {{
                background: #4db8ff;
                color: #1e1e1e;
            }}

            .section-content {{
                font-size: 20px;
                line-height: 2;
                padding: 16px 20px;
                border-left: 4px solid #0078d4;
                background: rgba(0, 120, 212, 0.03);
                border-radius: 0 8px 8px 0;
            }}

            .night_mode .section-content {{
                border-left-color: #4db8ff;
                background: rgba(77, 184, 255, 0.05);
            }}

            /* Concept Card Specific */
            .concept-name {{
                font-size: 24px;
                font-weight: 700;
                color: #0078d4;
            }}

            .night_mode .concept-name {{
                color: #4db8ff;
            }}

            /* Key Term Card Specific */
            .keyterm-name {{
                font-size: 24px;
                font-weight: 700;
                color: #0078d4;
                font-style: italic;
            }}

            .night_mode .keyterm-name {{
                color: #4db8ff;
            }}

            /* Cloze Card Specific */
            .cloze-content-wrapper {{
                font-size: 20px;
                line-height: 2.2;
                padding: 24px;
                background: rgba(0, 120, 212, 0.03);
                border-radius: 12px;
                border: 2px solid rgba(0, 120, 212, 0.1);
            }}

            .night_mode .cloze-content-wrapper {{
                background: rgba(77, 184, 255, 0.05);
                border-color: rgba(77, 184, 255, 0.15);
            }}

            .cloze {{
                display: inline-block;
                padding: 4px 12px;
                margin: 0 4px;
                background: linear-gradient(135deg, #0078d4 0%, #005a9e 100%);
                color: white;
                border-radius: 6px;
                font-weight: 600;
                font-size: 20px;
                box-shadow: 0 2px 6px rgba(0, 120, 212, 0.3);
            }}

            .night_mode .cloze {{
                background: linear-gradient(135deg, #4db8ff 0%, #0078d4 100%);
                box-shadow: 0 2px 6px rgba(77, 184, 255, 0.3);
            }}

            .cloze-bracket {{
                font-weight: 700;
                font-size: 22px;
            }}

            .cloze-content {{
                padding: 0 4px;
            }}

            /* Divider */
            .divider {{
                height: 3px;
                background: linear-gradient(to right, transparent 5%, #0078d4 50%, transparent 95%);
                margin: 48px 0;
                border-radius: 2px;
                box-shadow: 0 2px 8px rgba(0, 120, 212, 0.3);
            }}

            .night_mode .divider {{
                background: linear-gradient(to right, transparent 5%, #4db8ff 50%, transparent 95%);
                box-shadow: 0 2px 8px rgba(77, 184, 255, 0.3);
            }}

            /* Generic Card */
            .field {{
                margin-bottom: 24px;
                padding: 20px;
                background: rgba(0, 120, 212, 0.03);
                border-radius: 8px;
                border-left: 4px solid #0078d4;
            }}

            .night_mode .field {{
                background: rgba(77, 184, 255, 0.05);
                border-left-color: #4db8ff;
            }}

            .field-name {{
                font-size: 16px;
                font-weight: 700;
                color: #0078d4;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 12px;
            }}

            .night_mode .field-name {{
                color: #4db8ff;
            }}

            .field-content {{
                font-size: 20px;
                line-height: 2;
            }}
            </style>
        </head>
        <body class="{body_class}">
            <div class="card" data-card-type="{card_type}">{content}</div>
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
        self._push_worker = None

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
        layout.setSpacing(SPACING_MEDIUM)

        # Title
        self._title_label = TitleLabel("卡片预览" if self._main.config.language == "zh" else "Card Preview")
        apply_page_title_style(self._title_label)
        layout.addWidget(self._title_label)

        layout.addStretch()

        # Filter by note type
        self._filter_label = BodyLabel("筛选:" if self._main.config.language == "zh" else "Filter:")
        layout.addWidget(self._filter_label)

        self._note_type_combo = ComboBox()
        self._note_type_combo.addItem("全部" if self._main.config.language == "zh" else "All", userData="all")
        self._note_type_combo.addItem("Basic", userData="Basic")
        self._note_type_combo.addItem("Cloze", userData="Cloze")
        self._note_type_combo.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self._note_type_combo)

        # Search box
        self._search_input = LineEdit()
        self._search_input.setPlaceholderText("搜索卡片内容..." if self._main.config.language == "zh" else "Search card content...")
        self._search_input.setMinimumWidth(200)
        self._search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._search_input.textChanged.connect(self._apply_filters)
        layout.addWidget(self._search_input)

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
        self._list_title_label = BodyLabel("卡片列表" if self._main.config.language == "zh" else "Card List")
        layout.addWidget(self._list_title_label)

        # Card list
        self._card_list = QListWidget()
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

        # Push to Anki button
        self._btn_push = PrimaryPushButton("推送到 Anki" if self._main.config.language == "zh" else "Push to Anki")
        self._btn_push.setIcon(FIF.SEND)
        self._btn_push.clicked.connect(self._push_to_anki)
        layout.addWidget(self._btn_push)

        return layout

    def load_cards(self, cards: list[CardDraft]):
        """Load cards for preview."""
        self._all_cards = cards
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
            return

        tags_text = ", ".join(card.tags) if card.tags else "-"
        self._note_type_label.setText(
            f"类型: {card.note_type}" if is_zh else f"Type: {card.note_type}"
        )
        self._deck_label.setText(
            f"牌组: {card.deck_name}" if is_zh else f"Deck: {card.deck_name}"
        )
        self._tags_label.setText(
            f"标签: {tags_text}" if is_zh else f"Tags: {tags_text}"
        )

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
        self._set_total_count_text(len(self._filtered_cards))

        # Select first card if available
        if self._filtered_cards:
            self._card_list.setCurrentRow(0)
        else:
            self._set_card_meta_labels(None)

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
            "border-radius: 8px;"
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
            "padding: 8px 14px;"
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
        self._note_type_combo.setItemText(0, "全部" if is_zh else "All")
        self._search_input.setPlaceholderText(
            "搜索卡片内容..." if is_zh else "Search card content..."
        )
        self._list_title_label.setText("卡片列表" if is_zh else "Card List")
        self._btn_prev.setText("上一张" if is_zh else "Previous")
        self._btn_next.setText("下一张" if is_zh else "Next")
        self._btn_push.setText("推送到 Anki" if is_zh else "Push to Anki")

        if 0 <= self._current_index < len(self._filtered_cards):
            self._show_card(self._current_index)
        else:
            self._set_total_count_text(len(self._filtered_cards))
            self._set_card_meta_labels(None)

    def _push_to_anki(self):
        """Push all cards to Anki."""
        if not self._all_cards:
            InfoBar.warning(
                title="警告" if self._main.config.language == "zh" else "Warning",
                content="没有卡片需要推送" if self._main.config.language == "zh" else "No cards to push",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        # Disable push button during push
        is_zh = self._main.config.language == "zh"
        self._btn_push.setEnabled(False)
        self._progress_bar.show()
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
            update_mode=config.last_update_mode or "create_only",
        )
        self._push_worker.progress.connect(self._on_push_progress)
        self._push_worker.finished.connect(self._on_push_finished)
        self._push_worker.error.connect(self._on_push_error)
        self._push_worker.cancelled.connect(self._on_push_cancelled)
        self._push_worker.start()

    def _on_push_progress(self, message: str):
        """Handle push progress message."""
        is_zh = self._main.config.language == "zh"
        self._count_label.setText(
            f"推送中：{message}" if is_zh else f"Pushing: {message}"
        )

    def _on_push_finished(self, result):
        """Handle push completion."""
        is_zh = self._main.config.language == "zh"
        self._progress_bar.hide()
        self._btn_push.setEnabled(True)

        # Only update result data and keep current page.
        self._main.result_page.load_result(result, self._all_cards)
        self._count_label.setText(
            f"推送完成，共 {len(self._all_cards)} 张"
            if is_zh
            else f"Push complete, {len(self._all_cards)} cards"
        )
        InfoBar.success(
            title="推送完成" if is_zh else "Push Complete",
            content=(
                "结果页已更新，可按需手动查看；当前保持在卡片预览页。"
                if is_zh
                else "Result page updated. Stay on card preview; open result page manually if needed."
            ),
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=3200,
            parent=self,
        )
        logger.info(
            "push finished",
            extra={"event": "ui.push.finished", "cards_count": len(self._all_cards)},
        )

    def _on_push_error(self, error: str):
        """Handle push error."""
        is_zh = self._main.config.language == "zh"
        self._progress_bar.hide()
        self._btn_push.setEnabled(True)
        self._count_label.setText("推送失败" if is_zh else "Push failed")
        InfoBar.error(
            title="错误" if is_zh else "Error",
            content=error,
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

    def _on_push_cancelled(self):
        """Handle push cancellation."""
        is_zh = self._main.config.language == "zh"
        self._progress_bar.hide()
        self._btn_push.setEnabled(True)
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
