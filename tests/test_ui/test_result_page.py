from __future__ import annotations

from ankismart.core.models import CardDraft
from ankismart.ui.card_edit_widget import CardEditWidget


def _make_card(front: str = "Q", back: str = "A") -> CardDraft:
    return CardDraft(
        fields={"Front": front, "Back": back},
        note_type="Basic",
        deck_name="Test",
        tags=["test"],
    )


class _FakePlainTextEdit:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def toPlainText(self) -> str:
        return self._text

    def setPlainText(self, text: str) -> None:
        self._text = text


class _FakeListItem:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def setText(self, text: str) -> None:
        self._text = text


class _FakeListWidget:
    def __init__(self, count: int = 0) -> None:
        self._items = [_FakeListItem() for _ in range(count)]

    def item(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None


class _FakeSignal:
    def emit(self) -> None:
        pass


def test_card_editor_get_cards_returns_edited():
    """CardEditWidget.get_cards returns cards with edits applied."""
    cards = [_make_card("Q1", "A1"), _make_card("Q2", "A2")]
    w = CardEditWidget.__new__(CardEditWidget)
    w._cards = list(cards)
    w._current_index = 0
    w._field_editors = {
        "Front": _FakePlainTextEdit("Edited"),
        "Back": _FakePlainTextEdit("A1"),
    }
    w._list = _FakeListWidget(2)
    w.cards_changed = _FakeSignal()

    result = w.get_cards()
    assert result[0].fields["Front"] == "Edited"
    assert result[1].fields["Front"] == "Q2"
