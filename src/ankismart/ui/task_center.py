from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    FluentIcon,
    PrimaryPushButton,
    PushButton,
    SimpleCardWidget,
    SubtitleLabel,
)

from ankismart.core.task_models import TaskRun, TaskStatus


class TaskCenterPanel(SimpleCardWidget):
    """任务中心面板，展示可恢复任务及其进度。"""

    resume_requested = pyqtSignal(str)  # task_id
    dismiss_requested = pyqtSignal(str)  # task_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = "zh"
        self._task_widgets: dict[str, QWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self._title_label = SubtitleLabel("任务中心" if self._language == "zh" else "Task Center")
        self._summary_label = BodyLabel(
            "暂无可恢复任务" if self._language == "zh" else "No resumable tasks"
        )
        self._summary_label.setWordWrap(True)

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)

        self._tasks_container = QWidget()
        self._tasks_layout = QVBoxLayout(self._tasks_container)
        self._tasks_layout.setContentsMargins(0, 0, 0, 0)
        self._tasks_layout.setSpacing(6)
        layout.addWidget(self._tasks_container)

    def set_language(self, language: str) -> None:
        self._language = language
        self._title_label.setText("任务中心" if language == "zh" else "Task Center")

    def render_task(self, task: TaskRun) -> None:
        self.render_tasks([task])

    def render_tasks(self, tasks: list[TaskRun]) -> None:
        self._clear_task_widgets()

        if not tasks:
            self._summary_label.setText(
                "暂无可恢复任务" if self._language == "zh" else "No resumable tasks"
            )
            self._summary_label.show()
            return

        self._summary_label.hide()
        for task in tasks:
            widget = self._build_task_widget(task)
            self._task_widgets[task.task_id] = widget
            self._tasks_layout.addWidget(widget)

    def _clear_task_widgets(self) -> None:
        for widget in self._task_widgets.values():
            self._tasks_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._task_widgets.clear()

    def _build_task_widget(self, task: TaskRun) -> QWidget:
        is_zh = self._language == "zh"
        card = SimpleCardWidget()
        card.setBorderRadius(8)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        card_layout.setSpacing(4)

        # Header: task id + status badge
        header = QHBoxLayout()
        header.setSpacing(8)
        title = BodyLabel(f"任务 {task.task_id}")
        title.setStyleSheet("font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        status_text = self._status_label(task.status, is_zh)
        status_badge = BodyLabel(status_text)
        status_badge.setStyleSheet(self._status_style(task.status))
        header.addWidget(status_badge)
        card_layout.addLayout(header)

        # Stage progress summary
        completed = sum(1 for s in task.stages if s.status is TaskStatus.COMPLETED)
        total = len(task.stages)
        stage_summary = (
            f"阶段 {completed}/{total} 已完成" if is_zh else f"Stages {completed}/{total} completed"
        )
        card_layout.addWidget(BodyLabel(stage_summary))

        # Detail: each stage status
        detail_parts: list[str] = []
        for stage in task.stages:
            stage_label = self._stage_label(stage.name, is_zh)
            stage_status = self._status_label(stage.status, is_zh)
            progress_text = f" ({stage.progress}%)" if stage.progress > 0 else ""
            detail_parts.append(f"{stage_label}: {stage_status}{progress_text}")
        detail_label = BodyLabel(" | ".join(detail_parts))
        detail_label.setWordWrap(True)
        card_layout.addWidget(detail_label)

        # Action buttons
        actions = QHBoxLayout()
        actions.setSpacing(8)
        resume_btn = PrimaryPushButton("恢复" if is_zh else "Resume")
        resume_btn.setIcon(FluentIcon.PLAY)
        resume_btn.clicked.connect(lambda: self.resume_requested.emit(task.task_id))
        dismiss_btn = PushButton("忽略" if is_zh else "Dismiss")
        dismiss_btn.clicked.connect(lambda: self._on_dismiss(task.task_id))
        actions.addStretch()
        actions.addWidget(resume_btn)
        actions.addWidget(dismiss_btn)
        card_layout.addLayout(actions)

        return card

    def _on_dismiss(self, task_id: str) -> None:
        widget = self._task_widgets.pop(task_id, None)
        if widget is not None:
            self._tasks_layout.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self.dismiss_requested.emit(task_id)

    @staticmethod
    def _status_label(status: TaskStatus, is_zh: bool) -> str:
        mapping = {
            TaskStatus.PENDING: ("待处理", "Pending"),
            TaskStatus.RUNNING: ("运行中", "Running"),
            TaskStatus.FAILED: ("失败", "Failed"),
            TaskStatus.COMPLETED: ("已完成", "Completed"),
            TaskStatus.CANCELLED: ("已取消", "Cancelled"),
        }
        zh, en = mapping.get(status, ("未知", "Unknown"))
        return zh if is_zh else en

    @staticmethod
    def _status_style(status: TaskStatus) -> str:
        colors = {
            TaskStatus.PENDING: "#909399",
            TaskStatus.RUNNING: "#409EFF",
            TaskStatus.FAILED: "#F56C6C",
            TaskStatus.COMPLETED: "#67C23A",
            TaskStatus.CANCELLED: "#E6A23C",
        }
        color = colors.get(status, "#909399")
        return f"color: {color}; font-weight: 600;"

    @staticmethod
    def _stage_label(name: str, is_zh: bool) -> str:
        mapping = {
            "convert": ("文档转换", "Convert"),
            "generate": ("卡片生成", "Generate"),
            "push": ("推送到Anki", "Push"),
            "export": ("导出APKG", "Export"),
        }
        zh, en = mapping.get(name, (name, name))
        return zh if is_zh else en
