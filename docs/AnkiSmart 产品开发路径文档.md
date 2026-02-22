# AnkiSmart 产品开发路径文档

**文档版本**：4.0
**创建日期**：2026年2月10日
**更新日期**：2026年2月22日
**规划定位**：AnkiSmart 发布驱动路线图
**唯一上游依据**：`docs/AnkiSmart 产品需求文档.md` v3.0

---

## 1. 规划说明

### 1.1 目的

基于代码实际实现状态，以发布版本为驱动，定义从发布候选到生态扩展的完整路线图。

### 1.2 约束

- 版本定义、能力边界、发布门禁均以本文件为准。
- 需求来源为 PRD（v3.0）与当前代码实现现状。

### 1.3 产品定位约束

- 开源但非商用（商业使用需授权）。
- 首发平台为 Windows 桌面端。

### 1.4 状态标记说明

- ✅ 已完成
- 🔧 进行中 / 需收尾
- 📋 待启动

---

## 2. 版本总览

| 版本 | 定位 | 状态 |
|---|---|---|
| v1.0-rc | 发布候选（全功能验证 + 收尾） | 🔧 |
| v1.1 | 增强版（批量编排 + OCR 优化 + 打包分发） | 📋 |
| v1.2+ | 生态版（社区模板 + 多平台 + 云 OCR） | 📋 |

---

## 3. v1.0-rc — 发布候选

### 3.1 已完成能力清单

以下能力已在代码中实现并可运行：

#### M1 - 基础设施 ✅

| 任务 | 状态 | 说明 |
|---|---|---|
| 项目骨架与依赖 | ✅ | `pip install -e .` 可用 |
| 统一数据模型 | ✅ | CardDraft、MarkdownResult 等核心对象已定义 |
| 日志与追踪 | ✅ | traceId 贯穿全流程 |
| 配置与加密 | ✅ | API Key 加密存储，不明文落盘 |
| 错误码体系 | ✅ | 统一错误码与异常类型 |

#### M2 - 文档标准化与 OCR ✅

| 任务 | 状态 | 说明 |
|---|---|---|
| 输入识别 | ✅ | MIME + 扩展名识别，支持 docx/pptx/txt/md/pdf/图片 |
| 文本转换 | ✅ | md/txt/docx/pptx 转 Markdown |
| OCR 链路 | ✅ | PaddleOCR（PP-OCRv5），按需下载，逐页进度回调 |
| 回退与重试 | ✅ | 失败回退、错误记录 |
| 结果缓存 | ✅ | 转换结果按 traceId 存取 |

#### M3 - LLM 卡片生成 ✅

| 任务 | 状态 | 说明 |
|---|---|---|
| LLM 客户端 | ✅ | 超时、重试、错误封装；6 家供应商支持 |
| 8 种生成策略 | ✅ | basic/cloze/concept/key_terms/single_choice/multiple_choice/image_qa/image_occlusion |
| 后处理校验 | ✅ | JSON 修复、字段补全、schema 校验 |
| 多供应商管理 | ✅ | OpenAI、DeepSeek、Moonshot、智谱、通义千问、Ollama |
| 生成参数 | ✅ | temperature、max_tokens、代理配置 |

#### M4 - Anki 网关与导出 ✅

| 任务 | 状态 | 说明 |
|---|---|---|
| AnkiConnect 客户端 | ✅ | version:6 协议封装 |
| 健康检查 | ✅ | 可用性检测与引导提示 |
| 元数据查询 | ✅ | deck/model/field 拉取 |
| 单条/批量写入 | ✅ | addNote / addNotes |
| 写入前校验 | ✅ | 字段、语法、媒体校验 |
| APKG 导出 | ✅ | genanki 导出降级 |

#### M5 - PySide6 界面 ✅

| 任务 | 状态 | 说明 |
|---|---|---|
| 主窗口与导航 | ✅ | 页面路由与任务驱动布局 |
| 导入页 | ✅ | 文件导入、生成参数配置 |
| 预览页 | ✅ | Markdown 语法高亮预览 |
| 结果页 | ✅ | 推送、导出、逐张编辑、卡片更新、统计反馈 |
| 设置页 | ✅ | 多供应商管理、Anki 地址、连接检测、代理、生成参数 |

#### M6 - 测试（部分完成）

