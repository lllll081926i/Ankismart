"""Application entry point for Ankismart.

Initializes the Qt application, loads configuration, applies theme and language
settings, and launches the main window.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox
from qfluentwidgets import setTheme, Theme

from ankismart.core.config import load_config, save_config
from ankismart.core.logging import get_logger, setup_logging
from ankismart.ui.main_window import MainWindow

logger = get_logger("app")


def _get_icon_path() -> Path:
    """Get the path to the application icon.

    Returns:
        Path to icon.ico in package assets.
    """
    return Path(__file__).resolve().parent / "assets" / "icon.ico"


def _apply_theme(theme_name: str) -> None:
    """Apply the application theme.

    Args:
        theme_name: Theme name ("light", "dark", or "auto")
    """
    theme_name = theme_name.lower()

    if theme_name == "dark":
        theme = Theme.DARK
    elif theme_name == "light":
        theme = Theme.LIGHT
    elif theme_name == "auto":
        theme = Theme.AUTO
    else:
        theme = Theme.LIGHT  # Default fallback

    setTheme(theme)
    logger.info(f"Applied theme: {theme_name}")


def _restore_window_geometry(window: MainWindow, geometry_hex: str) -> None:
    """Restore window geometry from saved configuration.

    Args:
        window: Main window instance
        geometry_hex: Hex-encoded QByteArray geometry string
    """
    if geometry_hex:
        try:
            geometry_bytes = bytes.fromhex(geometry_hex)
            window.restoreGeometry(geometry_bytes)
            logger.debug("Restored window geometry")
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to restore window geometry: {e}")


def main() -> int:
    """Main application entry point.

    Initializes the Qt application, loads configuration, sets up logging,
    applies theme and language settings, and displays the main window.

    Returns:
        Application exit code (0 for success, non-zero for error)
    """
    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application instance
    app = QApplication(sys.argv)
    app.setApplicationName("Ankismart")
    app.setOrganizationName("Ankismart")

    # Set application icon
    icon_path = _get_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
        logger.debug(f"Set application icon: {icon_path}")
    else:
        logger.warning(f"Application icon not found: {icon_path}")

    try:
        # Load configuration
        config = load_config()
        logger.info("Configuration loaded successfully")

        # Setup logging with configured level
        log_level = getattr(logging, config.log_level.upper(), logging.INFO)
        setup_logging(level=log_level)
        logger.info(f"Logging initialized at level: {config.log_level}")

        # Apply theme
        _apply_theme(config.theme)

        # Create and configure main window (pass config to avoid duplicate loading)
        window = MainWindow(config)
        logger.info("Main window created")

        # Restore window geometry if available
        if config.window_geometry:
            _restore_window_geometry(window, config.window_geometry)

        # Show window
        window.show()
        logger.info("Application started successfully")

        # Run event loop
        return app.exec()

    except Exception as e:
        logger.exception("Fatal error during application startup")

        # Show error dialog
        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Icon.Critical)
        error_box.setWindowTitle("Ankismart - Startup Error")
        error_box.setText("Failed to start application")
        error_box.setInformativeText(str(e))
        error_box.setDetailedText(
            "Please check the log files for more details.\n\n"
            f"Error: {type(e).__name__}: {e}"
        )
        error_box.exec()

        return 1


if __name__ == "__main__":
    sys.exit(main())
