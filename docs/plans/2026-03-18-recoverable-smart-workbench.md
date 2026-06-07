# Recoverable Smart Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Ankismart 从一次性流程型工具升级为“任务可恢复、卡片可审阅、配置可预设、发布可门禁”的智能制卡工作台。

**Architecture:** 本版本按三条主线推进。第一条主线是“任务运行时”，把导入、转换、生成、推送、导出统一纳入可持久化的任务状态机，并支持取消、恢复、步骤级重试。第二条主线是“卡片质量闭环”，给卡片增加来源与质量元数据，提供批量筛选与重生成入口。第三条主线是“预设与发布质量”，将复杂配置映射为场景预设，并把 E2E 冒烟、回归和发布校验提升为正式门禁。

**Tech Stack:** Python 3.11, PyQt6, QFluentWidgets, pytest, Ruff, Pydantic, AnkiConnect, genanki.

---

## Scope

- 保留当前页面结构与主流程入口，不做推倒重写。
- 允许新增任务运行时、持久化、审阅筛选和预设层。
- 优先交付可恢复性、可诊断性和可回归性，再扩展 UI 体验。
- 所有新增行为必须有单测和至少一条 E2E 主链路覆盖。

## Non-Goals

- 本版本不新增大量卡片策略。
- 本版本不接入更多 LLM 供应商。
- 本版本不重做整套视觉设计系统。

## Milestones

1. **M1 任务基建**
   - 持久化任务状态模型
   - 统一任务事件协议
   - 任务中心和恢复能力
2. **M2 质量闭环**
   - 卡片质量标签
   - 批量审阅与重生成
   - 来源和策略追踪
3. **M3 预设与发布门禁**
   - 使用场景预设
   - 真实流程 E2E gate
   - 打包与升级验收

## Implementation Order

1. 先补任务状态与持久化模型，再接 UI。
2. 先让现有流程“挂到任务系统上”，再做质量闭环。
3. 预设层放在任务系统和质量闭环稳定之后。
4. 每个任务先写失败测试，再写最小实现，再跑最小验证。
5. 每个任务完成后单独提交，避免大提交难回滚。

### Task 1: Define Persistent Task Models And Serialization

**Files:**
- Create: `src/ankismart/core/task_models.py`
- Modify: `src/ankismart/core/models.py`
- Test: `tests/test_core/test_task_models.py`

**Step 1: Write the failing tests**

```python
from ankismart.core.task_models import TaskRun, TaskStage, TaskStatus


def test_task_run_round_trips_with_stage_progress():
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


def test_task_run_exposes_resume_target():
    task = TaskRun(
        task_id="task-2",
        flow="full_pipeline",
        status=TaskStatus.FAILED,
        resume_from_stage="generate",
    )

    assert task.resume_from_stage == "generate"
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_core/test_task_models.py -q
```

Expected: FAIL with missing module or missing task model fields.

**Step 3: Write minimal implementation**

```python
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
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_core/test_task_models.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/core/task_models.py src/ankismart/core/models.py tests/test_core/test_task_models.py
git commit -m "feat(core): add persistent task models"
```

### Task 2: Add Task Store And Recovery Snapshot Persistence

**Files:**
- Create: `src/ankismart/core/task_store.py`
- Modify: `src/ankismart/core/config.py`
- Test: `tests/test_core/test_task_store.py`

**Step 1: Write the failing tests**

```python
from ankismart.core.task_models import TaskRun, TaskStatus
from ankismart.core.task_store import JsonTaskStore


def test_task_store_persists_latest_run(tmp_path):
    store = JsonTaskStore(tmp_path / "tasks.json")
    task = TaskRun(task_id="task-1", flow="full_pipeline", status=TaskStatus.RUNNING)

    store.save(task)
    restored = store.get("task-1")

    assert restored is not None
    assert restored.status is TaskStatus.RUNNING


def test_task_store_lists_resumable_tasks_only(tmp_path):
    store = JsonTaskStore(tmp_path / "tasks.json")
    store.save(TaskRun(task_id="a", flow="x", status=TaskStatus.FAILED, resume_from_stage="generate"))
    store.save(TaskRun(task_id="b", flow="x", status=TaskStatus.COMPLETED))

    resumable = store.list_resumable()

    assert [task.task_id for task in resumable] == ["a"]
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_core/test_task_store.py -q
```

Expected: FAIL with missing store implementation.

**Step 3: Write minimal implementation**

