# Card Auto Format Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 Ankismart 新增统一的卡片自动格式化与结构校验管线，覆盖生成、编辑、预览、推送和导出全流程。

**Architecture:** 通过新增独立模块把“卡片类型识别、非标准文本解析、字段标准化、结构校验”集中实现，并让 `postprocess`、UI、validator、exporter 全部复用同一个入口。实现顺序遵循 TDD：先补新模块测试，再实现模块，再逐步接管调用方，最后做链路回归。

**Tech Stack:** Python 3.11, Pydantic, PyQt6, pytest, Ruff.

---

## Scope

- 新增 card auto-format 模块，不在 UI 中继续堆叠零散修复逻辑。
- 保持现有 `CardDraft` 数据模型和 Anki 模板兼容。
- 统一 `Cloze`、`Cloze 2`、`AnkiSmart Cloze` 的结构校验语义。
- 覆盖 AI 生成结果与用户手动编辑后的卡片。
- 本轮不引入新的 LLM 重试链路。

## Task 1: Add Card Kind Detection Module

**Files:**
- Create: `src/ankismart/card_gen/card_kind.py`
- Test: `tests/test_card_gen/test_card_kind.py`

**Step 1: Write the failing tests for card kind priority**

```python
from ankismart.card_gen.card_kind import detect_card_kind
from ankismart.core.models import CardDraft, CardMetadata


def test_detect_card_kind_prefers_strategy_id_over_tags_and_note_type():
    card = CardDraft(
        note_type="Basic",
        tags=["basic"],
        fields={"Front": "Q", "Back": "A"},
        metadata=CardMetadata(strategy_id="single_choice"),
    )

    assert detect_card_kind(card) == "single_choice"
```

```python
def test_detect_card_kind_falls_back_to_tags_then_note_type_then_field_shape():
    card = CardDraft(note_type="Basic", tags=["multiple_choice"], fields={"Front": "Q", "Back": "A"})
    assert detect_card_kind(card) == "multiple_choice"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_card_gen/test_card_kind.py -q
```

Expected: FAIL because `card_kind.py` does not exist yet.

**Step 3: Implement the minimal card kind detector**

```python
SUPPORTED_CARD_KINDS = {
    "basic",
    "concept",
    "key_terms",
    "single_choice",
    "multiple_choice",
    "cloze",
    "image_qa",
    "generic",
}


def detect_card_kind(card: CardDraft) -> str:
    strategy_id = (card.metadata.strategy_id or "").strip().lower()
    if strategy_id in SUPPORTED_CARD_KINDS:
        return strategy_id
    ...
```

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_card_gen/test_card_kind.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/card_gen/card_kind.py tests/test_card_gen/test_card_kind.py
git commit -m "test(card-gen): add card kind detection module"
```

## Task 2: Add Reusable Card Format Parsers

**Files:**
- Create: `src/ankismart/card_gen/card_format_parsers.py`
- Test: `tests/test_card_gen/test_card_format_parsers.py`

**Step 1: Write failing parser tests for messy choice/basic text**

```python
from ankismart.card_gen.card_format_parsers import parse_choice_front, parse_choice_back, parse_answer_block


def test_parse_choice_front_supports_inline_html_and_fullwidth_punctuation():
    question, options = parse_choice_front("Python 默认解释器是？<br>A：CPython B：JVM C：CLR D：Lua")
    assert question == "Python 默认解释器是？"
    assert [key for key, _ in options] == ["A", "B", "C", "D"]
```

```python
def test_parse_choice_back_extracts_answer_and_explanations_from_mixed_language_markers():
    answer_keys, explanation_lines = parse_choice_back("Answer: B\n解析:\nA. 错\nB. 对")
    assert answer_keys == ["B"]
    assert explanation_lines == ["A. 错", "B. 对"]
```

```python
def test_parse_answer_block_splits_answer_and_explanation_without_number_prefixes():
    answer, explanation = parse_answer_block("1. 答案: 原子性\n2. 解析:\n事务要么全部成功要么全部失败")
    assert answer == "原子性"
    assert "事务要么全部成功要么全部失败" in explanation
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_card_gen/test_card_format_parsers.py -q
```

Expected: FAIL because parser module does not exist yet.

**Step 3: Implement the parser helpers**

```python
def normalize_html_to_text(text: str) -> str:
    ...


def strip_leading_index(text: str) -> str:
    ...


def parse_choice_front(front: str) -> tuple[str, list[tuple[str, str]]]:
    ...


def parse_choice_back(back: str) -> tuple[list[str], list[str]]:
    ...


