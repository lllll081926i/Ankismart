# AnkiSmart MVP 任务分解与核心需求文档

**文档版本**：1.1
**创建日期**：2026年2月10日
**更新日期**：2026年2月10日
**依据文档**：产品需求文档 v1.3、产品开发路径文档 v1.3、闪卡格式规范 v1.0

> **v1.1 变更说明**：根据讨论确认以下决策并更新全文：
> 1. 架构方案：MVP 采用**同进程调用**，不启动独立 FastAPI 服务
> 2. 文档转换：**全格式覆盖**（含 PPT、PDF/OCR）
> 3. 客户端 UI：**极简 UI**，Markdown 编辑和卡片逐张编辑放阶段二
> 4. 开发人力：**单人开发**，串行推进，优先打通核心价值链
> 5. Anki 网关后置：M3 排在 M2、M4 之后开发
> 6. 新增 APKG 导出：作为 AnkiConnect 不可用时的降级方案
> 7. WebDAV 同步：经调研确认不可行，已排除

---

## 1. 核心需求提炼

经分析三份产品文档，AnkiSmart MVP 的核心价值链为：

```
多格式文档 → Markdown 标准化 → LLM 闪卡生成 → 写入 Anki（AnkiConnect 主 / APKG 备）
```

### 1.1 MVP 必须实现的能力

| # | 核心能力 | 来源依据 |
|---|---------|---------|
| C1 | 支持 `pptx`、`docx`、`txt`、`md` 输入并转为 Markdown | PRD §2.1, 路径 §阶段一 |
| C2 | 非文本文件走 PDF → OCR → Markdown 链路 | PRD §2.1.1, §2.1.2 |
| C3 | LLM 生成 Basic（问答对）和 Cloze（完形填空）两种卡片 | PRD §2.2, 路径 §阶段一 |
| C4 | 通过 AnkiConnect 写入卡片，覆盖 Basic、Cloze，并支持图片问答（附图）策略 | 路径 §阶段一 DoD |
| C5 | AnkiConnect 协议适配（version:6、result/error、可选 key） | PRD §2.3, 格式规范 §6 |
| C6 | 全流程 traceId 链路追踪与阶段耗时记录 | 路径 §阶段一 DoD, PRD §3.5 |
| C7 | PySide6 桌面客户端，同进程调用后端模块 | PRD §4.1, §4.6（架构调整为同进程） |
| C8 | API Key 加密存储与本地配置管理 | PRD §3.4, 路径 §阶段一 |
| C9 | APKG 文件导出（AnkiConnect 不可用时的降级方案） | 新增，调研结论 |

### 1.2 MVP 明确不做的内容

- 批量文件并行导入与任务队列（阶段二）
- DeepSeek / Ollama 本地 LLM 集成（阶段二/三）
- 卡片更新功能（阶段二）
- Markdown 预览编辑、卡片逐张编辑（阶段二）
- 多语言界面（阶段二）
- WebDAV 同步（经调研不可行，见附录 A）
- 知识图谱、社区模板分享（阶段三）
- macOS / Linux 支持（未来）

---

## 2. 模块划分与依赖关系

```
┌──────────────────────────────────────────────────┐
│              PySide6 客户端 (同进程)               │
│  文件选择 │ 生成配置 │ 结果列表 │ 设置            │
└──────┬──────────┬──────────┬──────────┬───────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
┌──────────────────────────────────────────────────┐
│            Python 模块层（同进程调用）              │
│  Converter │ CardGen │ AnkiGateway │ ApkgExporter │
└──────┬──────────┬──────────┬──────────┬───────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
   PaddleOCR   OpenAI API  AnkiConnect  genanki
```

> **架构说明**：MVP 不启动独立 HTTP 服务。PySide6 UI 通过 Python 函数调用直接使用后端模块，耗时操作放入 `QThread` 子线程避免阻塞 UI。模块间通过定义清晰的接口类/函数签名解耦，为后续拆分为独立服务预留可能。

