from __future__ import annotations

from PyQt6.QtCore import QEventLoop, Qt, QTimer
from PyQt6.QtWidgets import QApplication, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition

from ankismart.ui.utils import update_progress_infobar_text


class _Label:
    def __init__(self) -> None:
        self.text = ""
        self.visible = True

    def setText(self, value: str) -> None:
        self.text = value

    def setVisible(self, value: bool) -> None:
        self.visible = value


class _Parent:
    def __init__(self, width: int) -> None:
        self._width = width

    def width(self) -> int:
        return self._width


class _InfoBar:
    def __init__(
        self, *, width: int = 360, parent_width: int = 1000, window_width: int | None = None
    ) -> None:
        self._width = width
        self._parent = _Parent(parent_width)
        self._window = _Parent(window_width or parent_width)
        self._progress_title_label = _Label()
        self._progress_content_label = _Label()
        self.fixed_height = None
        self.fixed_width = None
        self.maximum_width = None
        self.moved_to: tuple[int, int] | None = None

    def width(self) -> int:
        if self.fixed_width is not None:
            return self.fixed_width
        return min(self._width, self.maximum_width or self._width)

    def height(self) -> int:
        return self.fixed_height or 52

    def y(self) -> int:
        return 16

    def parentWidget(self):
        return self._parent

    def window(self):
        return self._window

    def setFixedHeight(self, value: int) -> None:
        self.fixed_height = value

    def setFixedWidth(self, value: int) -> None:
        self.fixed_width = value

    def setMaximumWidth(self, value: int) -> None:
        self.maximum_width = value

    def setSizePolicy(self, *_args) -> None:
        pass

    def updateGeometry(self) -> None:
        pass

    def adjustSize(self) -> None:
        pass

    def move(self, x: int, y: int) -> None:
        self.moved_to = (x, y)


def test_progress_infobar_update_keeps_widget_centered() -> None:
    info_bar = _InfoBar(width=360, parent_width=1000)

    assert update_progress_infobar_text(info_bar, "正在生成卡片", "正在处理 demo.md")

    assert info_bar._progress_title_label.text == "正在生成卡片"
    assert info_bar._progress_content_label.text == "正在处理 demo.md"
    assert info_bar.fixed_width == 360
    assert info_bar.moved_to == (320, 16)


def test_progress_infobar_uses_minimum_width_when_content_size_is_unavailable() -> None:
    info_bar = _InfoBar(width=76, parent_width=1000, window_width=1456)

    assert update_progress_infobar_text(info_bar, "正在生成卡片", "正在生成很多卡片")

    assert info_bar.fixed_width == 240
    assert info_bar.moved_to == (608, 16)


def test_progress_infobar_matches_text_width_after_qfluent_slide_animation(
    qapp: QApplication,
) -> None:
    window = QWidget()
    window.resize(1456, 900)
    window.show()
    qapp.processEvents()

    short_info_bar = InfoBar.info(
        title="",
        content="",
        orient=Qt.Orientation.Horizontal,
        isClosable=False,
        position=InfoBarPosition.TOP,
        duration=-1,
        parent=window,
    )
    long_info_bar = InfoBar.info(
        title="",
        content="",
        orient=Qt.Orientation.Horizontal,
        isClosable=False,
        position=InfoBarPosition.TOP,
        duration=-1,
        parent=window,
    )

    try:
        assert update_progress_infobar_text(
            short_info_bar,
            "正在生成卡片",
            "短",
            duration=-1,
        )
        assert update_progress_infobar_text(
            long_info_bar,
            "正在生成卡片",
            "正在从 04_第四次课_原文.md 生成 基础问答 卡片",
            duration=-1,
        )

        loop = QEventLoop()
        QTimer.singleShot(260, loop.quit)
        loop.exec()
        qapp.processEvents()

        assert short_info_bar.width() < long_info_bar.width()
        assert short_info_bar.x() == (window.width() - short_info_bar.width()) // 2
        assert long_info_bar.x() == (window.width() - long_info_bar.width()) // 2
    finally:
        short_info_bar.close()
        long_info_bar.close()
        window.close()
        qapp.processEvents()


def test_progress_infobar_repositions_when_text_width_changes(qapp: QApplication) -> None:
    window = QWidget()
    window.resize(1456, 900)
    window.show()
    qapp.processEvents()

    info_bar = InfoBar.info(
        title="",
        content="",
        orient=Qt.Orientation.Horizontal,
        isClosable=False,
        position=InfoBarPosition.TOP,
        duration=-1,
        parent=window,
    )

    try:
        assert update_progress_infobar_text(info_bar, "正在生成卡片", "短", duration=-1)

        loop = QEventLoop()
        QTimer.singleShot(260, loop.quit)
        loop.exec()
        qapp.processEvents()
        short_width = info_bar.width()
        assert info_bar.x() == (window.width() - short_width) // 2

        assert update_progress_infobar_text(
            info_bar,
            "正在生成卡片",
            "正在从 04_第四次课_原文.md 生成 基础问答 卡片",
            duration=-1,
        )

        loop = QEventLoop()
        QTimer.singleShot(260, loop.quit)
        loop.exec()
        qapp.processEvents()
        long_width = info_bar.width()
        assert short_width < long_width
        assert info_bar.x() == (window.width() - long_width) // 2

        assert update_progress_infobar_text(info_bar, "正在生成卡片", "短", duration=-1)

        loop = QEventLoop()
        QTimer.singleShot(260, loop.quit)
        loop.exec()
        qapp.processEvents()

        assert info_bar.width() == short_width
        assert info_bar.x() == (window.width() - info_bar.width()) // 2
    finally:
        info_bar.close()
        window.close()
        qapp.processEvents()
