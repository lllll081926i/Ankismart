"""Unified notification manager for consistent InfoBar usage across the application."""

from __future__ import annotations

from typing import TYPE_CHECKING

from qfluentwidgets import InfoBar, InfoBarIcon, InfoBarPosition

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget


# Duration constants (in milliseconds)
DURATION_SUCCESS = 1500  # 1.5 seconds for success messages
DURATION_INFO = 2000  # 2 seconds for informational messages
DURATION_WARNING = 3000  # 3 seconds for warnings
DURATION_ERROR = 5000  # 5 seconds for errors
DURATION_CRITICAL = -1  # Persistent until user closes


class NotificationManager:
    """Centralized notification manager with consistent styling and timing."""

    @staticmethod
    def success(
        parent: QWidget,
        title: str,
        content: str = "",
        duration: int | None = None,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT,
    ) -> None:
        """Show a success notification (green checkmark).

        Use for: successful save, successful operation completion.
        Default duration: 1.5 seconds.
        """
        InfoBar.success(
            title=title,
            content=content,
            duration=duration if duration is not None else DURATION_SUCCESS,
            position=position,
            parent=parent,
        )

    @staticmethod
    def info(
        parent: QWidget,
        title: str,
        content: str = "",
        duration: int | None = None,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT,
    ) -> None:
        """Show an informational notification (blue icon).

        Use for: status updates, non-critical information.
        Default duration: 2 seconds.
        """
        InfoBar.info(
            title=title,
            content=content,
            duration=duration if duration is not None else DURATION_INFO,
            position=position,
            parent=parent,
        )

    @staticmethod
    def warning(
        parent: QWidget,
        title: str,
        content: str = "",
        duration: int | None = None,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT,
    ) -> None:
        """Show a warning notification (yellow icon).

        Use for: non-critical issues, things user should be aware of.
        Default duration: 3 seconds.
        """
        InfoBar.warning(
            title=title,
            content=content,
            duration=duration if duration is not None else DURATION_WARNING,
            position=position,
            parent=parent,
        )

    @staticmethod
    def error(
        parent: QWidget,
        title: str,
        content: str = "",
        duration: int | None = None,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT,
    ) -> None:
        """Show an error notification (red icon).

        Use for: operation failures, validation errors.
        Default duration: 5 seconds.
        """
        InfoBar.error(
            title=title,
            content=content,
            duration=duration if duration is not None else DURATION_ERROR,
            position=position,
            parent=parent,
        )

    @staticmethod
    def critical(
        parent: QWidget,
        title: str,
        content: str = "",
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT,
    ) -> None:
        """Show a critical error notification that persists until dismissed.

        Use for: critical failures, data loss warnings, security issues.
        Duration: Persistent (user must dismiss).
        """
        InfoBar.error(
            title=title,
            content=content,
            duration=DURATION_CRITICAL,
            position=position,
            parent=parent,
        )

    @staticmethod
    def custom(
        parent: QWidget,
        icon: InfoBarIcon,
        title: str,
        content: str = "",
        duration: int = DURATION_INFO,
        position: InfoBarPosition = InfoBarPosition.TOP_RIGHT,
    ) -> None:
        """Show a custom notification with specified icon and duration."""
        InfoBar.new(
            icon=icon,
            title=title,
            content=content,
            duration=duration,
            position=position,
            parent=parent,
        )


# Convenience functions for quick access
def show_success(parent: QWidget, title: str, content: str = "") -> None:
    """Quick success notification."""
    NotificationManager.success(parent, title, content)


def show_info(parent: QWidget, title: str, content: str = "") -> None:
    """Quick info notification."""
    NotificationManager.info(parent, title, content)


def show_warning(parent: QWidget, title: str, content: str = "") -> None:
    """Quick warning notification."""
    NotificationManager.warning(parent, title, content)


def show_error(parent: QWidget, title: str, content: str = "") -> None:
    """Quick error notification."""
    NotificationManager.error(parent, title, content)