模块依赖顺序（从底层到上层）：

1. **基础设施层**：项目骨架、配置管理、日志/追踪
2. **Converter 模块**：文档转 Markdown（不依赖外部服务）
3. **CardGen 模块**：LLM 卡片生成（依赖 OpenAI API + 格式规范）
4. **AnkiGateway 模块**：AnkiConnect 通信 + APKG 导出（依赖 Anki 运行 / genanki）
5. **UI 层**：PySide6 界面（依赖上述所有模块）

---

## 3. MVP 任务分解

### M1 - 项目基础设施搭建

> 所有模块的前置依赖，必须最先完成。

| 任务 ID | 任务名称 | 描述 | 验收标准 |
|---------|---------|------|---------|
| M1.1 | 项目目录结构初始化 | 创建 Python 项目骨架，含 `src/ankismart/`、`tests/`、`docs/` 等目录；配置 `pyproject.toml`、`.gitignore`、依赖管理 | 项目可通过 `pip install -e .` 安装，pytest 可运行 |
| M1.2 | 模块接口层定义 | 定义各模块的接口类/协议（Converter、CardGen、AnkiGateway），使用 Python Protocol 或 ABC；定义统一的请求/响应数据模型（Pydantic） | 接口定义清晰，模块间通过接口解耦 |
| M1.3 | 日志与链路追踪 | 实现结构化日志（JSON 格式）、traceId 生成与透传机制（contextvars）、关键阶段耗时记录 | 每次调用自动生成 traceId，日志包含 traceId 和耗时字段 |
| M1.4 | 配置管理模块 | 实现本地配置读写（YAML）、API Key 加密存储（使用 `cryptography` 库）、配置校验 | API Key 加密落盘，明文不出现在配置文件中 |
| M1.5 | 错误码体系 | 定义统一错误码枚举（参照格式规范 §7 的 E_* 错误码），实现异常类层次结构 | 所有模块使用统一错误码，异常包含 code + message + traceId |

**产出物**：可运行的项目骨架 + 接口定义 + 配置管理 + 日志追踪基础设施

---

### M2 - 文档输入与 Markdown 转换模块

> 依赖：M1（基础设施）

| 任务 ID | 任务名称 | 描述 | 验收标准 |
|---------|---------|------|---------|
| M2.1 | 文件类型识别 | 按 MIME 类型 + 扩展名双重判断输入文件类型，分流到对应处理链路 | 正确识别 md/txt/docx/pptx/pdf/图片 |
| M2.2 | Markdown 直接透传 | `.md` 文件读取、编码检测、格式规范化（标题层级、空白清理） | md 文件原样保留内容，仅做格式规范化 |
| M2.3 | TXT 转 Markdown | 编码自动检测（UTF-8/GBK 等）、段落识别与结构化 | 多种编码的 txt 文件正确转为 Markdown |
| M2.4 | Word 转 Markdown | 使用 `python-docx` 解析 docx，提取标题、段落、列表、表格并转为 Markdown | 保留标题层级、列表结构、表格内容 |
| M2.5 | PPT 转 Markdown | 使用 `python-pptx` 按页/文本框提取内容，转为 Markdown | 每页内容独立分节，保留标题和正文 |
| M2.6 | PDF → OCR → Markdown | 使用 PaddleOCR 对 PDF 逐页识别，拼接文本并重建结构 | 中英文 PDF 识别准确，输出结构化 Markdown |
| M2.7 | 转换失败回退 | 文本解析失败时自动切换到 PDF→OCR 链路；OCR 失败时记录错误并标记 | 失败场景有明确错误码和回退日志 |
| M2.8 | 转换结果缓存 | 保存标准化 Markdown 与处理日志到本地，供预览与回溯 | 转换结果可按 traceId 查询 |

