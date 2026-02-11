from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.config import save_config
from ankismart.core.models import CardDraft, PushResult
from ankismart.ui.card_edit_widget import CardEditWidget
from ankismart.ui.i18n import t
from ankismart.ui.workers import ExportWorker, PushWorker


class ResultPage(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("page_content")
        self._main = main_window
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title_row = QHBoxLayout()
        title = QLabel(t("result.title"))
        title.setProperty("role", "heading")
        title_row.addWidget(title)

        self._count_label = QLabel("(0)")
        self._count_label.setStyleSheet("color: #666666;")
        title_row.addWidget(self._count_label)

        title_row.addStretch()
        layout.addLayout(title_row)

        # Card editor widget
        self._card_editor = CardEditWidget()
        self._card_editor.cards_changed.connect(self._on_cards_changed)
        layout.addWidget(self._card_editor, 1)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._btn_push = QPushButton(t("result.push"))
        self._btn_push.setMinimumHeight(40)
        self._btn_push.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_push.setProperty("role", "primary")
        self._btn_push.clicked.connect(self._push_cards)
        btn_row.addWidget(self._btn_push, 2)

        self._btn_export = QPushButton(t("result.export"))
        self._btn_export.setMinimumHeight(40)
        self._btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_export.clicked.connect(self._export_apkg)
        btn_row.addWidget(self._btn_export, 1)

        layout.addLayout(btn_row)

        # Update mode option
        self._update_combo = QComboBox()
        self._update_combo.addItem(t("result.create_only"), "create_only")
        self._update_combo.addItem(t("result.update_only"), "update_only")
        self._update_combo.addItem(t("result.create_or_update"), "create_or_update")
        self._update_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self._update_combo)

        # Result summary
        self._result_label = QLabel("")
        layout.addWidget(self._result_label)

        # Keyboard shortcuts
        QShortcut(QKeySequence("Ctrl+S"), self, self._export_apkg)

    def showEvent(self, event: Any) -> None:  # noqa: N802
        super().showEvent(event)
        self._refresh()

        # Restore last update mode
        config = self._main.config
        if config.last_update_mode and hasattr(self, "_update_combo"):
            idx = self._update_combo.findData(config.last_update_mode)
            if idx >= 0:
                self._update_combo.setCurrentIndex(idx)

    def _refresh(self) -> None:
        cards = self._main.cards
        self._count_label.setText(f"({len(cards)})")
        self._card_editor.set_cards(cards)

    def _on_cards_changed(self) -> None:
        """Sync edited cards back to main window."""
        cards = self._card_editor.get_cards()
        self._main.cards = cards
        self._count_label.setText(f"({len(cards)})")

    def _get_cards(self) -> list[CardDraft]:
        """Return the current (edited) card list."""
        return self._card_editor.get_cards()

    def _push_cards(self) -> None:
        cards = self._get_cards()
        if not cards:
            QMessageBox.information(self, t("result.hint"), t("result.no_cards"))
            return

        config = self._main.config

        # Save last update mode
        if hasattr(self, "_update_combo"):
            config.last_update_mode = self._update_combo.currentData() or "create_only"
        try:
            save_config(config)
        except Exception:
            pass
        self._main.config = config

        self._btn_push.setEnabled(False)
        self._result_label.setText(t("result.pushing"))

        worker = PushWorker(
            cards, config.anki_connect_url, config.anki_connect_key,
            update_mode=self._update_combo.currentData(),
            proxy_url=config.proxy_url,
        )
        worker.finished.connect(self._on_push_done)
        worker.error.connect(self._on_push_error)
        worker.start()
        self._worker = worker

    def _on_push_done(self, result: PushResult) -> None:
        self._btn_push.setEnabled(True)
        summary = t("result.push_done", succeeded=result.succeeded, failed=result.failed)
        self._result_label.setText(summary)

        if result.failed > 0 and result.results:
            errors = []
            for r in result.results:
                if not r.success and r.error:
                    errors.append(t("result.card_error", index=r.index + 1, error=r.error))
            if errors:
                detail = "\n".join(errors[:20])  # Show at most 20 errors
                if len(errors) > 20:
                    detail += "\n" + t("result.more_errors", count=len(errors) - 20)
                QMessageBox.warning(self, t("result.push_partial_fail"), detail)

    def _on_push_error(self, msg: str) -> None:
        self._btn_push.setEnabled(True)
        self._result_label.setText("")
        QMessageBox.warning(self, t("result.push_error"), msg)

    def _export_apkg(self) -> None:
        cards = self._get_cards()
        if not cards:
            QMessageBox.information(self, t("result.hint"), t("result.no_cards_export"))
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            t("result.export_dialog"),
            "ankismart_export.apkg",
            t("result.export_filter"),
        )
        if not path:
            return

        self._btn_export.setEnabled(False)
        self._result_label.setText(t("result.exporting"))

        worker = ExportWorker(cards, Path(path))
        worker.finished.connect(self._on_export_done)
        worker.error.connect(self._on_export_error)
        worker.start()
        self._worker = worker

    def _on_export_done(self, path: Path) -> None:
        self._btn_export.setEnabled(True)
        self._result_label.setText(t("result.export_done", path=path))

    def _on_export_error(self, msg: str) -> None:
        self._btn_export.setEnabled(True)
        self._result_label.setText("")
        QMessageBox.warning(self, t("result.export_error"), msg)
