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

    def addItem(self, label: str, user_data: str = None, **kwargs) -> None:
        if "userData" in kwargs:
            user_data = kwargs["userData"]
        self._count += 1
        self._items.append((label, user_data))

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


def test_ollama_model_list_parsing():
    """Verify we can parse Ollama /api/tags response format."""
    data = {
        "models": [
            {"name": "llama3:latest", "size": 4000000000},
            {"name": "codellama:7b", "size": 3800000000},
        ]
    }
    models = [m["name"] for m in data.get("models", [])]
    assert models == ["llama3:latest", "codellama:7b"]


def test_ollama_model_list_empty():
    """Empty model list should be handled gracefully."""
    data = {"models": []}
    models = [m["name"] for m in data.get("models", [])]
    assert models == []


def test_save_preserves_unedited_persistence_fields(monkeypatch) -> None:
    base_config = SimpleNamespace(
        llm_providers=[LLMProviderConfig(id="p1", name="OpenAI", api_key="k")],
        active_provider_id="p1",
        window_geometry="cafebabe",
        theme="dark",
        last_deck="Deck-A",
        last_tags="tag-a",
        last_strategy="cloze",
        last_update_mode="update_only",
        model_copy=lambda update: SimpleNamespace(**{
            "window_geometry": "cafebabe",
            "theme": "dark",
            "last_deck": "Deck-A",
            "last_tags": "tag-a",
            "last_strategy": "cloze",
            "last_update_mode": "update_only",
            **update,
        }),
    )

    captured = {}
    page = SimpleNamespace(
        _save_form_to_provider=lambda: None,
        _selected_provider=lambda: LLMProviderConfig(id="p1", name="OpenAI", api_key="key"),
        _active_provider_id="p1",
        _providers=[LLMProviderConfig(id="p1", name="OpenAI", api_key="key")],
        _anki_url_input=SimpleNamespace(text=lambda: "http://127.0.0.1:8765"),
        _anki_key_input=SimpleNamespace(text=lambda: ""),
        _default_deck_input=SimpleNamespace(text=lambda: "Default"),
        _default_tags_input=SimpleNamespace(text=lambda: "ankismart"),
        _ocr_correction_check=SimpleNamespace(isChecked=lambda: False),
        _temperature_spin=SimpleNamespace(value=lambda: 0.3),
        _max_tokens_spin=SimpleNamespace(value=lambda: 0),
        _proxy_input=SimpleNamespace(text=lambda: ""),
        _lang_combo=SimpleNamespace(currentData=lambda: "zh"),
        _status_label=SimpleNamespace(setText=lambda *_: None, setStyleSheet=lambda *_: None),
        _refresh_provider_combo=lambda: None,
        _main=SimpleNamespace(config=base_config),
    )

    monkeypatch.setattr(
        "ankismart.ui.settings_page.save_config",
        lambda cfg: captured.setdefault("config", cfg),
    )
    monkeypatch.setattr("ankismart.ui.settings_page.set_language", lambda _lang: None)

    SettingsPage._save(page)

    saved = captured["config"]
    assert saved.window_geometry == "cafebabe"
    assert saved.theme == "dark"
    assert saved.last_deck == "Deck-A"
    assert saved.last_update_mode == "update_only"
