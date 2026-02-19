from __future__ import annotations

from .base_page import BasePageObject


class CardPreviewPageObject(BasePageObject):
    @property
    def page(self):
        return self.window.card_preview_page

    def push_to_anki(self) -> None:
        btn = getattr(self.page, "_btn_push", None)
        if btn is not None:
            btn.click()
        else:
            self.page._push_to_anki()
        self.process_events()

    def card_count(self) -> int:
        return len(self.page._all_cards)
