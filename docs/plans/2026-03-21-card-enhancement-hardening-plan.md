# Card Enhancement Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收口当前卡片增强分支的剩余风险，确保生成、预览、编辑、推送、导出与 E2E 验证使用一致的标准化结果与一致的质量提示。

**Architecture:** 以现有 `card_pipeline` 为唯一标准化入口，优先消除导出端的重复解析逻辑，再把结构化质量信息暴露到结果页与交互流程中，最后用 E2E 与跨层回归测试锁住行为。执行顺序遵循 TDD：先补失败测试，再最小实现，再做链路验证。

**Tech Stack:** Python 3.11, PyQt6, pytest, Ruff, genanki, existing E2E harness.

---

## Scope

- 保持现有 `card_kind` / `card_normalizer` / `card_structure_validator` / `card_pipeline` 设计不推翻。
- 收口 APKG 导出端仍然存在的 choice 二次解析逻辑。
- 让 `quality_flags` / blocking 信息在 UI 中变成可见、可筛选、可行动的反馈。
- 补齐 fast E2E 与跨层回归，确保真实链路稳定。
- 本轮不引入新的题型，不改 OCR、设置页、持久化、LLM 重试架构。

## Task 1: Establish A Real-Flow Baseline

**Files:**
- Modify: `tests/e2e/scenarios/test_main_workflow.py`
- Modify: `tests/e2e/page_objects/card_preview_page.py`
- Modify: `tests/e2e/page_objects/result_page.py`
- Test: `tests/test_ui/test_card_preview_page.py`
- Test: `tests/test_ui/test_result_page.py`

**Step 1: Write failing regression tests for normalized-card visibility**

```python
def test_preview_page_shows_quality_flags_for_normalized_cards():
    ...
```

```python
def test_result_page_keeps_edited_card_title_after_normalization():
    ...
```

**Step 2: Run focused tests to verify they fail**

Run:

```bash
uv run pytest tests/test_ui/test_card_preview_page.py tests/test_ui/test_result_page.py -q --maxfail=1
```

Expected: FAIL because current assertions do not yet cover the remaining hardening targets.

**Step 3: Add or refine page-object accessors for preview/result quality text**

```python
class CardPreviewPageObject:
    def quality_summary_text(self) -> str:
        ...
```

```python
class ResultPageObject:
    def visible_status_text(self) -> str:
        ...
```

**Step 4: Re-run focused tests**

Run:

```bash
uv run pytest tests/test_ui/test_card_preview_page.py tests/test_ui/test_result_page.py -q --maxfail=1
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_ui/test_card_preview_page.py tests/test_ui/test_result_page.py tests/e2e/scenarios/test_main_workflow.py tests/e2e/page_objects/card_preview_page.py tests/e2e/page_objects/result_page.py
git commit -m "test(ui): establish card enhancement hardening baseline"
```

## Task 2: Remove Duplicate Choice Parsing From APKG Export

**Files:**
- Modify: `src/ankismart/anki_gateway/apkg_exporter.py`
- Modify: `tests/test_anki_gateway/test_apkg_exporter.py`
- Test: `tests/test_ui/test_card_preview_page.py`

**Step 1: Write failing exporter tests that prove preview/export use the same canonical fields**

```python
def test_export_does_not_depend_on_runtime_choice_reformatting_for_single_choice():
    ...
```

```python
def test_export_does_not_depend_on_runtime_choice_reformatting_for_multiple_choice():
    ...
```

The test should assert that exported `genanki.Note.fields` already contain the standardized multiline layout and that template-side JS is not required to infer answer keys.

**Step 2: Run focused tests to verify they fail**

Run:

```bash
uv run pytest tests/test_anki_gateway/test_apkg_exporter.py tests/test_ui/test_card_preview_page.py -q --maxfail=1
```

Expected: FAIL because `_CHOICE_FORMATTER_SCRIPT` still reparses choice text during export.

