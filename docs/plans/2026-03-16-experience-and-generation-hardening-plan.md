# Ankismart Experience And Generation Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不删减任何现有功能的前提下，补齐长任务等待体验、导出/推送实时反馈，并修正卡片推荐与生成链路中的关键逻辑缺陷。

**Architecture:** 方案分两条主线推进。第一条主线收口 UI 长任务状态，统一使用 worker + 持续状态区 + 明确进度/取消语义，解决“程序像卡住了”的体感问题。第二条主线收口 card generation pipeline，统一策略命名、修正分片计数、补充坏卡过滤和图像策略一致性，避免推荐失效和生成结果漂移。

**Tech Stack:** Python 3.11, PyQt6, QFluentWidgets, pytest, Ruff, AnkiConnect, genanki.

---

## Scope

- 不移除任何现有按钮、页面、导出方式、推送模式或卡片策略。
- 允许调整长任务实现方式，但要保持现有用户入口不变。
- 优先修复已经确认的真实问题：
  - 结果页 APKG 导出同步阻塞
  - 推送缺少逐卡实时进度
  - 推荐器与生成器策略 ID 不一致
  - 分片生成时 `target_count` 语义错误
  - 非 Cloze 坏卡缺少结构校验
  - 图像类策略在分片路径下需要保持一致行为

## Implementation Order

1. 先补测试，锁定当前缺陷。
2. 先改 card generation correctness，再改 UI 长任务体验。
3. 每完成一个子任务就跑最小相关测试。
4. 所有任务完成后统一跑 lint + 关键测试集。

### Task 1: Lock Current Regressions With Failing Tests

**Files:**
- Modify: `tests/test_card_gen/test_generator.py`
- Modify: `tests/test_ui/test_result_page.py`
- Modify: `tests/test_ui/test_workers.py`

**Step 1: Write the failing tests for generator strategy compatibility**

```python
def test_recommended_strategy_ids_are_supported_by_generator():
    recommender = StrategyRecommender()
    recommendation = recommender.recommend("第1章 定义：测试概念。例题：请解释。")

    unsupported = [
        item["strategy"]
        for item in recommendation.strategy_mix
        if item["strategy"] not in _STRATEGY_MAP
    ]

    assert unsupported == []


def test_rule_based_recommendation_ratios_sum_to_100():
    result = StrategyRecommender().recommend("general summary notes")
    assert sum(item["ratio"] for item in result.strategy_mix) == 100
```

**Step 2: Write the failing tests for split generation correctness**

```python
def test_split_generation_respects_global_target_count():
    gen = _make_generator(chat_side_effect=_fake_llm_basic)
    request = GenerateRequest(
        markdown="Paragraph one.\n\nParagraph two.\n\nParagraph three.",
        strategy="basic",
        enable_auto_split=True,
        split_threshold=10,
        target_count=1,
    )

    drafts = gen.generate(request)

    assert len(drafts) == 1


def test_split_image_qa_still_attaches_source_image(tmp_path):
    img_path = tmp_path / "diagram.png"
    img_path.write_bytes(b"fake")
    gen = _make_generator(chat_side_effect=_fake_llm_basic)

    drafts = gen.generate(
        GenerateRequest(
            markdown="Paragraph one.\n\nParagraph two.\n\nParagraph three.",
            strategy="image_qa",
            source_path=str(img_path),
            enable_auto_split=True,
            split_threshold=10,
        )
    )

    assert drafts
    assert all(draft.media.picture for draft in drafts)
```

**Step 3: Write the failing tests for invalid non-cloze cards**

```python
def test_build_card_drafts_skips_basic_cards_missing_required_fields():
    drafts = build_card_drafts(
        raw_cards=[{"Front": ""}, {"Back": "A"}, {"Question": "Q"}],
        deck_name="Default",
        note_type="Basic",
        tags=["x"],
        trace_id="t",
    )

    assert drafts == []
```

**Step 4: Write the failing tests for async result-page export**

