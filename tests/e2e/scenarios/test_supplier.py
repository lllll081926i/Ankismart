from __future__ import annotations

import pytest

from tests.e2e.page_objects.settings_page import SettingsPageObject


@pytest.mark.p1
@pytest.mark.fast
def test_e2e_supplier_switch_and_persistence(window):
    settings_page = SettingsPageObject(window)

    before_provider_id = window.config.active_provider_id
    settings_page.activate_provider("Ollama (本地)")
    settings_page.save()

    assert window.config.active_provider_id != before_provider_id
    assert window.config.active_provider is not None
    assert window.config.active_provider.name == "Ollama (本地)"