| 任务 | 状态 | 说明 |
|---|---|---|
| 单元测试 | ✅ | 核心模块行为覆盖 |
| 集成测试 | ✅ | 模块链路测试 |
| E2E 冒烟测试 | 🔧 | 需补充自动化验证 |
| 性能基线 | ✅ | 性能统计面板已实现 |

### 3.2 剩余任务（发布前）

| 编号 | 任务 | 优先级 | 状态 |
|---|---|---|---|
| RC-1 | E2E 冒烟测试补全 | P0 | ✅ |
| RC-2 | 打包方案验证（PyInstaller / Nuitka 可行性） | P0 | 📋 |
| RC-3 | 安装向导与首次运行引导 | P1 | 📋 |
| RC-4 | 文档与代码对齐（本次重构） | P0 | 🔧 |
| RC-5 | 版本号更新至 1.0.0-rc | P1 | 📋 |
| RC-6 | 已知缺陷修复与回归验证 | P0 | ✅ |

### 3.2.1 RC-6 回归验证清单（2026-02-22）

| 缺陷主题 | 修复范围 | 回归用例 | 结果 |
|---|---|---|---|
| Anki 模板覆盖用户模型 | 独立模型与样式同步 | `tests/test_anki_gateway/test_gateway.py` `tests/test_anki_gateway/test_apkg_exporter.py` | ✅ |
| 窗口关闭后线程残留 | UI 关闭流程强制终止线程 | `tests/test_ui/test_workers.py` `tests/e2e/gate/test_gate_workflow.py` | ✅ |
| 图片合并 PDF 后 OCR 状态不一致 | 导入页/预览页状态键与去重修复 | `tests/test_ui/test_workers.py` `tests/e2e/scenarios/test_ocr.py` | ✅ |
| AnkiConnect 非 JSON 响应崩溃 | 客户端响应容错 | `tests/test_anki_gateway/test_client.py` | ✅ |
| LLM 代理连接未释放 | `LLMClient` 生命周期与资源释放 | `tests/test_card_gen/test_llm_client.py` | ✅ |
| 并发参数 `0` 语义偏差 | `0=按文档数自动并发` | `tests/test_ui/test_workers.py` | ✅ |
| 打包模式目录分歧（config/log/cache） | 统一 app dir 解析逻辑 | `tests/test_core/test_logging.py` `tests/test_converter/test_cache.py` | ✅ |
| 密钥跨环境解密失败 | `ANKISMART_MASTER_KEY` + 旧密钥兼容 | `tests/test_core/test_crypto.py` `tests/test_core/test_config.py` | ✅ |
| LaTeX 导出格式错乱 | 导出模板与 Word/MD 转换链路修复 | `tests/test_anki_gateway/test_apkg_exporter.py` `tests/test_anki_gateway/test_gateway.py` `tests/test_converter/test_docx_converter.py` `tests/test_converter/test_markdown_converter.py` | ✅ |
| 异常场景恢复能力 | 网络重试、无效文件恢复、Anki 降级导出 | `tests/e2e/scenarios/test_error_handling.py` | ✅ |

本轮 RC-6 验证执行记录：

- `uv run pytest -q tests/test_anki_gateway/test_client.py tests/test_anki_gateway/test_gateway.py tests/test_anki_gateway/test_apkg_exporter.py tests/test_card_gen/test_llm_client.py tests/test_ui/test_workers.py tests/test_converter/test_markdown_converter.py tests/test_converter/test_docx_converter.py tests/test_core/test_crypto.py tests/test_core/test_config.py tests/test_core/test_logging.py` -> `206 passed`
- `uv run pytest -q tests/e2e/scenarios -m "p0"` -> `4 passed, 3 deselected`
- `uv run pytest -q tests/e2e/gate -m "p0 and gate_real"` -> `2 passed`

### 3.3 发布门禁（v1.0-rc Checklist）

- [ ] 全部 8 种卡片策略在标准样例集可稳定生成
- [ ] 6 家 LLM 供应商连通性验证通过
- [ ] AnkiConnect 写入 + APKG 导出降级链路验证通过
- [ ] 逐张编辑与卡片更新功能回归通过
- [ ] OCR 按需下载与识别链路验证通过
- [ ] E2E 冒烟测试覆盖主流程
- [ ] API Key 加密存储策略生效
- [ ] 全流程 traceId、耗时、错误码可追踪
- [ ] 文档与代码口径一致
- [ ] 打包方案至少一种可行性验证通过

