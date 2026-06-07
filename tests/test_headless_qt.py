from __future__ import annotations

import os

from PyQt6.QtWidgets import QApplication


def test_qt_tests_default_to_offscreen(qapp: QApplication) -> None:
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"
    assert qapp.platformName().lower() == "offscreen"
