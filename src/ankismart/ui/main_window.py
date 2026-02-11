from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.config import AppConfig
from ankismart.core.models import BatchConvertResult, CardDraft


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

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Navigation bar
        nav = QHBoxLayout()
        nav.setSpacing(20)
        nav.setContentsMargins(0, 0, 0, 10)

        self._btn_import = QPushButton("导入与生成")
        self._btn_preview = QPushButton("预览")
        self._btn_results = QPushButton("结果")
        self._btn_settings = QPushButton("设置")

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
        self._connection_label = QLabel("AnkiConnect：检测中...")
        self._status_bar.addPermanentWidget(self._connection_label)

        # Navigation signals
        self._btn_import.clicked.connect(lambda: self._switch_page(0))
        self._btn_preview.clicked.connect(lambda: self._switch_page(1))
        self._btn_results.clicked.connect(lambda: self._switch_page(2))
        self._btn_settings.clicked.connect(lambda: self._switch_page(3))

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
            self._connection_label.setText("AnkiConnect：已连接")
            self._connection_label.setStyleSheet("color: green;")
        else:
            self._connection_label.setText("AnkiConnect：未连接")
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
