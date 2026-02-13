"""Ankismart UI module - QFluentWidgets based user interface."""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "main": ("ankismart.ui.app", "main"),
    "MainWindow": ("ankismart.ui.main_window", "MainWindow"),
    "ImportPage": ("ankismart.ui.import_page", "ImportPage"),
    "PreviewPage": ("ankismart.ui.preview_page", "PreviewPage"),
    "ResultPage": ("ankismart.ui.result_page", "ResultPage"),
    "PerformancePage": ("ankismart.ui.performance_page", "PerformancePage"),
    "SettingsPage": ("ankismart.ui.settings_page", "SettingsPage"),
    "get_text": ("ankismart.ui.i18n", "get_text"),
    "ConvertWorker": ("ankismart.ui.workers", "ConvertWorker"),
    "GenerateWorker": ("ankismart.ui.workers", "GenerateWorker"),
    "PushWorker": ("ankismart.ui.workers", "PushWorker"),
    "ExportWorker": ("ankismart.ui.workers", "ExportWorker"),
    "show_error": ("ankismart.ui.utils", "show_error"),
    "show_success": ("ankismart.ui.utils", "show_success"),
    "show_info": ("ankismart.ui.utils", "show_info"),
    "format_card_title": ("ankismart.ui.utils", "format_card_title"),
    "validate_config": ("ankismart.ui.utils", "validate_config"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module 'ankismart.ui' has no attribute '{name}'")

    module_name, attr_name = _LAZY_EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value

