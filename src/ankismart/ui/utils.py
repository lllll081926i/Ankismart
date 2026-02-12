from __future__ import annotations

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
    import re
    title = re.sub(r"<[^>]+>", "", title)

    # Truncate if too long
    if len(title) > max_length:
        title = title[:max_length] + "..."

    return title.strip()


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
