from __future__ import annotations

from PyQt6.QtWidgets import QListWidget, QVBoxLayout
from qfluentwidgets import BodyLabel, SimpleCardWidget, SubtitleLabel

from ankismart.core.task_models import TaskRun


class TaskCenterPanel(SimpleCardWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self._title_label = SubtitleLabel("任务中心")
        self._summary_label = BodyLabel("暂无可恢复任务")
        self._task_list = QListWidget()

        layout.addWidget(self._title_label)
        layout.addWidget(self._summary_label)
        layout.addWidget(self._task_list)

    def render_task(self, task: TaskRun) -> None:
        self.render_tasks([task])

    def render_tasks(self, tasks: list[TaskRun]) -> None:
        self._task_list.clear()
        if not tasks:
            self._summary_label.setText("暂无可恢复任务")
            return

        self._summary_label.setText("可恢复任务: " + ", ".join(task.task_id for task in tasks))
        for task in tasks:
            for stage in task.stages:
                self._task_list.addItem(
                    f"{task.task_id} | {stage.name}: {stage.status.value} ({stage.progress}%)"
                )
