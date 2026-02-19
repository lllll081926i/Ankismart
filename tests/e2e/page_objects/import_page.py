from __future__ import annotations

from pathlib import Path

from .base_page import BasePageObject


class ImportPageObject(BasePageObject):
    @property
    def page(self):
        return self.window.import_page

    def prepare_files(self, file_paths: list[Path]) -> None:
        self.page._add_files(list(file_paths))
        self.process_events()

    def configure(self, *, deck_name: str = "Default", tags: str = "ankismart,e2e", target_total: int = 20) -> None:
        self.page._deck_combo.setCurrentText(deck_name)
        self.page._tags_input.setText(tags)
        self.page._total_count_input.setText(str(target_total))

    def start_convert(self) -> None:
        btn = getattr(self.page, "_btn_convert", None)
        if btn is not None:
            btn.click()
        else:
            self.page._start_convert()
        self.process_events()
