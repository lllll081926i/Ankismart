# Ankismart API 文档

## 核心类说明

### 1. DocumentConverter

文档转换器，将各种格式的文档转换为 Markdown。

#### 初始化

```python
from ankismart.converter.converter import DocumentConverter

# 不使用 OCR 纠错
converter = DocumentConverter()

# 使用 OCR 纠错（需要 LLM）
def ocr_correction_fn(text: str) -> str:
    # 使用 LLM 纠正 OCR 错误
    return corrected_text

converter = DocumentConverter(ocr_correction_fn=ocr_correction_fn)
```

#### 方法

**convert(file_path: Path, *, progress_callback: Callable[[str], None] | None = None) -> MarkdownResult**

转换文档为 Markdown。

参数：
- `file_path` - 文档路径
- `progress_callback` - 进度回调函数（可选，用于 OCR 进度）

返回：
- `MarkdownResult` - 包含 Markdown 内容和元数据

异常：
- `ConvertError` - 转换失败时抛出

示例：

```python
from pathlib import Path
from ankismart.converter.converter import DocumentConverter

converter = DocumentConverter()

# 转换 Word 文档
result = converter.convert(Path("document.docx"))
print(result.content)  # Markdown 内容
print(result.source_format)  # "docx"

# 转换 PDF（带进度回调）
def on_progress(message: str):
    print(f"进度: {message}")

result = converter.convert(Path("document.pdf"), progress_callback=on_progress)
```

#### 支持的文件格式

| 格式 | 扩展名 | 转换器 |
|------|--------|--------|
| Markdown | `.md` | markdown_converter |
| 纯文本 | `.txt` | text_converter |
| Word | `.docx` | docx_converter |
| PowerPoint | `.pptx` | pptx_converter |
| PDF | `.pdf` | ocr_converter |
| 图片 | `.png`, `.jpg`, `.jpeg`, `.bmp`, `.tiff`, `.webp` | ocr_converter |

---

### 2. CardGenerator

卡片生成器，使用 LLM 从 Markdown 生成 Anki 闪卡。

#### 初始化

```python
from ankismart.card_gen.generator import CardGenerator
from ankismart.card_gen.llm_client import LLMClient

# 创建 LLM 客户端
llm_client = LLMClient(
    api_key="your-api-key",
    model="gpt-4o",
    base_url="https://api.openai.com/v1",  # 可选
    rpm_limit=60,  # 每分钟请求数限制
    temperature=0.3,
    max_tokens=0,  # 0 表示使用默认值
    proxy_url="",  # 代理 URL（可选）
)

# 创建卡片生成器
generator = CardGenerator(llm_client)
```

#### 从配置创建

```python
from ankismart.core.config import load_config
from ankismart.card_gen.llm_client import LLMClient
from ankismart.card_gen.generator import CardGenerator

# 从配置文件加载
config = load_config()
llm_client = LLMClient.from_config(config)
generator = CardGenerator(llm_client)
```

#### 方法

**generate(request: GenerateRequest) -> list[CardDraft]**

生成卡片草稿。

参数：
- `request` - 生成请求对象

返回：
- `list[CardDraft]` - 卡片草稿列表

异常：
- `CardGenError` - 生成失败时抛出

示例：

```python
from ankismart.core.models import GenerateRequest

# 创建生成请求
request = GenerateRequest(
    markdown="# Python 基础\n\nPython 是一种解释型语言...",
    strategy="basic",  # 策略：basic, cloze, concept, key_terms, etc.
    deck_name="Python 学习",
    tags=["python", "编程"],
    target_count=10,  # 目标卡片数量（0 表示不限制）
    enable_auto_split=False,  # 是否启用长文档自动分割
    split_threshold=70000,  # 分割阈值（字符数）
)

# 生成卡片
cards = generator.generate(request)

for card in cards:
    print(f"正面: {card.fields['Front']}")
    print(f"背面: {card.fields['Back']}")
    print(f"标签: {card.tags}")
    print("---")
```

**correct_ocr_text(text: str) -> str**

使用 LLM 纠正 OCR 识别错误。

参数：
- `text` - OCR 识别的文本

返回：
- `str` - 纠正后的文本

示例：

```python
ocr_text = "这是一段包含错误的OCR文本..."
corrected = generator.correct_ocr_text(ocr_text)
```

#### 支持的策略

