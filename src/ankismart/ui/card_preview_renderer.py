"""Shared card preview rendering utilities."""

from __future__ import annotations

import re

from qfluentwidgets import isDarkTheme

from ankismart.card_gen.card_format_parsers import (
    normalize_html_to_text,
    parse_answer_block,
    parse_choice_back,
    parse_choice_front,
    strip_leading_index,
)
from ankismart.card_gen.card_kind import detect_card_kind
from ankismart.core.models import CardDraft

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

.card[data-card-type] .flat-section-spacer {
    height: 18px;
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

.card[data-card-type] .flat-focus-line {
    display: inline-block;
    padding: 6px 12px;
    border-radius: 10px;
    background: linear-gradient(135deg, rgba(255, 244, 214, 0.92), rgba(255, 232, 176, 0.9));
    color: #8a4b00;
    font-size: 22px;
    font-weight: 800;
    line-height: 1.65;
}

.night_mode .card[data-card-type] .flat-focus-line,
.nightMode .card[data-card-type] .flat-focus-line {
    background: linear-gradient(135deg, rgba(131, 92, 22, 0.88), rgba(96, 67, 18, 0.84));
    color: #ffd980;
}

.card[data-card-type] .flat-keyword {
    color: #a24b00;
    font-weight: 800;
}

.night_mode .card[data-card-type] .flat-keyword,
.nightMode .card[data-card-type] .flat-keyword {
    color: #ffb86b;
}

.card[data-card-type] .flat-option-list {
    margin-top: 12px;
    display: grid;
    gap: 8px;
}

.card[data-card-type] .flat-option-line {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: start;
    column-gap: 10px;
    font-size: 20px;
    line-height: 1.85;
    padding: 10px 12px;
    border-radius: 10px;
    background: rgba(36, 96, 168, 0.05);
}

.card[data-card-type] .flat-option-key {
    font-weight: 700;
    color: #245fa8;
}

.card[data-card-type] .flat-answer-stack {
    display: grid;
    gap: 10px;
}

.card[data-card-type] .flat-answer-item {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: start;
    column-gap: 10px;
    padding: 10px 12px;
    border-radius: 10px;
    background: rgba(46, 125, 50, 0.08);
}

.card[data-card-type] .flat-answer-key {
    font-weight: 800;
    color: #2e7d32;
}

.card[data-card-type] .flat-answer-text {
    font-size: 20px;
    line-height: 1.85;
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

CARD_KIND_LABELS = {
    "basic": ("基础问答", "Basic Q&A"),
    "basic_reversed": ("双向基础卡", "Reversed Basic"),
    "cloze": ("填空题", "Cloze"),
    "concept": ("概念解释", "Concept"),
    "key_terms": ("关键术语", "Key Terms"),
    "single_choice": ("单选题", "Single Choice"),
    "multiple_choice": ("多选题", "Multiple Choice"),
    "image_qa": ("图片问答", "Image Q&A"),
    "generic": ("通用卡片", "Generic"),
}

QUALITY_FLAG_TEXTS = {
    "missing_explanation": ("缺少解析", "Explanation missing"),
    "too_short": ("内容过短", "Content too short"),
    "cloze_syntax_invalid": ("填空语法无效", "Invalid cloze syntax"),
    "multiple_answers_in_single_choice": (
        "单选题检测到多个答案",
        "Multiple answers detected in single choice",
    ),
}


def format_quality_flags(flags: list[str], lang: str) -> str:
    values = []
    for flag in flags:
        if not flag:
            continue
        zh_text, en_text = QUALITY_FLAG_TEXTS.get(flag, (flag, flag))
        values.append(zh_text if lang == "zh" else en_text)
    return ", ".join(values)


class CardRenderer:
    """Generates HTML for different Anki note types."""

    _CLOZE_PATTERN = re.compile(r"\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}", re.IGNORECASE | re.DOTALL)

    @staticmethod
    def detect_card_kind(card: CardDraft) -> str:
        if card.note_type == "Basic (and reversed card)":
            return "basic_reversed"
        return detect_card_kind(card)

    @staticmethod
    def render_card(card: CardDraft) -> str:
        card_kind = CardRenderer.detect_card_kind(card)

        if card_kind == "concept":
            return CardRenderer._render_concept(card)
        if card_kind == "key_terms":
            return CardRenderer._render_key_terms(card)
        if card_kind == "single_choice":
            return CardRenderer._render_single_choice(card)
        if card_kind == "multiple_choice":
            return CardRenderer._render_multiple_choice(card)
        if card_kind == "image_qa":
            return CardRenderer._render_image_qa(card)
        if card_kind == "basic":
            return CardRenderer._render_basic(card)
        if card_kind == "basic_reversed":
            return CardRenderer._render_basic_reversed(card)
        if card_kind == "cloze":
            return CardRenderer._render_cloze(card)
        return CardRenderer._render_generic(card)

    @staticmethod
    def _format_text_block(text: str, *, empty_text: str = "（空）") -> str:
        value = text.strip()
        if not value:
            return f'<span class="empty-placeholder">{empty_text}</span>'
        return CardRenderer._highlight_keywords(value).replace("\r\n", "\n").replace("\n", "<br>")

    @staticmethod
    def _highlight_keywords(text: str) -> str:
        highlighted_lines: list[str] = []
        for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw_line.strip()
            if not line:
                highlighted_lines.append("")
                continue
            line = re.sub(
                r"^(?P<label>[A-Ea-e]|C\d+)(?P<sep>[\.、\):：\-])\s*",
                lambda match: (
                    f'<span class="flat-keyword">{match.group("label").upper()}</span>'
                    f"{match.group('sep')} "
                ),
                line,
            )
            line = re.sub(
                r"^(?P<label>[^:：<>\n]{1,10})(?P<sep>[:：])\s*",
                lambda match: (
                    f'<span class="flat-keyword">{match.group("label").strip()}</span>'
                    f"{match.group('sep')} "
                ),
                line,
            )
            highlighted_lines.append(line)
        return "\n".join(highlighted_lines)

    @staticmethod
    def _render_focus_line(text: str, *, empty_text: str = "（空）") -> str:
        value = text.strip()
        if not value:
            return f'<span class="empty-placeholder">{empty_text}</span>'
        content = CardRenderer._format_text_block(value, empty_text=empty_text)
        return f'<div class="flat-focus-line">{content}</div>'

    @staticmethod
    def _render_answer_items(items: list[tuple[str, str]], *, empty_text: str = "（空）") -> str:
        if not items:
            return CardRenderer._format_text_block("", empty_text=empty_text)
        rows = "".join(
            (
                '<div class="flat-answer-item">'
                f'<span class="flat-answer-key">{CardRenderer._highlight_keywords(key)}</span>'
                f'<span class="flat-answer-text">'
                f"{CardRenderer._format_text_block(text, empty_text=empty_text)}"
                "</span>"
                "</div>"
            )
            for key, text in items
        )
        return f'<div class="flat-answer-stack">{rows}</div>'

    @staticmethod
    def _strip_leading_index(text: str) -> str:
        return strip_leading_index(text)

    @staticmethod
    def _normalize_html_to_text(text: str) -> str:
        return normalize_html_to_text(text)

    @staticmethod
    def _parse_choice_front(front: str) -> tuple[str, list[tuple[str, str]]]:
        return parse_choice_front(front)

    @staticmethod
    def _parse_choice_back(back: str) -> tuple[list[str], str]:
        keys, explanation_lines = parse_choice_back(back)
        return keys, "\n".join(explanation_lines).strip()

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
        return parse_answer_block(raw)

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
            f'<div class="flat-explain-item">{CardRenderer._format_text_block(section)}</div>'
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
            <div class="flat-section-spacer"></div>
            <section class="flat-block flat-answer">
                <div class="flat-title">答案</div>
                <div class="flat-answer-line">{answer_html}</div>
            </section>
            <div class="flat-section-spacer"></div>
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
        answer_keys: list[str],
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

        option_map = {key.upper(): text for key, text in options}
        answer_items = [
            (key, option_map.get(key.upper(), "（未标注选项内容）")) for key in answer_keys
        ]
        answer_html = CardRenderer._render_answer_items(answer_items, empty_text="（未标注）")
        return CardRenderer._render_three_blocks(
            question_html=question_block_html,
            answer_html=answer_html,
            explanation=explanation,
        )

    @staticmethod
    def _render_basic(card: CardDraft) -> str:
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
        return CardRenderer._render_basic(card)

    @staticmethod
    def _render_cloze(card: CardDraft) -> str:
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
            answer_items = []
            for idx, answer, hint in cloze_entries:
                item_text = answer or "（空）"
                if hint:
                    item_text = f"{item_text}\n提示：{hint}"
                answer_items.append((f"C{idx}", item_text))
        else:
            answer_items = []

        answer_html = CardRenderer._render_answer_items(
            answer_items,
            empty_text="（未检测到有效填空标记）",
        )
        explanation = CardRenderer._normalize_html_to_text(card.fields.get("Extra", ""))
        content = CardRenderer._render_three_blocks(
            question_html=question_html,
            answer_html=answer_html,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "cloze")

    @staticmethod
    def _render_concept(card: CardDraft) -> str:
        question_html = CardRenderer._render_focus_line(
            card.fields.get("Front", ""),
            empty_text="（空问题）",
        )
        back_raw = card.fields.get("Back", "")
        answer_text, explanation = CardRenderer._parse_answer_and_explanation(back_raw)
        if not answer_text:
            answer_text = CardRenderer._normalize_html_to_text(back_raw)
        answer_html = CardRenderer._render_answer_items(
            [("概念要点", answer_text)],
            empty_text="（空）",
        )
        content = CardRenderer._render_three_blocks(
            question_html=question_html,
            answer_html=answer_html,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "concept")

    @staticmethod
    def _render_key_terms(card: CardDraft) -> str:
        question_html = CardRenderer._render_focus_line(
            card.fields.get("Front", ""),
            empty_text="（空问题）",
        )
        back_raw = card.fields.get("Back", "")
        answer_text, explanation = CardRenderer._parse_answer_and_explanation(back_raw)
        if not answer_text:
            answer_text = CardRenderer._normalize_html_to_text(back_raw)
        answer_html = CardRenderer._render_answer_items(
            [("术语要点", answer_text)],
            empty_text="（空）",
        )
        content = CardRenderer._render_three_blocks(
            question_html=question_html,
            answer_html=answer_html,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "keyterm")

    @staticmethod
    def _render_single_choice(card: CardDraft) -> str:
        question, options = CardRenderer._parse_choice_front(card.fields.get("Front", ""))
        keys, explanation = CardRenderer._parse_choice_back(card.fields.get("Back", ""))
        if keys:
            keys = keys[:1]

        content = CardRenderer._render_choice_card(
            question=question,
            options=options,
            answer_keys=keys,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "choice")

    @staticmethod
    def _render_multiple_choice(card: CardDraft) -> str:
        question, options = CardRenderer._parse_choice_front(card.fields.get("Front", ""))
        keys, explanation = CardRenderer._parse_choice_back(card.fields.get("Back", ""))

        content = CardRenderer._render_choice_card(
            question=question,
            options=options,
            answer_keys=keys,
            explanation=explanation,
        )
        return CardRenderer._wrap_html(content, "choice")

    @staticmethod
    def _render_image_qa(card: CardDraft) -> str:
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
        from ankismart.anki_gateway.styling import MODERN_CARD_CSS, PREVIEW_CARD_EXTRA_CSS

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
