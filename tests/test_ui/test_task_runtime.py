from __future__ import annotations

from ankismart.core.task_models import TaskStatus, build_default_task_run
from ankismart.core.task_store import JsonTaskStore
from ankismart.ui.task_runtime import TaskEvent, TaskRuntime


def test_task_runtime_maps_progress_to_stage_update(tmp_path) -> None:
    store = JsonTaskStore(tmp_path / "tasks.json")
    events: list[TaskEvent] = []
    runtime = TaskRuntime(store=store, on_event=events.append)
    task = build_default_task_run(flow="full_pipeline", task_id="task-1")
    runtime.register(task)

    runtime.handle(
        TaskEvent(
            task_id="task-1",
            stage="generate",
            kind="progress",
            progress=35,
            message="generating",
        )
    )

    restored = store.get("task-1")
    assert restored is not None
    assert restored.status is TaskStatus.RUNNING
    assert restored.resume_from_stage == "generate"
    assert restored.get_stage("generate").progress == 35
    assert events[-1].message == "generating"


def test_task_runtime_marks_stage_failed_and_resumable(tmp_path) -> None:
    store = JsonTaskStore(tmp_path / "tasks.json")
    runtime = TaskRuntime(store=store)
    task = build_default_task_run(flow="full_pipeline", task_id="task-2")
    runtime.register(task)

    runtime.handle(TaskEvent(task_id="task-2", stage="export", kind="failed", message="disk full"))

    restored = store.get("task-2")
    assert restored is not None
    assert restored.status is TaskStatus.FAILED
    assert restored.resume_from_stage == "export"
    assert restored.get_stage("export").message == "disk full"