| 策略 | 说明 | 笔记类型 |
|------|------|----------|
| `basic` | 基础问答卡片 | Basic |
| `cloze` | 填空题卡片 | Cloze |
| `concept` | 概念解释卡片 | Basic |
| `key_terms` | 关键术语卡片 | Basic |
| `single_choice` | 单选题卡片 | Basic |
| `multiple_choice` | 多选题卡片 | Basic |
| `image_qa` | 图片问答卡片 | Basic |
| `image_occlusion` | 图片遮挡（别名） | Basic |

---

### 3. LLMClient

LLM 客户端，支持 OpenAI SDK 兼容的 API。

#### 初始化

```python
from ankismart.card_gen.llm_client import LLMClient

client = LLMClient(
    api_key="your-api-key",
    model="gpt-4o",
    base_url="https://api.openai.com/v1",  # 可选，默认 OpenAI
    rpm_limit=60,  # 每分钟请求数限制，0 表示不限制
    temperature=0.3,  # 温度参数
    max_tokens=0,  # 最大 token 数，0 表示使用默认值
    proxy_url="http://proxy.example.com:8080",  # 代理 URL（可选）
)
```

#### 方法

**chat(system_prompt: str, user_prompt: str) -> str**

发送聊天请求。

参数：
- `system_prompt` - 系统提示词
- `user_prompt` - 用户提示词

返回：
- `str` - LLM 响应内容

异常：
- `CardGenError` - 调用失败时抛出

示例：

```python
system_prompt = "你是一个 Anki 闪卡生成助手。"
user_prompt = "请从以下内容生成闪卡：\n\nPython 是一种解释型语言..."

response = client.chat(system_prompt, user_prompt)
print(response)
```

**validate_connection() -> bool**

测试 LLM 连接是否正常。

返回：
- `bool` - 连接是否成功

示例：

```python
if client.validate_connection():
    print("LLM 连接正常")
else:
    print("LLM 连接失败")
```

#### 支持的提供商

只要提供商兼容 OpenAI API 格式，都可以使用。已测试的提供商：

| 提供商 | Base URL | 说明 |
|--------|----------|------|
| OpenAI | `https://api.openai.com/v1` | 官方 API |
| DeepSeek | `https://api.deepseek.com` | DeepSeek API |
| Moonshot | `https://api.moonshot.cn/v1` | 月之暗面 |
| 智谱 (Zhipu) | `https://open.bigmodel.cn/api/paas/v4` | 智谱 AI |
| 通义千问 (Qwen) | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 阿里云 |
| Ollama | `http://localhost:11434/v1` | 本地部署 |

---

### 4. AnkiGateway

Anki 网关，负责与 Anki 桌面端通信（通过 AnkiConnect）。

#### 初始化

```python
from ankismart.anki_gateway.gateway import AnkiGateway
from ankismart.anki_gateway.client import AnkiConnectClient

# 创建 AnkiConnect 客户端
client = AnkiConnectClient(
    url="http://127.0.0.1:8765",
    api_key="",  # AnkiConnect API Key（如果设置了）
)

# 创建网关
gateway = AnkiGateway(client)
```

#### 方法

**check_connection() -> bool**

检查 AnkiConnect 连接是否正常。

返回：
- `bool` - 连接是否成功

示例：

```python
if gateway.check_connection():
    print("Anki 连接正常")
else:
    print("Anki 连接失败，请确保 Anki 已启动并安装了 AnkiConnect 插件")
```

**get_deck_names() -> list[str]**

获取所有牌组名称。

返回：
- `list[str]` - 牌组名称列表

示例：

```python
decks = gateway.get_deck_names()
print(f"可用牌组: {decks}")
```

**get_model_names() -> list[str]**

获取所有笔记类型名称。

返回：
- `list[str]` - 笔记类型名称列表

示例：

```python
models = gateway.get_model_names()
print(f"可用笔记类型: {models}")
```

**get_model_field_names(model_name: str) -> list[str]**

获取指定笔记类型的字段名称。

参数：
- `model_name` - 笔记类型名称

返回：
- `list[str]` - 字段名称列表

示例：

```python
fields = gateway.get_model_field_names("Basic")
print(f"Basic 笔记类型字段: {fields}")  # ['Front', 'Back']
```

**push(cards: list[CardDraft], update_mode: str = "create_only") -> PushResult**

批量推送卡片到 Anki。

参数：
- `cards` - 卡片草稿列表
- `update_mode` - 更新模式：
  - `"create_only"` - 仅创建新卡片（默认）
  - `"update_only"` - 仅更新已存在的卡片
  - `"create_or_update"` - 创建或更新

