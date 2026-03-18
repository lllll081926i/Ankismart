from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ankismart.core.task_models import TaskRun, TaskStatus, build_default_task_run
from ankismart.core.task_store import JsonTaskStore


@dataclass(frozen=True)
class TaskEvent:
    task_id: str
    stage: str
    kind: str
    progress: int = 0
    message: str = ""


class TaskRuntime:
    def __init__(
        self,
        *,
        store: JsonTaskStore,
        on_event: Callable[[TaskEvent], None] | None = None,
    ) -> None:
        self._store = store
        self._on_event = on_event
        self._tasks: dict[str, TaskRun] = {task.task_id: task for task in store.list_all()}

    def register(self, task: TaskRun) -> TaskRun:
        self._tasks[task.task_id] = task
        self._store.save(task)
        return task

    def get(self, task_id: str) -> TaskRun | None:
        task = self._tasks.get(task_id)
        if task is None:
            task = self._store.get(task_id)
            if task is not None:
                self._tasks[task_id] = task
        return task

    def list_resumable(self) -> list[TaskRun]:
        return self._store.list_resumable()

    def handle(self, event: TaskEvent) -> TaskRun:
        task = self.get(event.task_id)
        if task is None:
            task = build_default_task_run(flow="full_pipeline", task_id=event.task_id)
            self.register(task)
        stage = task.get_stage(event.stage)

        if event.kind in {"started", "progress", "warning"}:
            task.status = TaskStatus.RUNNING
            task.resume_from_stage = event.stage
            stage.status = TaskStatus.RUNNING
            stage.progress = max(0, min(100, int(event.progress)))
            if event.message:
                stage.message = event.message
        elif event.kind == "failed":
            task.status = TaskStatus.FAILED
            task.resume_from_stage = event.stage
            stage.status = TaskStatus.FAILED
            stage.message = event.message
        elif event.kind == "completed":
            stage.status = TaskStatus.COMPLETED
            stage.progress = max(100, int(event.progress or 100))
            if event.message:
                stage.message = event.message
            next_stage = task.next_pending_stage(event.stage)
            if next_stage is None:
                task.status = TaskStatus.COMPLETED
                task.resume_from_stage = ""
            else:
                task.status = TaskStatus.RUNNING
                task.resume_from_stage = next_stage.name
        elif event.kind == "cancelled":
            task.status = TaskStatus.CANCELLED
            task.resume_from_stage = event.stage
            stage.status = TaskStatus.CANCELLED
            stage.message = event.message

        self._tasks[task.task_id] = task
        self._store.save(task)
        if self._on_event is not None:
            self._on_event(event)
        return task
