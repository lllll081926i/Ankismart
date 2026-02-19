from __future__ import annotations

from pathlib import Path

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui.import_page import ImportPage


class DummyCombo:
    def __init__(self, value: str) -> None:
        self._value = value
        self._items: list[str] = [value] if value else []

    def currentData(self) -> str:
        return self._value

    def currentText(self) -> str:
        return self._value

    def setCurrentText(self, value: str) -> None:
        self._value = value

    def clear(self) -> None:
        self._items = []

    def addItem(self, value: str) -> None:
        self._items.append(value)


class DummyLineEdit:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:
        self._text = text


class DummyMain:
    def __init__(self) -> None:
        self.config = AppConfig(
            llm_providers=[
                LLMProviderConfig(
                    id="test",
                    name="OpenAI",
                    api_key="test-key",
                    base_url="https://api.openai.com/v1",
                    model="gpt-4o",
                )
            ],
            active_provider_id="test",
        )
        self.batch_result = None
        self._switched_to_preview = False
        self._loaded_batch_result = None

    def switch_to_preview(self):
        self._switched_to_preview = True

    def load_preview_documents(self, result):
        self._loaded_batch_result = result


class DummyModeCombo:
    def __init__(self, value: str) -> None:
        self._value = value

    def currentData(self) -> str:
        return self._value


class DummySlider:
    def __init__(self, value: int) -> None:
        self._value = value

    def value(self) -> int:
        return self._value


class DummyListItem:
    def __init__(self, text: str) -> None:
        self._text = text
        self._color_name = ""

    def text(self) -> str:
        return self._text

    def setForeground(self, color) -> None:
        self._color_name = color.name()

    @property
    def color_name(self) -> str:
        return self._color_name


class DummyListWidget:
    def __init__(self, items: list[DummyListItem]) -> None:
        self._items = items

    def count(self) -> int:
        return len(self._items)

    def item(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None


def make_page():
    page = ImportPage.__new__(ImportPage)
    page._main = DummyMain()
    page._file_paths = []
    page._worker = None
    page._strategy_sliders = [
        ("basic", DummySlider(100), None),
    ]
    page._total_count_input = DummyLineEdit("20")
    page._total_count_mode_combo = DummyModeCombo("custom")
    page._deck_combo = DummyCombo("Default")
    page._tags_input = DummyLineEdit("tag1, tag2")
    page._status_label = type("_Label", (), {"setText": lambda self, text: None})()
    page._progress = type(
        "_Progress",
        (),
        {
            "hide": lambda self: None,
            "show": lambda self: None,
            "setRange": lambda self, a, b: None,
            "setValue": lambda self, v: None,
        },
    )()
    page._btn_convert = type("_Btn", (), {"setEnabled": lambda self, v: None})()
    page._progress_ring = type("_Ring", (), {"show": lambda self: None, "hide": lambda self: None})()
    page._progress_bar = type(
        "_Bar", (), {"show": lambda self: None, "hide": lambda self: None, "setValue": lambda self, value: None}
    )()
    page._btn_cancel = type(
        "_Btn",
        (),
        {
            "show": lambda self: None,
            "hide": lambda self: None,
            "setEnabled": lambda self, value: None,
        },
    )()
    return page


def make_warning_box_collector(collected: list[tuple[str, str]]):
    return type(
        "_MB",
        (),
        {
            "warning": staticmethod(lambda _parent, title, msg: collected.append((title, msg)))
        },
    )


def patch_infobar(monkeypatch) -> dict[str, list[dict]]:
    calls: dict[str, list[dict]] = {
        "warning": [],
        "success": [],
        "info": [],
        "error": [],
    }

    def record(level: str):
        def inner(*args, **kwargs):
            calls[level].append(kwargs)
            return None

        return inner

    infobar_stub = type(
        "_InfoBarStub",
        (),
        {
            "warning": staticmethod(record("warning")),
            "success": staticmethod(record("success")),
            "info": staticmethod(record("info")),
            "error": staticmethod(record("error")),
        },
    )
    monkeypatch.setattr("ankismart.ui.import_page.InfoBar", infobar_stub)
    return calls

