# AnkiSmart E2E 测试

本目录按 `docs/AnkiSmart E2E自动化测试方案.md` 落地，覆盖 P0/P1 的核心流程。

## 场景映射

- `E2E-MAIN-DOCX-001` / `E2E-MAIN-MD-002`: `scenarios/test_main_workflow.py`
- `E2E-OCR-PDF-003`: `scenarios/test_ocr.py`
- `E2E-ERROR-ANKI-004`: `scenarios/test_error_handling.py`
- `E2E-SUPPLIER-SWITCH-005`: `scenarios/test_supplier.py`
- `Gate-Real-P0`（更少 mock）: `gate/test_gate_workflow.py`

## 运行方式（uv）

```bash
# 仅运行 P0（发布门禁）
uv run pytest tests/e2e/scenarios -m "p0" -q

# 运行全部 E2E
uv run pytest tests/e2e/scenarios -q

# 运行 Gate-Real（更少 mock）
uv run pytest tests/e2e/gate -q
```

## 说明

- 用例采用“真实页面链路 + 外部依赖替身”的 Fast E2E 方式，避免依赖真实 LLM/Anki/OCR 环境。
- `docx` 与 `pdf` 输入在测试运行时动态创建，`fixtures/files/text/sample.md` 作为静态样例。
- Gate-Real 用例走真实 `BatchConvertWorker/BatchGenerateWorker/PushWorker`，仅替换 LLM 输出与 AnkiConnect 通信层。

## CI 分层

- `E2E Fast` workflow:
  - `tests/e2e/scenarios -m "fast"`
  - `tests/e2e/gate -m "p0 and gate_real"`（门禁冒烟）
- `E2E Gate` workflow:
  - `tests/e2e/scenarios -m "p0 and gate"`
  - `tests/e2e/gate -m "p0 and gate_real"`
  - `tests/e2e/scenarios -q`（全量 Fast 回归）