def parse_answer_block(raw: str) -> tuple[str, str]:
    ...
```

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_card_gen/test_card_format_parsers.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/card_gen/card_format_parsers.py tests/test_card_gen/test_card_format_parsers.py
git commit -m "test(card-gen): add card format parsers"
```

## Task 3: Add Card Normalizer For Basic-Like, Choice, And Cloze Cards

**Files:**
- Create: `src/ankismart/card_gen/card_normalizer.py`
- Test: `tests/test_card_gen/test_card_normalizer.py`
- Modify: `src/ankismart/core/models.py`

**Step 1: Write failing normalization tests**

```python
from ankismart.card_gen.card_normalizer import normalize_fields


def test_normalize_basic_alias_fields_to_front_back_answer_explanation_block():
    result = normalize_fields(
        note_type="Basic",
        strategy_id="basic",
        fields={"Question": "什么是事务原子性？", "Answer": "操作要么全成要么全败。解析：这是 ACID 的 A。"},
    )
    assert result.fields["Front"] == "什么是事务原子性？"
    assert result.fields["Back"].startswith("答案:")
    assert "解析:" in result.fields["Back"]
```

```python
def test_normalize_single_choice_rewrites_front_and_back_to_standard_layout():
    result = normalize_fields(
        note_type="Basic",
        strategy_id="single_choice",
        fields={
            "Front": "Python 默认解释器是？ A. CPython B. JVM C. CLR D. Lua",
            "Back": "答案：A CPython 是官方实现。",
        },
    )
    assert result.fields["Front"].count("\n") >= 4
    assert result.fields["Back"].startswith("答案: A")
    assert "解析:" in result.fields["Back"]
```

```python
def test_normalize_cloze_keeps_text_and_marks_invalid_when_token_missing():
    result = normalize_fields(
        note_type="AnkiSmart Cloze",
        strategy_id="cloze",
        fields={"Text": "plain text", "Extra": "hint"},
    )
    assert "cloze_syntax_invalid" in result.quality_flags
```
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_card_gen/test_card_normalizer.py -q
```

Expected: FAIL because normalizer module does not exist yet.

**Step 3: Implement normalization result model and rules**

```python
@dataclass(slots=True)
class NormalizationResult:
    fields: dict[str, str]
    quality_flags: list[str]
    warnings: list[str]
    blocking_errors: list[str]
```

```python
def normalize_fields(*, note_type: str, strategy_id: str, fields: Mapping[str, object], tags: Sequence[str] | None = None) -> NormalizationResult:
    kind = detect_card_kind_from_parts(...)
    if kind in {"basic", "concept", "key_terms", "image_qa"}:
        return _normalize_basic_like(...)
    if kind == "single_choice":
        return _normalize_single_choice(...)
    if kind == "multiple_choice":
        return _normalize_multiple_choice(...)
    if kind == "cloze":
        return _normalize_cloze(...)
    return _normalize_generic(...)
```

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_card_gen/test_card_normalizer.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/card_gen/card_normalizer.py src/ankismart/core/models.py tests/test_card_gen/test_card_normalizer.py
git commit -m "feat(card-gen): add shared card normalizer"
```

## Task 4: Add Strict Structure Validator

**Files:**
- Create: `src/ankismart/card_gen/card_structure_validator.py`
- Test: `tests/test_card_gen/test_card_structure_validator.py`

**Step 1: Write failing validator tests for warning/blocking boundaries**

```python
from ankismart.card_gen.card_structure_validator import validate_normalized_card


def test_validate_single_choice_blocks_when_option_count_is_invalid():
    result = validate_normalized_card(
        note_type="Basic",
        card_kind="single_choice",
        fields={"Front": "题目\nA. 1\nB. 2", "Back": "答案: A\n解析:\nA. 对\nB. 错"},
    )
    assert result.status == "blocking"
```

```python
def test_validate_basic_like_warns_when_explanation_missing():
    result = validate_normalized_card(
        note_type="Basic",
        card_kind="basic",
        fields={"Front": "Q", "Back": "答案: A"},
    )
    assert result.status == "warning"
```

```python
def test_validate_ankismart_cloze_blocks_without_valid_cloze_token():
    result = validate_normalized_card(
        note_type="AnkiSmart Cloze",
        card_kind="cloze",
        fields={"Text": "plain text", "Extra": ""},
    )
    assert result.status == "blocking"
```

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_card_gen/test_card_structure_validator.py -q
```

Expected: FAIL because validator module does not exist yet.

**Step 3: Implement strict structure validation**

```python
@dataclass(slots=True)
class ValidationResult:
    status: Literal["normalized", "warning", "blocking"]
    warnings: list[str]
    blocking_errors: list[str]
