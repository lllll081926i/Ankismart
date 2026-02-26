"""Keyboard shortcuts configuration and management for Ankismart UI.

This module defines all keyboard shortcuts used in the application and provides
utilities for managing them across different pages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget


class ShortcutKeys:
    """Centralized keyboard shortcut definitions."""

    # File operations
    OPEN_FILE = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_O)

    # Generation and processing
    START_GENERATION = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_G)

    # Save operations
    SAVE_EDIT = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_S)

    # Export operations
    EXPORT_CARDS = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_E)

    # Navigation
    OPEN_SETTINGS = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Comma)
    HELP = QKeySequence(Qt.Key.Key_F1)

    # Application
    QUIT = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Q)


# Product decision: keyboard shortcuts are currently deprecated globally.
SHORTCUTS_ENABLED = False


def get_shortcut_text(key_sequence: QKeySequence, language: str = "zh") -> str:
    """Get human-readable shortcut text for display.

    Args:
        key_sequence: The QKeySequence to convert
        language: Language code ("zh" or "en")

    Returns:
        Formatted shortcut text (e.g., "Ctrl+O" or "F1")
    """
    if not SHORTCUTS_ENABLED:
        return "已停用" if language == "zh" else "Disabled"

    # Get native text representation
    text = key_sequence.toString(QKeySequence.SequenceFormat.NativeText)
    return text


def create_shortcut(
    parent: QWidget,
    key_sequence: QKeySequence,
    callback: Callable,
    context: Qt.ShortcutContext = Qt.ShortcutContext.WidgetWithChildrenShortcut,
) -> QShortcut | None:
    """Create and configure a keyboard shortcut.

    Args:
        parent: Parent widget for the shortcut
        key_sequence: Key sequence for the shortcut
        callback: Function to call when shortcut is activated
        context: Shortcut context (default: WidgetWithChildrenShortcut)

    Returns:
        Configured QShortcut instance
    """
    if not SHORTCUTS_ENABLED:
        return None

    shortcut = QShortcut(key_sequence, parent)
    shortcut.setContext(context)
    shortcut.activated.connect(callback)
    return shortcut


# Shortcut descriptions for help dialog
SHORTCUT_DESCRIPTIONS = {
    "zh": {
        "open_file": "打开文件",
        "start_generation": "开始生成",
        "save_edit": "保存编辑",
        "export_cards": "导出卡片",
        "open_settings": "打开设置",
        "help": "帮助文档",
        "quit": "退出应用",
    },
    "en": {
        "open_file": "Open File",
        "start_generation": "Start Generation",
        "save_edit": "Save Edit",
        "export_cards": "Export Cards",
        "open_settings": "Open Settings",
        "help": "Help",
        "quit": "Quit Application",
    },
}


def get_all_shortcuts(language: str = "zh") -> list[tuple[str, str]]:
    """Get all shortcuts with descriptions for display.

    Args:
        language: Language code ("zh" or "en")

    Returns:
        List of (shortcut_text, description) tuples
    """
    descriptions = SHORTCUT_DESCRIPTIONS.get(language, SHORTCUT_DESCRIPTIONS["zh"])

    shortcuts = [
        (get_shortcut_text(ShortcutKeys.OPEN_FILE, language), descriptions["open_file"]),
        (
            get_shortcut_text(ShortcutKeys.START_GENERATION, language),
            descriptions["start_generation"],
        ),
        (get_shortcut_text(ShortcutKeys.SAVE_EDIT, language), descriptions["save_edit"]),
        (get_shortcut_text(ShortcutKeys.EXPORT_CARDS, language), descriptions["export_cards"]),
        (get_shortcut_text(ShortcutKeys.OPEN_SETTINGS, language), descriptions["open_settings"]),
        (get_shortcut_text(ShortcutKeys.HELP, language), descriptions["help"]),
        (get_shortcut_text(ShortcutKeys.QUIT, language), descriptions["quit"]),
    ]

    return shortcuts
