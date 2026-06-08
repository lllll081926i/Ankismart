from __future__ import annotations

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
    def __init__(self, *, width: int = 360, parent_width: int = 1000) -> None:
        self._width = width
        self._parent = _Parent(parent_width)
        self._progress_title_label = _Label()
        self._progress_content_label = _Label()
        self.fixed_height = None
        self.maximum_width = None
        self.moved_to: tuple[int, int] | None = None

    def width(self) -> int:
        return min(self._width, self.maximum_width or self._width)

    def height(self) -> int:
        return self.fixed_height or 52

    def y(self) -> int:
        return 16

    def parentWidget(self):
        return self._parent

    def setFixedHeight(self, value: int) -> None:
        self.fixed_height = value

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
    assert info_bar.moved_to == (320, 16)