```python
class JsonTaskStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def save(self, task: TaskRun) -> None:
        data = self._read_all()
        data[task.task_id] = task.model_dump(mode="json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, task_id: str) -> TaskRun | None:
        payload = self._read_all().get(task_id)
        return TaskRun.model_validate(payload) if payload else None
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_core/test_task_store.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/core/task_store.py src/ankismart/core/config.py tests/test_core/test_task_store.py
git commit -m "feat(core): persist resumable task snapshots"
```

### Task 3: Introduce Task Runtime Events For Workers

**Files:**
- Create: `src/ankismart/ui/task_runtime.py`
- Modify: `src/ankismart/ui/workers.py`
- Test: `tests/test_ui/test_task_runtime.py`
- Test: `tests/test_ui/test_workers.py`

**Step 1: Write the failing tests**

```python
from ankismart.ui.task_runtime import TaskEvent, TaskRuntime


def test_task_runtime_maps_worker_progress_to_stage_update():
    events = []
    runtime = TaskRuntime(on_event=events.append)

    runtime.emit_progress(task_id="task-1", stage="generate", progress=35, message="generating")

    assert events == [
        TaskEvent(task_id="task-1", stage="generate", kind="progress", progress=35, message="generating")
    ]


def test_export_worker_can_publish_task_event_callback(monkeypatch, tmp_path):
    published = []
    worker = ExportWorker(exporter=object(), cards=[], output_path=tmp_path / "out.apkg")
    worker.set_task_event_callback(published.append)

    assert worker._task_event_callback is not None
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_ui/test_task_runtime.py tests/test_ui/test_workers.py -q
```

Expected: FAIL because runtime/event adapter APIs do not exist yet.

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class TaskEvent:
    task_id: str
    stage: str
    kind: str
    progress: int = 0
    message: str = ""


class TaskRuntime:
    def __init__(self, on_event: Callable[[TaskEvent], None]) -> None:
        self._on_event = on_event

    def emit_progress(self, *, task_id: str, stage: str, progress: int, message: str) -> None:
        self._on_event(TaskEvent(task_id=task_id, stage=stage, kind="progress", progress=progress, message=message))
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_ui/test_task_runtime.py tests/test_ui/test_workers.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/ui/task_runtime.py src/ankismart/ui/workers.py tests/test_ui/test_task_runtime.py tests/test_ui/test_workers.py
git commit -m "feat(ui): add task runtime event adapter"
```

### Task 4: Add Task Center UI And Startup Recovery Banner

**Files:**
- Create: `src/ankismart/ui/task_center.py`
- Modify: `src/ankismart/ui/main_window.py`
- Modify: `src/ankismart/ui/app.py`
- Test: `tests/test_window.py`
- Test: `tests/test_startup.py`
- Test: `tests/test_ui/test_task_center.py`

**Step 1: Write the failing tests**

```python
def test_main_window_shows_recovery_banner_when_resumable_task_exists(monkeypatch):
    task = TaskRun(task_id="task-1", flow="full_pipeline", status=TaskStatus.FAILED, resume_from_stage="generate")
    monkeypatch.setattr("ankismart.ui.main_window.load_resumable_tasks", lambda: [task])

    window = MainWindow()

    assert window._task_recovery_banner.isVisible() is True


def test_task_center_renders_stage_statuses(qtbot):
    panel = TaskCenterPanel()
    panel.render_task(
        TaskRun(
            task_id="task-1",
            flow="full_pipeline",
            stages=[TaskStage(name="convert", status=TaskStatus.COMPLETED)],
        )
    )

    assert "convert" in panel._list_widget.item(0).text().lower()
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_window.py tests/test_startup.py tests/test_ui/test_task_center.py -q
```

Expected: FAIL because the task center panel and recovery banner do not exist yet.

**Step 3: Write minimal implementation**

```python
class TaskCenterPanel(SimpleCardWidget):
    def render_task(self, task: TaskRun) -> None:
        for stage in task.stages:
            self._list_widget.addItem(f"{stage.name}: {stage.status.value} ({stage.progress}%)")
```

Wire `MainWindow` startup to load resumable tasks and toggle a banner that can route the user back into the interrupted stage.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_window.py tests/test_startup.py tests/test_ui/test_task_center.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/ui/task_center.py src/ankismart/ui/main_window.py src/ankismart/ui/app.py tests/test_window.py tests/test_startup.py tests/test_ui/test_task_center.py
git commit -m "feat(ui): add task center and startup recovery prompt"
```

### Task 5: Route Import, Preview, And Result Pages Through Task Runs