返回：
- `PushResult` - 推送结果，包含成功/失败统计

异常：
- `AnkiGatewayError` - 推送失败时抛出

示例：

```python
# 仅创建新卡片
result = gateway.push(cards, update_mode="create_only")
print(f"成功: {result.succeeded}, 失败: {result.failed}")

# 创建或更新卡片
result = gateway.push(cards, update_mode="create_or_update")

# 检查每张卡片的推送状态
for status in result.results:
    if status.success:
        print(f"卡片 {status.index} 推送成功，笔记 ID: {status.note_id}")
    else:
        print(f"卡片 {status.index} 推送失败: {status.error}")
```

**find_notes(query: str) -> list[int]**

查找符合条件的笔记 ID。

参数：
- `query` - Anki 搜索查询语法

返回：
- `list[int]` - 笔记 ID 列表

示例：

```python
# 查找特定牌组中的所有笔记
note_ids = gateway.find_notes('deck:"Python 学习"')

# 查找包含特定标签的笔记
note_ids = gateway.find_notes('tag:ankismart')
```

**update_note(note_id: int, fields: dict[str, str]) -> None**

更新指定笔记的字段。

参数：
- `note_id` - 笔记 ID
- `fields` - 字段字典

示例：

```python
gateway.update_note(
    note_id=1234567890,
    fields={
        "Front": "更新后的问题",
        "Back": "更新后的答案",
    }
)
```

---

### 5. ApkgExporter

APKG 导出器，将卡片草稿导出为 .apkg 文件（离线使用）。

#### 初始化

```python
from ankismart.anki_gateway.apkg_exporter import ApkgExporter

exporter = ApkgExporter()
```

#### 方法

**export(cards: list[CardDraft], output_path: Path) -> Path**

导出卡片为 .apkg 文件。

参数：
- `cards` - 卡片草稿列表
- `output_path` - 输出文件路径

返回：
- `Path` - 实际输出文件路径

异常：
- `AnkiGatewayError` - 导出失败时抛出

示例：

```python
from pathlib import Path

output_path = Path("output.apkg")
actual_path = exporter.export(cards, output_path)
print(f"APKG 文件已导出到: {actual_path}")
```

#### 支持的笔记类型

- `Basic` - 基础卡片（正面/背面）
- `Cloze` - 填空题卡片

#### 媒体附件支持

支持三种媒体来源：
1. **本地文件路径** - `MediaItem.path`
2. **URL** - `MediaItem.url`（自动下载）
3. **Base64 数据** - `MediaItem.data`

示例：

```python
from ankismart.core.models import CardDraft, MediaItem, MediaAttachments

card = CardDraft(
    deck_name="测试牌组",
    note_type="Basic",
    fields={
        "Front": "这是一张带图片的卡片",
        "Back": '<img src="image.png">',
    },
    tags=["test"],
    media=MediaAttachments(
        picture=[
            MediaItem(
                filename="image.png",
                path="/path/to/image.png",  # 本地路径
                fields=["Back"],
            )
        ]
    ),
)

exporter.export([card], Path("output.apkg"))
```

---

## 配置项说明

### AppConfig

应用配置类，使用 Pydantic 进行验证。

#### 字段

```python
class AppConfig(BaseModel):
    # LLM 提供商配置
    llm_providers: list[LLMProviderConfig] = []
    active_provider_id: str = ""

    # Anki 连接配置
    anki_connect_url: str = "http://127.0.0.1:8765"
    anki_connect_key: str = ""  # 自动加密存储

    # 默认值
    default_deck: str = "Default"
    default_tags: list[str] = ["ankismart"]

    # LLM 参数
    llm_temperature: float = 0.3
    llm_max_tokens: int = 0  # 0 表示使用提供商默认值

    # 功能开关
    ocr_correction: bool = False  # 是否启用 OCR 纠错
    enable_auto_split: bool = False  # 是否启用长文档自动分割
    split_threshold: int = 70000  # 分割阈值（字符数）

    # UI 配置
    theme: str = "light"  # light/dark/auto
    language: str = "zh"  # zh/en
    proxy_url: str = ""  # HTTP 代理 URL

    # 持久化配置（上次使用的值）
    last_deck: str = ""
    last_tags: str = ""
    last_strategy: str = ""
    last_update_mode: str = ""
    window_geometry: str = ""  # 窗口几何信息（十六进制编码）

    # 日志级别
    log_level: str = "INFO"  # DEBUG/INFO/WARNING/ERROR
```

