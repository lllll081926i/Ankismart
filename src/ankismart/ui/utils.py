from __future__ import annotations

import re
import time
from statistics import median
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition

if TYPE_CHECKING:
    from qfluentwidgets import ProgressBar, ProgressRing, PushButton

    from ankismart.core.config import AppConfig


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


def format_operation_hint(config: AppConfig, *, event: str, language: str) -> str:
    duration_field_map = {
        "convert": "ops_conversion_durations",
        "generate": "ops_generation_durations",
        "push": "ops_push_durations",
        "export": "ops_export_durations",
    }
    history_event_map = {
        "convert": "batch_convert",
        "generate": "batch_generate",
        "push": "batch_push",
        "export": "export_apkg",
    }
    title_map = {
        "convert": ("最近转换", "Recent convert"),
        "generate": ("最近生成", "Recent generation"),
        "push": ("最近推送", "Recent push"),
        "export": ("最近导出", "Recent export"),
    }
    empty_map = {
        "convert": ("转换后会在这里显示最近耗时", "Recent conversion timing will appear here"),
        "generate": (
            "生成后会在这里显示最近耗时",
            "Recent generation timing will appear here",
        ),
        "push": ("推送后会在这里显示最近耗时", "Recent push timing will appear here"),
        "export": ("导出后会在这里显示最近耗时", "Recent export timing will appear here"),
    }

    durations = [float(v) for v in getattr(config, duration_field_map.get(event, ""), []) or []]
    last_duration = 0.0
    history_event = history_event_map.get(event, "")
    for item in list(getattr(config, "task_history", []) or []):
        if str(item.get("event", "")) != history_event:
            continue
        payload = item.get("payload", {}) or {}
        try:
            last_duration = float(payload.get("duration_seconds", 0.0) or 0.0)
        except (TypeError, ValueError):
            last_duration = 0.0
        if last_duration > 0:
            break

    is_zh = language == "zh"
    title = title_map.get(event, ("最近操作", "Recent operation"))[0 if is_zh else 1]
    empty_text = empty_map.get(event, ("最近耗时将在此显示", "Recent timing will appear here"))[
        0 if is_zh else 1
    ]
    if not durations and last_duration <= 0:
        return empty_text

    segments: list[str] = []
    if last_duration > 0:
        segments.append(
            f"{title} {last_duration:.1f} 秒" if is_zh else f"{title} {last_duration:.1f} s"
        )
    if durations:
        p50 = median(durations)
        segments.append(f"P50 {p50:.1f} 秒" if is_zh else f"P50 {p50:.1f} s")
    return "，".join(segments) if is_zh else ", ".join(segments)


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
