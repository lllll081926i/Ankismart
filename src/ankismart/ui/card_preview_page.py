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

from ankismart.core.config import append_task_history, save_config
from ankismart.core.logging import get_logger
from ankismart.core.models import CardDraft
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

PREVIEW_READABILITY_CSS = """
.card[data-card-type] {
    font-size: 19px !important;
    line-height: 1.95 !important;
}

.card[data-card-type] .flat-card {
    max-width: 980px;
    margin: 0 auto;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--surface);
    box-shadow: 0 8px 20px rgba(16, 39, 72, 0.12);
    padding: 14px;
}

.night_mode .card[data-card-type] .flat-card,
.nightMode .card[data-card-type] .flat-card {
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.32);
}

.card[data-card-type] .flat-block {
    border: 1px solid var(--border);
    border-radius: 12px;
    background: #fbfdff;
    padding: 14px;
}

.card[data-card-type] .flat-block + .flat-block {
    margin-top: 12px;
}

.card[data-card-type] .flat-answer {
    border-color: #b7e1c7;
    background: #f3fcf6;
}

.card[data-card-type] .flat-explain {
    background: #f9fbff;
}

.night_mode .card[data-card-type] .flat-block,
.nightMode .card[data-card-type] .flat-block,
.night_mode .card[data-card-type] .flat-explain,
.nightMode .card[data-card-type] .flat-explain {
    background: rgba(58, 58, 58, 0.9);
}

.card[data-card-type] .flat-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-secondary);
    margin-bottom: 8px;
}

.card[data-card-type] .flat-content {
    font-size: 20px;
    line-height: 1.85;
}

.card[data-card-type] .flat-option-list {
    margin-top: 12px;
}

.card[data-card-type] .flat-option-line {
    display: block;
    margin-top: 6px;
    font-size: 20px;
    line-height: 1.85;
}

.card[data-card-type] .flat-option-key {
    font-weight: 700;
    margin-right: 6px;
}

.card[data-card-type] .flat-answer-line {
    font-size: 20px;
    line-height: 1.85;
}

.card[data-card-type] .flat-explain-wrap {
    margin-top: 6px;
}

.card[data-card-type] .flat-explain-stack {
    margin-top: 6px;
    display: grid;
    gap: 8px;
}

.card[data-card-type] .flat-explain-item {
    font-size: 20px;
    margin: 0;
    line-height: 1.85;
}

.card[data-card-type] .flat-content *,
.card[data-card-type] .flat-answer-line *,
.card[data-card-type] .flat-explain-item *,
.card[data-card-type] .flat-option-line * {
    font-size: inherit !important;
    line-height: 1.85 !important;
}
""".strip()