```

```python
def validate_normalized_card(*, note_type: str, card_kind: str, fields: Mapping[str, str]) -> ValidationResult:
    ...
```

**Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_card_gen/test_card_structure_validator.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/card_gen/card_structure_validator.py tests/test_card_gen/test_card_structure_validator.py
git commit -m "feat(card-gen): add card structure validator"
```

## Task 5: Add Unified Card Pipeline And Integrate Generation Postprocess

**Files:**
- Create: `src/ankismart/card_gen/card_pipeline.py`
- Modify: `src/ankismart/card_gen/postprocess.py`
- Modify: `src/ankismart/card_gen/generator.py`
- Test: `tests/test_card_gen/test_postprocess.py`
- Test: `tests/test_card_gen/test_generator.py`

**Step 1: Write failing regression tests around postprocess normalization**

```python
def test_build_card_drafts_normalizes_basic_alias_fields_and_quality_flags():
    drafts = build_card_drafts(
        raw_cards=[{"Question": "Q1", "Answer": "A1。解析：补充说明。"}],
        deck_name="Deck",
        note_type="Basic",
        tags=["tag1"],
        trace_id="t-123",
        strategy_id="basic",
    )
    assert drafts[0].fields["Front"] == "Q1"
    assert drafts[0].fields["Back"].startswith("答案:")
```

```python
def test_build_card_drafts_normalizes_single_choice_using_strategy_id():
    drafts = build_card_drafts(
        raw_cards=[{"Front": "题目 A. 一 B. 二 C. 三 D. 四", "Back": "答案：B 二是正确项。"}],
        deck_name="Deck",
        note_type="Basic",
        tags=["ankismart"],
        trace_id="t-123",
        strategy_id="single_choice",
    )
    assert drafts[0].fields["Front"].splitlines()[1].startswith("A.")
```

**Step 2: Run focused tests to verify they fail**

Run:

```bash
uv run pytest tests/test_card_gen/test_postprocess.py tests/test_card_gen/test_generator.py -q
```

Expected: FAIL because `build_card_drafts()` still uses legacy normalization.

**Step 3: Implement the pipeline helpers and wire them into postprocess**

```python
def normalize_card_draft(draft: CardDraft) -> CardDraft:
    ...


def normalize_raw_card(*, note_type: str, strategy_id: str, fields: Mapping[str, object], tags: Sequence[str] | None = None) -> NormalizationResult:
    ...
```

```python
normalized = normalize_raw_card(
    note_type=note_type,
    strategy_id=strategy_id,
    fields=card,
    tags=tags,
)
```

**Step 4: Run focused tests to verify they pass**

Run:

```bash
uv run pytest tests/test_card_gen/test_postprocess.py tests/test_card_gen/test_generator.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/card_gen/card_pipeline.py src/ankismart/card_gen/postprocess.py src/ankismart/card_gen/generator.py tests/test_card_gen/test_postprocess.py tests/test_card_gen/test_generator.py
git commit -m "feat(card-gen): normalize generated cards in postprocess"
```

## Task 6: Replace Preview Parsing With Shared Card Modules

**Files:**
- Modify: `src/ankismart/ui/card_preview_page.py`
- Test: `tests/test_theme.py`
- Test: `tests/test_ui/test_card_preview_page.py`

**Step 1: Write failing preview regression tests for strategy-aware rendering**

```python
def test_preview_detects_choice_kind_from_strategy_id_not_only_tags():
    card = CardDraft(
        note_type="Basic",
        fields={"Front": "题目 A. 一 B. 二 C. 三 D. 四", "Back": "答案：B 二正确"},
        metadata=CardMetadata(strategy_id="single_choice"),
    )
    assert CardRenderer.detect_card_kind(card) == "single_choice"
```

```python
def test_preview_renders_normalized_choice_layout_from_shared_parser():
    ...
```

**Step 2: Run focused tests to verify they fail**

Run:

```bash
uv run pytest tests/test_theme.py tests/test_ui/test_card_preview_page.py -q
```

Expected: FAIL because preview still uses its own detection/parsing logic.

**Step 3: Update preview code to delegate to shared modules**

```python
from ankismart.card_gen.card_kind import detect_card_kind
from ankismart.card_gen.card_format_parsers import parse_choice_front, parse_choice_back, parse_answer_block
```

```python
def detect_card_kind(card: CardDraft) -> str:
    return detect_card_kind(card)
```

Rename local helpers as needed to avoid shadowing and remove duplicated parsing branches only after tests pass.

