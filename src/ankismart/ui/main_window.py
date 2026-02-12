from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition, setTheme, Theme

from ankismart.core.config import AppConfig, load_config, save_config
from .import_page import ImportPage
from .preview_page import PreviewPage
from .result_page import ResultPage
from .settings_page import SettingsPage


class MainWindow(FluentWindow):
    """Main application window with navigation and page management."""

    def __init__(self):
        super().__init__()
        self.config = load_config()

        # Initialize pages
        self.import_page = ImportPage(self)
        self.preview_page = PreviewPage(self)
        self.result_page = ResultPage(self)
        self.settings_page = SettingsPage(self)

        self._init_window()
        self._init_navigation()
        self._apply_theme()

    def _init_window(self):
        """Initialize window properties."""
        self.setWindowTitle("Ankismart")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 700)  # Set minimum size for DPI compatibility

        # Set window icon
        icon_path = self._get_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _init_navigation(self):
        """Initialize navigation interface with pages."""
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
            self.result_page,
            FluentIcon.COMPLETED,
            labels["result"],
            NavigationItemPosition.TOP
        )

        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            labels["settings"],
            NavigationItemPosition.BOTTOM
        )

    def _apply_theme(self):
        """Apply theme based on configuration."""
        theme = Theme.DARK if self.config.theme == "dark" else Theme.LIGHT
        setTheme(theme)

    def _get_navigation_labels(self) -> dict[str, str]:
        """Get navigation labels based on current language."""
        if self.config.language == "en":
            return {
                "import": "Import",
                "preview": "Preview",
                "result": "Result",
                "settings": "Settings"
            }
        else:  # zh (default)
            return {
                "import": "导入",
                "preview": "预览",
                "result": "结果",
                "settings": "设置"
            }

    def _get_icon_path(self) -> Path:
        """Get the path to the application icon."""
        # Resolve project root (3 levels up from this file)
        project_root = Path(__file__).resolve().parents[3]
        return project_root / "icon.png"

    def switch_theme(self, theme: str):
        """Switch application theme.

        Args:
            theme: Theme name ("light" or "dark")
        """
        self.config.theme = theme
        save_config(self.config)
        self._apply_theme()

    def switch_language(self, language: str):
        """Switch application language.

        Args:
            language: Language code ("zh" or "en")
        """
        self.config.language = language
        save_config(self.config)
        # Note: Full language switch requires window restart or dynamic update
        # This can be implemented in the settings page

    def closeEvent(self, event):
        """Save window geometry before closing."""
        geometry = self.saveGeometry().toHex().data().decode()
        self.config.window_geometry = geometry
        save_config(self.config)
        super().closeEvent(event)