**Files:**
- Modify: `src/ankismart/ui/import_page.py`
- Modify: `src/ankismart/ui/preview_page.py`
- Modify: `src/ankismart/ui/result_page.py`
- Modify: `src/ankismart/ui/workflows.py`
- Test: `tests/test_ui/test_import_page_generation.py`
- Test: `tests/test_ui/test_preview_page.py`
- Test: `tests/test_ui/test_result_page.py`
- Test: `tests/e2e/scenarios/test_main_workflow.py`
- Test: `tests/e2e/scenarios/test_error_handling.py`

**Step 1: Write the failing tests**

```python
def test_start_convert_creates_pending_task_run(monkeypatch):
    page = ImportPage(_make_main_window())
    created = {}
    monkeypatch.setattr(page, "_create_task_run", lambda flow: created.setdefault("flow", flow) or object())

    page._on_start_convert()

    assert created["flow"] == "full_pipeline"


def test_generation_warning_updates_task_stage(monkeypatch):
    page = PreviewPage(_make_main_window())
    events = []
    monkeypatch.setattr(page, "_publish_task_event", events.append)

    page._on_generation_warning("partial result")

    assert events[-1].kind == "warning"


def test_export_error_marks_export_stage_failed(monkeypatch, _qapp):
    page = ResultPage(_FakeMainWindow())
    events = []
    monkeypatch.setattr(page, "_publish_task_event", events.append)

    page._on_export_error("disk full")

    assert events[-1].stage == "export"
    assert events[-1].kind == "failed"
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_ui/test_import_page_generation.py tests/test_ui/test_preview_page.py tests/test_ui/test_result_page.py -q
```

Expected: FAIL because the pages are still page-driven rather than task-driven.

**Step 3: Write minimal implementation**

```python
def _publish_task_event(self, event: TaskEvent) -> None:
    if self._main.task_runtime is not None:
        self._main.task_runtime.handle(event)


def _create_task_run(self, flow: str) -> TaskRun:
    task = build_default_task_run(flow=flow)
    self._main.register_task(task)
    return task
```

Update the convert/generate/push/export handlers so each stage publishes `progress`, `warning`, `failed`, and `completed` events.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_ui/test_import_page_generation.py tests/test_ui/test_preview_page.py tests/test_ui/test_result_page.py tests/e2e/scenarios/test_main_workflow.py tests/e2e/scenarios/test_error_handling.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/ui/import_page.py src/ankismart/ui/preview_page.py src/ankismart/ui/result_page.py src/ankismart/ui/workflows.py tests/test_ui/test_import_page_generation.py tests/test_ui/test_preview_page.py tests/test_ui/test_result_page.py tests/e2e/scenarios/test_main_workflow.py tests/e2e/scenarios/test_error_handling.py
git commit -m "feat(ui): route pipeline pages through task runs"
```

### Task 6: Add Card Quality Metadata And Review Filters

**Files:**
- Modify: `src/ankismart/core/models.py`
- Modify: `src/ankismart/card_gen/postprocess.py`
- Modify: `src/ankismart/ui/card_preview_page.py`
- Modify: `src/ankismart/ui/card_edit_widget.py`
- Test: `tests/test_card_gen/test_postprocess.py`
- Test: `tests/test_ui/test_card_edit_widget.py`
- Create: `tests/test_ui/test_card_preview_page.py`

**Step 1: Write the failing tests**

```python
def test_postprocess_attaches_quality_flags_for_short_basic_cards():
    drafts = build_card_drafts(
        raw_cards=[{"Front": "Q", "Back": "A"}],
        deck_name="Default",
        note_type="Basic",
        tags=[],
        trace_id="t-1",
    )

    assert drafts[0].metadata.quality_flags == ["too_short"]


def test_card_preview_can_filter_only_low_quality_cards(qtbot):
    page = CardPreviewPage(_make_main_window())
    page.load_cards([
        _make_card(front="Q", back="A", quality_flags=["too_short"]),
        _make_card(front="Long enough question", back="Long enough answer", quality_flags=[]),
    ])

    page._quality_filter_combo.setCurrentText("Low quality")

    assert page._card_list.count() == 1
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_card_gen/test_postprocess.py tests/test_ui/test_card_edit_widget.py tests/test_ui/test_card_preview_page.py -q
```

Expected: FAIL because quality flags and filter UI do not exist yet.

**Step 3: Write minimal implementation**

```python
class CardMetadata(BaseModel):
    source_format: str = ""
    source_path: str = ""
    generated_at: str = ""
    strategy_id: str = ""
    source_document: str = ""
    quality_flags: list[str] = Field(default_factory=list)
