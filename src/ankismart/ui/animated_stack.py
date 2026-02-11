from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QStackedLayout,
    QWidget,
)


class AnimatedStackedWidget(QWidget):
    """
    A widget that manages pages with a sliding animation using QStackedLayout.
    """
    
    currentChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QStackedLayout(self)
        self._layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self._layout.currentChanged.connect(self.currentChanged)
        
        self._anim_duration = 300
        self._anim_curve = QEasingCurve.Type.OutCubic
        self._is_animating = False
        self._next_index = -1

    def addWidget(self, widget: QWidget) -> int:
        return self._layout.addWidget(widget)

    def insertWidget(self, index: int, widget: QWidget) -> int:
        return self._layout.insertWidget(index, widget)

    def setCurrentIndex(self, index: int, animated: bool = True) -> None:
        if index == self.currentIndex():
            return

        if not animated or self._is_animating:
            self._layout.setCurrentIndex(index)
            return

        current_widget = self.currentWidget()
        next_widget = self.widget(index)

        if not current_widget or not next_widget:
            self._layout.setCurrentIndex(index)
            return

        # Prepare for animation: show both
        self._layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        next_widget.show()
        next_widget.raise_()

        # Determine direction
        width = self.width()
        direction = 1 if index > self.currentIndex() else -1
        
        # Initial positions
        next_widget.move(width * direction, 0)
        
        # Create animation group
        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.finished.connect(self._on_animation_finished)

        # Animate current out
        anim_out = QPropertyAnimation(current_widget, b"pos")
        anim_out.setDuration(self._anim_duration)
        anim_out.setEasingCurve(self._anim_curve)
        anim_out.setStartValue(QPoint(0, 0))
        anim_out.setEndValue(QPoint(-width * direction, 0))
        self._anim_group.addAnimation(anim_out)

        # Animate next in
        anim_in = QPropertyAnimation(next_widget, b"pos")
        anim_in.setDuration(self._anim_duration)
        anim_in.setEasingCurve(self._anim_curve)
        anim_in.setStartValue(QPoint(width * direction, 0))
        anim_in.setEndValue(QPoint(0, 0))
        self._anim_group.addAnimation(anim_in)

        self._next_index = index
        self._is_animating = True
        self._anim_group.start()

    def _on_animation_finished(self) -> None:
        self._is_animating = False
        # Commit the switch
        self._layout.setCurrentIndex(self._next_index)
        # Restore mode
        self._layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        
        # Reset positions just in case
        for i in range(self._layout.count()):
            w = self._layout.widget(i)
            if w:
                w.move(0, 0)

    def currentIndex(self) -> int:
        return self._layout.currentIndex()

    def currentWidget(self) -> QWidget | None:
        return self._layout.currentWidget()

    def widget(self, index: int) -> QWidget | None:
        return self._layout.widget(index)
    
    def count(self) -> int:
        return self._layout.count()
