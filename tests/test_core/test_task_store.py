from __future__ import annotations

import json
from pathlib import Path

import pytest

import ankismart.core.task_store as json_task_store_module
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


def test_task_store_preserves_existing_file_when_save_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tasks.json"
    original_payload = {
        "task-1": TaskRun(
            task_id="task-1", flow="full_pipeline", status=TaskStatus.COMPLETED
        ).model_dump(mode="json")
    }
    path.write_text(json.dumps(original_payload), encoding="utf-8")
    store = JsonTaskStore(path)

    original_write_text = Path.write_text

    def flaky_write_text(self: Path, data: str, *args, **kwargs) -> int:
        if '"task-2"' in data:
            original_write_text(self, '{"task-2": ', *args, **kwargs)
            raise OSError("disk full")
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write_text)

    with pytest.raises(OSError, match="disk full"):
        store.save(TaskRun(task_id="task-2", flow="full_pipeline", status=TaskStatus.RUNNING))

    restored = json.loads(path.read_text(encoding="utf-8"))
    assert restored == original_payload


def test_task_store_retries_replace_on_transient_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "tasks.json"
    store = JsonTaskStore(path)
    original_replace = json_task_store_module.os.replace
    calls = {"count": 0}

    def flaky_replace(src, dst) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise PermissionError("locked")
        original_replace(src, dst)

    monkeypatch.setattr(json_task_store_module.os, "replace", flaky_replace)

    store.save(TaskRun(task_id="task-3", flow="full_pipeline", status=TaskStatus.RUNNING))

    restored = store.get("task-3")
    assert restored is not None
    assert calls["count"] == 2
