from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.config import AppConfig, save_config
from ankismart.core.models import BatchConvertResult, CardDraft
from ankismart.core.tracing import metrics
from ankismart.ui.i18n import t


class MetricsDialog(QDialog):
    """Simple dialog showing performance metrics."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("metrics.title"))
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout(self)

        # Cache stats
        hits = metrics.cache_hits
        misses = metrics.cache_misses
        total = hits + misses
        rate = f"{hits / total * 100:.1f}%" if total else "N/A"
        cache_label = QLabel(t("metrics.cache", hits=hits, total=total, rate=rate))
        layout.addWidget(cache_label)

        # Stage timing table
        snapshot = metrics.snapshot()
        table = QTableWidget(len(snapshot), 5)
        table.setHorizontalHeaderLabels(t("metrics.cols"))
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for row, (name, m) in enumerate(sorted(snapshot.items())):
            table.setItem(row, 0, QTableWidgetItem(name))
            table.setItem(row, 1, QTableWidgetItem(str(m.count)))
            table.setItem(row, 2, QTableWidgetItem(f"{m.avg_ms:.1f}"))
            table.setItem(row, 3, QTableWidgetItem(f"{m.min_ms:.1f}" if m.count else "N/A"))
            table.setItem(row, 4, QTableWidgetItem(f"{m.max_ms:.1f}" if m.count else "N/A"))

        table.resizeColumnsToContents()
        layout.addWidget(table)

        # Reset button
        btn_reset = QPushButton(t("metrics.reset"))
        btn_reset.clicked.connect(self._reset)
        layout.addWidget(btn_reset)

    def _reset(self) -> None:
        metrics.reset()
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._cards: list[CardDraft] = []
        self._batch_result: BatchConvertResult | None = None
        self._import_page: QWidget | None = None
        self._preview_page: QWidget | None = None

        self.setWindowTitle("AnkiSmart")
        self.setMinimumSize(800, 600)

        # Restore window geometry
        if config.window_geometry:
            try:
                from PySide6.QtCore import QByteArray
                geo = QByteArray.fromHex(config.window_geometry.encode())
                self.restoreGeometry(geo)
            except Exception:
                pass

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Navigation bar
        nav = QHBoxLayout()
        nav.setSpacing(8)
        nav.setContentsMargins(0, 0, 0, 10)

        self._btn_import = QPushButton(t("nav.import"))
        self._btn_preview = QPushButton(t("nav.preview"))
        self._btn_results = QPushButton(t("nav.results"))
        self._btn_settings = QPushButton(t("nav.settings"))

        for btn in (
            self._btn_import,
            self._btn_preview,
            self._btn_results,
            self._btn_settings,
        ):
            btn.setCheckable(True)
            btn.setMinimumHeight(40)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("role", "nav")
            nav.addWidget(btn)

        self._btn_import.setChecked(True)
        layout.addLayout(nav)

        # Stacked pages (pages will be set from app.py after creation)
        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._connection_label = QLabel(t("status.checking"))
        self._status_bar.addPermanentWidget(self._connection_label)

        self._btn_metrics = QPushButton(t("metrics.button"))
        self._btn_metrics.setFlat(True)
        self._btn_metrics.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_metrics.clicked.connect(self._show_metrics)
        self._status_bar.addPermanentWidget(self._btn_metrics)

        self._btn_theme = QPushButton("\u2600\ufe0f" if config.theme == "dark" else "\U0001f319")
        self._btn_theme.setFlat(True)
        self._btn_theme.setToolTip(t("theme.toggle"))
        self._btn_theme.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_theme.clicked.connect(self._toggle_theme)
        self._status_bar.addPermanentWidget(self._btn_theme)

        # Navigation signals
        self._btn_import.clicked.connect(lambda: self._switch_page(0))
        self._btn_preview.clicked.connect(lambda: self._switch_page(1))
        self._btn_results.clicked.connect(lambda: self._switch_page(2))
        self._btn_settings.clicked.connect(lambda: self._switch_page(3))

        # Keyboard shortcuts for page switching
        QShortcut(QKeySequence("Ctrl+1"), self, lambda: self._switch_page(0))
        QShortcut(QKeySequence("Ctrl+2"), self, lambda: self._switch_page(1))
        QShortcut(QKeySequence("Ctrl+3"), self, lambda: self._switch_page(2))
        QShortcut(QKeySequence("Ctrl+4"), self, lambda: self._switch_page(3))
        QShortcut(QKeySequence("Escape"), self, self._cancel_current_operation)

    def _cancel_current_operation(self) -> None:
        """Cancel any running operation on the current page."""
        current = self._stack.currentWidget()
        cancel_fn = getattr(current, "cancel_operation", None)
        if callable(cancel_fn):
            cancel_fn()

    def add_page(self, page: QWidget) -> None:
        self._stack.addWidget(page)

    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        buttons = [
            self._btn_import,
            self._btn_preview,
            self._btn_results,
            self._btn_settings,
        ]
        for i, btn in enumerate(buttons):
            btn.setChecked(i == index)

    def switch_to_preview(self) -> None:
        if self._preview_page is not None and self._batch_result is not None:
            load_documents = getattr(self._preview_page, "load_documents", None)
            if callable(load_documents):
                load_documents(self._batch_result)
        self._switch_page(1)

    def switch_to_results(self) -> None:
        self._switch_page(2)

    def add_preview_page(self, page: QWidget) -> None:
        self._preview_page = page
        self._stack.insertWidget(1, page)

    def set_import_page(self, page: QWidget) -> None:
        self._import_page = page

    def set_connection_status(self, connected: bool) -> None:
        if connected:
            self._connection_label.setText(t("status.connected"))
            self._connection_label.setStyleSheet("color: green;")
        else:
            self._connection_label.setText(t("status.disconnected"))
            self._connection_label.setStyleSheet("color: red;")

    @property
    def config(self) -> AppConfig:
        return self._config

    @config.setter
    def config(self, value: AppConfig) -> None:
        self._config = value

    @property
    def cards(self) -> list[CardDraft]:
        return self._cards

    @cards.setter
    def cards(self, value: list[CardDraft]) -> None:
        self._cards = value

    @property
    def batch_result(self) -> BatchConvertResult | None:
        return self._batch_result

    @batch_result.setter
    def batch_result(self, value: BatchConvertResult | None) -> None:
        self._batch_result = value

    @property
    def import_page(self) -> QWidget | None:
        return self._import_page

    def _show_metrics(self) -> None:
        dialog = MetricsDialog(self)
        dialog.exec()

    def _toggle_theme(self) -> None:
        from ankismart.ui.styles import get_stylesheet

        config = self._config
        config.theme = "dark" if config.theme == "light" else "light"
        is_dark = config.theme == "dark"
        self._btn_theme.setText("\u2600\ufe0f" if is_dark else "\U0001f319")
        from PySide6.QtWidgets import QApplication

        qapp = QApplication.instance()
        if qapp:
            qapp.setStyleSheet(get_stylesheet(dark=is_dark))
        try:
            save_config(config)
        except Exception:
            pass

    def closeEvent(self, event) -> None:  # noqa: N802
        geo_hex = self.saveGeometry().toHex().data().decode()
        config = self._config
        config.window_geometry = geo_hex
        try:
            save_config(config)
        except Exception:
            pass
        super().closeEvent(event)
