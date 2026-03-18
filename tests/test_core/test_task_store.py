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


def test_task_store_ignores_corrupt_json_payload(tmp_path) -> None:
    path = tmp_path / "tasks.json"
    path.write_text('{"broken": true} trailing', encoding="utf-8")
    store = JsonTaskStore(path)

    assert store.list_all() == []

    store.save(TaskRun(task_id="fresh", flow="full_pipeline", status=TaskStatus.RUNNING))

    restored = store.get("fresh")
    assert restored is not None
    assert restored.task_id == "fresh"
