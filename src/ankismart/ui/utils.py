from __future__ import annotations

import re
from statistics import median
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox

from ankismart.core.config import AppConfig

if TYPE_CHECKING:
    from qfluentwidgets import ProgressBar, ProgressRing, PushButton


def show_error(parent: QWidget, title: str, message: str) -> None:
    """Display an error dialog."""
    MessageBox(title, message, parent).exec()


def show_success(parent: QWidget, message: str, duration: int = 2000) -> None:
    """Display a success notification."""
    InfoBar.success(
        title="成功",
        content=message,
        orient=InfoBarPosition.TOP,
        isClosable=True,
        duration=duration,
        parent=parent,
    )


def show_info(parent: QWidget, message: str, duration: int = 2000) -> None:
    """Display an info notification."""
    InfoBar.info(
        title="提示",
        content=message,
        orient=InfoBarPosition.TOP,
        isClosable=True,
        duration=duration,
        parent=parent,
    )


def format_card_title(card_fields: dict[str, str], max_length: int = 50) -> str:
    """Format a card's title for display.

    Args:
        card_fields: Dictionary of card fields
        max_length: Maximum length of the title

    Returns:
        Formatted title string
    """
    # Try to get Front field first, then Text for cloze cards
    title = card_fields.get("Front") or card_fields.get("Text") or "未命名卡片"

    # Strip HTML tags for display
    title = re.sub(r"<[^>]+>", "", title)

    # Truncate if too long
    if len(title) > max_length:
        title = title[:max_length] + "..."

    return title.strip()


def split_tags_text(tags_text: str) -> list[str]:
    """Split tags by both English and Chinese commas and trim blanks."""
    if not tags_text.strip():
        return []
    return [part.strip() for part in re.split(r"[，,]", tags_text) if part.strip()]


def validate_config(config: AppConfig) -> tuple[bool, str]:
    """Validate configuration for required fields.

    Args:
        config: Application configuration

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if active provider is configured
    active_provider = config.active_provider
    if not active_provider:
        return False, "未配置 LLM 提供商，请在设置中添加"

    if not active_provider.api_key:
        return False, f"LLM 提供商 '{active_provider.name}' 缺少 API Key"

    if not active_provider.base_url:
        return False, f"LLM 提供商 '{active_provider.name}' 缺少 Base URL"

    if not active_provider.model:
        return False, f"LLM 提供商 '{active_provider.name}' 缺少模型名称"

    # Check Anki Connect URL
    if not config.anki_connect_url:
        return False, "未配置 AnkiConnect URL"

    # Check default deck
    if not config.default_deck:
        return False, "未配置默认牌组"

    return True, ""


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
