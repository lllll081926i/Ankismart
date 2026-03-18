from __future__ import annotations

import json
from pathlib import Path

from ankismart.core.task_models import TaskRun


class JsonTaskStore:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def _read_all(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def save(self, task: TaskRun) -> None:
        data = self._read_all()
        data[task.task_id] = task.model_dump(mode="json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, task_id: str) -> TaskRun | None:
        payload = self._read_all().get(task_id)
        return TaskRun.model_validate(payload) if payload else None

    def list_all(self) -> list[TaskRun]:
        tasks = [TaskRun.model_validate(item) for item in self._read_all().values()]
        return sorted(tasks, key=lambda item: item.created_at, reverse=True)

    def list_resumable(self) -> list[TaskRun]:
        return [task for task in self.list_all() if task.is_resumable]