**产出物**：`converter.convert(file_path) → MarkdownResult` 模块接口

---

### M3 - LLM 卡片生成模块

> 依赖：M1（基础设施）、格式规范（CardDraft 结构）。

| 任务 ID | 任务名称 | 描述 | 验收标准 |
|---------|---------|------|---------|
| M3.1 | OpenAI API 客户端封装 | 封装 OpenAI API 调用，含重试、超时、错误处理、token 用量记录 | API 调用稳定，异常有明确错误信息 |
| M3.2 | Basic 卡片生成策略 | 设计 Prompt，从 Markdown 提取核心概念生成问答对，输出 CardDraft JSON | 输入一段 Markdown，输出符合格式规范的 Basic CardDraft 数组 |
| M3.3 | Cloze 卡片生成策略 | 设计 Prompt，识别关键术语生成完形填空，确保 `{{cN::...}}` 语法正确 | 输出的 Cloze 卡片含合法挖空语法 |
| M3.4 | CardDraft 结构化与校验 | LLM 输出后处理：JSON 解析、字段补全（schemaVersion/traceId/tags）、格式校验 | 输出严格符合格式规范 §3.2 的 CardDraft 结构 |
| M3.5 | OCR 文本纠错 | 在卡片生成前，利用 LLM 对 OCR 产出的 Markdown 进行错误纠正 | OCR 常见错误（如形近字、断行）被修正 |

**产出物**：`card_gen.generate(markdown, strategy) → list[CardDraft]` 模块接口

---

### M4 - Anki 网关模块

> 依赖：M1（基础设施）、M3（CardDraft 结构已定义）。排在 M2、M3 之后开发。

| 任务 ID | 任务名称 | 描述 | 验收标准 |
|---------|---------|------|---------|
| M4.1 | AnkiConnect 客户端封装 | 封装 HTTP 请求层，支持 `version:6` 协议、可选 `key` 字段、`result/error` 响应解析 | 请求自动携带 version:6，正确解析 result 和 error |
| M4.2 | 连接检测与健康检查 | 启动时检测 AnkiConnect 可用性（`127.0.0.1:8765`），不可用时给出明确提示 | Anki 未运行时返回 `E_ANKICONNECT_ERROR` 及修复建议 |
| M4.3 | 牌组与笔记类型查询 | 实现 `deckNames`、`modelNames`、`modelFieldNames` 查询 | 正确返回用户 Anki 中的牌组和笔记类型列表 |
| M4.4 | 单条卡片写入 | 实现 `addNote` 写入，含字段映射（noteType→modelName）、去重选项、媒体附件 | Basic 和 Cloze 卡片成功写入 Anki |
| M4.5 | 批量卡片写入 | 实现 `addNotes` 批量写入，含部分失败处理与结果汇总 | 批量写入返回每张卡片的成功/失败状态 |
| M4.6 | 写入前校验 | 实现格式规范 §7 定义的全部校验：deckName 存在性、noteType 存在性、字段完整性、Cloze 语法、媒体合法性 | 校验失败返回对应 E_* 错误码 |
| M4.7 | APKG 文件导出 | 使用 `genanki` 库将 CardDraft 数组导出为 `.apkg` 文件，作为 AnkiConnect 不可用时的降级方案 | 生成的 .apkg 文件可在 Anki 中正常导入，卡片内容正确 |

**产出物**：`anki_gateway.push(cards) → PushResult` + `apkg_exporter.export(cards, path) → Path` 模块接口

---

### M5 - PySide6 客户端 UI（极简版）

> 依赖：M1-M4 模块接口就绪。