```

Add a simple low-quality rule set in postprocess:

```python
if len(front_text) < 3 or len(back_text) < 3:
    quality_flags.append("too_short")
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_card_gen/test_postprocess.py tests/test_ui/test_card_edit_widget.py tests/test_ui/test_card_preview_page.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/core/models.py src/ankismart/card_gen/postprocess.py src/ankismart/ui/card_preview_page.py src/ankismart/ui/card_edit_widget.py tests/test_card_gen/test_postprocess.py tests/test_ui/test_card_edit_widget.py tests/test_ui/test_card_preview_page.py
git commit -m "feat(review): add card quality metadata and filters"
```

### Task 7: Add Regenerate Actions For Single Card, Selection, And Source Document

**Files:**
- Modify: `src/ankismart/ui/card_preview_page.py`
- Modify: `src/ankismart/ui/preview_page.py`
- Modify: `src/ankismart/ui/workers.py`
- Test: `tests/test_ui/test_preview_page.py`
- Test: `tests/test_ui/test_card_preview_page.py`
- Test: `tests/e2e/scenarios/test_error_handling.py`

**Step 1: Write the failing tests**

```python
def test_regenerate_selected_cards_reuses_source_document(monkeypatch):
    page = CardPreviewPage(_make_main_window())
    page.load_cards([_make_card(source_document="sample.md", strategy_id="basic")])
    launched = {}
    monkeypatch.setattr(page, "_start_regenerate_job", lambda payload: launched.setdefault("payload", payload))

    page._regenerate_selected_cards()

    assert launched["payload"].scope == "selected_cards"


def test_preview_page_can_resume_generation_from_failed_stage(monkeypatch):
    page = PreviewPage(_make_main_window())
    resumed = {}
    monkeypatch.setattr(page, "_resume_generation_task", lambda task: resumed.setdefault("task_id", task.task_id))

    page.resume_task(TaskRun(task_id="task-1", flow="full_pipeline", resume_from_stage="generate"))

    assert resumed["task_id"] == "task-1"
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_ui/test_preview_page.py tests/test_ui/test_card_preview_page.py tests/e2e/scenarios/test_error_handling.py -q
```

Expected: FAIL because regenerate actions and resume APIs are missing.

**Step 3: Write minimal implementation**

```python
class RegenerateRequest(BaseModel):
    scope: str
    card_indices: list[int] = Field(default_factory=list)
    source_document: str = ""
```

Add three UI actions:
- regenerate current card
- regenerate selection
- regenerate source document

Each action should build a `RegenerateRequest` and route it through the same task runtime.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_ui/test_preview_page.py tests/test_ui/test_card_preview_page.py tests/e2e/scenarios/test_error_handling.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/ui/card_preview_page.py src/ankismart/ui/preview_page.py src/ankismart/ui/workers.py tests/test_ui/test_preview_page.py tests/test_ui/test_card_preview_page.py tests/e2e/scenarios/test_error_handling.py
git commit -m "feat(review): add regenerate actions and resume flows"
```

### Task 8: Add Usage Presets In Settings And Import Flow

**Files:**
- Modify: `src/ankismart/core/config.py`
- Modify: `src/ankismart/ui/settings_page.py`
- Modify: `src/ankismart/ui/import_page.py`
- Modify: `src/ankismart/ui/i18n.py`
- Test: `tests/test_core/test_config.py`
- Test: `tests/test_ui/test_settings_page_config.py`
- Test: `tests/test_ui/test_import_page_navigation.py`

**Step 1: Write the failing tests**

```python
def test_config_round_trips_generation_preset(tmp_path):
    config = AppConfig()
    config.generation_preset = "exam_dense"

    save_config(config, config_path=tmp_path / "config.json")
    loaded = load_config(config_path=tmp_path / "config.json")

    assert loaded.generation_preset == "exam_dense"


def test_import_page_applies_exam_dense_preset(monkeypatch):
    page = ImportPage(_make_main_window())
    page._apply_generation_preset("exam_dense")

    assert page._target_total_spin.value() >= 20
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_core/test_config.py tests/test_ui/test_settings_page_config.py tests/test_ui/test_import_page_navigation.py -q
```

Expected: FAIL because generation presets do not exist.

**Step 3: Write minimal implementation**

