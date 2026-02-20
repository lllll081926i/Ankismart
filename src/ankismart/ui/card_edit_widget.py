from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import (
    BodyLabel,
    LineEdit,
    MessageBoxBase,
    PlainTextEdit,
    SubtitleLabel,
)

from ankismart.core.models import CardDraft
from ankismart.ui.i18n import t


class CardEditDialog(MessageBoxBase):
    """Modal dialog for editing a single card's fields and tags."""

    def __init__(self, card: CardDraft, lang: str = "zh", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._card = card
        self._lang = lang
        self._field_editors: dict[str, PlainTextEdit] = {}
        self._tags_editor: LineEdit | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        # Title
        title = t("card_edit.title", self._lang)
        self.titleLabel = SubtitleLabel(title, self)
        self.viewLayout.addWidget(self.titleLabel)

        # Card fields
        for field_name, field_value in self._card.fields.items():
            field_label = BodyLabel(field_name, self)
            field_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            self.viewLayout.addWidget(field_label)

            editor = PlainTextEdit(self)
            editor.setPlainText(field_value)
            editor.setMinimumHeight(80)
            editor.setMaximumHeight(150)
            self.viewLayout.addWidget(editor)
            self._field_editors[field_name] = editor

        # Tags
        tags_label = BodyLabel(t("card_edit.tags", self._lang), self)
        tags_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.viewLayout.addWidget(tags_label)

        self._tags_editor = LineEdit(self)
        self._tags_editor.setText(", ".join(self._card.tags))
        self._tags_editor.setPlaceholderText(t("card_edit.tags_placeholder", self._lang))
        self.viewLayout.addWidget(self._tags_editor)

        # Deck name
        deck_label = BodyLabel(t("card_edit.deck", self._lang), self)
        deck_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        self.viewLayout.addWidget(deck_label)

        self._deck_editor = LineEdit(self)
        self._deck_editor.setText(self._card.deck_name)
        self._deck_editor.setPlaceholderText("Default")
        self.viewLayout.addWidget(self._deck_editor)

        # Button text
        self.yesButton.setText(t("common.ok", self._lang))
        self.cancelButton.setText(t("common.cancel", self._lang))

        self.widget.setMinimumWidth(500)

    def get_edited_card(self) -> CardDraft:
        """Get the card with edited values."""
        # Update fields
        for field_name, editor in self._field_editors.items():
            self._card.fields[field_name] = editor.toPlainText()

        # Update tags
        if self._tags_editor:
            tags_text = self._tags_editor.text().strip()
            self._card.tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]

        # Update deck name
        if self._deck_editor:
            deck_name = self._deck_editor.text().strip()
            if deck_name:
                self._card.deck_name = deck_name

        return self._card


class CardEditWidget(QWidget):
    """Card editor widget with lightweight logic for card field updates."""

    cards_changed = pyqtSignal()

    def __init__(self, cards: list[CardDraft] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: list[CardDraft] = list(cards or [])
        self._current_index = -1
        self._field_editors: dict[str, Any] = {}
        self._list = None

    def set_cards(self, cards: list[CardDraft]) -> None:
        self._save_current()
        self._cards = list(cards)
        self._current_index = -1

    def get_cards(self) -> list[CardDraft]:
        self._save_current()
        return list(self._cards)

    def _save_current(self) -> None:
        if not (0 <= self._current_index < len(self._cards)):
            return

        card = self._cards[self._current_index]
        changed = False
        for field_name, editor in self._field_editors.items():
            if not hasattr(editor, "toPlainText"):
                continue
            text = editor.toPlainText()
            if card.fields.get(field_name) != text:
                card.fields[field_name] = text
                changed = True

        if not changed:
            return

        item = self._list.item(self._current_index) if self._list and hasattr(self._list, "item") else None
        if item is not None and hasattr(item, "setText"):
            item.setText(self._card_title(card))

        signal = getattr(self, "cards_changed", None)
        if signal is not None and hasattr(signal, "emit"):
            signal.emit()

    @staticmethod
    def _card_title(card: CardDraft) -> str:
        if not card.fields:
            return ""
        first_value = next(iter(card.fields.values()))
        return first_value if len(first_value) <= 48 else f"{first_value[:45]}..."