| 任务 ID | 任务名称 | 描述 | 验收标准 |
|---------|---------|------|---------|
| M5.1 | 应用框架与主窗口 | PySide6 应用入口、主窗口布局（向导式流程）、QThread 异步调用封装 | 应用启动显示主窗口，耗时操作不阻塞 UI |
| M5.2 | 文件导入与生成配置 | 文件选择对话框（多格式过滤）、拖拽导入、目标牌组/笔记类型/生成策略选择、一键生成按钮 | 用户选择文件 + 配置后点击生成，触发完整链路 |
| M5.3 | 结果列表与推送 | 生成的卡片列表展示（只读预览）、全选/取消、推送到 Anki / 导出 APKG、成功/失败统计 | 用户可查看生成结果并一键推送或导出 |
| M5.4 | 设置页面 | API Key 配置（加密存储）、AnkiConnect 地址配置、连接状态检测 | 配置保存后立即生效 |

**产出物**：极简 PySide6 桌面客户端，支持完整的"导入→生成→推送/导出"流程

> **阶段二再做**：Markdown 预览编辑（M5.3 原）、卡片逐张编辑（M5.5 原）、快捷键自定义（M5.8 原）

---

### M6 - 集成测试与端到端验证

> 依赖：M1-M5 全部完成。

| 任务 ID | 任务名称 | 描述 | 验收标准 |
|---------|---------|------|---------|
| M6.1 | 单元测试补全 | 各模块核心逻辑的单元测试（转换、校验、映射、错误处理） | 核心模块测试覆盖率 ≥ 80% |
| M6.2 | 集成测试 | Converter→CardGen→AnkiGateway 全链路集成测试 | 端到端流程可自动化运行并通过 |
| M6.3 | 端到端冒烟测试 | 从文件导入到卡片出现在 Anki 的完整流程验证 | Word/PPT/TXT/MD 各一个用例全部通过 |
| M6.4 | 性能基准测试 | 验证 PRD §3.1 的性能指标（转换 ≤8s、OCR ≤5s/页、LLM ≤3s/卡） | 各指标 P95 达标 |

**产出物**：测试报告 + 性能基准报告

---

## 4. 单人开发执行顺序

> 单人串行开发，按"最快验证核心价值链"原则排序。

```
M1 基础设施
 │
 ▼
M2 文档转换 ──→ 里程碑 A：任意文档可转为 Markdown
 │
 ▼
M3 LLM 生成 ──→ 里程碑 B：Markdown 可生成 CardDraft（CLI 验证）
 │
 ▼
M4 Anki 网关 ──→ 里程碑 C：CardDraft 可写入 Anki / 导出 APKG
 │
 ▼
M5 极简 UI ───→ 里程碑 D：完整 GUI 流程可用
 │
 ▼
M6 测试验收 ──→ 里程碑 E：MVP 交付
```

**执行说明**：

| 阶段 | 模块 | 里程碑 | 验证方式 |
|------|------|--------|---------|
| 1 | M1 | 项目可运行 | `pip install -e .` + `pytest` 通过 |
| 2 | M2 | 文档→Markdown | CLI 脚本：输入 docx/pptx/txt/md，输出 Markdown 文件 |
| 3 | M3 | Markdown→CardDraft | CLI 脚本：输入 Markdown，输出 CardDraft JSON |
| 4 | M4 | CardDraft→Anki | CLI 脚本：输入 CardDraft JSON，写入 Anki 或导出 .apkg |
| 5 | M5 | GUI 可用 | 桌面应用完成完整流程 |
| 6 | M6 | MVP 交付 | 全部测试通过 |

> **提示**：每个阶段完成后先用 CLI 脚本验证，确保模块独立可用，再进入下一阶段。这样即使 UI 未完成，核心功能也可通过命令行使用。

---

## 5. 关键技术决策（已确认）

