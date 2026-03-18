from __future__ import annotations

from ankismart.core.task_models import TaskRun, TaskStage, TaskStatus


def test_task_run_round_trips_with_stage_progress() -> None:
    task = TaskRun(
        task_id="task-1",
        flow="full_pipeline",
        status=TaskStatus.RUNNING,
        stages=[
            TaskStage(name="convert", status=TaskStatus.COMPLETED, progress=100),
            TaskStage(name="generate", status=TaskStatus.RUNNING, progress=40),
        ],
    )

    payload = task.model_dump()
    restored = TaskRun.model_validate(payload)

    assert restored == task


def test_task_run_exposes_resume_target() -> None:
    task = TaskRun(
        task_id="task-2",
        flow="full_pipeline",
        status=TaskStatus.FAILED,
        resume_from_stage="generate",
    )

    assert task.resume_from_stage == "generate"