**Step 4: Run focused tests to verify they pass**

Run:

```bash
uv run pytest tests/test_theme.py tests/test_ui/test_card_preview_page.py -q
```

Expected: PASS, preview remains visually consistent while consuming normalized data.

**Step 5: Commit**

```bash
git add src/ankismart/ui/card_preview_page.py tests/test_theme.py tests/test_ui/test_card_preview_page.py
git commit -m "refactor(ui): reuse shared card normalization in preview"
```

## Task 7: Normalize And Revalidate Cards After Manual Editing

**Files:**
- Modify: `src/ankismart/ui/card_edit_widget.py`
- Modify: `src/ankismart/ui/result_page.py`
- Test: `tests/test_ui/test_card_edit_widget.py`
- Test: `tests/test_ui/test_result_page.py`

**Step 1: Write failing edit-save tests**

```python
def test_get_edited_card_reformats_basic_back_to_answer_explanation_block(qtbot):
    ...
```

```python
def test_edit_widget_save_current_reformats_choice_fields_after_user_edit(qtbot):
    ...
```

**Step 2: Run focused tests to verify they fail**

Run:

```bash
uv run pytest tests/test_ui/test_card_edit_widget.py tests/test_ui/test_result_page.py -q
```

Expected: FAIL because edited fields are currently written back raw.

**Step 3: Normalize cards after edit-save paths**

```python
from ankismart.card_gen.card_pipeline import normalize_card_draft


edited = normalize_card_draft(self._card)
self._card = edited
```

Apply the same normalization in `_save_current()` and ensure list titles refresh from normalized fields.

**Step 4: Run focused tests to verify they pass**

Run:

```bash
uv run pytest tests/test_ui/test_card_edit_widget.py tests/test_ui/test_result_page.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/ui/card_edit_widget.py src/ankismart/ui/result_page.py tests/test_ui/test_card_edit_widget.py tests/test_ui/test_result_page.py
git commit -m "feat(ui): normalize cards after manual edits"
```

## Task 8: Harden Push Validation And APKG Export

**Files:**
- Modify: `src/ankismart/anki_gateway/validator.py`
- Modify: `src/ankismart/anki_gateway/apkg_exporter.py`
- Modify: `src/ankismart/anki_gateway/gateway.py`
- Test: `tests/test_anki_gateway/test_validator.py`
- Test: `tests/test_anki_gateway/test_apkg_exporter.py`

**Step 1: Write failing gateway/export tests**

```python
def test_validate_card_draft_requires_normalized_back_for_basic_cards():
    draft = CardDraft(note_type="Basic", fields={"Front": "Q", "Back": ""}, deck_name="Default")
    with pytest.raises(AnkiGatewayError):
        validate_card_draft(draft, _FakeClient())
```

```python
def test_validate_card_draft_checks_ankismart_cloze_syntax():
    draft = CardDraft(note_type="AnkiSmart Cloze", fields={"Text": "plain text", "Extra": ""}, deck_name="Default")
    with pytest.raises(AnkiGatewayError):
        validate_card_draft(draft, _FakeClient(models=["AnkiSmart Cloze"], fields=["Text", "Extra"]))
```

```python
def test_apkg_export_blocks_cards_with_unrepairable_structure(tmp_path):
    exporter = ApkgExporter()
    cards = [CardDraft(note_type="Basic", deck_name="Deck", fields={"Front": "Q", "Back": ""})]
    with pytest.raises(AnkiGatewayError):
        exporter.export(cards, tmp_path / "bad.apkg")
```

**Step 2: Run focused tests to verify they fail**

Run:

```bash
uv run pytest tests/test_anki_gateway/test_validator.py tests/test_anki_gateway/test_apkg_exporter.py -q
```

Expected: FAIL because validator/exporter are still permissive.

**Step 3: Normalize before validating and exporting**

```python
normalized = normalize_card_draft(draft)
validation = validate_card_for_output(normalized)
if validation.status == "blocking":
    raise AnkiGatewayError(...)
```

Use the same path inside `ApkgExporter.export()` before building `genanki.Note`, and make cloze validation apply to `Cloze`, `Cloze 2`, and `AnkiSmart Cloze`.

**Step 4: Run focused tests to verify they pass**

Run:

```bash
uv run pytest tests/test_anki_gateway/test_validator.py tests/test_anki_gateway/test_apkg_exporter.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/anki_gateway/validator.py src/ankismart/anki_gateway/apkg_exporter.py src/ankismart/anki_gateway/gateway.py tests/test_anki_gateway/test_validator.py tests/test_anki_gateway/test_apkg_exporter.py
git commit -m "fix(anki): validate normalized cards before push and export"
```

