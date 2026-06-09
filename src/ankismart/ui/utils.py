from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QEvent, QObject, QPoint, Qt, QTimer
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


_PROGRESS_INFOBAR_MIN_WIDTH = 240
_PROGRESS_INFOBAR_WINDOW_MARGIN = 88
_PROGRESS_INFOBAR_MAX_WIDTH = 920


def _widget_width(widget: object) -> int:
    width_getter = getattr(widget, "width", None)
    if not callable(width_getter):
        return 0
    try:
        return max(0, int(width_getter() or 0))
    except RuntimeError:
        raise
    except Exception:
        return 0


def _widget_size_hint_width(widget: object) -> int:
    size_hint_getter = getattr(widget, "sizeHint", None)
    if not callable(size_hint_getter):
        return 0
    try:
        size_hint = size_hint_getter()
        width_getter = getattr(size_hint, "width", None)
        return max(0, int(width_getter() or 0)) if callable(width_getter) else 0
    except RuntimeError:
        raise
    except Exception:
        return 0


def _progress_infobar_max_width(window_width: int) -> int:
    available_width = max(
        _PROGRESS_INFOBAR_MIN_WIDTH,
        window_width - _PROGRESS_INFOBAR_WINDOW_MARGIN,
    )
    return min(available_width, _PROGRESS_INFOBAR_MAX_WIDTH)


def _progress_infobar_chrome_width(info_bar: QWidget) -> int:
    stored_width = getattr(info_bar, "_progress_chrome_width", None)
    if isinstance(stored_width, int) and stored_width > 0:
        return stored_width

    hint_width = _widget_size_hint_width(info_bar)
    if hint_width > 0:
        setattr(info_bar, "_progress_chrome_width", hint_width)
        return hint_width

    current_width = _widget_width(info_bar)
    if current_width > 0:
        setattr(info_bar, "_progress_chrome_width", current_width)
    return current_width


def _progress_infobar_natural_width(info_bar: QWidget) -> int:
    text_widget = getattr(info_bar, "_progress_text_widget", None)
    text_width = _widget_size_hint_width(text_widget)
    if text_width > 0:
        return _progress_infobar_chrome_width(info_bar) + text_width

    return _widget_width(info_bar)


def _progress_infobar_target_width(info_bar: QWidget, window_width: int) -> int:
    max_width = _progress_infobar_max_width(window_width)
    min_width = min(_PROGRESS_INFOBAR_MIN_WIDTH, max_width)
    natural_width = _progress_infobar_natural_width(info_bar)
    return min(max(natural_width, min_width), max_width)


