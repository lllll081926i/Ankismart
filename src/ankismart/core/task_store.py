from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from ankismart.core.task_models import TaskRun

_REPLACE_RETRIES = 5
_REPLACE_RETRY_DELAY_SECONDS = 0.05


class JsonTaskStore:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def _read_all(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def save(self, task: TaskRun) -> None:
        data = self._read_all()
        data[task.task_id] = task.model_dump(mode="json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        fd, temp_path_raw = tempfile.mkstemp(
            prefix=f"{self._path.stem}.",
            suffix=".tmp",
            dir=self._path.parent,
            text=True,
        )
        temp_path = Path(temp_path_raw)
        os.close(fd)
        try:
            temp_path.write_text(payload, encoding="utf-8")
            for attempt in range(_REPLACE_RETRIES):
                try:
                    os.replace(temp_path, self._path)
                    break
                except PermissionError:
                    if attempt == _REPLACE_RETRIES - 1:
                        raise
                    time.sleep(_REPLACE_RETRY_DELAY_SECONDS)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    def get(self, task_id: str) -> TaskRun | None:
        payload = self._read_all().get(task_id)
        return TaskRun.model_validate(payload) if payload else None

    def list_all(self) -> list[TaskRun]:
        tasks = [TaskRun.model_validate(item) for item in self._read_all().values()]
        return sorted(tasks, key=lambda item: item.created_at, reverse=True)

    def list_resumable(self) -> list[TaskRun]:
        return [task for task in self.list_all() if task.is_resumable]
