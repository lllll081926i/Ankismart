"""Keyboard shortcuts help dialog for Ankismart UI."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout
from qfluentwidgets import BodyLabel, CaptionLabel, PrimaryPushButton, ScrollArea, isDarkTheme

from .i18n import t
from .shortcuts import get_all_shortcuts


class ShortcutsHelpDialog(QDialog):
    """Dialog displaying all available keyboard shortcuts."""

    def __init__(self, language: str = "zh", parent=None):
        super().__init__(parent)
        self._language = language
        self._init_ui()

    def _init_ui(self):
        """Initialize the dialog UI."""
        self.setWindowTitle(t("shortcuts.help_title", self._language))
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = BodyLabel(t("shortcuts.help_title", self._language))
        title.setStyleSheet("font-weight: 700;")
        layout.addWidget(title)

        # Description
        desc = CaptionLabel(t("shortcuts.help_desc", self._language))
        desc_color = "#9CA3AF" if isDarkTheme() else "#666666"
        desc.setStyleSheet(f"color: {desc_color};")
        layout.addWidget(desc)

        # Shortcuts list in scroll area
        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        shortcuts_widget = self._create_shortcuts_widget()
        scroll.setWidget(shortcuts_widget)
        layout.addWidget(scroll, 1)

        # Close button
        close_btn = PrimaryPushButton(t("common.close", self._language))
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(100)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _create_shortcuts_widget(self):
        """Create widget containing all shortcuts."""
        widget = QLabel()
        widget.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        shortcuts = get_all_shortcuts(self._language)

        for shortcut_text, description in shortcuts:
            row = self._create_shortcut_row(shortcut_text, description)
            layout.addWidget(row)

        layout.addStretch()
        return widget

    def _create_shortcut_row(self, shortcut: str, description: str):
        """Create a single shortcut row."""
        dark = isDarkTheme()
        border_color = "rgba(255, 255, 255, 0.12)" if dark else "#E0E0E0"
        key_text_color = "#60A5FA" if dark else "#0078D4"
        key_bg_color = "rgba(255, 255, 255, 0.08)" if dark else "#F0F0F0"
        desc_text_color = "#E5E7EB" if dark else "#333333"

        row_widget = QLabel()
        row_widget.setStyleSheet(
            "QLabel {{"
            "background: transparent;"
            "padding: 8px;"
            f"border-bottom: 1px solid {border_color};"
            "}}"
        )

        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(20)

        # Shortcut key
        key_label = BodyLabel(shortcut)
        key_label.setStyleSheet(f"""
            font-family: 'Consolas', 'Monaco', monospace;
            font-weight: bold;
            color: {key_text_color};
            background: {key_bg_color};
            padding: 4px 8px;
            border-radius: 4px;
        """)
        key_label.setFixedWidth(120)
        row_layout.addWidget(key_label)

        # Description
        desc_label = BodyLabel(description)
        desc_label.setStyleSheet(f"color: {desc_text_color};")
        row_layout.addWidget(desc_label, 1)

        return row_widget
