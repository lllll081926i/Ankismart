from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ankismart.core.config import AppConfig, save_config
from ankismart.ui.workers import ConnectionCheckWorker


class SettingsPage(QWidget):
    def __init__(self, main_window) -> None:
        super().__init__()
        self.setObjectName("page_content")
        self._main = main_window
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("设置")
        title.setProperty("role", "heading")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(15)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # OpenAI
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key_input.setPlaceholderText("sk-...")
        self._api_key_input.setMinimumHeight(36)
        form.addRow("OpenAI API Key：", self._api_key_input)

        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("gpt-4o")
        self._model_input.setMinimumHeight(36)
        form.addRow("OpenAI 模型：", self._model_input)

        # AnkiConnect
        self._anki_url_input = QLineEdit()
        self._anki_url_input.setPlaceholderText("http://127.0.0.1:8765")
        self._anki_url_input.setMinimumHeight(36)
        form.addRow("AnkiConnect 地址：", self._anki_url_input)

        self._anki_key_input = QLineEdit()
        self._anki_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._anki_key_input.setPlaceholderText("可选")
        self._anki_key_input.setMinimumHeight(36)
        form.addRow("AnkiConnect Key：", self._anki_key_input)

        # Defaults
        self._default_deck_input = QLineEdit()
        self._default_deck_input.setMinimumHeight(36)
        form.addRow("默认牌组：", self._default_deck_input)

        self._default_tags_input = QLineEdit()
        self._default_tags_input.setMinimumHeight(36)
        form.addRow("默认标签：", self._default_tags_input)

        layout.addLayout(form)
        layout.addSpacing(10)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(15)

        btn_test = QPushButton("测试 AnkiConnect")
        btn_test.setMinimumHeight(40)
        btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test.clicked.connect(self._test_connection)
        btn_row.addWidget(btn_test)

        btn_save = QPushButton("保存")
        btn_save.setMinimumHeight(40)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setProperty("role", "primary")
        btn_save.clicked.connect(self._save)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Load current config into fields
        self._load_config()

    def _load_config(self) -> None:
        config = self._main.config
        self._api_key_input.setText(config.openai_api_key)
        self._model_input.setText(config.openai_model)
        self._anki_url_input.setText(config.anki_connect_url)
        self._anki_key_input.setText(config.anki_connect_key)
        self._default_deck_input.setText(config.default_deck)
        self._default_tags_input.setText(", ".join(config.default_tags))

    def _save(self) -> None:
        tags = [t.strip() for t in self._default_tags_input.text().split(",") if t.strip()]
        config = AppConfig(
            openai_api_key=self._api_key_input.text(),
            openai_model=self._model_input.text() or "gpt-4o",
            anki_connect_url=self._anki_url_input.text() or "http://127.0.0.1:8765",
            anki_connect_key=self._anki_key_input.text(),
            default_deck=self._default_deck_input.text() or "Default",
            default_tags=tags or ["ankismart"],
        )
        try:
            save_config(config)
            self._main.config = config
            self._status_label.setText("设置已保存")
            self._status_label.setStyleSheet("color: green;")
        except Exception as exc:
            QMessageBox.warning(self, "错误", f"保存失败：{exc}")

    def _test_connection(self) -> None:
        url = self._anki_url_input.text() or "http://127.0.0.1:8765"
        key = self._anki_key_input.text()
        self._status_label.setText("正在测试连接...")
        self._status_label.setStyleSheet("")

        worker = ConnectionCheckWorker(url, key)
        worker.finished.connect(self._on_test_result)
        worker.start()
        self._worker = worker

    def _on_test_result(self, connected: bool) -> None:
        if connected:
            self._status_label.setText("AnkiConnect：连接成功！")
            self._status_label.setStyleSheet("color: green;")
        else:
            self._status_label.setText("AnkiConnect：连接失败")
            self._status_label.setStyleSheet("color: red;")
        self._main.set_connection_status(connected)
