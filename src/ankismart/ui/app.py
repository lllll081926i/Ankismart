"""Application entry point for Ankismart.

Initializes the Qt application, loads configuration, applies theme and language
settings, and launches the main window.
"""

from __future__ import annotations

import logging
import os
import re
import sys
import traceback
from datetime import date, datetime
from pathlib import Path

# Set environment variables as early as possible to avoid startup delays
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "1")

import httpx
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox
from qfluentwidgets import InfoBar, InfoBarPosition, Theme, isDarkTheme, setTheme, setThemeColor

from ankismart import __version__
from ankismart.core.config import CONFIG_DIR, create_config_backup, load_config, save_config
from ankismart.core.logging import get_logger, setup_logging
from ankismart.ui.main_window import MainWindow
from ankismart.ui.styles import FIXED_THEME_ACCENT_HEX, get_stylesheet

logger = get_logger("app")

_GITHUB_RELEASES_API_URL = "https://api.github.com/repos/lllll081926i/Ankismart/releases/latest"
_GITHUB_TAGS_API_URL = "https://api.github.com/repos/lllll081926i/Ankismart/tags?per_page=1"
_GITHUB_RELEASES_WEB_URL = "https://github.com/lllll081926i/Ankismart/releases"


def _get_icon_path() -> Path:
    """Get the path to the application icon.

    Returns:
        Path to icon.ico in package assets.
    """
    return Path(__file__).resolve().parent / "assets" / "icon.ico"


