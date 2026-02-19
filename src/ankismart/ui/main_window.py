from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import QMessageBox
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    NavigationItemPosition,
    NavigationToolButton,
    setTheme,
    Theme,
    qconfig,
    isDarkTheme,
)

from ankismart.core.config import AppConfig, load_config, save_config
from .i18n import set_language, t
from .import_page import ImportPage
from .preview_page import PreviewPage
from .result_page import ResultPage
from .performance_page import PerformancePage
from .card_preview_page import CardPreviewPage
from .settings_page import SettingsPage
from .shortcuts import ShortcutKeys, create_shortcut, get_shortcut_text


class MainWindow(FluentWindow):
    """Main application window with navigation and page management."""

    language_changed = pyqtSignal(str)  # Signal emitted when language changes
    theme_changed = pyqtSignal(str)  # Signal emitted when theme changes
    config_updated = pyqtSignal(list)  # Signal emitted when runtime config fields change

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        if self.config.theme not in {"light", "dark", "auto"}:
            self.config.theme = "light"
        self._cards = []
        self._batch_result = None
        self._connection_status = False

        # Set initial language
        set_language(self.config.language)

        # Apply initial theme before creating pages
        self._apply_theme()

        # Initialize pages
        self.import_page = ImportPage(self)
        self.preview_page = PreviewPage(self)
        self.card_preview_page = CardPreviewPage(self)
        self.result_page = ResultPage(self)
        self.performance_page = PerformancePage(self)
        self.settings_page = SettingsPage(self)
        self._import_page = self.import_page
        self._preview_page = self.preview_page
        self._card_preview_page = self.card_preview_page
        self._result_page = self.result_page
        self._performance_page = self.performance_page
        self._settings_page = self.settings_page

        self._init_window()
        self._init_navigation()
        self._init_shortcuts()

        # Connect to qconfig theme change signal for real-time updates
        qconfig.themeChanged.connect(self._on_theme_changed)

    def _init_window(self):
        """Initialize window properties."""
        self.setWindowTitle("Ankismart")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 700)  # Set minimum size for DPI compatibility

        # Make top title bar slimmer and sync content top margin
        if hasattr(self, "titleBar") and self.titleBar is not None:
            self.titleBar.setFixedHeight(34)
            if hasattr(self, "widgetLayout") and self.widgetLayout is not None:
                self.widgetLayout.setContentsMargins(0, self.titleBar.height(), 0, 0)

        # Set window icon
        icon_path = self._get_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _init_navigation(self):
        """Initialize navigation interface with pages."""
        # Set navigation panel width to 1/3 of default (narrower)
        self.navigationInterface.setMinimumExpandWidth(150)
        self.navigationInterface.setExpandWidth(150)

        # Get translated labels
        labels = self._get_navigation_labels()

        # Add navigation items
        self.addSubInterface(
            self.import_page,
            FluentIcon.FOLDER_ADD,
            labels["import"],
            NavigationItemPosition.TOP
        )

        self.addSubInterface(
            self.preview_page,
            FluentIcon.VIEW,
            labels["preview"],
            NavigationItemPosition.TOP
        )

        self.addSubInterface(
            self.card_preview_page,
            FluentIcon.BOOK_SHELF,
            labels.get("card_preview", "卡片预览" if self.config.language == "zh" else "Card Preview"),
            NavigationItemPosition.TOP
        )

        self.addSubInterface(
            self.result_page,
            FluentIcon.COMPLETED,
            labels["result"],
            NavigationItemPosition.TOP
        )

        self.addSubInterface(
            self.performance_page,
            FluentIcon.SPEED_HIGH,
            labels["performance"],
            NavigationItemPosition.TOP
        )

        self._theme_nav_button = NavigationToolButton(self._get_theme_button_icon())
        self.navigationInterface.addWidget(
            "themeModeButton",
            self._theme_nav_button,
            onClick=self._cycle_theme_mode,
            position=NavigationItemPosition.BOTTOM,
            tooltip=self._get_theme_button_tooltip(),
        )

        self._github_nav_button = NavigationToolButton(FluentIcon.GITHUB)
        self.navigationInterface.addWidget(
            "githubButton",
            self._github_nav_button,
            onClick=self._open_github_repository,
            position=NavigationItemPosition.BOTTOM,
            tooltip="GitHub",
        )

        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            labels["settings"],
            NavigationItemPosition.BOTTOM
        )
        self._update_theme_button_tooltip()

    def _get_theme_button_tooltip(self) -> str:
        """Get localized tooltip text for sidebar theme mode button."""
        is_zh = self.config.language == "zh"
        theme_map_zh = {
            "light": "浅色",
            "dark": "深色",
            "auto": "跟随系统",
        }
        theme_map_en = {
            "light": "Light",
            "dark": "Dark",
            "auto": "System",
        }
        if is_zh:
            current = theme_map_zh.get(self.config.theme, "浅色")
            return f"主题：{current}"
        current = theme_map_en.get(self.config.theme, "Light")
        return f"Theme: {current}"

    def _get_theme_button_icon(self) -> FluentIcon:
        """Get icon for current theme mode: light/dark/auto."""
        icon_map = {
            "light": FluentIcon.BRIGHTNESS,
            "dark": FluentIcon.QUIET_HOURS,
            "auto": FluentIcon.IOT,
        }
        return icon_map.get(self.config.theme, FluentIcon.BRIGHTNESS)

    def _update_theme_button_tooltip(self) -> None:
        """Refresh sidebar theme mode button tooltip."""
        button = getattr(self, "_theme_nav_button", None)
        if button is not None:
            button.setToolTip(self._get_theme_button_tooltip())
            button.setIcon(self._get_theme_button_icon())

    def _cycle_theme_mode(self) -> None:
        """Cycle theme mode: light -> dark -> auto -> light."""
        modes = ["light", "dark", "auto"]
        current = self.config.theme if self.config.theme in modes else "light"
        next_mode = modes[(modes.index(current) + 1) % len(modes)]
        self.switch_theme(next_mode)

    def _open_github_repository(self) -> None:
        """Open project GitHub repository."""
        QDesktopServices.openUrl(QUrl("https://github.com/lllll081926i/Ankismart"))

    def _init_shortcuts(self):
        """Initialize global keyboard shortcuts."""
        # Ctrl+, : Open Settings
        create_shortcut(
            self,
            ShortcutKeys.OPEN_SETTINGS,
            self._open_settings,
            Qt.ShortcutContext.ApplicationShortcut
        )

        # F1: Help
        create_shortcut(
            self,
            ShortcutKeys.HELP,
            self._show_help,
            Qt.ShortcutContext.ApplicationShortcut
        )

        # Ctrl+Q: Quit
        create_shortcut(
            self,
            ShortcutKeys.QUIT,
            self._quit_application,
            Qt.ShortcutContext.ApplicationShortcut
        )

    def _open_settings(self):
        """Open settings page via shortcut."""
        self.switchTo(self.settings_page)

    def _show_help(self):
        """Show keyboard shortcuts help dialog."""
        from .shortcuts_dialog import ShortcutsHelpDialog

        dialog = ShortcutsHelpDialog(self.config.language, self)
        dialog.exec()

    def _quit_application(self):
        """Quit application via shortcut."""
        self.close()

    def _apply_theme(self):
        """Apply theme based on configuration."""
        theme_name = self.config.theme.lower()

        if theme_name == "dark":
            theme = Theme.DARK
        elif theme_name == "light":
            theme = Theme.LIGHT
        elif theme_name == "auto":
            theme = Theme.AUTO
        else:
            theme = Theme.LIGHT  # Default fallback

        setTheme(theme)

    def _on_theme_changed(self, theme: Theme):
        """Handle theme change from qconfig signal.

        This is called when the theme actually changes (including auto mode
        following system theme changes).
        """
        # Emit our own signal to notify all pages
        theme_name = "dark" if isDarkTheme() else "light"
        self.theme_changed.emit(theme_name)

        # Notify all pages to update their custom styles
        if hasattr(self.preview_page, 'update_theme'):
            self.preview_page.update_theme()
        if hasattr(self.import_page, 'update_theme'):
            self.import_page.update_theme()
        if hasattr(self.result_page, 'update_theme'):
            self.result_page.update_theme()
        if hasattr(self.performance_page, 'update_theme'):
            self.performance_page.update_theme()
        if hasattr(self.card_preview_page, 'update_theme'):
            self.card_preview_page.update_theme()
        if hasattr(self.settings_page, 'update_theme'):
            self.settings_page.update_theme()
        self._update_theme_button_tooltip()

    def _get_navigation_labels(self) -> dict[str, str]:
        """Get navigation labels based on current language."""
        lang = self.config.language
        return {
            "import": t("nav.import", lang),
            "preview": t("nav.preview", lang),
            "card_preview": t("nav.card_preview", lang),
            "result": t("nav.result", lang),
            "performance": t("nav.performance", lang),
            "settings": t("nav.settings", lang)
        }

    @staticmethod
    def _diff_config_fields(old_config: AppConfig, new_config: AppConfig) -> set[str]:
        old_data = old_config.model_dump()
        new_data = new_config.model_dump()
        changed: set[str] = set()
        for key, value in new_data.items():
            if old_data.get(key) != value:
                changed.add(key)
        return changed

    def _apply_language_runtime(self, language: str) -> None:
        """Apply language change immediately without restart."""
        set_language(language)
        self.language_changed.emit(language)
        self._refresh_navigation()

        if hasattr(self.import_page, "retranslate_ui"):
            self.import_page.retranslate_ui()
        if hasattr(self.preview_page, "retranslate_ui"):
            self.preview_page.retranslate_ui()
        if hasattr(self.result_page, "retranslate_ui"):
            self.result_page.retranslate_ui()
        if hasattr(self.card_preview_page, "retranslate_ui"):
            self.card_preview_page.retranslate_ui()
        if hasattr(self.performance_page, "retranslate_ui"):
            self.performance_page.retranslate_ui()
        if hasattr(self.settings_page, "retranslate_ui"):
            self.settings_page.retranslate_ui()
        self._update_theme_button_tooltip()

    def apply_runtime_config(
        self,
        config: AppConfig,
        *,
        persist: bool = True,
        changed_fields: set[str] | None = None,
    ) -> set[str]:
        """Apply runtime config updates and notify listeners."""
        current = self.config
        changed = changed_fields or self._diff_config_fields(current, config)
        self.config = config

        if persist:
            save_config(self.config)

        if "theme" in changed:
            self._apply_theme()
            self._update_theme_button_tooltip()

        if "language" in changed:
            self._apply_language_runtime(self.config.language)

        if "log_level" in changed:
            from ankismart.core.logging import set_log_level
            set_log_level(self.config.log_level)

        self.config_updated.emit(sorted(changed))
        return changed

    def _get_icon_path(self) -> Path:
        """Get the path to the application icon."""
        return Path(__file__).resolve().parent / "assets" / "icon.ico"

    def switch_theme(self, theme: str):
        """Switch application theme and apply immediately.

        Args:
            theme: Theme name ("light", "dark", or "auto")
        """
        if self.config.theme == theme:
            return
        updated = self.config.model_copy(update={"theme": theme})
        self.apply_runtime_config(updated, persist=True, changed_fields={"theme"})
        # Note: _on_theme_changed will be called automatically by qconfig.themeChanged signal.

    def switch_language(self, language: str):
        """Switch application language and refresh all UI components.

        Args:
            language: Language code ("zh" or "en")
        """
        if self.config.language == language:
            return  # No change needed

        updated = self.config.model_copy(update={"language": language})
        self.apply_runtime_config(updated, persist=True, changed_fields={"language"})

    def _refresh_navigation(self):
        """Refresh navigation labels after language change."""
        labels = self._get_navigation_labels()
        set_item_text = getattr(self.navigationInterface, "setItemText", None)
        if not callable(set_item_text):
            return

        route_to_label = {
            self.import_page.objectName(): labels["import"],
            self.preview_page.objectName(): labels["preview"],
            self.card_preview_page.objectName(): labels["card_preview"],
            self.result_page.objectName(): labels["result"],
            self.performance_page.objectName(): labels["performance"],
            self.settings_page.objectName(): labels["settings"],
        }
        for route_key, text in route_to_label.items():
            try:
                set_item_text(route_key, text)
            except Exception:
                continue

    def _switch_page(self, index: int) -> None:
        """Switch page by index for backward compatibility."""
        pages = [self.import_page, self.preview_page, self.card_preview_page, self.result_page, self.performance_page, self.settings_page]
        if 0 <= index < len(pages):
            self.switchTo(pages[index])

    def switch_to_preview(self, pending_files_count: int = 0, total_expected: int = 0) -> None:
        """Switch to preview page and load batch result when available.

        Args:
            pending_files_count: Number of files still being converted
            total_expected: Total expected number of documents
        """
        preview_page = getattr(self, "_preview_page", None)
        if preview_page is None:
            preview_page = getattr(self, "preview_page", None)
        batch_result = getattr(self, "_batch_result", None)
        if preview_page is not None and batch_result is not None:
            load_documents = getattr(preview_page, "load_documents", None)
            if callable(load_documents):
                try:
                    load_documents(batch_result, pending_files_count, total_expected)
                except TypeError:
                    # Backward compatibility for legacy mocks/adapters.
                    load_documents(batch_result)
        self._switch_page(1)

    def switch_to_result(self) -> None:
        """Switch to result page."""
        self._switch_page(3)

    def switch_to_results(self) -> None:
        """Compatibility alias for old callers."""
        self.switch_to_result()

    def set_connection_status(self, connected: bool) -> None:
        """Store connection status for settings page feedback."""
        self._connection_status = connected

    @property
    def cards(self):
        return self._cards

    @cards.setter
    def cards(self, value):
        self._cards = value

    @property
    def batch_result(self):
        return self._batch_result

    @batch_result.setter
    def batch_result(self, value):
        self._batch_result = value

    def closeEvent(self, event):
        """Save window geometry before closing."""
        geometry = self.saveGeometry().toHex().data().decode()
        self.config.window_geometry = geometry
        save_config(self.config)
        super().closeEvent(event)
