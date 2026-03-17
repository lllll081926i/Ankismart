# Ankismart 贡献指南

欢迎为 Ankismart 项目做出贡献！本文档将帮助你快速上手开发。

## 开发环境搭建

### 系统要求

- **Python 版本**：3.11 或更高
- **操作系统**：Windows、macOS 或 Linux
- **推荐 IDE**：VS Code、PyCharm

### 安装步骤

1. **克隆仓库**

```bash
git clone https://github.com/yourusername/ankismart.git
cd ankismart
```

2. **创建虚拟环境**

```bash
# 使用 venv
python -m venv .venv

# 激活虚拟环境
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

3. **安装依赖**

```bash
# 推荐：使用 uv 安装项目依赖和开发工具
uv sync --group dev
```

这将安装：
- 项目核心依赖（PySide6、OpenAI、PaddleOCR 等）
- 开发工具（pytest、pytest-cov、ruff）

4. **配置 Anki**

- 安装 [Anki 桌面端](https://apps.ankiweb.net/)
- 安装 [AnkiConnect 插件](https://ankiweb.net/shared/info/2055492159)
- 启动 Anki（保持运行状态以便测试）

5. **配置 LLM API**

创建配置文件 `.local/ankismart/config.yaml`：

```yaml
llm_providers:
  - id: "test123"
    name: "OpenAI"
    api_key: "your-api-key-here"
    base_url: "https://api.openai.com/v1"
    model: "gpt-4o"
    rpm_limit: 60

active_provider_id: "test123"
```

6. **验证安装**

```bash
# 运行测试
uv run pytest -q

