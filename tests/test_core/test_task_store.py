from __future__ import annotations

from ankismart.core.task_models import TaskRun, TaskStatus
from ankismart.core.task_store import JsonTaskStore


def test_task_store_persists_latest_run(tmp_path) -> None:
    store = JsonTaskStore(tmp_path / "tasks.json")
    task = TaskRun(task_id="task-1", flow="full_pipeline", status=TaskStatus.RUNNING)

    store.save(task)
    restored = store.get("task-1")

    assert restored is not None
    assert restored.status is TaskStatus.RUNNING


def test_task_store_lists_resumable_tasks_only(tmp_path) -> None:
    store = JsonTaskStore(tmp_path / "tasks.json")
    store.save(
        TaskRun(
            task_id="a",
            flow="full_pipeline",
            status=TaskStatus.FAILED,
            resume_from_stage="generate",
        )
    )
    store.save(TaskRun(task_id="b", flow="full_pipeline", status=TaskStatus.COMPLETED))

    resumable = store.list_resumable()

    assert [task.task_id for task in resumable] == ["a"]