```python
def test_export_apkg_uses_export_worker(monkeypatch, _qapp, tmp_path):
    page = ResultPage(_FakeMainWindow())
    page._cards = [_make_card()]
    monkeypatch.setattr(
        "ankismart.ui.result_page.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(tmp_path / "out.apkg"), "Anki Package (*.apkg)"),
    )

    created = {}

    class _ExportWorkerStub:
        def __init__(self, exporter, cards, output_path):
            created["cards"] = cards
            created["path"] = output_path
            self.finished = _SignalStub()
            self.error = _SignalStub()
            self.progress = _SignalStub()
            self.cancelled = _SignalStub()

        def start(self):
            created["started"] = True

    monkeypatch.setattr("ankismart.ui.result_page.ExportWorker", _ExportWorkerStub)
    page._export_apkg()

    assert created["started"] is True
```

**Step 5: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_card_gen/test_generator.py tests/test_ui/test_result_page.py tests/test_ui/test_workers.py -q
```

Expected: FAIL on unsupported strategy IDs, ratio sum, split target-count behavior, split image attachment, invalid basic card filtering, and result-page async export expectation.

**Step 6: Commit**

```bash
git add tests/test_card_gen/test_generator.py tests/test_ui/test_result_page.py tests/test_ui/test_workers.py
git commit -m "test: lock generation and async export regressions"
```

### Task 2: Unify Strategy IDs And Recommendation Ratios

**Files:**
- Modify: `src/ankismart/card_gen/strategy_recommender.py`
- Modify: `src/ankismart/card_gen/generator.py`
- Modify: `src/ankismart/core/models.py`
- Test: `tests/test_card_gen/test_generator.py`

**Step 1: Normalize recommender output IDs to generator-supported values**

```python
RULE_STRATEGY_ALIASES = {
    "basic_qa": "basic",
    "fill_blank": "cloze",
    "concept_explanation": "concept",
}
```

Apply the alias map before returning `StrategyRecommendation`.

**Step 2: Replace lossy ratio normalization with remainder distribution**

```python
total_ratio = sum(item["ratio"] for item in strategy_mix)
normalized = []
remainders = []
allocated = 0

for index, item in enumerate(strategy_mix):
    raw = item["ratio"] * 100 / total_ratio
    value = int(raw)
    normalized.append({**item, "ratio": value})
    remainders.append((raw - value, index))
    allocated += value

for _, index in sorted(remainders, reverse=True)[: 100 - allocated]:
    normalized[index]["ratio"] += 1
```

**Step 3: Document accepted strategy IDs on the request boundary**

```python
class GenerateRequest(BaseModel):
    strategy: str = "basic"  # basic, cloze, concept, key_terms, single_choice, multiple_choice, image_qa, image_occlusion
```

**Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_card_gen/test_generator.py -q
```

Expected: PASS for recommendation compatibility and ratio-sum assertions.

**Step 5: Commit**

```bash
git add src/ankismart/card_gen/strategy_recommender.py src/ankismart/card_gen/generator.py src/ankismart/core/models.py tests/test_card_gen/test_generator.py
git commit -m "fix(card-gen): unify strategy ids and normalize recommendation ratios"
```

### Task 3: Fix Split Generation Semantics And Image Strategy Consistency

**Files:**
- Modify: `src/ankismart/card_gen/generator.py`
- Test: `tests/test_card_gen/test_generator.py`

**Step 1: Stop injecting the same global target into every chunk**

Use a chunk-local target only when explicitly allocated.

```python
remaining_target = request.target_count if request.target_count > 0 else 0

for i, chunk in enumerate(chunks, 1):
    chunk_target = 0
    if remaining_target > 0:
        chunks_left = len(chunks) - i + 1
        chunk_target = max(1, remaining_target // chunks_left)
```

**Step 2: Build a per-chunk prompt instead of mutating the global prompt once**

```python
chunk_system_prompt = base_system_prompt
if chunk_target > 0:
    chunk_system_prompt += f"\n- Generate exactly {chunk_target} cards\n"
```

