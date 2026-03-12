# Ankismart Experience Improvement Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不破坏现有主流程稳定性的前提下，系统性优化 Ankismart 的首次使用成功率、长任务可控性、错误可恢复性、预览编辑效率和发布稳定性。

**Architecture:** 方案以“先修主路径体验，再拆流程架构，最后补齐发布护栏”为原则推进。短期优先控制用户最容易放弃的节点，中期把页面内流程状态收口为可复用的 workflow/service，长期再扩展更强的批量能力和体验指标体系。

**Tech Stack:** Python 3.11, PyQt6, QFluentWidgets, PaddleOCR, OpenAI-compatible LLM clients, AnkiConnect, genanki, pytest, Ruff, GitHub Actions, PyInstaller, Inno Setup.

---

## 审查摘要

### 已确认的事实

- 主流程已形成闭环：导入 -> 转换/OCR -> 生成 -> 卡片预览编辑 -> 推送/导出。
- 主窗口已经做了首屏优化，只先创建导入页，其他页面延迟初始化。
- 项目具备较完整的自动化测试分层：单元/集成、Fast E2E、Gate-Real、打包验证。
- 当前本地质量基线健康：
  - `uv run ruff check src tests` 通过
  - `uv run pytest tests --ignore=tests/e2e -q --maxfail=1` 通过，`621 passed`
  - `uv run pytest tests/e2e/scenarios -m "fast" -q --maxfail=1` 通过，`7 passed`
  - `uv run pytest tests/e2e/gate -m "p0 and gate_real" -q --maxfail=1` 通过，`2 passed`

### 主要问题

1. 首次成功路径成本偏高
- README 要求用户先配 LLM、再测 AnkiConnect、再确认 OCR 档位和下载源，首次成功路径依赖过多外部条件。

2. 长任务可控性不足
- `ConvertWorker`、`GenerateWorker`、`ExportWorker` 缺少完整取消/恢复语义，`PushWorker` 仅在任务前后检查取消状态。

3. 错误反馈不够产品化
- UI 侧错误处理对非 `AnkiSmartError` 基本直接输出 `str(exc)`，缺少“原因 + 修复动作 + 日志入口”的统一映射。

4. 页面职责过重
- `import_page.py` 体量过大，同时承担文件导入、OCR 配置、模型下载、生成参数、历史恢复、任务协调和进度展示，后续体验优化成本高。

5. 质量口径存在断层
- 全局 coverage 只覆盖 `core/converter/card_gen/anki_gateway`，没有把 `ui` 纳入统一口径；CI 又额外对少数 UI 模块单独做 50% 基线，规则分散。

6. 文档与实现存在漂移
- README 与代码已明确使用 PyQt6，但 PRD/更新日志仍写 PySide6，版本和流程叙述也有滞后，容易误导贡献者和发布执行者。

## 目标指标

### 用户体验目标

- 新用户在 5 分钟内完成首个“导入 -> 生成 -> 导出/推送”流程。
- 长任务都具备可见状态、可取消、可重试、可部分继续。
- 常见错误具备稳定错误码、用户可读说明和明确修复动作。
- 卡片审阅阶段支持快速筛掉低质量结果，而不是只能逐条人工检查。

### 研发效率目标

- 页面逻辑不再承担跨阶段流程编排，改由统一 workflow/service 控制。
- UI 风险进入统一质量口径。
- 发布前验证入口收敛成一套标准命令和 CI 对应关系。

## 分阶段计划

### Phase 0: 事实对齐与基线固化

**用户收益：** 降低协作和发布时的认知偏差，避免“文档说一套、代码跑一套”。

**建议修改文件：**
- `README.md`
- `README.en.md`
- `docs/AnkiSmart 产品需求文档.md`
- `docs/changelog.md`
- `pyproject.toml`
- `.github/workflows/quality-gate.yml`

**工作内容：**
- 统一技术栈表述为 PyQt6，修正文档中残留的 PySide6 描述。
- 把“开发命令”“发布命令”“CI 门禁命令”整理成一致口径。
- 评估是否将 `src/ankismart/ui` 纳入 `tool.coverage.run.source`，避免 coverage 口径与用户风险脱节。
- 把 UI coverage 规则从“附加 baseline”升级为正式质量策略，至少明确哪些模块必须持续纳入。

**验证：**
- `uv run ruff check src tests`
- `uv run pytest tests --ignore=tests/e2e -q --maxfail=1`
- 校对 README、PRD、CI 命令是否一致

**完成标准：**
- 新开发者只看 README 和 CI 文件，就能理解完整验证顺序。
- 文档中不再出现与当前实现矛盾的框架或版本描述。

### Phase 1: 首次使用成功率优化

**用户收益：** 把“第一次就用起来”从说明文依赖改成产品内引导。

