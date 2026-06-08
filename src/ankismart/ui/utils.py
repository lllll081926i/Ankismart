from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget
from qfluentwidgets import BodyLabel, InfoBar, InfoBarPosition

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


def _set_regular_label(label: BodyLabel) -> None:
    font = label.font()
    font.setBold(False)
    label.setFont(font)
    label.setWordWrap(False)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


def update_progress_infobar_text(
    info_bar: QWidget | None,
    title: str,
    content: str,
    *,
    duration: int | None = None,
    fixed_height: int = 52,
) -> bool:
    """Use stable single-line labels inside a qfluent InfoBar for progress updates."""
    if info_bar is None:
        return False

    try:
        if duration is not None:
            setattr(info_bar, "duration", duration)

        title_label = getattr(info_bar, "_progress_title_label", None)
        content_label = getattr(info_bar, "_progress_content_label", None)

        if title_label is None or content_label is None:
            if not hasattr(info_bar, "addWidget"):
                return False

            for attr in ("titleLabel", "contentLabel"):
                default_label = getattr(info_bar, attr, None)
                if default_label is not None:
                    default_label.setText("")
                    default_label.setVisible(False)
                    default_label.setWordWrap(False)

            text_widget = QWidget(info_bar)
            text_widget.setObjectName("progressInfoBarText")
            text_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            text_layout = QHBoxLayout(text_widget)
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(24)

            title_label = BodyLabel(text_widget)
            title_label.setObjectName("progressInfoBarTitle")
            content_label = BodyLabel(text_widget)
            content_label.setObjectName("progressInfoBarContent")
            _set_regular_label(title_label)
            _set_regular_label(content_label)

            title_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            content_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            text_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)
            text_layout.addWidget(content_label, 1, Qt.AlignmentFlag.AlignVCenter)

            info_bar.addWidget(text_widget, 1)
            setattr(info_bar, "_progress_text_widget", text_widget)
            setattr(info_bar, "_progress_title_label", title_label)
            setattr(info_bar, "_progress_content_label", content_label)

        title_label.setText(title)
        content_label.setText(content)
        title_label.setVisible(bool(title))
        content_label.setVisible(bool(content))

        if hasattr(info_bar, "setFixedHeight"):
            info_bar.setFixedHeight(fixed_height)
        if hasattr(info_bar, "setSizePolicy"):
            info_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if hasattr(info_bar, "updateGeometry"):
            info_bar.updateGeometry()
        parent_widget = getattr(info_bar, "parentWidget", lambda: None)()
        parent_width = 0
        if parent_widget is not None:
            width_getter = getattr(parent_widget, "width", None)
            if callable(width_getter):
                parent_width = int(width_getter() or 0)
        if parent_width > 0:
            max_width = max(240, min(parent_width - 48, max(360, int(parent_width * 0.72))))
            if hasattr(info_bar, "setMaximumWidth"):
                info_bar.setMaximumWidth(max_width)
        if hasattr(info_bar, "adjustSize"):
            info_bar.adjustSize()
        if parent_width > 0 and hasattr(info_bar, "move"):
            width_getter = getattr(info_bar, "width", None)
            y_getter = getattr(info_bar, "y", None)
            info_width = int(width_getter() if callable(width_getter) else 0)
            y_pos = int(y_getter() if callable(y_getter) else 0)
            x_pos = max(0, (parent_width - info_width) // 2)
            info_bar.move(x_pos, max(0, y_pos))
        return True
    except RuntimeError:
        return False


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
