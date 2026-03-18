from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

_DEFAULT_FLOW_STAGES: dict[str, tuple[str, ...]] = {
    "full_pipeline": ("convert", "generate", "push", "export"),
}


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskStage(BaseModel):
    name: str
    status: TaskStatus = TaskStatus.PENDING
    progress: int = 0
    message: str = ""


class TaskRun(BaseModel):
    task_id: str
    flow: str
    status: TaskStatus = TaskStatus.PENDING
    stages: list[TaskStage] = Field(default_factory=list)
    resume_from_stage: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def is_resumable(self) -> bool:
        return bool(self.resume_from_stage) and self.status in {
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
        }

    def get_stage(self, name: str) -> TaskStage:
        for stage in self.stages:
            if stage.name == name:
                return stage
        stage = TaskStage(name=name)
        self.stages.append(stage)
        return stage

    def next_pending_stage(self, current_stage: str) -> TaskStage | None:
        names = [stage.name for stage in self.stages]
        try:
            start = names.index(current_stage) + 1
        except ValueError:
            start = 0

        for stage in self.stages[start:]:
            if stage.status is not TaskStatus.COMPLETED:
                return stage
        return None


def build_default_task_run(*, flow: str, task_id: str | None = None) -> TaskRun:
    stage_names = _DEFAULT_FLOW_STAGES.get(flow, ())
    return TaskRun(
        task_id=task_id or uuid4().hex[:12],
        flow=flow,
        stages=[TaskStage(name=name) for name in stage_names],
    )