**建议修改文件：**
- `src/ankismart/ui/main_window.py`
- `src/ankismart/ui/import_page.py`
- `src/ankismart/ui/settings_page.py`
- `src/ankismart/ui/error_handler.py`
- `src/ankismart/core/config.py`
- `tests/test_ui/test_import_page_*.py`
- `tests/test_ui/test_settings_page_*.py`
- `tests/e2e/scenarios/test_main_workflow.py`

**工作内容：**
- 增加首次启动欢迎/预检引导，展示 LLM、AnkiConnect、OCR 三类依赖的当前状态。
- 在导入前前置提醒 OCR 模型是否缺失、当前 OCR 模式是否可用。
- 给出推荐默认值，降低首次配置决策成本。
- 区分“生成卡片”与“仅导出 APKG”两条新手路径，避免首次就被 AnkiConnect 阻塞。

**验证：**
- 新增“全新配置文件启动”测试。
- 新增“Anki 未启动但 APKG 仍可用”测试。
- 新增“OCR 模型缺失时能被前置识别”测试。

**完成标准：**
- 用户首次进入应用时，不需要翻 README 才知道下一步怎么做。
- 关键外部依赖在发起任务前即可被发现并提示。

### Phase 2: 长任务可控化

**用户收益：** 解决“卡住、看不懂、只能重来”的核心痛点。

**建议修改文件：**
- `src/ankismart/ui/workers.py`
- `src/ankismart/ui/import_page.py`
- `src/ankismart/ui/preview_page.py`
- `src/ankismart/ui/result_page.py`
- `src/ankismart/converter/converter.py`
- `src/ankismart/card_gen/generator.py`
- `src/ankismart/anki_gateway/gateway.py`
- `tests/test_ui/test_workers.py`
- `tests/e2e/scenarios/test_error_handling.py`
- `tests/e2e/gate/test_gate_workflow.py`

**工作内容：**
- 为转换、OCR、生成、推送、导出统一设计任务状态模型：`queued/running/cancelling/cancelled/failed/partial_success/succeeded`。
- 为 worker 增加真实取消检查点，而不是只在开始/结束阶段检查。
- 支持失败后“跳过当前文件继续”“仅重试失败项”“从上次中断处恢复”。
- 统一阶段进度展示，至少区分：预检、转换、OCR、生成、导出/推送。

**验证：**
- 为每种长任务补取消、失败恢复、部分成功继续的测试。
- 回归现有 Fast E2E 与 Gate-Real。

**完成标准：**
- 任一长任务都能解释当前卡在什么阶段。
- 任一批处理都不要求用户因为单点失败而全量重跑。

### Phase 3: 错误反馈产品化

**用户收益：** 用户遇到问题时知道该做什么，而不是只看到技术字符串。

**建议修改文件：**
- `src/ankismart/ui/workers.py`
- `src/ankismart/ui/error_handler.py`
- `src/ankismart/ui/log_exporter.py`
- `src/ankismart/core/errors.py`
- `src/ankismart/core/logging.py`
- `tests/test_core/test_errors.py`
- `tests/e2e/scenarios/test_error_handling.py`

**工作内容：**
- 建立统一错误映射层：错误码、标题、用户说明、建议动作、是否可重试、是否建议导出日志。
- UI 只展示必要说明；详细异常和堆栈进入日志与 crash report。
- 为 LLM、OCR、Anki、网络、配置损坏分别提供可执行修复提示。
- 在错误提示里增加“复制诊断信息/导出日志”入口。

**验证：**
- 对典型异常输入做映射单测。
- 对 E2E 错误场景校验用户提示文本和恢复动作是否正确。

**完成标准：**
- 常见错误提示都包含“原因 + 下一步建议”。
- 用户侧提示不再直接暴露难理解的原始异常文本。

### Phase 4: 导入与预览编辑提效

**用户收益：** 从“能生成”提升为“能高效筛选出可用卡片”。

**建议修改文件：**
- `src/ankismart/ui/import_page.py`
- `src/ankismart/ui/preview_page.py`
- `src/ankismart/ui/card_preview_page.py`
- `src/ankismart/ui/card_edit_widget.py`
- `src/ankismart/ui/result_page.py`
- `tests/test_ui/test_preview_page.py`
- `tests/test_ui/test_card_edit_widget.py`
- `tests/e2e/scenarios/test_main_workflow.py`

**工作内容：**
- 将导入页拆分为更清晰的区域：文件区、OCR 区、策略区、任务区。
- 在 Markdown/卡片预览页加入质量告警、重复候选、低质量卡片筛选入口。
- 加强批量操作：批量打标签、批量删卡、批量切牌组、只看失败项、只看低质量项。
- 明确“样本预览”和“正式生成”的差异与适用场景。

**验证：**
- 新增筛选、批量编辑、低质量提示相关 UI 测试。
- 回归结果页重推、导出与编辑链路。

**完成标准：**
- 用户能快速找到并修正低质量卡片，而不是依赖手动通读。
- 导入页不再承载互相干扰的过多状态。

### Phase 5: 流程编排与架构拆分

**用户收益：** 间接收益，但能显著提升后续体验迭代速度和稳定性。

