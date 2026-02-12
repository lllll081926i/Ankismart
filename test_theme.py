"""Test script for theme switching functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from qfluentwidgets import Theme, setTheme, isDarkTheme, qconfig

from ankismart.ui.main_window import MainWindow


def test_theme_switching():
    """Test theme switching functionality."""
    app = QApplication(sys.argv)
    app.setApplicationName("Ankismart Theme Test")

    # Enable High DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    window = MainWindow()
    window.show()

    print(f"Initial theme: {window.config.theme}")
    print(f"Is dark theme: {isDarkTheme()}")

    # Test theme switching after 2 seconds
    def switch_to_dark():
        print("\n=== Switching to DARK theme ===")
        window.switch_theme("dark")
        print(f"Current theme: {window.config.theme}")
        print(f"Is dark theme: {isDarkTheme()}")

        # Switch to light after 2 more seconds
        QTimer.singleShot(2000, switch_to_light)

    def switch_to_light():
        print("\n=== Switching to LIGHT theme ===")
        window.switch_theme("light")
        print(f"Current theme: {window.config.theme}")
        print(f"Is dark theme: {isDarkTheme()}")

        # Switch to auto after 2 more seconds
        QTimer.singleShot(2000, switch_to_auto)

    def switch_to_auto():
        print("\n=== Switching to AUTO theme ===")
        window.switch_theme("auto")
        print(f"Current theme: {window.config.theme}")
        print(f"Is dark theme: {isDarkTheme()}")
        print("\nAuto mode will follow system theme")

    # Start the test sequence
    QTimer.singleShot(2000, switch_to_dark)

    return app.exec()


if __name__ == "__main__":
    sys.exit(test_theme_switching())
