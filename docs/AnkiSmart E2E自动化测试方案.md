# AnkiSmart E2E自动化测试方案（精简版）

## 1. 文档信息

- 版本：2.0（精简可执行版）

- 日期：2026-02-14

- 适用：AnkiSmart v1.0-rc 发布门禁

## 2. 目标与边界

### 2.1 目标

- 验证核心用户链路：导入文件 -> 转换 -> 生成卡片 -> 推送/导出。

- 作为发布门禁，提供可量化通过标准。

- 在保证稳定性的前提下，控制执行时长。

### 2.2 不在本方案内

- 单元测试、模块级集成测试（由现有体系负责）。

- 安全专项、压力专项（独立测试计划）。

## 3. 测试分层（必须区分）

### 3.1 Gate E2E（发布门禁）

- 特点：尽量真实依赖，最小 mock。

- 目的：验证真实可发布性。

- 触发：PR 合并前、RC 打包前。

### 3.2 Fast E2E（快速回归）

- 特点：允许 mock LLM/AnkiConnect/OCR。

- 目的：快速反馈回归问题。

- 触发：每次提交或每日定时。

## 4. 最小技术栈

- `pytest`：测试框架

- `pytest-qt`：Qt UI 自动化

- `pytest-asyncio`：异步流程

- `pytest-xdist`：并行提速（仅用于互不干扰用例）

- GitHub Actions + Windows Runner：CI 执行环境

说明：`rerun` 仅用于收集 flaky 统计，不作为“通过即绿色”的依据。

## 5. 统一目录结构

```text
tests/e2e/
  conftest.py
  page_objects/
    base_page.py
    import_page.py
    preview_page.py
    result_page.py
    settings_page.py
  scenarios/
    test_main_workflow.py
    test_ocr.py
    test_supplier.py
    test_error_handling.py
  fixtures/
    files/
      docx/simple.docx
      pptx/presentation.pptx
      pdf/text_based.pdf
      pdf/image_based.pdf
      text/sample.md
    data/
      e2e_main_docx_001_expected.json
```

## 6. 核心场景（只保留最关键）

### 6.1 P0（必须通过）

1. `E2E-MAIN-DOCX-001`：DOCX 完整主流程（导入->转换->生成->推送）。
2. `E2E-MAIN-MD-002`：Markdown 完整主流程。
3. `E2E-OCR-PDF-003`：图片型 PDF + OCR 完整主流程。
4. `E2E-ERROR-ANKI-004`：AnkiConnect 不可用时 APKG 导出回退。

### 6.2 P1（建议通过）

1. `E2E-SUPPLIER-SWITCH-005`：供应商切换与配置持久化。
2. `E2E-ERROR-NET-006`：网络超时/429 场景重试与恢复。
3. `E2E-ERROR-FILE-007`：无效格式文件错误提示与状态恢复。

## 7. 发布门禁（量化）

- P0 通过率：`100%`

- P1 通过率：`>= 95%`

- Flaky 比例（近7天）：`< 2%`

- 单条 P0 最大耗时：`<= 180s`

- 全量 Gate E2E 总耗时：`<= 20min`

- 失败必须产出：日志 + 截图 + 失败步骤

未达标处理：

- 阻断发布；

- 允许一次重跑用于诊断，但重跑通过不自动解除阻断；

- 需提交缺陷单并标注责任模块。

## 8. 执行策略

- 本地开发：优先跑 Fast E2E 的改动相关用例。

- CI（PR）：运行 Fast E2E 全量 + Gate E2E 的 P0。

- RC 发布：运行 Gate E2E 全量（P0+P1）。

- 执行顺序：先串行 P0，再并行 P1。

## 9. 实施计划（两周）

- 第1-2天：框架与基础夹具（`conftest.py`、启动/清理、日志采集）。

- 第3-5天：P0 场景开发与稳定性调优。

- 第6-8天：P1 场景开发与失败归因规则。

- 第9-10天：CI 接入、门禁阈值落地、文档收口。

## 10. 完成定义（DoD）

- P0/P1 场景全部可在 CI 稳定执行。

- 门禁阈值已在流水线中强制生效。

- 每个失败用例可定位到步骤与模块。

- 有一份最近7天的 flaky 统计报表。

## 11. 自动化测试实现（落地模板）

### 11.1 本地执行命令

```bash
pip install pytest pytest-qt pytest-asyncio pytest-xdist pytest-html

# 仅执行 P0（发布前必跑）
pytest tests/e2e/scenarios -m "p0" -q --maxfail=1

# 执行全部 E2E
pytest tests/e2e/scenarios -q
```

### 11.2 最小代码骨架

```python
# tests/e2e/conftest.py
import pytest

@pytest.fixture
def app_window(qtbot):
    # 按实际入口替换
    from ankismart.main import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    yield win
    win.close()
```

```python
# tests/e2e/scenarios/test_main_workflow.py
import pytest

@pytest.mark.p0
def test_e2e_main_docx_001(app_window, qtbot):
    app_window.filePathEdit.setText("tests/e2e/fixtures/files/docx/simple.docx")
    app_window.convertButton.click()

    qtbot.waitUntil(
        lambda: app_window.markdownPreview.toPlainText().strip() != "",
        timeout=180000
    )
    app_window.generateButton.click()

    qtbot.waitUntil(lambda: app_window.generatedCardCount > 0, timeout=180000)
    assert app_window.generatedCardCount > 
```

### 11.3 标记与分组约定

- `@pytest.mark.p0`：发布门禁用例，必须稳定。

- `@pytest.mark.p1`：核心回归用例，建议通过。

- `@pytest.mark.fast`：可在提交时快速执行。

- `@pytest.mark.gate`：仅发布门禁流水线执行。
