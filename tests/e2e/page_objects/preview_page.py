from __future__ import annotations

from .base_page import BasePageObject


class PreviewPageObject(BasePageObject):
    @property
    def page(self):
        return self.window.preview_page

    def generate_cards(self) -> None:
        btn = getattr(self.page, "_btn_generate", None)
        if btn is not None:
            btn.click()
        else:
            self.page._on_generate_cards()
        self.process_events()

    def converted_documents_count(self) -> int:
        return len(self.page._documents)
