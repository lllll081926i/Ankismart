# MarkItDown Backend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 `Ankismart` 增加一个可在设置页切换的 `MarkItDown` 非 OCR 文档 Markdown 转换后端。

**Architecture:** 保持 `DocumentConverter` 作为唯一转换入口；在配置层新增 `doc_convert_backend`，在转换层增加一个薄 `markitdown` 适配器，仅对 `docx/pptx` 生效；`pdf/image` 继续走既有 OCR，`markdown/text` 继续走既有轻量转换器。

**Tech Stack:** Python 3.11, PyQt6, pytest, uv, MarkItDown, Ruff

---

### Task 1: 配置模型增加后端字段

**Files:**
- Modify: `src/ankismart/core/config.py`
- Test: `tests/test_core/test_config.py`

**Step 1: Write the failing test**

在 `tests/test_core/test_config.py` 新增：

- 默认配置下 `doc_convert_backend == "native"`
- 配置文件写入非法值后，`load_config()` 回退到 `"native"`

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_core/test_config.py -q --maxfail=1`

Expected: FAIL，因为 `AppConfig` 还没有该字段，也没有回退逻辑。

**Step 3: Write minimal implementation**

在 `src/ankismart/core/config.py`：

- 为 `AppConfig` 新增 `doc_convert_backend: str = "native"`
- 在 `load_config()` 的规范化逻辑中限定允许值 `{"native", "markitdown"}`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_core/test_config.py -q --maxfail=1`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_core/test_config.py src/ankismart/core/config.py
git commit -m "feat: add doc markdown backend config"
```

### Task 2: 转换路由先写失败测试

**Files:**
- Modify: `tests/test_converter/test_converter_pipeline.py`
- Modify: `src/ankismart/converter/converter.py`

**Step 1: Write the failing test**

新增测试覆盖：

- `docx + native` 走原生转换器
- `docx + markitdown` 走新后端
- `pdf` 即使设置为 `markitdown` 也继续走 OCR 路径

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_converter/test_converter_pipeline.py -q --maxfail=1`

Expected: FAIL，因为 `DocumentConverter` 尚未接受并使用 `doc_convert_backend`。

**Step 3: Write minimal implementation**

在 `src/ankismart/converter/converter.py`：

- 新增 `doc_convert_backend` 初始化参数
- 为 `docx/pptx` 增加后端路由决策
- 保持 `pdf/image` 的 OCR 路由不变

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_converter/test_converter_pipeline.py -q --maxfail=1`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_converter/test_converter_pipeline.py src/ankismart/converter/converter.py
git commit -m "feat: route non-ocr document conversion backend"
```

### Task 3: 增加 MarkItDown 适配器

**Files:**
- Create: `src/ankismart/converter/markitdown_converter.py`
- Modify: `tests/test_converter/test_converter_pipeline.py`

**Step 1: Write the failing test**

新增测试覆盖：

- 适配器将 `MarkItDown().convert(...)` 的结果映射为 `MarkdownResult`
- 缺少 `markitdown` 依赖时抛出明确错误

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_converter/test_converter_pipeline.py -q --maxfail=1`

Expected: FAIL，因为适配器文件还不存在。

**Step 3: Write minimal implementation**

在 `src/ankismart/converter/markitdown_converter.py`：

- 延迟导入 `markitdown`
- 调用公开 API
- 把返回的文本写入 `MarkdownResult(content=..., source_format=...)`
- 将依赖缺失与转换失败统一包装

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_converter/test_converter_pipeline.py -q --maxfail=1`

Expected: PASS

**Step 5: Commit**

```bash
git add src/ankismart/converter/markitdown_converter.py tests/test_converter/test_converter_pipeline.py
git commit -m "feat: add markitdown converter adapter"
```

### Task 4: 设置页增加后端切换控件

**Files:**
- Modify: `src/ankismart/ui/settings_page.py`
- Modify: `tests/test_ui/test_settings_page_config.py`

**Step 1: Write the failing test**

新增测试覆盖：

