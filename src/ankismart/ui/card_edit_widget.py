from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.models import CardDraft
from ankismart.ui.styles import Colors


class CardEditWidget(QWidget):
    """Card list + editor panel for reviewing and editing generated cards."""

    cards_changed = Signal()  # emitted when cards are modified (edit/delete)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cards: list[CardDraft] = []
        self._current_index: int = -1
        self._field_editors: dict[str, QPlainTextEdit] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # -- Left: card list --
        left = QVBoxLayout()
        left.setSpacing(6)

        list_label = QLabel("卡片列表")
        list_label.setStyleSheet(f"font-weight: 600; color: {Colors.TEXT_SECONDARY};")
        left.addWidget(list_label)

        self._list = QListWidget()
        self._list.setMaximumWidth(260)
        self._list.setMinimumWidth(200)
        self._list.currentRowChanged.connect(self._on_row_changed)
        left.addWidget(self._list)

        self._btn_delete = QPushButton("删除选中卡片")
        self._btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_delete.setStyleSheet(
            f"color: {Colors.ERROR}; border-color: {Colors.ERROR};"
        )
        self._btn_delete.clicked.connect(self._delete_current)
        left.addWidget(self._btn_delete)

        layout.addLayout(left)

        # -- Right: editor area --
        self._right_layout = QVBoxLayout()
        self._right_layout.setSpacing(10)

        self._type_label = QLabel("")
        self._type_label.setStyleSheet(
            f"background-color: {Colors.PRIMARY}22;"
            f" color: {Colors.PRIMARY};"
            " padding: 4px 12px;"
            " border-radius: 4px;"
            " font-weight: 600;"
            " font-size: 13px;"
        )
        self._type_label.setFixedHeight(28)
        self._type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._type_label.hide()

        type_row = QHBoxLayout()
        type_row.addWidget(self._type_label)
        type_row.addStretch()
        self._right_layout.addLayout(type_row)

        # Placeholder for dynamic field editors
        self._fields_container = QVBoxLayout()
        self._fields_container.setSpacing(8)
        self._right_layout.addLayout(self._fields_container)

        self._right_layout.addStretch()
        layout.addLayout(self._right_layout, 1)

    # -- Public API --

    def set_cards(self, cards: list[CardDraft]) -> None:
        """Load cards into the widget."""
        self._save_current()
        self._cards = cards
        self._current_index = -1
        self._refresh_list()
        if self._cards:
            self._list.setCurrentRow(0)
        else:
            self._clear_editor()

    def get_cards(self) -> list[CardDraft]:
        """Return the (possibly edited) card list."""
        self._save_current()
        return list(self._cards)

    # -- Internal --

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for i, card in enumerate(self._cards):
            preview = next(iter(card.fields.values()), "")
            # Strip HTML for display
            clean = preview.replace("<br>", " ").replace("<br/>", " ")
            # Truncate
            if len(clean) > 60:
                clean = clean[:57] + "..."
            item = QListWidgetItem(f"{i + 1}. [{card.note_type}] {clean}")
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_row_changed(self, new_index: int) -> None:
        if new_index < 0 or new_index >= len(self._cards):
            return
        self._save_current()
        self._current_index = new_index
        self._load_card(self._cards[new_index])

    def _load_card(self, card: CardDraft) -> None:
        self._clear_editor()
        self._type_label.setText(card.note_type)
        self._type_label.show()

        self._field_editors.clear()
        for key, value in card.fields.items():
            label = QLabel(key)
            label.setStyleSheet(f"font-weight: 600; color: {Colors.TEXT_SECONDARY};")
            self._fields_container.addWidget(label)

            editor = QPlainTextEdit()
            editor.setPlainText(value)
            editor.setMinimumHeight(80)
            self._fields_container.addWidget(editor)
            self._field_editors[key] = editor

    def _clear_editor(self) -> None:
        self._type_label.hide()
        self._field_editors.clear()
        # Remove all widgets from fields container
        while self._fields_container.count():
            item = self._fields_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _save_current(self) -> None:
        """Write editor contents back into the current CardDraft."""
        if self._current_index < 0 or self._current_index >= len(self._cards):
            return
        card = self._cards[self._current_index]
        changed = False
        for key, editor in self._field_editors.items():
            new_val = editor.toPlainText()
            if card.fields.get(key) != new_val:
                card.fields[key] = new_val
                changed = True
        if changed:
            # Update list item preview
            item = self._list.item(self._current_index)
            if item:
                preview = next(iter(card.fields.values()), "")
                clean = preview.replace("<br>", " ").replace("<br/>", " ")
                if len(clean) > 60:
                    clean = clean[:57] + "..."
                item.setText(
                    f"{self._current_index + 1}. [{card.note_type}] {clean}"
                )
            self.cards_changed.emit()

    def _delete_current(self) -> None:
        if self._current_index < 0 or self._current_index >= len(self._cards):
            return
        idx = self._current_index
        self._field_editors.clear()  # prevent save_current writing to deleted card
        self._current_index = -1
        del self._cards[idx]
        self._refresh_list()
        if self._cards:
            new_idx = min(idx, len(self._cards) - 1)
            self._list.setCurrentRow(new_idx)
        else:
            self._clear_editor()
        self.cards_changed.emit()