**建议修改文件：**
- `src/ankismart/ui/import_page.py`
- `src/ankismart/ui/preview_page.py`
- `src/ankismart/ui/result_page.py`
- `src/ankismart/ui/workers.py`
- `src/ankismart/core/interfaces.py`
- 新增：`src/ankismart/ui/workflows/*.py` 或 `src/ankismart/application/*.py`
- 配套测试目录

**工作内容：**
- 把页面内流程状态机抽离为统一 workflow service。
- 将 worker 只保留为执行壳，业务编排放到 workflow/service 层。
- 为导入、生成、导出三类主链路定义稳定的输入输出模型。
- 减少页面直接操作 config/service/gateway 的耦合点。

**验证：**
- 为 workflow 层增加高价值单测。
- 让页面测试更多聚焦交互，减少对内部流程细节的强耦合断言。

**完成标准：**
- 页面不再是业务逻辑集散地。
- 后续新增流程节点不需要继续堆大页面文件。

### Phase 6: 测试与发布链路补强

**用户收益：** 让“首次使用、异常恢复、打包分发”这些真实高风险路径不再依赖人工经验。

**建议修改文件：**
- `pyproject.toml`
- `.github/workflows/quality-gate.yml`
- `.github/workflows/e2e-fast.yml`
- `.github/workflows/e2e-gate.yml`
- `packaging/build.py`
- `tests/e2e/scenarios/*.py`
- `tests/e2e/gate/*.py`

**工作内容：**
- 把文档中的标准命令与 CI 一一对齐。
- 增补首次启动向导、依赖预检、取消/重试、OCR 缺模型、Anki 不可达、APKG 导出的自动化用例。
- 为打包产物补一条最小 smoke test，验证首启、配置目录、日志目录、OCR 缺失提示等关键行为。
- 将关键发布门禁写成单一入口脚本或文档化命令矩阵。

**验证：**
- 现有 CI 全量通过。
- 新增的 smoke test 能在打包产物上执行。

**完成标准：**
- 用户最常见失败路径被自动化覆盖，而不只是理想主路径。
- 发布执行者不需要依靠口口相传来理解门禁。

### Phase 7: 感知性能优化

**用户收益：** 即使总耗时不变，也能明显感到“更快、更稳、更透明”。

**建议修改文件：**
- `src/ankismart/ui/main_window.py`
- `src/ankismart/ui/import_page.py`
- `src/ankismart/ui/preview_page.py`
- `src/ankismart/ui/performance_page.py`
- `src/ankismart/core/tracing.py`
- `src/ankismart/core/config.py`

**工作内容：**
- 增加分阶段耗时采集与展示。
- 对缓存命中、OCR 预热完成、模型已就绪等状态做显式反馈。
- 优化大文件/批处理时的 UI 渲染节奏，优先显示可交互状态。
- 结合已有性能面板，给出用户可理解的性能诊断信息。

**验证：**
- 为 tracing 指标和性能面板增加回归测试。
- 采集代表性样本的基线数据。

**完成标准：**
- 关键阶段耗时可见。
- 页面不再长时间无反馈。

## 实施顺序建议

推荐顺序：

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 6
7. Phase 5
8. Phase 7

说明：
- `Phase 0-4` 直接决定用户会不会继续使用。
- `Phase 6` 要尽早跟上，否则前面的体验收益容易回退。
- `Phase 5` 是中期结构性投资，应在体验主路径稳定后推进。
- `Phase 7` 适合作为持续优化项，在具备稳定观测数据后迭代。

## 推荐立即启动的前三个任务

### Task 1: 统一文档与质量口径

**优先级：** P0

**范围：**
- 修正文档中的 PySide6 漂移
- 对齐 README、CI、coverage 规则
- 给出统一验证命令矩阵

**完成标志：**
- 文档、CI、包配置对同一套流程表述一致

### Task 2: 引入首次启动依赖预检

**优先级：** P0

**范围：**
- LLM/Anki/OCR 状态检查
- 推荐默认值
- 新手路径分流

**完成标志：**
- 新用户不看 README 也能完成首个可用链路

### Task 3: 为长任务补取消/恢复语义

**优先级：** P0

**范围：**
- worker 取消检查点
- 失败项重试
- 阶段化进度展示

**完成标志：**
- 用户不需要因为单点失败而全量重来

## 参考依据

- 技术栈与 coverage 规则：`pyproject.toml`
- 用户路径与开发命令：`README.md`
- 主窗口与延迟页面初始化：`src/ankismart/ui/main_window.py`
- 导入页复杂度与职责集中：`src/ankismart/ui/import_page.py`
- worker 取消与错误格式化现状：`src/ankismart/ui/workers.py`
- 设置页与高密度配置输入：`src/ankismart/ui/settings_page.py`
- 配置体量与持久化项：`src/ankismart/core/config.py`
- 质量门禁与打包验证：`.github/workflows/quality-gate.yml`, `packaging/build.py`
