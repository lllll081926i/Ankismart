from __future__ import annotations

from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QApplication

from ankismart.core.config import AppConfig, LLMProviderConfig
from ankismart.ui import settings_page as settings_page_module

ProviderListItemWidget = getattr(settings_page_module, "ProviderListItemWidget", None)
ProviderListWidget = getattr(settings_page_module, "ProviderListWidget", None)


@pytest.fixture(scope="session")
def _qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def make_main(config: AppConfig | None = None):
    if config is None:
        provider = LLMProviderConfig(
            id="p1",
            name="OpenAI",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
        )
        config = AppConfig(llm_providers=[provider], active_provider_id="p1")

    status_calls: list[bool] = []
    main = SimpleNamespace(
        config=config,
        set_connection_status=lambda connected: status_calls.append(connected),
    )
    return main, status_calls