def _set_windows_app_user_model_id() -> None:
    """Set explicit AppUserModelID so taskbar uses the app icon on Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Ankismart.Desktop"
        )
    except Exception as exc:  # pragma: no cover - Windows-only best effort
        logger.warning(f"Failed to set Windows AppUserModelID: {exc}")


def _apply_theme(theme_name: str) -> None:
    """Apply the application theme.

    Args:
        theme_name: Theme name ("light", "dark", or "auto")
    """
    theme_name = (theme_name or "light").lower()
    if theme_name == "dark":
        theme = Theme.DARK
    elif theme_name == "auto":
        theme = Theme.AUTO
    else:
        theme = Theme.LIGHT  # Default fallback
        theme_name = "light"

    try:
        setTheme(theme, lazy=True)
        setThemeColor(FIXED_THEME_ACCENT_HEX, lazy=True)
    except RuntimeError as exc:
        # qfluentwidgets may raise this during rapid style manager mutations.
        if "dictionary changed size during iteration" not in str(exc):
            raise
        setTheme(theme, lazy=False)
        setThemeColor(FIXED_THEME_ACCENT_HEX, lazy=False)
    app = QApplication.instance()
    if app is not None:
        css = get_stylesheet(dark=isDarkTheme())
        if app.styleSheet() != css:
            app.setStyleSheet(css)
    logger.info(f"Applied theme: {theme_name}")


def _apply_text_clarity_profile(app: QApplication) -> None:
    """Improve glyph sharpness without changing layout/font sizing."""
    font = app.font()
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferQuality | QFont.StyleStrategy.PreferAntialias
    )
    app.setFont(font)


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


def _parse_version_tuple(version_text: str) -> tuple[int, ...]:
    cleaned = (version_text or "").strip().lstrip("vV")
    parts = []
    for chunk in cleaned.split("."):
        match = re.match(r"^(\d+)", chunk)
        parts.append(int(match.group(1)) if match else 0)
    return tuple(parts) if parts else (0,)


def _github_update_headers() -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Ankismart/{__version__}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _resolve_update_check_proxy(config) -> str:
    mode = str(getattr(config, "proxy_mode", "system")).strip().lower()
    if mode != "manual":
        return ""
    return str(getattr(config, "proxy_url", "")).strip()


def _fetch_latest_github_release(*, timeout: float, proxy_url: str = "") -> tuple[str, str]:
    latest_url = _GITHUB_RELEASES_WEB_URL
    client_kwargs: dict[str, object] = {"timeout": timeout}
    if proxy_url:
        client_kwargs["proxy"] = proxy_url

    with httpx.Client(**client_kwargs) as client:
        headers = _github_update_headers()

        latest_response = client.get(_GITHUB_RELEASES_API_URL, headers=headers)
        if latest_response.status_code < 400:
            payload = latest_response.json() if latest_response.content else {}
            if isinstance(payload, dict):
                latest_version = str(payload.get("tag_name", "")).strip().lstrip("vV")
                latest_url = str(payload.get("html_url", latest_url)).strip() or latest_url
                if latest_version:
                    return latest_version, latest_url

        tags_response = client.get(_GITHUB_TAGS_API_URL, headers=headers)
        tags_response.raise_for_status()
        payload = tags_response.json() if tags_response.content else []
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict):
                latest_version = str(first.get("name", "")).strip().lstrip("vV")
                if latest_version:
                    return latest_version, latest_url

    raise RuntimeError("GitHub did not return a valid latest version tag")


def _auto_check_latest_version(config) -> dict[str, object]:
    """Silent startup update check (query only, no auto-install)."""
    result: dict[str, object] = {
        "checked": False,
        "has_update": False,
        "should_notify": False,
        "latest_version": "",
        "latest_url": _GITHUB_RELEASES_WEB_URL,
    }
    if not getattr(config, "auto_check_updates", True):
        return result

    if str(getattr(config, "last_update_check_at", "")).startswith(date.today().isoformat()):
        return result

    result["checked"] = True
    previous_seen = str(getattr(config, "last_update_version_seen", "")).strip()
    latest = ""
    latest_url = _GITHUB_RELEASES_WEB_URL
    try:
        latest, latest_url = _fetch_latest_github_release(
            timeout=6.0,
            proxy_url=_resolve_update_check_proxy(config),
        )
    except Exception as exc:
        logger.debug(f"Silent update check failed: {exc}")
        latest = ""

    config.last_update_check_at = datetime.now().isoformat(timespec="seconds")
    if latest:
        config.last_update_version_seen = latest
        result["latest_version"] = latest
        result["latest_url"] = latest_url
        if _parse_version_tuple(latest) > _parse_version_tuple(__version__):
            logger.info(f"New version detected: current={__version__}, latest={latest}")
            result["has_update"] = True
            result["should_notify"] = latest != previous_seen
    try:
        save_config(config)
    except Exception as exc:
        logger.debug(f"Persisting update-check metadata failed: {exc}")
    return result


def _write_crash_report(exc_type, exc_value, exc_tb) -> Path:
    crash_dir = CONFIG_DIR / "crash"
    crash_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = crash_dir / f"crash-{stamp}.log"
    lines = [
        f"Ankismart crash report @ {datetime.now().isoformat(timespec='seconds')}",
        f"Exception: {exc_type.__name__}: {exc_value}",
        "",
        "Traceback:",
        "".join(traceback.format_exception(exc_type, exc_value, exc_tb)),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _install_global_exception_hooks(config_getter) -> None:
    """Install runtime crash handlers for report+backup recovery."""
    previous_hook = sys.excepthook

    def _resolve_config():
        try:
            return config_getter()
        except Exception:
            return None

    def _main_hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return previous_hook(exc_type, exc_value, exc_tb)

        logger.error("Unhandled exception in main thread", exc_info=(exc_type, exc_value, exc_tb))
        report_path = _write_crash_report(exc_type, exc_value, exc_tb)
        config = _resolve_config()
        if config is not None:
            try:
                config.last_crash_report_path = str(report_path)
                create_config_backup(config, reason="crash")
                save_config(config)
            except Exception as backup_exc:
                logger.debug(f"Crash backup failed: {backup_exc}")

        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Icon.Critical)
        error_box.setWindowTitle("Ankismart - Crash")
        error_box.setText("应用发生未处理异常并已生成崩溃报告")
        error_box.setInformativeText(str(report_path))
        error_box.setDetailedText(
            "".join(traceback.format_exception(exc_type, exc_value, exc_tb))[:6000]
        )
        error_box.exec()

    def _thread_hook(args):
        logger.error(
            "Unhandled exception in worker thread",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )
        report_path = _write_crash_report(args.exc_type, args.exc_value, args.exc_traceback)
        config = _resolve_config()
        if config is not None:
            try:
                config.last_crash_report_path = str(report_path)
                create_config_backup(config, reason="thread-crash")
                save_config(config)
            except Exception as backup_exc:
                logger.debug(f"Thread crash backup failed: {backup_exc}")

    sys.excepthook = _main_hook
    try:
        import threading

        threading.excepthook = _thread_hook
    except Exception:
        logger.debug("threading.excepthook is unavailable")


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
    _set_windows_app_user_model_id()

    # Create application instance
    app = QApplication(sys.argv)
    app.setApplicationName("Ankismart")
    app.setOrganizationName("Ankismart")
    _apply_text_clarity_profile(app)

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

        state = {"config": config, "window": window}
        _install_global_exception_hooks(lambda: state.get("window").config)
        update_result = _auto_check_latest_version(window.config)

        # Restore window geometry if available
        if config.window_geometry:
            _restore_window_geometry(window, config.window_geometry)

        # Show window
        window.show()
        if update_result.get("should_notify"):
            latest_version = str(update_result.get("latest_version", "")).strip()
            is_zh = str(getattr(window.config, "language", "zh")) == "zh"
            InfoBar.info(
                title="发现新版本" if is_zh else "Update Available",
                content=(
                    f"当前版本 {__version__}，最新版本 {latest_version}。"
                    "可在设置页“版本更新”查看发布页。"
                    if is_zh
                    else (
                        f"Current version {__version__}, latest {latest_version}. "
                        "Open releases from Settings > Version Update."
                    )
                ),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=7000,
                parent=window,
            )
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