#### LLMProviderConfig

```python
class LLMProviderConfig(BaseModel):
    id: str  # 唯一标识符（自动生成）
    name: str  # 提供商名称
    api_key: str  # API Key（自动加密存储）
    base_url: str  # API Base URL
    model: str  # 模型名称
    rpm_limit: int = 0  # 每分钟请求数限制（0 表示不限制）
```

#### 使用示例

```python
from ankismart.core.config import load_config, save_config

# 加载配置
config = load_config()

# 修改配置
config.default_deck = "我的牌组"
config.llm_temperature = 0.5

# 添加新的 LLM 提供商
from ankismart.core.config import LLMProviderConfig
import uuid

new_provider = LLMProviderConfig(
    id=uuid.uuid4().hex[:12],
    name="DeepSeek",
    api_key="your-api-key",
    base_url="https://api.deepseek.com",
    model="deepseek-chat",
    rpm_limit=60,
)
config.llm_providers.append(new_provider)
config.active_provider_id = new_provider.id

# 保存配置
save_config(config)
```

---

## 数据模型

### MarkdownResult

文档转换结果。

```python
class MarkdownResult(BaseModel):
    content: str  # Markdown 内容
    source_path: str  # 源文件路径
    source_format: str  # 文件格式（docx/pdf/image 等）
    trace_id: str = ""  # 追踪 ID
```

### CardDraft

卡片草稿，符合"闪卡格式规范"。

```python
class CardDraft(BaseModel):
    schema_version: str = "1.0"
    trace_id: str = ""
    deck_name: str = "Default"
    note_type: str = "Basic"  # Basic/Cloze
    fields: dict[str, str]  # 字段内容
    tags: list[str] = []
    media: MediaAttachments = MediaAttachments()
    options: CardOptions = CardOptions()
    metadata: CardMetadata = CardMetadata()
```

### GenerateRequest

卡片生成请求。

```python
class GenerateRequest(BaseModel):
    markdown: str  # Markdown 内容
    strategy: str = "basic"  # 生成策略
    deck_name: str = "Default"
    tags: list[str] = []
    trace_id: str = ""
    source_path: str = ""  # 源文件路径（用于图片附件）
    target_count: int = 0  # 目标卡片数量（0 表示不限制）
    enable_auto_split: bool = False  # 是否启用自动分割
    split_threshold: int = 70000  # 分割阈值
```

### PushResult

推送结果。

```python
class PushResult(BaseModel):
    total: int  # 总卡片数
    succeeded: int  # 成功数
    failed: int  # 失败数
    results: list[CardPushStatus] = []  # 每张卡片的状态
    trace_id: str = ""

class CardPushStatus(BaseModel):
    index: int  # 卡片索引
    note_id: int | None = None  # Anki 笔记 ID
    success: bool  # 是否成功
    error: str = ""  # 错误信息
```

---

## 完整示例

### 端到端流程

```python
from pathlib import Path
from ankismart.converter.converter import DocumentConverter
from ankismart.card_gen.generator import CardGenerator
from ankismart.card_gen.llm_client import LLMClient
from ankismart.anki_gateway.gateway import AnkiGateway
from ankismart.anki_gateway.client import AnkiConnectClient
from ankismart.core.models import GenerateRequest

# 1. 转换文档
converter = DocumentConverter()
markdown_result = converter.convert(Path("document.pdf"))

# 2. 生成卡片
llm_client = LLMClient(
    api_key="your-api-key",
    model="gpt-4o",
)
generator = CardGenerator(llm_client)

request = GenerateRequest(
    markdown=markdown_result.content,
    strategy="basic",
    deck_name="学习笔记",
    tags=["ankismart", "pdf"],
)
cards = generator.generate(request)

# 3. 推送到 Anki
client = AnkiConnectClient(url="http://127.0.0.1:8765")
gateway = AnkiGateway(client)

if gateway.check_connection():
    result = gateway.push(cards, update_mode="create_only")
    print(f"推送完成: 成功 {result.succeeded}, 失败 {result.failed}")
else:
    print("Anki 未连接，导出为 APKG 文件")
    from ankismart.anki_gateway.apkg_exporter import ApkgExporter
    exporter = ApkgExporter()
    output_path = exporter.export(cards, Path("output.apkg"))
    print(f"已导出到: {output_path}")
```

### 使用配置文件

