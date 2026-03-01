from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import QApplication
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    NavigationItemPosition,
    NavigationToolButton,
    Theme,
    isDarkTheme,
    qconfig,
    setCustomStyleSheet,
    setTheme,
    setThemeColor,
)

from ankismart.core.config import AppConfig, load_config, save_config
from ankismart.core.logging import get_logger

from .i18n import set_language, t
from .import_page import ImportPage
from .shortcuts import ShortcutKeys, create_shortcut
from .styles import (
    DARK_PAGE_BACKGROUND_HEX,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    FIXED_PAGE_BACKGROUND_HEX,
    FIXED_THEME_ACCENT_HEX,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    TITLE_BAR_HEIGHT,
    get_display_scale,
    get_stylesheet,
    scale_px,
)

if TYPE_CHECKING:
    from .card_preview_page import CardPreviewPage
    from .performance_page import PerformancePage
    from .preview_page import PreviewPage
    from .result_page import ResultPage
    from .settings_page import SettingsPage

logger = get_logger("ui.main_window")


class MainWindow(FluentWindow):
    """Main application window with navigation and page management."""

    language_changed = pyqtSignal(str)  # Signal emitted when language changes
    theme_changed = pyqtSignal(str)  # Signal emitted when theme changes
    config_updated = pyqtSignal(list)  # Signal emitted when runtime config fields change

    def __init__(self, config: AppConfig | None = None):
        super().__init__()
        self.config = config or load_config()
        if self.config.theme not in {"light", "dark", "auto"}:
            self.config.theme = "light"
        self._cards = []
        self._batch_result = None
        self._connection_status = False
        self._effective_theme_name = "dark" if isDarkTheme() else "light"

        # Set initial language
        set_language(self.config.language)

        # Apply initial theme before creating pages
        self._apply_theme(apply_stylesheet=True)

        # Build only import page on first paint; other pages are lazy/deferred.
        self._import_page = ImportPage(self)
        self._preview_page: PreviewPage | None = None
        self._card_preview_page: CardPreviewPage | None = None
        self._result_page: ResultPage | None = None
        self._performance_page: PerformancePage | None = None
        self._settings_page: SettingsPage | None = None
        self._nav_routes_added: set[str] = set()
        self._deferred_page_queue: list[str] = [
            "preview",
            "card_preview",
            "result",
            "performance",
            "settings",
        ]
        self._deferred_bootstrap_started = False

        self._init_window()
        self._init_navigation()
        self._init_shortcuts()

        # Connect to qconfig theme change signal for real-time updates
        qconfig.themeChanged.connect(self._on_theme_changed)

    def _init_window(self):
        """Initialize window properties."""
        self.setWindowTitle("Ankismart")
        # Keep app chrome color fully controlled by our stylesheet/background config.
        # Win11 mica blends with system accent and makes title bar color unstable.
        self.setMicaEffectEnabled(False)
        self.setCustomBackgroundColor(FIXED_PAGE_BACKGROUND_HEX, DARK_PAGE_BACKGROUND_HEX)

        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        scale = get_display_scale(screen=screen)

        preferred_w = scale_px(DEFAULT_WINDOW_WIDTH, scale=scale, min_value=DEFAULT_WINDOW_WIDTH)
        preferred_h = scale_px(DEFAULT_WINDOW_HEIGHT, scale=scale, min_value=DEFAULT_WINDOW_HEIGHT)
        min_w = scale_px(MIN_WINDOW_WIDTH, scale=scale, min_value=MIN_WINDOW_WIDTH)
        min_h = scale_px(MIN_WINDOW_HEIGHT, scale=scale, min_value=MIN_WINDOW_HEIGHT)

        if available is not None:
            max_w = max(820, available.width() - scale_px(48, scale=scale, min_value=48))
            max_h = max(620, available.height() - scale_px(64, scale=scale, min_value=64))

            effective_min_w = min(min_w, max_w)
            effective_min_h = min(min_h, max_h)
            target_w = max(effective_min_w, min(preferred_w, max_w))
            target_h = max(effective_min_h, min(preferred_h, max_h))

            self.setMinimumSize(effective_min_w, effective_min_h)
            self.resize(target_w, target_h)
        else:
            self.setMinimumSize(min_w, min_h)
            self.resize(preferred_w, preferred_h)

        # Make top title bar slimmer and sync content top margin
        if hasattr(self, "titleBar") and self.titleBar is not None:
            self.titleBar.setFixedHeight(TITLE_BAR_HEIGHT)
            if hasattr(self, "widgetLayout") and self.widgetLayout is not None:
                self.widgetLayout.setContentsMargins(0, self.titleBar.height(), 0, 0)

        # Set window icon
        icon_path = self._get_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._apply_fixed_background_regions()

    def _apply_fixed_background_regions(self) -> None:
        """Apply themed backgrounds: blue in light mode, deep gray in dark mode."""
        bg_light = FIXED_PAGE_BACKGROUND_HEX
        bg_dark = DARK_PAGE_BACKGROUND_HEX
        base_light_qss = f"FluentWindowBase {{ background-color: {bg_light}; }}"
        base_dark_qss = f"FluentWindowBase {{ background-color: {bg_dark}; }}"
        setCustomStyleSheet(self, base_light_qss, base_dark_qss)

        if hasattr(self, "titleBar") and self.titleBar is not None:
            title_light_qss = f"""
FluentTitleBar,
MSFluentTitleBar,
SplitTitleBar,
TitleBar {{
    background-color: {bg_light};
}}
"""
            title_dark_qss = f"""
FluentTitleBar,
MSFluentTitleBar,
SplitTitleBar,
TitleBar {{
    background-color: {bg_dark};
}}
"""
            setCustomStyleSheet(self.titleBar, title_light_qss, title_dark_qss)

        if hasattr(self, "stackedWidget") and self.stackedWidget is not None:
            stacked_light_qss = f"StackedWidget {{ background-color: {bg_light}; }}"
            stacked_dark_qss = f"StackedWidget {{ background-color: {bg_dark}; }}"
            setCustomStyleSheet(self.stackedWidget, stacked_light_qss, stacked_dark_qss)

        panel = getattr(getattr(self, "navigationInterface", None), "panel", None)
        if panel is not None:
            nav_light_qss = f"""
NavigationPanel[menu=true],
NavigationPanel[menu=false],
NavigationPanel[transparent=true] {{
    background-color: {bg_light};
    border: 1px solid transparent;
}}
"""
            nav_dark_qss = f"""
NavigationPanel[menu=true],
NavigationPanel[menu=false],
NavigationPanel[transparent=true] {{
    background-color: {bg_dark};
    border: 1px solid transparent;
}}
"""
            setCustomStyleSheet(panel, nav_light_qss, nav_dark_qss)

    def _init_navigation(self):
        """Initialize navigation interface with pages."""
        # Set adaptive navigation panel width for different resolutions.
        screen = self.screen() or QApplication.primaryScreen()
        available_width = screen.availableGeometry().width() if screen is not None else 1400
        if available_width <= 1200:
            nav_width = 120
        elif available_width <= 1440:
            nav_width = 132
        else:
            nav_width = 150
        self.navigationInterface.setMinimumExpandWidth(nav_width)
        self.navigationInterface.setExpandWidth(nav_width)

        # Get translated labels
        labels = self._get_navigation_labels()

        # Add navigation items
        self.addSubInterface(
            self.import_page,
            FluentIcon.FOLDER_ADD,
            labels["import"],
            NavigationItemPosition.TOP
        )
        self._nav_routes_added.add(self.import_page.objectName())

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

        self._update_theme_button_tooltip()

    def bootstrap_secondary_pages(self) -> None:
        """Build non-import pages incrementally after first frame is shown."""
        if self._deferred_bootstrap_started:
            return
        self._deferred_bootstrap_started = True
        QTimer.singleShot(0, self._bootstrap_next_page)

    def _bootstrap_next_page(self) -> None:
        if not self._deferred_page_queue:
            return
        page_key = self._deferred_page_queue.pop(0)
        self._ensure_page(page_key, add_to_navigation=True)
        if self._deferred_page_queue:
            QTimer.singleShot(0, self._bootstrap_next_page)

    def _create_page(self, page_key: str):
        if page_key == "preview":
            from .preview_page import PreviewPage

            return PreviewPage(self)
        if page_key == "card_preview":
            from .card_preview_page import CardPreviewPage

            return CardPreviewPage(self)
        if page_key == "result":
            from .result_page import ResultPage

            return ResultPage(self)
        if page_key == "performance":
            from .performance_page import PerformancePage

            return PerformancePage(self)
        if page_key == "settings":
            from .settings_page import SettingsPage

            return SettingsPage(self)
        raise KeyError(f"Unsupported page key: {page_key}")

    def _ensure_navigation_item(self, page_key: str, page) -> None:
        route = page.objectName()
        if route in self._nav_routes_added:
            return

        labels = self._get_navigation_labels()
        if page_key == "preview":
            self.addSubInterface(
                page,
                FluentIcon.VIEW,
                labels["preview"],
                NavigationItemPosition.TOP,
            )
        elif page_key == "card_preview":
            self.addSubInterface(
                page,
                FluentIcon.BOOK_SHELF,
                labels.get(
                    "card_preview",
                    "卡片预览" if self.config.language == "zh" else "Card Preview",
                ),
                NavigationItemPosition.TOP,
            )
        elif page_key == "result":
            self.addSubInterface(
                page,
                FluentIcon.COMPLETED,
                labels["result"],
                NavigationItemPosition.TOP,
            )
        elif page_key == "performance":
            self.addSubInterface(
                page,
                FluentIcon.SPEED_HIGH,
                labels["performance"],
                NavigationItemPosition.TOP,
            )
        elif page_key == "settings":
            self.addSubInterface(
                page,
                FluentIcon.SETTING,
                labels["settings"],
                NavigationItemPosition.BOTTOM,
            )
        else:
            raise KeyError(f"Unsupported page key: {page_key}")
        self._nav_routes_added.add(route)

    def _ensure_page(self, page_key: str, *, add_to_navigation: bool = True):
        if page_key == "import":
            return self.import_page

        attr_map = {
            "preview": "_preview_page",
            "card_preview": "_card_preview_page",
            "result": "_result_page",
            "performance": "_performance_page",
            "settings": "_settings_page",
        }
        attr = attr_map.get(page_key)
        if attr is None:
            raise KeyError(f"Unsupported page key: {page_key}")

        page = getattr(self, attr)
        if page is None:
            page = self._create_page(page_key)
            setattr(self, attr, page)
        if add_to_navigation:
            self._ensure_navigation_item(page_key, page)
        return page

    def _iter_initialized_pages(self):
        for page in (
            self._import_page,
            self._preview_page,
            self._card_preview_page,
            self._result_page,
            self._performance_page,
            self._settings_page,
        ):
            if page is not None:
                yield page

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

    def _quit_application(self):
        """Quit application via shortcut."""
        self.close()

    def _apply_theme(self, *, apply_stylesheet: bool = False):
        """Apply theme based on configuration."""
        theme_name = (self.config.theme or "light").lower()
        if theme_name == "dark":
            theme = Theme.DARK
        elif theme_name == "auto":
            theme = Theme.AUTO
        else:
            theme = Theme.LIGHT

        try:
            setTheme(theme, lazy=True)
            setThemeColor(FIXED_THEME_ACCENT_HEX, lazy=True)
        except RuntimeError as exc:
            # qfluentwidgets may raise this during rapid style manager mutations.
            if "dictionary changed size during iteration" not in str(exc):
                raise
            setTheme(theme, lazy=False)
            setThemeColor(FIXED_THEME_ACCENT_HEX, lazy=False)
        if apply_stylesheet:
            self._apply_global_stylesheet()

    def _apply_global_stylesheet(self) -> None:
        """Apply app-level stylesheet derived from current effective theme."""
        app = QApplication.instance()
        if app is not None:
            css = get_stylesheet(dark=isDarkTheme())
            if app.styleSheet() != css:
                app.setStyleSheet(css)

    def _on_theme_changed(self, theme: Theme):
        """Handle theme change from qconfig signal.

        This is called when the effective theme actually changes.
        """
        # Emit our own signal to notify all pages
        theme_name = "dark" if isDarkTheme() else "light"
        if theme_name == self._effective_theme_name:
            self._update_theme_button_tooltip()
            return
        self._effective_theme_name = theme_name
        self.theme_changed.emit(theme_name)
        self._apply_global_stylesheet()

        # Notify all pages to update their custom styles
        for page in self._iter_initialized_pages():
            update_theme = getattr(page, "update_theme", None)
            if callable(update_theme):
                update_theme()
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

        for page in self._iter_initialized_pages():
            retranslate_ui = getattr(page, "retranslate_ui", None)
            if callable(retranslate_ui):
                retranslate_ui()
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
        if theme not in {"light", "dark", "auto"}:
            theme = "light"
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
        }
        if self._preview_page is not None:
            route_to_label[self._preview_page.objectName()] = labels["preview"]
        if self._card_preview_page is not None:
            route_to_label[self._card_preview_page.objectName()] = labels["card_preview"]
        if self._result_page is not None:
            route_to_label[self._result_page.objectName()] = labels["result"]
        if self._performance_page is not None:
            route_to_label[self._performance_page.objectName()] = labels["performance"]
        if self._settings_page is not None:
            route_to_label[self._settings_page.objectName()] = labels["settings"]
        for route_key, text in route_to_label.items():
            try:
                set_item_text(route_key, text)
            except Exception as exc:
                logger.debug(
                    "Skip updating navigation label",
                    extra={
                        "event": "ui.nav.label_update_failed",
                        "route": route_key,
                        "error_detail": str(exc),
                    },
                )
                continue

    def _switch_page(self, index: int) -> None:
        """Switch page by index for backward compatibility."""
        page_keys = ["import", "preview", "card_preview", "result", "performance", "settings"]
        if 0 <= index < len(page_keys):
            page = self._ensure_page(page_keys[index], add_to_navigation=True)
            self.switchTo(page)

    def switch_to_preview(self, pending_files_count: int = 0, total_expected: int = 0) -> None:
        """Switch to preview page and load batch result when available.

        Args:
            pending_files_count: Number of files still being converted
            total_expected: Total expected number of documents
        """
        preview_page = getattr(self, "_preview_page", None)
        if preview_page is None:
            try:
                preview_page = self.preview_page
            except RuntimeError:
                # Compatibility for tests that construct MainWindow via __new__.
                preview_page = None
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

    def _shutdown_pages(self) -> None:
        """Close child pages first so their closeEvent hooks can stop workers safely."""
        page_map = {
            "import_page": self._import_page,
            "preview_page": self._preview_page,
            "card_preview_page": self._card_preview_page,
            "result_page": self._result_page,
            "performance_page": self._performance_page,
            "settings_page": self._settings_page,
        }
        for attr, page in page_map.items():
            if page is None:
                continue
            close_page = getattr(page, "close", None)
            if not callable(close_page):
                continue
            try:
                close_page()
            except Exception as exc:
                logger.debug(
                    "Skip closing page during shutdown",
                    extra={
                        "event": "ui.page.close_failed",
                        "page_attr": attr,
                        "error_detail": str(exc),
                    },
                )
                continue

    @property
    def import_page(self) -> ImportPage:
        return self._import_page

    @property
    def preview_page(self) -> PreviewPage:
        return self._ensure_page("preview", add_to_navigation=True)

    @property
    def card_preview_page(self) -> CardPreviewPage:
        return self._ensure_page("card_preview", add_to_navigation=True)

    @property
    def result_page(self) -> ResultPage:
        return self._ensure_page("result", add_to_navigation=True)

    @property
    def performance_page(self) -> PerformancePage:
        return self._ensure_page("performance", add_to_navigation=True)

    @property
    def settings_page(self) -> SettingsPage:
        return self._ensure_page("settings", add_to_navigation=True)

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

    def closeEvent(self, event):  # noqa: N802
        """Save window geometry before closing."""
        self._shutdown_pages()
        geometry = self.saveGeometry().toHex().data().decode()
        self.config.window_geometry = geometry
        save_config(self.config)
        super().closeEvent(event)
