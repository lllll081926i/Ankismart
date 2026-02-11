from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ankismart.core.config import load_config
from ankismart.core.logging import setup_logging
from ankismart.ui.main_window import MainWindow
from ankismart.ui.styles import get_stylesheet


def _setup_local_dependency_dirs() -> None:
    if getattr(sys, "frozen", False):
        project_root = Path(sys.executable).resolve().parent
    else:
        project_root = Path(__file__).resolve().parents[3]

    local_root = Path(
        os.getenv("ANKISMART_LOCAL_DIR", str(project_root / ".local"))
    ).expanduser().resolve()
    app_root = Path(
        os.getenv("ANKISMART_APP_DIR", str(local_root / "ankismart"))
    ).expanduser().resolve()
    model_root = Path(
        os.getenv("ANKISMART_OCR_MODEL_DIR", str(project_root / "model"))
    ).expanduser().resolve()

    defaults = {
        "ANKISMART_LOCAL_DIR": str(local_root),
        "ANKISMART_APP_DIR": str(app_root),
        "ANKISMART_OCR_MODEL_DIR": str(model_root),
        "ANKISMART_CONFIG_PATH": str(app_root / "config.yaml"),
        "PADDLE_HOME": str(local_root / "paddle"),
        "PADDLE_PDX_CACHE_HOME": str(model_root),
        "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "1",
        "XDG_CACHE_HOME": str(local_root / "cache"),
        "HF_HOME": str(local_root / "hf"),
        "UV_CACHE_DIR": str(local_root / "uv-cache"),
        "PIP_CACHE_DIR": str(local_root / "pip-cache"),
        "HF_HUB_DISABLE_PROGRESS_BARS": "1",
        "TMPDIR": str(local_root / "tmp"),
        "TMP": str(local_root / "tmp"),
        "TEMP": str(local_root / "tmp"),
    }

    for key, value in defaults.items():
        os.environ.setdefault(key, value)

    for env_key in (
        "ANKISMART_LOCAL_DIR",
        "ANKISMART_APP_DIR",
        "ANKISMART_OCR_MODEL_DIR",
        "PADDLE_HOME",
        "PADDLE_PDX_CACHE_HOME",
        "XDG_CACHE_HOME",
        "HF_HOME",
        "UV_CACHE_DIR",
        "PIP_CACHE_DIR",
        "TMPDIR",
    ):
        Path(os.environ[env_key]).mkdir(parents=True, exist_ok=True)


def main() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    _setup_local_dependency_dirs()

    setup_logging()
    config = load_config()

    app = QApplication(sys.argv)
    app.setApplicationName("AnkiSmart")
    app.setStyleSheet(get_stylesheet())

    window = MainWindow(config)

    # Import pages lazily to avoid circular imports
    from ankismart.ui.import_page import ImportPage
    from ankismart.ui.preview_page import PreviewPage
    from ankismart.ui.result_page import ResultPage
    from ankismart.ui.settings_page import SettingsPage

    import_page = ImportPage(window)
    preview_page = PreviewPage(window)
    result_page = ResultPage(window)
    settings_page = SettingsPage(window)

    window.add_page(import_page)
    window.add_preview_page(preview_page)
    window.add_page(result_page)
    window.add_page(settings_page)
    window.set_import_page(import_page)

    # Check AnkiConnect on startup
    from ankismart.ui.workers import ConnectionCheckWorker

    checker = ConnectionCheckWorker(config.anki_connect_url, config.anki_connect_key)
    checker.finished.connect(window.set_connection_status)
    checker.start()
    # Keep reference to prevent GC
    window._connection_checker = checker

    from ankismart.converter.ocr_converter import get_missing_ocr_models

    missing_models = get_missing_ocr_models()
    if missing_models:
        names = ", ".join(missing_models)
        window.statusBar().showMessage(
            f"OCR 模型缺失（{names}）。处理 PDF/图片 时将提示下载。",
            15000,
        )

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
