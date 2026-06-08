from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition

if TYPE_CHECKING:
    from qfluentwidgets import ProgressBar, ProgressRing, PushButton


def request_infobar_confirmation(
    parent: QWidget,
    confirmations: dict[str, float],
    *,
    key: str,
    title: str,
    content: str,
    timeout_seconds: float = 2.5,
) -> bool:
    """Require a second click within a short window instead of modal confirmation."""
    now = time.monotonic()
    last = float(confirmations.get(key, 0.0) or 0.0)
    if now - last <= timeout_seconds:
        confirmations.pop(key, None)
        return True

    confirmations[key] = now
    InfoBar.warning(
        title=title,
        content=content,
        orient=Qt.Orientation.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=max(1800, int(timeout_seconds * 1000)),
        parent=parent,
    )
    return False


def split_tags_text(tags_text: str) -> list[str]:
    """Split tags by both English and Chinese commas and trim blanks."""
    if not tags_text.strip():
        return []
    return [part.strip() for part in re.split(r"[，,]", tags_text) if part.strip()]


class ProgressMixin:
    """Mixin class for common progress display functionality.

    Requires the following attributes in the subclass:
    - _progress_ring: ProgressRing widget
    - _progress_bar: ProgressBar widget
    - _btn_cancel: PushButton widget
    """

    _progress_ring: ProgressRing
    _progress_bar: ProgressBar
    _btn_cancel: PushButton

    def _show_progress(self, message: str = "") -> None:
        """Show progress indicators.

        Args:
            message: Optional status message to display
        """
        self._progress_ring.show()
        self._progress_bar.show()
        self._progress_bar.setValue(0)
        self._btn_cancel.show()

    def _hide_progress(self) -> None:
        """Hide all progress indicators."""
        self._progress_ring.hide()
        self._progress_bar.hide()
        self._btn_cancel.hide()
        self._btn_cancel.setEnabled(True)

    def _update_progress(self, value: int, message: str = "") -> None:
        """Update progress bar value.

        Args:
            value: Progress value (0-100)
            message: Optional status message to display
        """
        self._progress_bar.setValue(value)