def _progress_infobar_center_x(info_bar: QWidget, target_width: int, window_width: int) -> int:
    parent_widget = info_bar.parentWidget()
    window_getter = getattr(info_bar, "window", None)
    window_widget = window_getter() if callable(window_getter) else parent_widget
    if parent_widget is not None and window_widget is not None and window_widget is not info_bar:
        try:
            center_global = window_widget.mapToGlobal(QPoint(window_width // 2, 0))
            center_in_parent = parent_widget.mapFromGlobal(center_global).x()
            return center_in_parent - target_width // 2
        except RuntimeError:
            raise
        except Exception:
            pass
    return (window_width - target_width) // 2


class _ProgressInfoBarPositionFilter(QObject):
    def __init__(self, info_bar: QWidget) -> None:
        super().__init__(info_bar)
        self._info_bar = info_bar

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() in (QEvent.Type.Resize, QEvent.Type.WindowStateChange):
            QTimer.singleShot(0, lambda: _safe_position_progress_infobar(self._info_bar))
        return super().eventFilter(obj, event)


def _ensure_progress_infobar_position_filter(info_bar: QWidget) -> None:
    if not isinstance(info_bar, QObject):
        return

    event_filter = getattr(info_bar, "_progress_position_filter", None)
    if event_filter is None:
        event_filter = _ProgressInfoBarPositionFilter(info_bar)
        setattr(info_bar, "_progress_position_filter", event_filter)
        setattr(info_bar, "_progress_position_filter_targets", [])

    targets = getattr(info_bar, "_progress_position_filter_targets", [])
    parent_widget = info_bar.parentWidget()
    window_getter = getattr(info_bar, "window", None)
    window_widget = window_getter() if callable(window_getter) else None

    for target in (parent_widget, window_widget):
        if target is None or any(target is installed for installed in targets):
            continue
        try:
            target.installEventFilter(event_filter)
            targets.append(target)
        except RuntimeError:
            raise
        except Exception:
            continue


def _progress_infobar_animation_y(info_bar: QWidget, fallback_y: int) -> int:
    property_getter = getattr(info_bar, "property", None)
    if not callable(property_getter):
        return fallback_y

    try:
        slide_animation = property_getter("slideAni")
        end_value_getter = getattr(slide_animation, "endValue", None)
        end_value = end_value_getter() if callable(end_value_getter) else None
    except RuntimeError:
        raise
    except Exception:
        return fallback_y

    if isinstance(end_value, QPoint):
        return max(0, end_value.y())
    return fallback_y


def _sync_progress_infobar_animation_target(info_bar: QWidget, target_pos: QPoint) -> None:
    property_getter = getattr(info_bar, "property", None)
    if not callable(property_getter):
        return

    for animation_name in ("slideAni", "dropAni"):
        try:
            animation = property_getter(animation_name)
        except RuntimeError:
            raise
        except Exception:
            continue
        if animation is None:
            continue

        for method_name in ("stop",):
            method = getattr(animation, method_name, None)
            if callable(method):
                method()
        for method_name in ("setStartValue", "setEndValue"):
            method = getattr(animation, method_name, None)
            if callable(method):
                method(target_pos)


def _position_progress_infobar(info_bar: QWidget) -> None:
    parent_widget = info_bar.parentWidget()
    window_getter = getattr(info_bar, "window", None)
    window_widget = window_getter() if callable(window_getter) else parent_widget
    width_source = (
        window_widget
        if window_widget is not None and window_widget is not info_bar
        else parent_widget
    )
    width_getter = getattr(width_source, "width", None)
    window_width = int(width_getter() or 0) if callable(width_getter) else 0
    if window_width <= 0:
        return

    target_width = _progress_infobar_target_width(info_bar, window_width)
    if hasattr(info_bar, "setFixedWidth"):
        info_bar.setFixedWidth(target_width)
    elif hasattr(info_bar, "setMaximumWidth"):
        info_bar.setMaximumWidth(target_width)

    if hasattr(info_bar, "adjustSize"):
        info_bar.adjustSize()
    if hasattr(info_bar, "move"):
        actual_width = _widget_width(info_bar) or target_width
        y_getter = getattr(info_bar, "y", None)
        fallback_y = max(0, int(y_getter() if callable(y_getter) else 0))
        target_pos = QPoint(
            _progress_infobar_center_x(info_bar, actual_width, window_width),
            _progress_infobar_animation_y(info_bar, fallback_y),
        )
        _sync_progress_infobar_animation_target(info_bar, target_pos)
        try:
            info_bar.move(target_pos)
        except TypeError:
            info_bar.move(target_pos.x(), target_pos.y())

    _ensure_progress_infobar_position_filter(info_bar)


def _safe_position_progress_infobar(info_bar: QWidget) -> None:
    try:
        _position_progress_infobar(info_bar)
    except RuntimeError:
        return


def update_progress_infobar_text(
    info_bar: QWidget | None,
    title: str,
    content: str,
    *,
    duration: int | None = None,
    fixed_height: int = 52,
) -> bool:
    """Use stable single-line labels inside a qfluent InfoBar for progress updates.

    Args:
        info_bar: InfoBar widget to update
        title: Title text to display
        content: Content text to display
        duration: Optional duration in milliseconds
        fixed_height: Fixed height for the InfoBar

    Returns:
        True if update succeeded, False otherwise
    """
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

            _progress_infobar_chrome_width(info_bar)

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

        # Safely set text with truncation for very long strings
        safe_title = title[:200] if len(title) > 200 else title
        safe_content = content[:500] if len(content) > 500 else content

        title_label.setText(safe_title)
        content_label.setText(safe_content)
        title_label.setVisible(bool(title))
        content_label.setVisible(bool(content))

        # Set tooltip for truncated text (check if method exists)
        if len(title) > 200 and hasattr(title_label, "setToolTip"):
            title_label.setToolTip(title)
        elif hasattr(title_label, "setToolTip"):
            title_label.setToolTip("")

        if len(content) > 500 and hasattr(content_label, "setToolTip"):
            content_label.setToolTip(content)
        elif hasattr(content_label, "setToolTip"):
            content_label.setToolTip("")

        if hasattr(info_bar, "setFixedHeight"):
            info_bar.setFixedHeight(fixed_height)
        if hasattr(info_bar, "setSizePolicy"):
            info_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if hasattr(info_bar, "updateGeometry"):
            info_bar.updateGeometry()
        _position_progress_infobar(info_bar)
        QTimer.singleShot(0, lambda: _safe_position_progress_infobar(info_bar))
        return True
    except RuntimeError:
        return False
    except Exception as exc:
        # Log unexpected errors but don't crash the UI
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating progress infobar: {exc}", exc_info=True)
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
