from __future__ import annotations

from .base_page import BasePageObject


class SettingsPageObject(BasePageObject):
    @property
    def page(self):
        return self.window.settings_page

    def activate_provider(self, provider_name: str) -> None:
        target = next((p for p in self.page._providers if p.name == provider_name), None)
        if target is None:
            raise AssertionError(f"provider not found: {provider_name}")
        self.page._activate_provider(target)
        self.process_events()

    def save(self) -> None:
        self.page._save_config_silent(show_feedback=False)
        self.process_events()