**Step 3: Replace template-side reparsing with direct rendering of normalized fields**

Implementation target:

```python
# Remove or heavily simplify _CHOICE_FORMATTER_SCRIPT.
# Templates should display standardized Front / Back directly.
# Export path must trust normalize_card_draft(card) output.
```

Keep only minimal display formatting that does not infer structure from raw text again.

**Step 4: Re-run focused tests**

Run:

```bash
uv run pytest tests/test_anki_gateway/test_apkg_exporter.py tests/test_ui/test_card_preview_page.py -q --maxfail=1
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/anki_gateway/apkg_exporter.py tests/test_anki_gateway/test_apkg_exporter.py tests/test_ui/test_card_preview_page.py
git commit -m "refactor(anki): remove duplicate choice parsing from export templates"
```

## Task 3: Surface Quality Flags And Blocking Reasons In Result UI

**Files:**
- Modify: `src/ankismart/ui/result_page.py`
- Modify: `tests/test_ui/test_result_page.py`
- Modify: `tests/test_anki_gateway/test_validator.py`

**Step 1: Write failing UI tests for quality feedback**

```python
def test_result_page_shows_warning_style_for_cards_with_quality_flags():
    ...
```

```python
def test_result_page_displays_human_readable_blocking_reason_for_invalid_structure():
    ...
```

**Step 2: Run focused tests to verify they fail**

Run:

```bash
uv run pytest tests/test_ui/test_result_page.py tests/test_anki_gateway/test_validator.py -q --maxfail=1
```

Expected: FAIL because result UI currently does not present structured normalization/validation feedback cleanly.

**Step 3: Implement user-facing quality feedback**

Implementation targets:

```python
def _format_quality_flags(flags: list[str], lang: str) -> str:
    ...
```

```python
def _format_structure_error(error_key: str, lang: str) -> str:
    ...
```

Apply them to:
- edited-card save success hints
- export/push error rows
- result table status or error text

**Step 4: Re-run focused tests**

Run:

```bash
uv run pytest tests/test_ui/test_result_page.py tests/test_anki_gateway/test_validator.py -q --maxfail=1
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/ui/result_page.py tests/test_ui/test_result_page.py tests/test_anki_gateway/test_validator.py
git commit -m "feat(ui): surface card quality and structure feedback in result page"
```

## Task 4: Add Cross-Layer Regression Tests For Edit -> Preview -> Export

**Files:**
- Modify: `tests/test_ui/test_card_edit_widget.py`
- Modify: `tests/test_ui/test_card_preview_page.py`
- Modify: `tests/test_anki_gateway/test_apkg_exporter.py`
- Modify: `tests/test_card_gen/test_postprocess.py`

**Step 1: Write failing integration-style unit regressions**

```python
def test_edited_basic_card_uses_same_normalized_back_in_preview_and_export():
    ...
```

```python
def test_generated_multiple_choice_card_keeps_same_answers_after_edit_and_export():
    ...
```

```python
def test_postprocess_and_manual_edit_produce_same_quality_flags_for_same_card():
    ...
```

**Step 2: Run focused tests to verify they fail**

Run:

```bash
uv run pytest tests/test_ui/test_card_edit_widget.py tests/test_ui/test_card_preview_page.py tests/test_anki_gateway/test_apkg_exporter.py tests/test_card_gen/test_postprocess.py -q --maxfail=1
```

Expected: FAIL until all three layers consume the same normalized structure.

**Step 3: Fix parity gaps only where tests expose them**

Likely touch points:
- `src/ankismart/ui/card_edit_widget.py`
- `src/ankismart/ui/card_preview_renderer.py`
- `src/ankismart/anki_gateway/apkg_exporter.py`
- `src/ankismart/card_gen/postprocess.py`

Rule:
- no new parallel parsing branch
- no UI-only repair logic
- all formatting must derive from normalized fields

**Step 4: Re-run focused tests**

Run:

