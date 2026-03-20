from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from ankismart.core.task_models import TaskStage, TaskStatus, build_default_task_run
from ankismart.ui.task_center import TaskCenterPanel

_APP = QApplication.instance() or QApplication(sys.argv)


def test_task_center_renders_stage_statuses() -> None:
    panel = TaskCenterPanel()
    task = build_default_task_run(flow="full_pipeline", task_id="task-1")
    task.stages = [TaskStage(name="convert", status=TaskStatus.COMPLETED, progress=100)]

    panel.render_task(task)

    assert len(panel._task_widgets) == 1
    assert "task-1" in panel._task_widgets