---

## 4. v1.1 — 增强版

**目标**：提升批量处理效率、OCR 质量，完成打包分发。

| 编号 | 能力 | 说明 |
|---|---|---|
| E-1 | 批量高级编排 | 并发调度、任务队列、重试策略、错误汇总面板 |
| E-2 | OCR 复杂版面优化 | 表格/多栏/混排版面识别增强 |
| E-3 | OCR 多语言支持 | 日/韩/法/德等语言模型按需加载 |
| E-4 | 性能监控面板增强 | 历史趋势、瓶颈定位、资源占用可视化 |
| E-5 | 高级导出选项 | 自定义牌组结构、标签策略、导出格式选择 |
| E-6 | 打包分发 | 安装包（PyInstaller/Nuitka）+ 便携版 + 自动更新检查 |

**发布门禁**：

- 批量任务在异常场景可恢复。
- 打包产物可在干净 Windows 10 环境安装运行。
- 性能与稳定性相较 v1.0 有可量化提升。

---

## 5. v1.2+ — 生态版

**目标**：形成可持续增长的模板与协作生态。

| 编号 | 能力 | 说明 |
|---|---|---|
| G-1 | 社区模板 | 模板分享、质量审核、版本管理 |
| G-2 | 高级学习分析 | 复习建议、遗忘曲线可视化、学习效果追踪 |
| G-3 | 多平台评估 | macOS / Linux 可行性评估与迁移方案 |
| G-4 | 云 OCR 适配 | 云端 OCR 服务适配层（百度/腾讯/Google Vision） |

**发布门禁（滚动发布）**：

- 生态能力具备治理规则、质量门禁与回滚能力。

---

## 6. 风险管理

| 风险 | 关联版本 | 影响 | 缓解策略 |
|---|---|---|---|
| PaddleOCR 模型体积（~150 MB） | v1.0-rc | 首次安装耗时长 | 按需下载 + 进度回调 + 缓存复用 |
| LLM API 调用成本 | v1.0-rc | 大量生成时费用累积 | 支持 Ollama 本地免费方案 |
| Anki 版本兼容性 | v1.0-rc | 协议变更导致写入失败 | version:6 固定 + 动态字段映射 |
| 打包体积过大 | v1.1 | 安装包 > 500 MB | 模型按需下载、依赖精简、UPX 压缩 |
| `.doc`/`.ppt` 旧格式不支持 | v1.0-rc | 用户持有旧格式无法导入 | 明确提示 + 建议转换格式 |
| 批量任务内存压力 | v1.1 | 大文件批量处理 OOM | 流式处理 + 内存监控 + 任务拆分 |
| 社区模板质量参差 | v1.2+ | 低质量模板影响体验 | 审核机制 + 评分系统 |

---

## 7. 打包与分发策略

### 7.1 方案选型

| 方案 | 优势 | 劣势 | 优先级 |
|---|---|---|---|
| PyInstaller | 成熟稳定，社区支持好 | 产物体积大，启动较慢 | 首选 |
| Nuitka | 编译为原生代码，启动快 | 编译耗时长，兼容性需验证 | 备选 |

### 7.2 模型打包策略

- PaddleOCR 模型不打入安装包，首次运行按需下载。
- 下载进度实时回调至 UI。
- 模型缓存至用户数据目录，支持手动指定路径。

### 7.3 体积优化

- 排除未使用的 PySide6 模块（QtWebEngine 等）。
- 使用 UPX 压缩可执行文件。
- 依赖树精简，移除开发依赖。

---

## 8. 非商用开源边界

- 本规划默认服务于非商用开源版本。
- 不包含商业计费、商业授权后台、SaaS 运营能力。
- 商业化需求需作为独立路线另行立项。

---

## 9. 跨文档引用

| 文档 | 版本 | 关系 |
|---|---|---|
| `docs/AnkiSmart 产品需求文档.md` | v3.0 | 上游需求母本 |
| `docs/AnkiSmart 闪卡格式规范.md` | 3.0 | 卡片对象与校验规范 |
| `docs/design_specs.md` | - | UI 视觉与组件规范 |
| `docs/OCR 模型目录与自动下载说明.md` | - | OCR 模型管理规范 |
