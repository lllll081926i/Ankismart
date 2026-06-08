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

    # Navigation
    OPEN_SETTINGS = QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Comma)

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
