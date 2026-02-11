from __future__ import annotations

from PySide6.QtCore import Qt

from ankismart.ui.result_page import ResultPage


class _DummyItem:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def checkState(self):
        return Qt.CheckState.Checked if self._checked else Qt.CheckState.Unchecked


class _DummyTable:
    def __init__(self, checked_rows: list[bool]) -> None:
        self._checked_rows = checked_rows

    def rowCount(self) -> int:
        return len(self._checked_rows)

    def item(self, row: int, col: int):
        if col != 0:
            return None
        return _DummyItem(self._checked_rows[row])


def test_get_selected_cards_uses_row_mapping():
    page = ResultPage.__new__(ResultPage)
    page._main = type("_Main", (), {"cards": ["c0", "c1", "c2"]})()
    page._table = _DummyTable([False, True])
    page._row_to_card_index = [0, 2]

    selected_cards, selected_rows = ResultPage._get_selected_cards(page)

    assert selected_cards == ["c2"]
    assert selected_rows == [1]