class CardRenderer:
    """Generates HTML for different Anki note types."""

    _OPTION_LINE_PATTERN = re.compile(r"^\s*([A-Ea-e])[\.、\):：\-]\s*(.+?)\s*$")
    _ANSWER_LINE_PATTERN = re.compile(
        r"^(?:答案|正确答案|answer)?\s*[:：]?\s*([A-Ea-e](?:\s*[,，、/]\s*[A-Ea-e])*)\s*$",
        re.IGNORECASE,
    )
    _CLOZE_PATTERN = re.compile(r"\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}", re.IGNORECASE | re.DOTALL)

    @staticmethod
    def detect_card_kind(card: CardDraft) -> str:
        """Return normalized card kind key used by UI filtering and rendering."""
        note_type = card.note_type
        tags = card.tags or []
        lower_tags = {tag.lower() for tag in tags}
        front_preview = str(card.fields.get("Front", ""))[:80]

        if "concept" in lower_tags or "概念" in front_preview:
            return "concept"
        if "key_terms" in lower_tags or "术语" in tags:
            return "key_terms"
        if "single_choice" in lower_tags or "单选" in tags:
            return "single_choice"
        if "multiple_choice" in lower_tags or "多选" in tags:
            return "multiple_choice"
        if "image" in lower_tags:
            return "image_qa"
        if note_type == "Basic (and reversed card)":
            return "basic_reversed"
        if note_type.startswith("Cloze"):
            return "cloze"
        if note_type == "Basic":
            return "basic"
        return "generic"

    @staticmethod
    def render_card(card: CardDraft) -> str:
        """Generate HTML for card preview - always show both question and answer."""
        card_kind = CardRenderer.detect_card_kind(card)

        if card_kind == "concept":
            return CardRenderer._render_concept(card)
        elif card_kind == "key_terms":
            return CardRenderer._render_key_terms(card)
        elif card_kind == "single_choice":
            return CardRenderer._render_single_choice(card)
        elif card_kind == "multiple_choice":
            return CardRenderer._render_multiple_choice(card)
        elif card_kind == "image_qa":
            return CardRenderer._render_image_qa(card)
        elif card_kind == "basic":
            return CardRenderer._render_basic(card)
        elif card_kind == "basic_reversed":
            return CardRenderer._render_basic_reversed(card)
        elif card_kind == "cloze":
            return CardRenderer._render_cloze(card)
        else:
            return CardRenderer._render_generic(card)

    @staticmethod
    def _format_text_block(text: str, *, empty_text: str = "（空）") -> str:
        """Format raw field text for HTML display."""
        value = text.strip()
        if not value:
            return f'<span class="empty-placeholder">{empty_text}</span>'
        return value.replace("\r\n", "\n").replace("\n", "<br>")

    @staticmethod
    def _extract_plain_lines(text: str) -> list[str]:
        """Extract plain text lines from html/plain content."""
        if not text:
            return []
        plain = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        plain = re.sub(r"</p\s*>", "\n", plain, flags=re.IGNORECASE)
        plain = re.sub(r"<[^>]+>", "", plain)
        return [line.strip() for line in plain.splitlines() if line.strip()]

    @staticmethod
    def _strip_leading_index(text: str) -> str:
        """Remove auto-generated leading line indexes like `1. ` before content."""
        return re.sub(r"^\s*\d+[\.、\):：\-]\s*", "", text or "").strip()

    @staticmethod
    def _normalize_html_to_text(text: str) -> str:
        if not text:
            return ""
        plain = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        plain = re.sub(r"</p\s*>", "\n", plain, flags=re.IGNORECASE)
        plain = re.sub(r"<[^>]+>", " ", plain)
        plain = plain.replace("\r", "")
        plain = re.sub(r"\n{3,}", "\n\n", plain)
        return plain.strip()

    @staticmethod
    def _extract_answer_keys(raw: str) -> list[str]:
        """Extract unique answer keys in stable order."""
        keys: list[str] = []
        for key in re.findall(r"[A-Ea-e]", raw):
            key = key.upper()
            if key not in keys:
                keys.append(key)
        return keys

    @staticmethod
    def _parse_choice_front(front: str) -> tuple[str, list[tuple[str, str]]]:
        """Parse question/options from front field."""
        plain = CardRenderer._normalize_html_to_text(front)
        lines = [line.strip() for line in plain.splitlines() if line.strip()]
        options: list[tuple[str, str]] = []
        question_lines: list[str] = []

        for line in lines:
            match = CardRenderer._OPTION_LINE_PATTERN.match(line)
            if match:
                options.append((match.group(1).upper(), match.group(2).strip()))
            elif not options:
                question_lines.append(line)

        if not options:
            compact = re.sub(r"\s+", " ", plain).strip()
            inline_matches = list(re.finditer(r"(^|\s)([A-Ea-e])[\.、\):：\-]\s*", compact))
            if len(inline_matches) >= 2:
                question = compact[: inline_matches[0].start(2)].strip()
                for i, match in enumerate(inline_matches):
                    key = match.group(2).upper()
                    start = match.end()
                    end = (
                        inline_matches[i + 1].start(2)
                        if i + 1 < len(inline_matches)
                        else len(compact)
                    )
                    option_text = compact[start:end].strip(" ;；")
                    if option_text:
                        options.append((key, option_text))
                if options:
                    return question, options

            return plain, []
        question = "\n".join(question_lines) if question_lines else lines[0]
        return question, options

    @staticmethod
    def _parse_choice_back(back: str) -> tuple[list[str], str]:
        """Parse answer keys and explanation from back field."""
        lines = CardRenderer._extract_plain_lines(back)
        if not lines:
            return [], ""

        first = lines[0]
        match = CardRenderer._ANSWER_LINE_PATTERN.match(first)
        if match:
            return CardRenderer._extract_answer_keys(match.group(1)), "\n".join(lines[1:]).strip()

        if re.fullmatch(r"[A-Ea-e](?:\s*[,，、/]\s*[A-Ea-e])*", first):
            return CardRenderer._extract_answer_keys(first), "\n".join(lines[1:]).strip()

        prefixed = re.match(
            r"^([A-Ea-e](?:\s*[,，、/]\s*[A-Ea-e])*)(?:[\.、\):：\-]\s*|\s+)(.+)$",
            first,
        )
        if prefixed:
            keys = CardRenderer._extract_answer_keys(prefixed.group(1))
            explanation_lines = [prefixed.group(2).strip(), *lines[1:]]
            explanation = "\n".join(line for line in explanation_lines if line).strip()
            return keys, explanation

        whole = "\n".join(lines)
        inline = re.search(
            r"(?:答案|正确答案|answer)\s*[:：]?\s*([A-Ea-e](?:\s*[,，、/]\s*[A-Ea-e])*)",
            whole,
            re.IGNORECASE,
        )
        if inline:
            keys = CardRenderer._extract_answer_keys(inline.group(1))
            explanation = whole.replace(inline.group(0), "", 1).strip(" \n:：")
            return keys, explanation

        return [], whole

    @staticmethod
    def _split_explanation_sections(explanation: str) -> list[str]:
        text = (explanation or "").strip()
        if not text:
            return []

        lines = [
            CardRenderer._strip_leading_index(line.strip())
            for line in text.replace("\r", "").split("\n")
            if line.strip()
        ]
        lines = [line for line in lines if line]
        if lines:
            marker_with_text = re.match(
                r"^(?:解析|explanation)\s*[:：]\s*(.+)$", lines[0], re.IGNORECASE
            )
            if marker_with_text:
                lines[0] = marker_with_text.group(1).strip()
            while lines and re.match(
                r"^(?:解析|explanation)\s*[:：]?\s*$", lines[0], re.IGNORECASE
            ):
                lines = lines[1:]
        if len(lines) >= 2:
            return lines

        sentences = [
            part.strip() for part in re.split(r"(?<=[。！？!?；;])\s*", lines[0]) if part.strip()
        ]
        if len(sentences) <= 1:
            return lines

        sections: list[str] = []
        buffer = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if buffer and len(buffer) + len(sentence) > 44:
                sections.append(buffer.strip())
                buffer = sentence
            else:
                buffer = f"{buffer} {sentence}".strip()
        if buffer:
            sections.append(buffer.strip())
        return sections

    @staticmethod
    def _parse_answer_and_explanation(raw: str) -> tuple[str, str]:
        lines = CardRenderer._extract_plain_lines(raw)
        if not lines:
            return "", ""
        lines = [CardRenderer._strip_leading_index(line) for line in lines if line.strip()]
        lines = [line for line in lines if line]
        if not lines:
            return "", ""

        first = lines[0]
        answer_match = re.match(r"^(?:答案|正确答案|answer)\s*[:：]\s*(.+)$", first, re.IGNORECASE)
        if answer_match:
            answer = answer_match.group(1).strip()
            remaining = lines[1:]
        else:
            answer = first.strip()
            remaining = lines[1:]

        if remaining:
            marker_with_text = re.match(
                r"^(?:解析|explanation)\s*[:：]\s*(.+)$",
                remaining[0],
                re.IGNORECASE,
            )
            marker_only = re.match(
                r"^(?:解析|explanation)\s*[:：]?\s*$", remaining[0], re.IGNORECASE
            )
            if marker_with_text:
                remaining = [marker_with_text.group(1).strip(), *remaining[1:]]
            elif marker_only:
                remaining = remaining[1:]

        explanation = "\n".join(line for line in remaining if line).strip()
        if not explanation:
            sentences = [
                part.strip() for part in re.split(r"(?<=[。！？!?；;])\s*", answer) if part.strip()
            ]
            if len(sentences) >= 2:
                answer = sentences[0]
                explanation = "\n".join(sentences[1:]).strip()

        return answer, explanation

    @staticmethod
    def _render_explanation_html(explanation: str) -> str:
        sections = CardRenderer._split_explanation_sections(explanation)
        if not sections:
            return (
                '<div class="flat-explain-item">'
                '<span class="empty-placeholder">（无解析）</span>'
                "</div>"
            )
        if len(sections) == 1:
            return (
                '<div class="flat-explain-item">'
                f"{CardRenderer._format_text_block(sections[0])}"
                "</div>"
            )
        items = "".join(
            (f'<div class="flat-explain-item">{CardRenderer._format_text_block(section)}</div>')
            for section in sections
        )
        return f'<div class="flat-explain-stack">{items}</div>'

    @staticmethod
    def _render_three_blocks(*, question_html: str, answer_html: str, explanation: str) -> str:
        explanation_html = CardRenderer._render_explanation_html(explanation)
        return f"""
        <div class="flat-card">
            <section class="flat-block flat-question">
                <div class="flat-title">问题</div>
                <div class="flat-content">{question_html}</div>
            </section>
            <section class="flat-block flat-answer">
                <div class="flat-title">答案</div>
                <div class="flat-answer-line">{answer_html}</div>
            </section>
            <section class="flat-block flat-explain">
                <div class="flat-title">解析</div>
                <div class="flat-explain-wrap">{explanation_html}</div>
            </section>
        </div>
        """

    @staticmethod
    def _render_choice_card(
        *,
        question: str,
        options: list[tuple[str, str]],
        answer_text: str,
        explanation: str,
    ) -> str:
        question_html = CardRenderer._format_text_block(question, empty_text="（空问题）")
        option_rows = "".join(
            (
                '<div class="flat-option-line">'
                f'<span class="flat-option-key">{key}.</span>'
                f'<span class="flat-option-text">{CardRenderer._format_text_block(text)}</span>'
                "</div>"
            )
            for key, text in options
        )
        options_html = f'<div class="flat-option-list">{option_rows}</div>' if option_rows else ""
        question_block_html = f"{question_html}{options_html}"

        answer_html = CardRenderer._format_text_block(answer_text, empty_text="（未标注）")
        return CardRenderer._render_three_blocks(
            question_html=question_block_html,
            answer_html=answer_html,
            explanation=explanation,
        )

    @staticmethod
    def _render_basic(card: CardDraft) -> str:
        """Render Basic note type as question/answer/explanation."""
        question_html = CardRenderer._format_text_block(card.fields.get("Front", ""))
        answer_raw = card.fields.get("Back", "")
        answer_text, explanation = CardRenderer._parse_answer_and_explanation(answer_raw)
        if not answer_text:
            answer_text = CardRenderer._normalize_html_to_text(answer_raw)
        answer_html = CardRenderer._format_text_block(answer_text, empty_text="（空）")
        content = CardRenderer._render_three_blocks(
            question_html=question_html,
            answer_html=answer_html,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "basic")

    @staticmethod
    def _render_basic_reversed(card: CardDraft) -> str:
        """Render reversed basic cards with same visual style as basic cards."""
        return CardRenderer._render_basic(card)

    @staticmethod
    def _render_cloze(card: CardDraft) -> str:
        """Render Cloze note type as question/answer/explanation."""
        text = card.fields.get("Text", "")
        cloze_entries: list[tuple[str, str, str]] = []

        def _replace_cloze(match: re.Match[str]) -> str:
            idx = match.group(1)
            answer = (match.group(2) or "").strip()
            hint = (match.group(3) or "").strip()
            cloze_entries.append((idx, answer, hint))
            return f"[C{idx}: ____]"

        question_plain = CardRenderer._CLOZE_PATTERN.sub(_replace_cloze, text)
        question_html = CardRenderer._format_text_block(question_plain, empty_text="（无填空内容）")

        if cloze_entries:
            answer_lines = []
            for idx, answer, hint in cloze_entries:
                line = f"C{idx}: {answer or '（空）'}"
                if hint:
                    line = f"{line}（提示：{hint}）"
                answer_lines.append(line)
            answer_text = "\n".join(answer_lines)
        else:
            answer_text = "（未检测到有效填空标记）"

        answer_html = CardRenderer._format_text_block(answer_text, empty_text="（空）")
        explanation = CardRenderer._normalize_html_to_text(card.fields.get("Extra", ""))
        content = CardRenderer._render_three_blocks(
            question_html=question_html,
            answer_html=answer_html,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "cloze")

    @staticmethod
    def _render_concept(card: CardDraft) -> str:
        """Render concept cards as question/answer/explanation."""
        question_html = CardRenderer._format_text_block(card.fields.get("Front", ""))
        back_raw = card.fields.get("Back", "")
        answer_text, explanation = CardRenderer._parse_answer_and_explanation(back_raw)
        if not answer_text:
            answer_text = CardRenderer._normalize_html_to_text(back_raw)
        answer_html = CardRenderer._format_text_block(answer_text, empty_text="（空）")
        content = CardRenderer._render_three_blocks(
            question_html=question_html,
            answer_html=answer_html,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "concept")

    @staticmethod
    def _render_key_terms(card: CardDraft) -> str:
        """Render key term cards as question/answer/explanation."""
        question_html = CardRenderer._format_text_block(card.fields.get("Front", ""))
        back_raw = card.fields.get("Back", "")
        answer_text, explanation = CardRenderer._parse_answer_and_explanation(back_raw)
        if not answer_text:
            answer_text = CardRenderer._normalize_html_to_text(back_raw)
        answer_html = CardRenderer._format_text_block(answer_text, empty_text="（空）")
        content = CardRenderer._render_three_blocks(
            question_html=question_html,
            answer_html=answer_html,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "keyterm")

    @staticmethod
    def _render_single_choice(card: CardDraft) -> str:
        """Render single choice question cards."""
        question, options = CardRenderer._parse_choice_front(card.fields.get("Front", ""))
        keys, explanation = CardRenderer._parse_choice_back(card.fields.get("Back", ""))
        if keys:
            keys = keys[:1]

        answer_text = ", ".join(keys) if keys else "（未标注）"
        content = CardRenderer._render_choice_card(
            question=question,
            options=options,
            answer_text=answer_text,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "choice")

    @staticmethod
    def _render_multiple_choice(card: CardDraft) -> str:
        """Render multiple choice question cards."""
        question, options = CardRenderer._parse_choice_front(card.fields.get("Front", ""))
        keys, explanation = CardRenderer._parse_choice_back(card.fields.get("Back", ""))

        answer_text = ", ".join(keys) if keys else "（未标注）"
        content = CardRenderer._render_choice_card(
            question=question,
            options=options,
            answer_text=answer_text,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "choice")

    @staticmethod
    def _render_image_qa(card: CardDraft) -> str:
        """Render image Q&A cards as question/answer/explanation."""
        question_html = CardRenderer._format_text_block(card.fields.get("Front", ""))
        back_raw = card.fields.get("Back", "")
        answer_text, explanation = CardRenderer._parse_answer_and_explanation(back_raw)
        if not answer_text:
            answer_text = CardRenderer._normalize_html_to_text(back_raw)
        answer_html = CardRenderer._format_text_block(answer_text, empty_text="（空）")
        content = CardRenderer._render_three_blocks(
            question_html=question_html,
            answer_html=answer_html,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "image")

    @staticmethod
    def _render_generic(card: CardDraft) -> str:
        """Render unknown note types using unified question/answer/explanation layout."""
        question_source = ""
        for key in ("Front", "Question", "Text"):
            value = (card.fields.get(key, "") or "").strip()
            if value:
                question_source = value
                break
        if not question_source and card.fields:
            question_source = next(iter(card.fields.values()))

        answer_source = ""
        for key in ("Back", "Answer", "Extra"):
            value = (card.fields.get(key, "") or "").strip()
            if value:
                answer_source = value
                break
        if not answer_source:
            leftovers = [
                value
                for key, value in card.fields.items()
                if key not in {"Front", "Question", "Text"} and str(value).strip()
            ]
            answer_source = "\n".join(str(value) for value in leftovers).strip()

        answer_text, explanation = CardRenderer._parse_answer_and_explanation(answer_source)
        if not answer_text:
            answer_text = CardRenderer._normalize_html_to_text(answer_source)

        content = CardRenderer._render_three_blocks(
            question_html=CardRenderer._format_text_block(question_source, empty_text="（空问题）"),
            answer_html=CardRenderer._format_text_block(answer_text, empty_text="（空）"),
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "generic")

    @staticmethod
    def _wrap_html(content: str, card_type: str = "basic") -> str:
        """Wrap content with CSS and card structure."""
        from ankismart.anki_gateway.styling import MODERN_CARD_CSS, PREVIEW_CARD_EXTRA_CSS

        # Keep both class names for compatibility with historical CSS selectors.
        body_class = "night_mode nightMode" if isDarkTheme() else ""

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
            {MODERN_CARD_CSS}
            {PREVIEW_CARD_EXTRA_CSS}
            {PREVIEW_READABILITY_CSS}
            </style>
        </head>
        <body class="{body_class}">
            <div class="card" data-card-type="{card_type}">{content}</div>
        </body>
        </html>
        """


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
        self._tags_label.setWordWrap(True)
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

        self._btn_export_json = PushButton(
            "导出为 JSON" if self._main.config.language == "zh" else "Export JSON"
        )
        self._btn_export_json.setIcon(FluentIcon.DICTIONARY)
        self._btn_export_json.clicked.connect(self._export_json)
        layout.addWidget(self._btn_export_json)

        self._btn_push_preview = PushButton(
            "推送预演" if self._main.config.language == "zh" else "Push Preview"
        )
        self._btn_push_preview.setIcon(FluentIcon.VIEW)
        self._btn_push_preview.clicked.connect(self._show_push_preview)
        layout.addWidget(self._btn_push_preview)

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
        self._deck_label.setText(f"牌组: {card.deck_name}" if is_zh else f"Deck: {card.deck_name}")
        self._tags_label.setText(f"标签: {tags_text}" if is_zh else f"Tags: {tags_text}")

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

        self._filtered_cards = filtered
        self._refresh_card_list()

    def _refresh_card_list(self):
        """Refresh the card list widget."""
        self._card_list.clear()

        for card in self._filtered_cards:
            question = self._get_card_question_text(card)
            item = QListWidgetItem(question)
            self._card_list.addItem(item)

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
        self._list_title_label.setText("问题列表" if is_zh else "Questions")
        self._btn_prev.setText("上一张" if is_zh else "Previous")
        self._btn_next.setText("下一张" if is_zh else "Next")
        self._btn_export_apkg.setText("导出为 APKG" if is_zh else "Export as APKG")
        self._btn_export_csv.setText("导出为 CSV" if is_zh else "Export CSV")
        self._btn_export_json.setText("导出为 JSON" if is_zh else "Export JSON")
        self._btn_push_preview.setText("推送预演" if is_zh else "Push Preview")
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
            summary=(
                "推送成功 "
                f"{succeeded} 张，"
                f"失败 {failed} 张"
            ),
            payload={
                "cards_total": len(self._all_cards),
                "cards_succeeded": succeeded,
                "cards_failed": failed,
                "duration_seconds": round(elapsed, 2),
            },
        )
        save_config(self._main.config)

    def _on_push_error(self, error: str):
        """Handle push error."""
        self._cleanup_push_worker()
        is_zh = self._main.config.language == "zh"
        elapsed = max(0.0, time.monotonic() - self._push_start_ts) if self._push_start_ts else 0.0
        self._progress_bar.hide()
        self._set_action_buttons_enabled(True)
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
        save_config(self._main.config)

    def _on_export_error(self, error: str) -> None:
        is_zh = self._main.config.language == "zh"
        elapsed = (
            max(0.0, time.monotonic() - self._export_start_ts) if self._export_start_ts else 0.0
        )
        self._cleanup_export_worker()
        self._progress_bar.hide()
        self._set_action_buttons_enabled(True)
        self._count_label.setText("导出失败" if is_zh else "Export failed")

        InfoBar.error(
            title="导出失败" if is_zh else "Export Failed",
            content=error,
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
        self._btn_export_json.setEnabled(enabled)
        self._btn_push_preview.setEnabled(enabled)

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
            getattr(self._main.config, "last_update_mode", "create_or_update")
            or "create_or_update"
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
            self._export_worker.requestInterruption()
            self._export_worker.wait(300)
        self._cleanup_push_worker()
        self._cleanup_export_worker()
        super().closeEvent(event)