## Task 9: Add Full-Pipeline Regression Coverage

**Files:**
- Modify: `tests/test_card_gen/test_postprocess.py`
- Modify: `tests/test_theme.py`
- Modify: `tests/test_ui/test_card_preview_page.py`
- Modify: `tests/test_ui/test_card_edit_widget.py`
- Modify: `tests/test_anki_gateway/test_validator.py`
- Modify: `tests/test_anki_gateway/test_apkg_exporter.py`

**Step 1: Add end-to-end regression tests for generated malformed cards**

```python
def test_malformed_generated_choice_card_is_normalized_consistently_across_preview_and_export():
    ...
```

```python
def test_user_edit_then_export_uses_same_normalized_card_structure():
    ...
```

```python
def test_object_wrapped_or_html_heavy_card_content_is_either_normalized_or_blocked_explicitly():
    ...
```

**Step 2: Run the focused regression suites**

Run:

```bash
uv run pytest tests/test_card_gen/test_postprocess.py tests/test_theme.py tests/test_ui/test_card_preview_page.py tests/test_ui/test_card_edit_widget.py tests/test_anki_gateway/test_validator.py tests/test_anki_gateway/test_apkg_exporter.py -q
```

Expected: FAIL at first until all integration points are consistent.

**Step 3: Fix any remaining parity gaps between preview, validator, and exporter**

```python
# Keep one normalization path and one validation path.
# Remove or delegate any remaining duplicated parser branch.
```

**Step 4: Re-run the focused regression suites**

Run:

```bash
uv run pytest tests/test_card_gen/test_postprocess.py tests/test_theme.py tests/test_ui/test_card_preview_page.py tests/test_ui/test_card_edit_widget.py tests/test_anki_gateway/test_validator.py tests/test_anki_gateway/test_apkg_exporter.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/test_card_gen/test_postprocess.py tests/test_theme.py tests/test_ui/test_card_preview_page.py tests/test_ui/test_card_edit_widget.py tests/test_anki_gateway/test_validator.py tests/test_anki_gateway/test_apkg_exporter.py
git commit -m "test: add full card auto-format regression coverage"
```

## Task 10: Run Final Verification And Housekeeping

**Files:**
- Modify: `src/ankismart/card_gen/__init__.py`
- Modify: any touched files from Tasks 1-9 as needed
- Test: `tests/test_card_gen/test_card_kind.py`
- Test: `tests/test_card_gen/test_card_format_parsers.py`
- Test: `tests/test_card_gen/test_card_normalizer.py`
- Test: `tests/test_card_gen/test_card_structure_validator.py`
- Test: `tests/test_card_gen/test_postprocess.py`
- Test: `tests/test_card_gen/test_generator.py`
- Test: `tests/test_theme.py`
- Test: `tests/test_ui/test_card_preview_page.py`
- Test: `tests/test_ui/test_card_edit_widget.py`
- Test: `tests/test_ui/test_result_page.py`
- Test: `tests/test_anki_gateway/test_validator.py`
- Test: `tests/test_anki_gateway/test_apkg_exporter.py`

**Step 1: Export the new module API cleanly if needed**

```python
from .card_pipeline import normalize_card_draft, validate_card_for_output
```

**Step 2: Run Ruff on touched source and test paths**

Run:

```bash
uv run ruff check src/ankismart/card_gen src/ankismart/ui/card_preview_page.py src/ankismart/ui/card_edit_widget.py src/ankismart/ui/result_page.py src/ankismart/anki_gateway tests/test_card_gen tests/test_ui tests/test_anki_gateway tests/test_theme.py
```

Expected: PASS.

**Step 3: Run the full focused test matrix**

Run:

```bash
uv run pytest tests/test_card_gen tests/test_ui/test_card_preview_page.py tests/test_ui/test_card_edit_widget.py tests/test_ui/test_result_page.py tests/test_anki_gateway tests/test_theme.py -q --maxfail=1
```

Expected: PASS.

**Step 4: Run a broader regression pass for confidence**

Run:

```bash
uv run pytest tests --ignore=tests/e2e -q --maxfail=1
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ankismart/card_gen src/ankismart/ui/card_preview_page.py src/ankismart/ui/card_edit_widget.py src/ankismart/ui/result_page.py src/ankismart/anki_gateway tests/test_card_gen tests/test_ui tests/test_anki_gateway tests/test_theme.py
git commit -m "feat(card-gen): unify card auto-format across preview push and export"
```
