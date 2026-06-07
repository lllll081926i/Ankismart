from __future__ import annotations

import os

import pytest
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication, QWidget

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")


def _configure_test_qapp(app: QApplication) -> QApplication:
    app.setQuitOnLastWindowClosed(False)
    return app


def _teardown_test_window(window: QWidget, app: QApplication) -> None:
    window.hide()
    window.close()
    window.deleteLater()
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, 0)
    app.processEvents()


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app = _configure_test_qapp(app)
    yield app
    app.closeAllWindows()
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, 0)
    app.processEvents()
    app.quit()