```python
from ankismart.core.config import load_config
from ankismart.card_gen.llm_client import LLMClient
from ankismart.card_gen.generator import CardGenerator

# 从配置文件加载
config = load_config()

# 创建 LLM 客户端
llm_client = LLMClient.from_config(config)

# 创建生成器
generator = CardGenerator(llm_client)

# 使用配置中的默认值
request = GenerateRequest(
    markdown="...",
    strategy="basic",
    deck_name=config.default_deck,
    tags=config.default_tags,
)
cards = generator.generate(request)
```

---

## 扩展开发

### 添加新的卡片生成策略

1. 在 `ankismart/card_gen/prompts.py` 中定义系统提示词：

```python
MY_STRATEGY_SYSTEM_PROMPT = """
你是一个 Anki 闪卡生成助手。请根据用户提供的内容生成闪卡。

输出格式要求：
- 使用 JSON 数组格式
- 每张卡片包含 front 和 back 字段

示例输出：
[
  {"front": "问题1", "back": "答案1"},
  {"front": "问题2", "back": "答案2"}
]
"""
```

2. 在 `ankismart/card_gen/generator.py` 中注册策略：

```python
_STRATEGY_MAP["my_strategy"] = (MY_STRATEGY_SYSTEM_PROMPT, "Basic")
```

3. 使用新策略：

```python
request = GenerateRequest(
    markdown="...",
    strategy="my_strategy",
    deck_name="测试",
)
cards = generator.generate(request)
```

### 添加新的文档格式支持

1. 创建新的转换器模块 `ankismart/converter/my_converter.py`：

```python
from pathlib import Path
from ankismart.core.models import MarkdownResult

def convert(file_path: Path, trace_id: str) -> MarkdownResult:
    # 实现转换逻辑
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 转换为 Markdown
    markdown_content = process_content(content)

    return MarkdownResult(
        content=markdown_content,
        source_path=str(file_path),
        source_format="my_format",
        trace_id=trace_id,
    )
```

2. 在 `ankismart/converter/converter.py` 中注册：

```python
from ankismart.converter import my_converter

_CONVERTERS["my_format"] = my_converter.convert
```

3. 在 `ankismart/converter/detector.py` 中添加检测逻辑：

```python
def detect_file_type(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".myext":
        return "my_format"
    # ...
```

### 自定义卡片样式

修改 `ankismart/anki_gateway/styling.py`：

```python
MODERN_CARD_CSS = """
.card {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 18px;
    text-align: center;
    color: #333;
    background-color: #fff;
    padding: 20px;
}

/* 自定义样式 */
.highlight {
    background-color: yellow;
}

code {
    font-family: 'Consolas', monospace;
    background-color: #f5f5f5;
    padding: 2px 4px;
    border-radius: 3px;
}
"""
```

---

## 错误处理

所有核心类的方法都可能抛出以下异常：

- `ConvertError` - 文档转换错误
- `CardGenError` - 卡片生成错误
- `AnkiGatewayError` - Anki 网关错误
- `ConfigError` - 配置错误

建议使用 try-except 捕获异常：

```python
from ankismart.core.errors import ConvertError, CardGenError, AnkiGatewayError

try:
    result = converter.convert(file_path)
    cards = generator.generate(request)
    push_result = gateway.push(cards)
except ConvertError as e:
    print(f"转换失败: {e.message} (错误码: {e.code})")
except CardGenError as e:
    print(f"生成失败: {e.message} (错误码: {e.code})")
except AnkiGatewayError as e:
    print(f"推送失败: {e.message} (错误码: {e.code})")
```

---

## 性能优化建议

1. **启用转换缓存** - 自动启用，基于文件哈希
2. **使用 RPM 限流** - 避免触发 API 速率限制
3. **启用长文档分割** - 对于超长文档，设置 `enable_auto_split=True`
4. **批量处理** - 使用 `gateway.push()` 批量推送卡片
5. **异步处理** - 在 UI 中使用 QThread 处理耗时操作

---

## 日志和调试

启用调试日志：

```python
from ankismart.core.config import load_config, save_config

config = load_config()
config.log_level = "DEBUG"
save_config(config)
```

查看日志输出（控制台）：

```bash
python -m ankismart.ui.app
```

日志格式（JSON）：

```json
{
  "timestamp": "2024-01-01T12:00:00.000Z",
  "level": "INFO",
  "logger": "card_gen",
  "message": "Card generation completed",
  "trace_id": "abc123",
  "card_count": 10
}
```