| # | 决策项 | 结论 | 状态 |
|---|-------|------|------|
| D1 | 客户端框架 | PySide6 | ✅ 已确认 |
| D2 | 前后端架构 | **同进程调用**，不启动独立 HTTP 服务 | ✅ 已确认 |
| D3 | OCR 引擎 | PaddleOCR 为主 | ✅ 已确认 |
| D4 | LLM 引擎 | OpenAI API (GPT-4o) | ✅ 已确认 |
| D5 | AnkiConnect 协议版本 | 固定 version: 6 | ✅ 已确认 |
| D6 | 字段映射策略 | 运行时动态查询，不硬编码 | ✅ 已确认 |
| D7 | 数据格式 | CardDraft JSON（格式规范 §3.2） | ✅ 已确认 |
| D8 | 部署方式 | Windows 安装包，内含 Python 运行时 | ✅ 已确认 |
| D9 | Anki 写入降级 | AnkiConnect 主路径 + APKG 导出备选 | ✅ 已确认 |
| D10 | WebDAV 同步 | **不可行，已排除**（见附录 A） | ✅ 已确认 |

---

## 6. 风险与缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| PaddleOCR 中文复杂排版识别率不足 | 卡片内容质量下降 | 利用 LLM 纠错（M3.5）作为兜底；预留云端 OCR 接口 |
| LLM 输出 JSON 格式不稳定 | CardDraft 解析失败 | M3.4 中实现健壮的 JSON 解析与修复逻辑；设计 fallback prompt |
| AnkiConnect 未安装/未启动 | 实时写入不可用 | M4.2 启动检测 + 用户引导；M4.7 APKG 导出作为降级方案 |
| PaddleOCR 打包体积大（~1GB） | 安装包过大 | 评估按需下载 OCR 模型；或将 OCR 标记为可选功能 |
| 单人开发周期长 | 交付延迟 | 严格按里程碑推进，每阶段 CLI 验证确保可用 |

---

## 7. MVP 验收标准汇总

对照开发路径文档阶段一 DoD：

- [ ] 支持 `pptx`、`docx`、`txt`、`md` 输入并稳定生成 Markdown
- [ ] 非文本文件可走 PDF → OCR → Markdown 链路并完成任务状态追踪
- [ ] 至少支持 `Basic`、`Cloze` 两类笔记类型写入 Anki，并支持图片问答（附图）策略
- [ ] AnkiConnect 协议适配完成（version:6、result/error、可选 key）
- [ ] APKG 导出功能可用（AnkiConnect 不可用时的降级方案）
- [ ] 关键流程具备可观测性（traceId、阶段耗时、失败原因）
- [ ] API Key 加密存储，不以明文暴露
- [ ] PySide6 客户端可完成完整的"导入→生成→推送/导出"流程
- [ ] 核心模块单元测试覆盖率 ≥ 80%
- [ ] 端到端冒烟测试通过（至少 4 种输入格式各一个用例）

---

## 附录 A：WebDAV 同步方案调研结论

### 调研背景

评估是否可通过 WebDAV 协议实现 Anki 卡片同步，作为 AnkiConnect 的替代或补充方案。

### 结论：不可行

| 维度 | 说明 |
|------|------|
| 协议兼容性 | Anki 同步协议是私有 HTTP 协议，操作数据库记录（笔记、卡片、复习历史）；WebDAV 是文件级协议，两者架构不兼容 |
| 数据安全 | Anki 使用 SQLite 数据库，文件级同步工具（WebDAV/Nextcloud/Syncthing）在数据库使用中操作会导致数据库损坏。Anki 官方明确警告此风险 |
| 自建同步服务器 | Anki 2.1.57+ 内置自建同步服务器支持，但仅用于客户端间同步，不暴露卡片创建 API，无法用于程序化写入 |
| 社区方案 | 无成熟的 WebDAV→Anki 同步方案存在 |

### 推荐替代方案

| 方案 | 适用场景 | 依赖 |
|------|---------|------|
| **AnkiConnect**（主路径） | 实时写入、去重校验、字段查询 | Anki 桌面端运行 + AnkiConnect 插件 |
| **APKG 导出**（降级方案） | AnkiConnect 不可用、移动端导入 | `genanki` 库，无需 Anki 运行 |