**Step 3: Stop early once the global target is satisfied**

```python
all_drafts.extend(chunk_drafts)
if request.target_count > 0 and len(all_drafts) >= request.target_count:
    break
```

**Step 4: Keep image attachment behavior identical between split and non-split paths**

Leave `_attach_image()` after the final `drafts` assignment so both paths share it.

**Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_card_gen/test_generator.py -q
```

Expected: PASS for split-target and split-image tests.

**Step 6: Commit**

```bash
git add src/ankismart/card_gen/generator.py tests/test_card_gen/test_generator.py
git commit -m "fix(card-gen): respect global target count in split generation"
```

### Task 4: Filter Invalid Non-Cloze Cards In Postprocess

**Files:**
- Modify: `src/ankismart/card_gen/postprocess.py`
- Test: `tests/test_card_gen/test_generator.py`

**Step 1: Add a minimal required-field validator by note type**

```python
def _has_required_fields(card: dict, note_type: str) -> bool:
    if note_type == "Cloze":
        return bool(card.get("Text", "").strip()) and validate_cloze(card.get("Text", ""))
    if note_type == "Basic":
        front = str(card.get("Front", "")).strip()
        back = str(card.get("Back", "")).strip()
        return bool(front and back)
    return bool(card)
```

**Step 2: Skip malformed cards with explicit logging**

```python
if not _has_required_fields(card, note_type):
    logger.warning("Skipping malformed card", extra={"index": i, "note_type": note_type, "trace_id": trace_id})
    continue
```

**Step 3: Run focused tests**

Run:

```bash
uv run pytest tests/test_card_gen/test_generator.py -q
```

Expected: PASS for malformed-card filtering tests.

**Step 4: Commit**

```bash
git add src/ankismart/card_gen/postprocess.py tests/test_card_gen/test_generator.py
git commit -m "fix(card-gen): filter malformed non-cloze cards"
```

### Task 5: Make Result-Page Export Asynchronous And Visible

**Files:**
- Modify: `src/ankismart/ui/result_page.py`
- Modify: `src/ankismart/ui/workers.py`
- Test: `tests/test_ui/test_result_page.py`
- Test: `tests/test_ui/test_workers.py`

**Step 1: Add explicit export worker state to ResultPage**

```python
self._export_worker = None
self._export_status_label = BodyLabel("")
```

**Step 2: Replace synchronous export with `ExportWorker`**

```python
worker = ExportWorker(ApkgExporter(), self._cards, Path(path))
self._export_worker = worker
worker.progress.connect(self._on_export_progress)
worker.finished.connect(self._on_export_done)
worker.error.connect(self._on_export_error)
worker.cancelled.connect(self._on_export_cancelled)
worker.start()
```

**Step 3: Disable conflicting actions while exporting**

```python
self._btn_export_apkg.setEnabled(False)
self._btn_retry.setEnabled(False)
self._btn_repush_all.setEnabled(False)
```

**Step 4: Surface a persistent visible status**

```python
def _on_export_progress(self, message: str) -> None:
    self._export_status_label.setText(message)
```

**Step 5: Restore state on finish, error, and cancel**

Reconnect the existing callbacks so every exit path reenables buttons and clears worker references.

**Step 6: Run focused tests**

Run:

```bash
uv run pytest tests/test_ui/test_result_page.py tests/test_ui/test_workers.py -q
```

Expected: PASS for result-page export worker wiring and worker cancellation behavior.

**Step 7: Commit**

```bash
git add src/ankismart/ui/result_page.py src/ankismart/ui/workers.py tests/test_ui/test_result_page.py tests/test_ui/test_workers.py
git commit -m "fix(ui): make result-page export asynchronous"
```

### Task 6: Add Real-Time Push Progress To Preview And Result Flows

**Files:**
- Modify: `src/ankismart/anki_gateway/gateway.py`
- Modify: `src/ankismart/ui/workers.py`
- Modify: `src/ankismart/ui/preview_page.py`
- Modify: `src/ankismart/ui/result_page.py`
- Test: `tests/test_ui/test_workers.py`
- Test: `tests/test_ui/test_preview_page.py`
- Test: `tests/test_ui/test_result_page.py`

**Step 1: Add an optional per-card callback to gateway push**

```python
def push(self, cards, update_mode="create_only", progress_callback=None):
    ...
    for i, card in enumerate(prepared_cards):
        ...
        if progress_callback is not None:
            progress_callback(i + 1, len(prepared_cards), status)
