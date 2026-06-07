# Card Auto Format Design

**Date:** 2026-03-21

**Status:** Approved for implementation

## Goal

为 Ankismart 建立一套统一、可复用的卡片标准化与结构校验机制，让 AI 生成结果、用户编辑后的卡片、预览、推送到 Anki、导出 `.apkg` 全部遵循同一份标准格式与同一套错误分级规则。

## Current Problems

- 当前生成链路只做了 JSON 抽取和少量字段别名处理，缺少真正的结构标准化。
- `single_choice` / `multiple_choice` 的格式约束主要依赖 prompt，自身代码没有把结果修成统一格式。
- 预览层已经包含较多容错解析逻辑，但这些逻辑只影响显示，不会回写到底层卡片数据。
- `CardEditDialog` 保存后直接写回字段，不做格式重整，用户改坏结构后仍可能继续进入后续流程。
- `validator` 只校验首字段，`apkg` 导出路径甚至绕过了统一校验，导致“预览正常、导出异常”的风险。
- `AnkiSmart Cloze` 与 `Cloze` 的校验规则不一致，存在语法漏检。

## Design Principles

- **Single source of truth:** 所有标准化和结构校验逻辑都集中在独立模块，不再散落在 UI、导出器、validator 中。
- **Lossless first:** 优先重排、清洗、映射，不随意改写知识内容。
- **Deterministic only:** 只有在可稳定识别时才自动修复；无法确定时给出 warning 或 blocking，而不是猜测。
- **Same input, same output:** 同一张卡片无论从生成、编辑、推送还是导出入口进入，最终得到的规范化结果一致。
- **Structured diagnostics:** 修复、告警、阻断都要带稳定的 flags，便于 UI 呈现与测试断言。

## Proposed Modules

### `src/ankismart/card_gen/card_kind.py`

负责识别卡片类型，输出统一种类键：

- `basic`
- `concept`
- `key_terms`
- `single_choice`
- `multiple_choice`
- `cloze`
- `image_qa`
- `generic`

判定优先级：

1. `metadata.strategy_id`
2. `tags`
3. `note_type`
4. 字段内容启发式

这会替代 UI 中当前依赖 tags / note type 的分散判定逻辑。

### `src/ankismart/card_gen/card_format_parsers.py`

负责把非标准文本解析为结构化中间结果。重点能力：

- 统一 HTML / plain text / markdown 列表的清洗
- 解析 choice front：题干、选项键、选项文本
- 解析 choice back：答案键、解析正文
- 解析 basic-like back：答案、解析
- 处理中英文 `答案/Answer`、`解析/Explanation`
- 去掉前导编号、全角/半角差异、多余空行

该模块吸收目前 `src/ankismart/ui/card_preview_page.py` 中的字符串容错逻辑，但不直接依赖 UI。

### `src/ankismart/card_gen/card_normalizer.py`

负责把结构化中间结果重写成标准字段格式，并返回修复 flags。主要职责：

- 收口字段别名：`Question/Answer/front/back/text/extra`
- Basic-like 统一成 `Front + Back`
- Cloze 统一成 `Text + Extra`
- Choice 统一为多行选项布局和标准答案区块
- 生成 `quality_flags` / `normalization_flags`

### `src/ankismart/card_gen/card_structure_validator.py`

负责严格校验卡片结构是否达标。输出三个等级：

- `normalized`: 已修复并达标
- `warning`: 可显示但结构仍不完整，需要人工关注
- `blocking`: 无法安全推送/导出

### `src/ankismart/card_gen/card_pipeline.py`

对外提供统一入口，避免调用方自己拼步骤。建议暴露：

- `normalize_raw_card(...)`
- `normalize_card_draft(...)`
- `normalize_cards(...)`
- `validate_card_for_output(...)`

## Normalization Rules

### Basic / Concept / Key Terms / Image Q&A

- 收口为 `Front` / `Back`
- `Front` 清理 HTML 噪音、多余空白、前导编号
- `Back` 重写为：

```text
答案: <单行答案>
解析:
<逐行解析>
```

