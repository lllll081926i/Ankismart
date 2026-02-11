from __future__ import annotations

from types import SimpleNamespace

from ankismart.core.config import LLMProviderConfig
from ankismart.ui.settings_page import SettingsPage


class _DummyProviderCombo:
    def __init__(self) -> None:
        self._index = 0
        self._count = 0
        self._items = []

    def currentIndex(self) -> int:
        return self._index

    def clear(self) -> None:
        self._count = 0
        self._items = []

    def addItem(self, label: str, userData: str = None) -> None:
        self._count += 1
        self._items.append((label, userData))

    def count(self) -> int:
        return self._count

    def setCurrentIndex(self, index: int) -> None:
        self._index = index


class _DummyDeleteButton:
    def __init__(self) -> None:
        self.enabled = False

    def setEnabled(self, value: bool) -> None:
        self.enabled = value


def test_refresh_provider_combo_updates_form(monkeypatch) -> None:
    page = SimpleNamespace(
        _updating_ui=False,
        _providers=[
            LLMProviderConfig(id="p1", name="OpenAI", model="gpt-4o"),
            LLMProviderConfig(id="p2", name="DeepSeek", model="deepseek-chat"),
        ],
        _active_provider_id="p1",
        _provider_combo=_DummyProviderCombo(),
        _btn_delete=_DummyDeleteButton(),
    )

    called = {"count": 0}

    def _fake_on_provider_changed(_index: int) -> None:
        called["count"] += 1

    page._on_provider_changed = _fake_on_provider_changed

    SettingsPage._refresh_provider_combo(page)

    assert called["count"] == 1
    assert page._provider_combo.count() == 2
    assert page._btn_delete.enabled is True