- 配置加载时回显 `doc_convert_backend`
- 保存配置时正确持久化 `doc_convert_backend`

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_settings_page_config.py -q --maxfail=1`

Expected: FAIL，因为设置页还没有该控件。

**Step 3: Write minimal implementation**

在 `src/ankismart/ui/settings_page.py`：

- 新增后端选项定义
- 新增设置卡与下拉框
- 加入自动保存连接
- `_load_config()` 中回显
- `_save_config_silent()` 中持久化

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_settings_page_config.py -q --maxfail=1`

Expected: PASS

**Step 5: Commit**

```bash
git add src/ankismart/ui/settings_page.py tests/test_ui/test_settings_page_config.py
git commit -m "feat(ui): add markdown backend setting"
```

### Task 5: 工作线程把配置传递给转换器

**Files:**
- Modify: `src/ankismart/ui/workers.py`
- Modify: `tests/test_ui/test_workers.py`

**Step 1: Write the failing test**

新增测试覆盖：

- `_build_converter()` 会把 `doc_convert_backend` 传给 `DocumentConverter`

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_workers.py -q --maxfail=1`

Expected: FAIL，因为当前尚未传递该配置。

**Step 3: Write minimal implementation**

在 `src/ankismart/ui/workers.py` 的 `_build_converter()` 中：

- 从配置读取 `doc_convert_backend`
- 创建 `DocumentConverter(doc_convert_backend=...)`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_workers.py -q --maxfail=1`

Expected: PASS

**Step 5: Commit**

```bash
git add src/ankismart/ui/workers.py tests/test_ui/test_workers.py
git commit -m "feat: pass markdown backend setting to converter"
```

### Task 6: 接入依赖并做回归验证

**Files:**
- Modify: `pyproject.toml`
- Test: `tests/test_core/test_config.py`
- Test: `tests/test_converter/test_converter_pipeline.py`
- Test: `tests/test_ui/test_settings_page_config.py`
- Test: `tests/test_ui/test_workers.py`

**Step 1: Write the failing test**

这里不新增单独行为测试，直接以前面测试为门禁。

**Step 2: Run test to verify current state**

Run: `uv run pytest tests/test_core/test_config.py tests/test_converter/test_converter_pipeline.py tests/test_ui/test_settings_page_config.py tests/test_ui/test_workers.py -q --maxfail=1`

Expected: 全部 PASS。

**Step 3: Write minimal implementation**

在 `pyproject.toml` 中增加 `markitdown` 依赖。

**Step 4: Run test to verify it passes**

Run:

- `uv run pytest tests/test_core/test_config.py tests/test_converter/test_converter_pipeline.py tests/test_ui/test_settings_page_config.py tests/test_ui/test_workers.py -q --maxfail=1`
- `uv run ruff check src tests`

Expected: PASS

**Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: add markitdown dependency"
```

### Task 7: 终检与代码审查

**Files:**
- Review: `src/ankismart/core/config.py`
- Review: `src/ankismart/converter/converter.py`
- Review: `src/ankismart/converter/markitdown_converter.py`
- Review: `src/ankismart/ui/settings_page.py`
- Review: `src/ankismart/ui/workers.py`

**Step 1: Run focused regression**

Run:

- `uv run pytest tests/test_core/test_config.py -q --maxfail=1`
- `uv run pytest tests/test_converter/test_converter_pipeline.py -q --maxfail=1`
- `uv run pytest tests/test_ui/test_settings_page_config.py -q --maxfail=1`
- `uv run pytest tests/test_ui/test_workers.py -q --maxfail=1`

**Step 2: Run lint**

Run: `uv run ruff check src tests`

**Step 3: Review for risks**

检查点：

- `pdf/image` 是否被错误路由到 `MarkItDown`
- 非法配置是否回退到 `native`
- `MarkItDown` 依赖缺失报错是否清晰
- 设置页文案与行为是否一致
- 适配层是否只依赖公开 API

**Step 4: Summarize findings**

输出按严重级别排序的审查结果；若无问题，明确说明无新增发现，并注明残余风险。

**Step 5: Commit**

```bash
git add .
git commit -m "test: verify markitdown backend integration"
```
