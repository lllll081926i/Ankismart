from __future__ import annotations

from .base_page import BasePageObject


class ResultPageObject(BasePageObject):
    @property
    def page(self):
        return self.window.result_page

    def export_apkg(self) -> None:
        btn = getattr(self.page, "_btn_export_apkg", None)
        if btn is not None:
            btn.click()
        else:
            self.page._export_apkg()
        self.process_events()

    @property
    def push_result(self):
        return self.page._push_result

    def status_label_text(self) -> str:
        return self.page._status_label.text()

    def row_status_text(self, row: int = 0) -> str:
        item = self.page._table.item(row, 2)
        return item.text() if item is not None else ""

    def row_message_text(self, row: int = 0) -> str:
        item = self.page._table.item(row, 3)
        return item.text() if item is not None else ""