# 启动应用
uv run ankismart
```

### 启动性能测量

如需评估启动优化，请同时记录“冷启动导入成本”和“运行期阶段耗时”。

导入成本：

```bash
uv run python -X importtime -c "import ankismart.ui.app" 2> importtime.log
```

运行期阶段耗时：

```bash
uv run ankismart
```

应用启动后查看日志目录中的 `app.startup.timing` 记录，对比以下字段：

- `qapp_ms`
- `config_ms`
- `theme_ms`
- `window_ms`
- `show_ms`
- `total_ms`

提交启动性能相关改动时，建议在 PR 描述里附上改动前后的两组数据。

---

## 代码规范

### 代码风格

项目使用 [Ruff](https://github.com/astral-sh/ruff) 进行代码检查和格式化。

#### Ruff 配置

配置位于 `pyproject.toml`：

```toml
[tool.ruff]
target-version = "py311"
line-length = 100
src = ["src"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["N802", "N806"]
```

#### 运行代码检查

```bash
# 统一质量门禁（与 CI 一致）
uv run ruff check src tests

# 自动修复可修复问题
uv run ruff check src tests --fix

# 格式化代码
uv run ruff format src tests
```

当前阶段规则：
- `E501` 已切换为全量门禁，`uv run ruff check src tests` 必须通过。
- UI 风险模块覆盖率门禁当前为 `50%`。
- 打包校验门禁已启用，CI 执行 `uv run --with pyinstaller==6.19.0 python packaging/build.py --clean`（含安装版与便携版）。

### 命名规范

- **模块名**：小写字母，下划线分隔（`card_generator.py`）
- **类名**：大驼峰命名（`CardGenerator`）
- **函数名**：小写字母，下划线分隔（`generate_cards`）
- **常量**：大写字母，下划线分隔（`MAX_RETRIES`）
- **私有成员**：单下划线前缀（`_internal_method`）

### 类型注解

所有公共 API 必须包含类型注解：

```python
from __future__ import annotations

def convert(file_path: Path, *, progress_callback: Callable[[str], None] | None = None) -> MarkdownResult:
    """Convert document to Markdown.

    Args:
        file_path: Path to the document file
        progress_callback: Optional callback for progress updates

    Returns:
        MarkdownResult containing the converted content

    Raises:
        ConvertError: If conversion fails
    """
    ...
```

### 文档字符串

使用 Google 风格的文档字符串：

```python
def push(self, cards: list[CardDraft], update_mode: str = "create_only") -> PushResult:
    """Push cards to Anki.

    Args:
        cards: List of card drafts to push
        update_mode: Update mode - "create_only", "update_only", or "create_or_update"

    Returns:
        PushResult containing success/failure statistics

    Raises:
        AnkiGatewayError: If push operation fails

    Example:
        >>> result = gateway.push(cards, update_mode="create_or_update")
        >>> print(f"Succeeded: {result.succeeded}, Failed: {result.failed}")
    """
    ...
```

### 导入顺序

按以下顺序组织导入：

1. 标准库
2. 第三方库
3. 本地模块

使用 Ruff 自动排序：

```python
from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml
from pydantic import BaseModel

from ankismart.core.errors import ConfigError
from ankismart.core.logging import get_logger
```

---

## Git 提交规范

### Conventional Commits

项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

#### 提交消息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### 类型（Type）

- `feat` - 新功能
- `fix` - Bug 修复
- `docs` - 文档更新
- `style` - 代码格式调整（不影响功能）
- `refactor` - 代码重构
- `perf` - 性能优化
- `test` - 测试相关
- `chore` - 构建/工具链相关

#### 作用域（Scope）

可选，表示影响的模块：

- `converter` - 文档转换模块
- `card_gen` - 卡片生成模块
- `anki_gateway` - Anki 网关模块
- `ui` - 用户界面
- `core` - 核心模块
- `config` - 配置相关
- `ocr` - OCR 相关

#### 示例

```bash
# 新功能
git commit -m "feat(card_gen): 添加多选题卡片策略"

# Bug 修复
git commit -m "fix(converter): 修复 PDF 转换时的内存泄漏"

# 文档更新
git commit -m "docs: 更新 API 文档和使用示例"

# 重构
git commit -m "refactor(ui): 重构设置页面组件结构"

# 性能优化
git commit -m "perf(ocr): 优化 OCR 批量处理性能"
```

#### 多行提交消息

```bash
git commit -m "feat(anki_gateway): 支持批量更新模式

- 添加 update_mode 参数
- 支持 create_only、update_only、create_or_update 三种模式
- 更新相关测试用例

Closes #123"
```

---

## PR 流程

### 1. Fork 和分支

```bash
# Fork 仓库到你的账号

# 克隆你的 Fork
git clone https://github.com/yourusername/ankismart.git
cd ankismart

# 添加上游仓库
git remote add upstream https://github.com/originalowner/ankismart.git

# 创建功能分支
git checkout -b feat/my-new-feature
```

### 2. 开发和提交

```bash
# 进行开发
# ...

# 运行代码检查（与 CI 对齐）
uv run ruff check src tests
uv run ruff format src tests

# 运行测试
uv run pytest -q

# 提交更改
git add .
git commit -m "feat: 添加新功能"
```

### 3. 同步上游

```bash
# 获取上游更新
git fetch upstream

# 合并到你的分支
git rebase upstream/master
```

### 4. 推送和创建 PR

```bash
# 推送到你的 Fork
git push origin feat/my-new-feature

# 在 GitHub 上创建 Pull Request
```

### 5. PR 检查清单

提交 PR 前请确保：

- [ ] 代码通过 Ruff 检查（`uv run ruff check src tests`）
- [ ] 代码已格式化（`uv run ruff format src tests`）
- [ ] 所有测试通过（`uv run pytest -q`）
- [ ] 添加了必要的测试用例
- [ ] 更新了相关文档
- [ ] 提交消息符合 Conventional Commits 规范
- [ ] PR 描述清晰，说明了改动的目的和影响

### 6. PR 模板

创建 PR 时请包含以下信息：

```markdown
## 改动说明

简要描述这个 PR 的目的和改动内容。

## 改动类型

- [ ] 新功能
- [ ] Bug 修复
- [ ] 文档更新
- [ ] 代码重构
- [ ] 性能优化
- [ ] 其他

## 测试

描述如何测试这些改动。

## 相关 Issue

Closes #123

## 截图（如果适用）

添加截图展示 UI 改动。

## 检查清单

- [ ] 代码通过 Ruff 检查
- [ ] 所有测试通过
- [ ] 添加了测试用例
- [ ] 更新了文档
```

---

## 测试要求

### 测试框架

项目使用 pytest 进行测试。

### 运行测试

```bash
# 运行所有测试
uv run pytest -q

# 运行特定模块的测试
uv run pytest tests/test_converter.py -q

# 运行特定测试函数
uv run pytest tests/test_converter.py::test_docx_conversion -q

# 显示详细输出
uv run pytest -v

# 显示打印输出
uv run pytest -s
```

### 测试覆盖率

```bash
# 生成覆盖率报告（本地全量趋势）
uv run pytest -q --cov=src/ankismart --cov-report=term

# UI 风险模块门禁（与 CI 一致）
uv run pytest tests --ignore=tests/e2e -q \
  --cov=ankismart.ui.import_page \
  --cov=ankismart.ui.result_page \
  --cov=ankismart.ui.workers \
  --cov-report=term-missing \
  --cov-fail-under=50

# 查看报告
# 打开 htmlcov/index.html
```

### 编写测试

#### 单元测试示例

```python
# tests/test_converter.py
from pathlib import Path
import pytest
from ankismart.converter.converter import DocumentConverter
from ankismart.core.errors import ConvertError

def test_convert_markdown():
    """Test Markdown file conversion."""
    converter = DocumentConverter()
    result = converter.convert(Path("tests/fixtures/sample.md"))

    assert result.content
    assert result.source_format == "markdown"
    assert result.source_path.endswith("sample.md")

def test_convert_nonexistent_file():
    """Test conversion of non-existent file raises error."""
    converter = DocumentConverter()

    with pytest.raises(ConvertError) as exc_info:
        converter.convert(Path("nonexistent.txt"))

    assert exc_info.value.code == "E_FILE_NOT_FOUND"
```

#### 集成测试示例

```python
# tests/test_integration.py
from pathlib import Path
from ankismart.converter.converter import DocumentConverter
from ankismart.card_gen.generator import CardGenerator
from ankismart.card_gen.llm_client import LLMClient
from ankismart.core.models import GenerateRequest

def test_end_to_end_flow():
    """Test complete flow from document to cards."""
    # Convert document
    converter = DocumentConverter()
    result = converter.convert(Path("tests/fixtures/sample.md"))

    # Generate cards
    llm_client = LLMClient(api_key="test-key", model="gpt-4o")
    generator = CardGenerator(llm_client)

    request = GenerateRequest(
        markdown=result.content,
        strategy="basic",
        deck_name="Test",
    )
    cards = generator.generate(request)

    assert len(cards) > 0
    assert cards[0].deck_name == "Test"
```

#### 测试夹具（Fixtures）

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def sample_markdown():
    """Provide sample Markdown content."""
    return "# Test\n\nThis is a test document."

@pytest.fixture
def temp_file(tmp_path):
    """Create a temporary file for testing."""
    file_path = tmp_path / "test.txt"
    file_path.write_text("Test content")
    return file_path
```

### 测试覆盖目标

- **核心模块**：≥ 80% 覆盖率
- **转换器**：≥ 70% 覆盖率
- **UI 模块**：≥ 50% 覆盖率（UI 测试较复杂）

---

## 开发工作流

### 日常开发

1. **创建功能分支**

```bash
git checkout -b feat/my-feature
```

2. **开发和测试**

```bash
# 编写代码
# ...

# 运行测试
uv run pytest -q

# 检查代码
uv run ruff check src tests
```

3. **提交更改**

```bash
git add .
git commit -m "feat: 添加新功能"
```

4. **推送和创建 PR**

```bash
git push origin feat/my-feature
# 在 GitHub 上创建 PR
```

### 调试技巧

#### 启用调试日志

```python
from ankismart.core.config import load_config, save_config

config = load_config()
config.log_level = "DEBUG"
save_config(config)
```

#### 使用 Python 调试器

```python
# 在代码中添加断点
import pdb; pdb.set_trace()

# 或使用 breakpoint()（Python 3.7+）
breakpoint()
```

#### VS Code 调试配置

创建 `.vscode/launch.json`：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Ankismart",
      "type": "python",
      "request": "launch",
      "module": "ankismart.ui.app",
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Python: Pytest",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["-v"],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

---

## 常见问题

### Q: 如何添加新的文档格式支持？

A: 参考 [API 文档 - 扩展开发](api.md#扩展开发) 部分。

### Q: 如何添加新的卡片生成策略？

A: 在 `ankismart/card_gen/prompts.py` 中定义提示词，然后在 `generator.py` 中注册。

### Q: 测试时如何模拟 LLM 响应？

A: 使用 pytest 的 monkeypatch 或 mock：

```python
def test_generate_with_mock(monkeypatch):
    def mock_chat(system_prompt, user_prompt):
        return '[{"front": "Q", "back": "A"}]'

    monkeypatch.setattr(llm_client, "chat", mock_chat)
    # 继续测试
```

### Q: 如何测试 UI 组件？

A: 使用 pytest-qt 进行 Qt 组件测试：

```bash
pip install pytest-qt
```

```python
def test_main_window(qtbot):
    from ankismart.ui.main_window import MainWindow
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.isVisible()
```

### Q: 代码检查失败怎么办？

A: 先运行 `uv run ruff check src tests --fix` 自动修复，再手动处理剩余问题。

### Q: 如何贡献文档？

A: 文档位于 `docs/` 目录，使用 Markdown 格式。修改后提交 PR 即可。

---

## 项目结构

```
ankismart/
├── src/
│   └── ankismart/
│       ├── core/           # 核心模块
│       ├── converter/      # 文档转换
│       ├── card_gen/       # 卡片生成
│       ├── anki_gateway/   # Anki 网关
│       └── ui/             # 用户界面
├── tests/                  # 测试文件
├── docs/                   # 文档
├── pyproject.toml          # 项目配置
└── README.md               # 项目说明
```

---

## 获取帮助

- **GitHub Issues**：报告 Bug 或提出功能请求
- **GitHub Discussions**：讨论和提问
- **文档**：查看 `docs/` 目录中的文档

---

## 行为准则

- 尊重所有贡献者
- 保持友好和专业的沟通
- 接受建设性的反馈
- 关注项目的最佳利益

---

## 许可证

通过贡献代码，你同意你的贡献将在与项目相同的许可证下发布。

---

感谢你的贡献！🎉