```python
PRESET_DEFAULTS = {
    "reading_general": {"strategy_mix": ["basic", "concept"], "target_total": 12},
    "exam_dense": {"strategy_mix": ["basic", "cloze", "multiple_choice"], "target_total": 24},
    "language_vocab": {"strategy_mix": ["basic", "key_terms"], "target_total": 18},
}
```

Expose the preset in settings, and apply it as a one-click configuration template in the import flow.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_core/test_config.py tests/test_ui/test_settings_page_config.py tests/test_ui/test_import_page_navigation.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/core/config.py src/ankismart/ui/settings_page.py src/ankismart/ui/import_page.py src/ankismart/ui/i18n.py tests/test_core/test_config.py tests/test_ui/test_settings_page_config.py tests/test_ui/test_import_page_navigation.py
git commit -m "feat(settings): add generation presets"
```

### Task 9: Harden E2E Gates, Packaging Checks, And Release Criteria

**Files:**
- Modify: `tests/e2e/conftest.py`
- Modify: `tests/e2e/scenarios/test_main_workflow.py`
- Modify: `tests/e2e/scenarios/test_error_handling.py`
- Modify: `tests/e2e/gate/test_gate_workflow.py`
- Modify: `tests/test_packaging_build.py`
- Modify: `packaging/build.py`
- Modify: `docs/README.md`

**Step 1: Write the failing tests**

```python
def test_gate_real_can_resume_failed_generation_then_export(window, monkeypatch):
    ...
    result_page.export_apkg()
    _wait_until(export_path.exists)
    assert export_path.exists()


def test_packaging_build_embeds_plan_version_metadata(tmp_path):
    metadata = build_release_metadata(version="vnext")
    assert metadata["channel"] == "stable"
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/e2e/scenarios -m "fast" -q --maxfail=1
uv run pytest tests/e2e/gate -m "p0 and gate_real" -q --maxfail=1
uv run pytest tests/test_packaging_build.py -q
```

Expected: FAIL on missing recovery-oriented E2E assertions and release metadata coverage.

**Step 3: Write minimal implementation**

```python
RELEASE_CHECKLIST = [
    "task recovery smoke passed",
    "fast e2e passed",
    "gate real passed",
    "portable build verified",
]
```

Add release metadata generation in `packaging/build.py`, update test fixtures, and document the release checklist in `docs/README.md`.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/e2e/scenarios -m "fast" -q --maxfail=1
uv run pytest tests/e2e/gate -m "p0 and gate_real" -q --maxfail=1
uv run pytest tests/test_packaging_build.py -q
uv run ruff check src tests packaging
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/e2e/conftest.py tests/e2e/scenarios/test_main_workflow.py tests/e2e/scenarios/test_error_handling.py tests/e2e/gate/test_gate_workflow.py tests/test_packaging_build.py packaging/build.py docs/README.md
git commit -m "test: harden release gates for recoverable workflow"
```

## Final Verification

Run:

```bash
uv run ruff check src tests packaging
uv run pytest tests --ignore=tests/e2e -q --maxfail=20
uv run pytest tests/e2e/scenarios -m "fast" -q --maxfail=5
uv run pytest tests/e2e/gate -m "p0 and gate_real" -q --maxfail=1
uv run python packaging/build.py --clean
```

Expected:
- Ruff passes with no errors.
- Unit/integration suite passes.
- `fast` E2E passes.
- `gate_real` E2E passes.
- Packaging build produces portable and installer artifacts without regression.

## Risks And Watchpoints

- `MainWindow` 目前承担较多页面协调责任，任务中心接入时要避免继续膨胀；优先抽出独立 task runtime API。
- `workers.py` 已经承担多个线程角色，新增任务事件时要防止信号协议继续漂移；统一 callback/事件适配层，不要把页面逻辑塞回 worker。
- `CardDraft.metadata` 扩展字段后，要确认 `AnkiGateway`、APKG 导出、编辑对话框不会误删新字段。
- 恢复能力必须明确“可恢复的数据边界”；不要承诺恢复外部副作用，例如已经推送到 Anki 的部分状态。
- 预设层只做映射，不要把策略推荐器和 UI preset 逻辑互相耦合。

## Execution Notes

- 每个任务都按 TDD 执行：先写失败测试，再写最小实现，再重构。
- 每个任务完成后先跑最小测试，再提交，不要攒成一个巨型提交。
- 新建文件只限任务运行时和任务中心两个横切模块，其他改动优先复用现有文件。
- UI 改动完成后都要补截图或录屏证据，便于回归审查。
