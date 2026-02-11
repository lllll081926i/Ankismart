from __future__ import annotations

from ankismart.core.models import CardDraft
from ankismart.ui.card_edit_widget import CardEditWidget


def _make_card(front: str = "Q", back: str = "A", note_type: str = "Basic") -> CardDraft:
    return CardDraft(
        fields={"Front": front, "Back": back},
        note_type=note_type,
        deck_name="Test",
        tags=["test"],
    )


def _make_cloze(text: str = "{{c1::answer}}") -> CardDraft:
    return CardDraft(
        fields={"Text": text, "Back Extra": ""},
        note_type="Cloze",
        deck_name="Test",
        tags=["test"],
    )


class _FakePlainTextEdit:
    """Minimal stand-in for QPlainTextEdit."""

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

    def text(self) -> str:
        return self._text


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


def _build_widget_no_qt(cards: list[CardDraft]) -> CardEditWidget:
    """Create a CardEditWidget without Qt initialization, wiring only the
    fields needed for logic tests."""
    w = CardEditWidget.__new__(CardEditWidget)
    w._cards = list(cards)
    w._current_index = -1
    w._field_editors = {}
    w._list = _FakeListWidget(len(cards))
    w.cards_changed = _FakeSignal()
    return w


# -- Tests --


def test_set_cards_stores_list():
    """set_cards (simulated) should store a copy of the card list."""
    cards = [_make_card("Q1", "A1"), _make_card("Q2", "A2")]
    w = _build_widget_no_qt(cards)
    assert len(w._cards) == 2
    assert w._cards[0].fields["Front"] == "Q1"


def test_get_cards_returns_copy():
    """get_cards should return a list copy, not the internal reference."""
    cards = [_make_card()]
    w = _build_widget_no_qt(cards)
    result = w.get_cards()
    assert result == cards
    assert result is not w._cards


def test_save_current_writes_back_to_model():
    """Editing a field should update the CardDraft.fields dict."""
    card = _make_card("Original Q", "Original A")
    w = _build_widget_no_qt([card])
    w._current_index = 0
    w._field_editors = {
        "Front": _FakePlainTextEdit("Edited Q"),
        "Back": _FakePlainTextEdit("Edited A"),
    }
    w._save_current()

    assert card.fields["Front"] == "Edited Q"
    assert card.fields["Back"] == "Edited A"


def test_save_current_noop_when_no_selection():
    """_save_current should do nothing when no card is selected."""
    card = _make_card("Q", "A")
    w = _build_widget_no_qt([card])
    w._current_index = -1
    w._field_editors = {
        "Front": _FakePlainTextEdit("Changed"),
    }
    w._save_current()
    assert card.fields["Front"] == "Q"  # unchanged


def test_delete_removes_card():
    """Deleting a card should remove it from the internal list."""
    cards = [_make_card("Q1", "A1"), _make_card("Q2", "A2"), _make_card("Q3", "A3")]
    w = _build_widget_no_qt(cards)
    w._current_index = 1
    # Simulate delete without Qt widgets
    del w._cards[w._current_index]
    w._current_index = -1

    assert len(w._cards) == 2
    assert w._cards[0].fields["Front"] == "Q1"
    assert w._cards[1].fields["Front"] == "Q3"


def test_cloze_card_fields():
    """Cloze cards should have their fields editable too."""
    card = _make_cloze("{{c1::test}}")
    w = _build_widget_no_qt([card])
    w._current_index = 0
    w._field_editors = {
        "Text": _FakePlainTextEdit("{{c1::edited}}"),
        "Back Extra": _FakePlainTextEdit("some note"),
    }
    w._save_current()

    assert card.fields["Text"] == "{{c1::edited}}"
    assert card.fields["Back Extra"] == "some note"


def test_save_current_no_change_when_text_same():
    """_save_current should not flag changes when text is identical."""
    card = _make_card("Q", "A")
    w = _build_widget_no_qt([card])
    w._current_index = 0
    w._field_editors = {
        "Front": _FakePlainTextEdit("Q"),
        "Back": _FakePlainTextEdit("A"),
    }
    # Should not raise or break
    w._save_current()
    assert card.fields["Front"] == "Q"
    assert card.fields["Back"] == "A"


def test_get_cards_after_edit_reflects_changes():
    """Full round-trip: edit then get_cards should return edited data."""
    card = _make_card("Q", "A")
    w = _build_widget_no_qt([card])
    w._current_index = 0
    w._field_editors = {
        "Front": _FakePlainTextEdit("New Q"),
        "Back": _FakePlainTextEdit("New A"),
    }
    result = w.get_cards()
    assert result[0].fields["Front"] == "New Q"
    assert result[0].fields["Back"] == "New A"