- 如果只有一句答案且没有解析，保留答案并打 `missing_explanation`
- 如果原文本可稳定拆句，则首句作为答案，剩余句子作为解析

### Single Choice

- `Front` 标准化为：

```text
<题干>
A. ...
B. ...
C. ...
D. ...
```

- 兼容单行选项、HTML `<br>`、markdown 列表、`A)` / `A：` / `1.` 等格式
- `Back` 标准化为：

```text
答案: B
解析:
A. ...
B. ...
C. ...
D. ...
```

- 若识别到多个答案键，只保留第一个并打 `multiple_answers_in_single_choice`
- 若选项数量不足 4 或超过 4，优先修复，修复不了则标记 `invalid_option_count`

### Multiple Choice

- `Front` 规则与单选一致，但允许 4-5 个选项
- `Back` 标准化为：

```text
答案: B, C
解析:
A. ...
B. ...
C. ...
D. ...
```

- 自动去重并按 A-E 排序答案键
- 最终答案键少于 2 个时，标记 `insufficient_correct_options`

### Cloze

- 统一 `Text` / `Extra` 字段别名
- 兼容 `Cloze`、`Cloze 2`、`AnkiSmart Cloze`
- 只做轻量清洗，不自动“发明” cloze token
- 缺少合法 `{{cN::...}}` 时直接进入 blocking

### Generic

- 只做保守清洗，不强行推断题型
- 若规范化后仍无法识别成受支持类型，则允许预览但阻止推送/导出

## Data Flow

### Generation

`parse_llm_output()` 解析出原始卡片后，`build_card_drafts()` 在构造 `CardDraft` 前先调用标准化模块，得到规范字段和 flags，再生成 `CardDraft`。

### Preview

`CardPreviewPage` 不再维护独立的修复逻辑；它只消费规范化结果，并读取结构化 flags 生成质量提示和筛选条件。

### Editing

`CardEditDialog.get_edited_card()` 与 `CardEditWidget._save_current()` 保存后立即重新标准化字段，让用户编辑后的卡片也回到标准格式。

### Push

`validate_card_draft()` 调整为：先标准化，再严格校验，再执行 deck/model/media 校验。

### Export

`ApkgExporter.export()` 在写出 `genanki.Note` 之前，对全部卡统一执行标准化和结构校验，彻底消除导出漏检。

## Error Levels And UI Behavior

### Normalized

- 已自动修复，无需阻断
- 记录 flag 供调试与质量分析

### Warning

- 可预览，可继续编辑
- UI 显示黄标或低质量提示
- 默认不应被静默视为“完全合格”

### Blocking

- 禁止 push/export
- 返回明确错误原因，例如：
  - `cloze_syntax_invalid`
  - `choice_missing_answer`
  - `choice_missing_options`
  - `unsupported_generic_structure`

## Testing Strategy

新增测试模块：

- `tests/test_card_gen/test_card_kind.py`
- `tests/test_card_gen/test_card_format_parsers.py`
- `tests/test_card_gen/test_card_normalizer.py`
- `tests/test_card_gen/test_card_structure_validator.py`

重点覆盖：

- 字段别名收口
- 中英文字段标记混用
- HTML / markdown / 单行 choice 格式
- 单选多答案、多选少答案、缺失解析
- `AnkiSmart Cloze` 与 `Cloze 2` 的统一校验
- 编辑后 -> 预览 -> 推送 / 导出的回归链路
- 预览与导出对同一卡片的呈现/结构一致性

## Non-Goals

- 不新增新的题型协议
- 不把“模糊文本”交给 LLM 二次修复
- 不修改 Anki 模板的视觉样式
- 不扩展新的 metadata 持久化格式，除非现有 `quality_flags` 明显不足

## Migration Notes

- 先引入新模块和测试，再逐步接管旧逻辑，避免一次性重写造成回归。
- 旧的 UI 解析 helper 可以先代理到新模块，验证稳定后再简化 UI 层实现。
- 推送与导出必须在最后一阶段切换到新管线，以便先完成上游标准化和测试覆盖。