```

**Step 2: Forward gateway progress in PushWorker**

```python
def on_progress(current: int, total: int, status: CardPushStatus) -> None:
    self.card_progress.emit(current, total)
    self.progress.emit(f"已推送 {current}/{total} 张卡片")

result = self._gateway.push(self._cards, update_mode=self._update_mode, progress_callback=on_progress)
```

**Step 3: Show progress in PreviewPage**

```python
self._push_worker.card_progress.connect(self._on_push_card_progress)

def _on_push_card_progress(self, current: int, total: int) -> None:
    self._show_state_tooltip("正在推送到 Anki", f"已完成 {current}/{total}")
```

**Step 4: Show progress in ResultPage retry and repush flows**

Add a visible label or status area instead of a short-lived 2-second InfoBar.

**Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_ui/test_workers.py tests/test_ui/test_preview_page.py tests/test_ui/test_result_page.py -q
```

Expected: PASS for push progress signal wiring and UI status updates.

**Step 6: Commit**

```bash
git add src/ankismart/anki_gateway/gateway.py src/ankismart/ui/workers.py src/ankismart/ui/preview_page.py src/ankismart/ui/result_page.py tests/test_ui/test_workers.py tests/test_ui/test_preview_page.py tests/test_ui/test_result_page.py
git commit -m "feat(ui): surface real-time push progress"
```

### Task 7: Strengthen Sample Generation And Long-Task Status Messaging

**Files:**
- Modify: `src/ankismart/ui/preview_page.py`
- Modify: `src/ankismart/ui/card_preview_page.py`
- Test: `tests/test_ui/test_preview_page.py`

**Step 1: Replace short-lived sample InfoBar with persistent task status**

```python
self._show_state_tooltip("正在生成样本卡片", "正在调用模型，请稍候")
```

**Step 2: Reuse the same task-complete semantics on success and failure**

```python
self._finish_state_tooltip(True, "样本卡片生成完成")
self._finish_state_tooltip(False, "样本卡片生成失败")
```

**Step 3: Keep buttons and messages mutually consistent**

Ensure `_btn_generate` and `_btn_preview` are always restored on every sample exit path.

**Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_ui/test_preview_page.py -q
```

Expected: PASS for sample-generation state restoration and visible status behavior.

**Step 5: Commit**

```bash
git add src/ankismart/ui/preview_page.py src/ankismart/ui/card_preview_page.py tests/test_ui/test_preview_page.py
git commit -m "fix(ui): make sample generation status persistent"
```

### Task 8: Final Verification

**Files:**
- Verify only

**Step 1: Run card generation and UI regression suite**

Run:

```bash
uv run pytest tests/test_card_gen/test_generator.py tests/test_ui/test_workers.py tests/test_ui/test_preview_page.py tests/test_ui/test_result_page.py -q
```

Expected: PASS

**Step 2: Run affected domain suites**

Run:

```bash
uv run pytest tests/test_converter tests/test_card_gen tests/test_anki_gateway -q
```

Expected: PASS

**Step 3: Run lint**

Run:

```bash
uv run ruff check src tests
```

Expected: All checks passed

**Step 4: Optional fast E2E smoke**

Run:

```bash
uv run pytest tests/e2e/scenarios -m "fast" -q --maxfail=1
```

Expected: PASS

**Step 5: Commit**

```bash
git add src tests
git commit -m "chore: verify experience and generation hardening"
```