```bash
uv run pytest tests/test_ui/test_card_edit_widget.py tests/test_ui/test_card_preview_page.py tests/test_anki_gateway/test_apkg_exporter.py tests/test_card_gen/test_postprocess.py -q --maxfail=1
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/ui/card_edit_widget.py src/ankismart/ui/card_preview_renderer.py src/ankismart/anki_gateway/apkg_exporter.py src/ankismart/card_gen/postprocess.py tests/test_ui/test_card_edit_widget.py tests/test_ui/test_card_preview_page.py tests/test_anki_gateway/test_apkg_exporter.py tests/test_card_gen/test_postprocess.py
git commit -m "test(card-gen): lock preview edit and export parity"
```

## Task 5: Add Fast E2E Scenario For Card Enhancement Workflow

**Files:**
- Modify: `tests/e2e/scenarios/test_main_workflow.py`
- Modify: `tests/e2e/page_objects/card_preview_page.py`
- Modify: `tests/e2e/page_objects/result_page.py`
- Modify: `tests/e2e/fixtures/data/e2e_main_docx_001_expected.json`

**Step 1: Write a failing fast E2E scenario**

```python
@pytest.mark.fast
def test_card_enhancement_flow_keeps_quality_feedback_consistent(app, ...):
    # import document
    # generate cards
    # enter preview
    # verify quality hint or normalized structure marker
    # export or enter result page
    # verify same card title / same warning semantics
```

**Step 2: Run the fast E2E subset and verify it fails**

Run:

```bash
uv run pytest tests/e2e/scenarios/test_main_workflow.py -m "fast" -q --maxfail=1
```

Expected: FAIL until page objects and UI feedback are aligned.

**Step 3: Implement the minimum E2E-facing support**

Typical changes:
- add page-object selectors for preview quality summary
- add page-object selectors for result status text
- update fixture expectation file only if user-visible output intentionally changed

**Step 4: Re-run the fast E2E subset**

Run:

```bash
uv run pytest tests/e2e/scenarios/test_main_workflow.py -m "fast" -q --maxfail=1
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/e2e/scenarios/test_main_workflow.py tests/e2e/page_objects/card_preview_page.py tests/e2e/page_objects/result_page.py tests/e2e/fixtures/data/e2e_main_docx_001_expected.json
git commit -m "test(e2e): cover card enhancement workflow consistency"
```

## Task 6: Final Verification And Review Gate

**Files:**
- Modify: any touched files from Tasks 1-5 as needed
- Test: `tests/test_card_gen`
- Test: `tests/test_ui`
- Test: `tests/test_anki_gateway`
- Test: `tests/e2e/scenarios/test_main_workflow.py`

**Step 1: Run Ruff on all touched paths**

Run:

```bash
uv run --python 3.11 ruff check src/ankismart/card_gen src/ankismart/ui src/ankismart/anki_gateway tests/test_card_gen tests/test_ui tests/test_anki_gateway tests/e2e/scenarios tests/e2e/page_objects
```

Expected: PASS.

**Step 2: Run non-E2E regression**

Run:

```bash
uv run --python 3.11 pytest tests --ignore=tests/e2e -q --maxfail=1
```

Expected: PASS.

**Step 3: Run fast E2E regression**

Run:

```bash
uv run --python 3.11 pytest tests/e2e/scenarios -m "fast" -q --maxfail=1
```

Expected: PASS.

**Step 4: If environment is available, run gate-real smoke**

Run:

```bash
uv run --python 3.11 pytest tests/e2e/gate -m "p0 and gate_real" -q --maxfail=1
```

Expected: PASS or document environment blocker explicitly.

**Step 5: Commit**

```bash
git add src/ankismart/card_gen src/ankismart/ui src/ankismart/anki_gateway tests/test_card_gen tests/test_ui tests/test_anki_gateway tests/e2e
git commit -m "feat(card-gen): harden card enhancement across ui export and e2e"
```
