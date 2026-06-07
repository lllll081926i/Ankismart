# MarkItDown 备选后端设计

## 背景

`Ankismart` 当前已经具备稳定的本地 OCR / 云 OCR 转 Markdown 链路，也有自研的 `docx`、`pptx`、`markdown`、`text` 转换器。现在需要把 `microsoft/markitdown` 原生接入为“非 OCR 文档”的备选后端，并在设置页中允许用户切换。

本次设计目标不是替换现有 OCR 主链，也不是引入新的插件系统，而是在保持现有入口和缓存模型基本不变的前提下，为 `docx/pptx` 增加第二条可选转换路径。

## 目标

- 在设置页新增“非 OCR 文档转 Markdown 后端”配置。
- 支持 `native` 和 `markitdown` 两种后端。
- `pdf/image` 继续强制走现有 OCR 链，不受新设置影响。
- `markdown/text` 继续走现有轻量转换器，不走 `MarkItDown`。
- 接入方式尽量依赖 `MarkItDown` 的公开 API，降低后续官方升级的维护成本。

## 非目标

- 不把 `MarkItDown` 接管到 `pdf/image`。
- 不做按文件类型分别配置后端。
- 不引入新的“转换器插件框架”。
- 不静默回退到 `native`，避免设置与实际行为不一致。

## 设计决策

### 1. 配置模型

在 `AppConfig` 中新增：

- `doc_convert_backend: str = "native"`

允许值仅为：

- `native`
- `markitdown`

读取配置时，如果值非法，统一回退到 `native`。

### 2. 转换路由

保留 `DocumentConverter` 作为统一入口，不改调用方式。

路由规则：

- `markdown` -> `markdown_converter`
- `text` -> `text_converter`
- `docx/pptx` -> 根据 `doc_convert_backend` 选择 `native` 或 `markitdown`
- `pdf/image` -> 继续走现有 OCR 逻辑

这样可以保证：

- 现有业务层不需要感知新后端
- OCR 路径完全隔离
- 缓存、日志、错误包装仍统一由 `DocumentConverter` 控制

### 3. MarkItDown 适配层

新增 `src/ankismart/converter/markitdown_converter.py`，职责仅限：

- 延迟导入 `markitdown`
- 调用官方公开 API 进行转换
- 把返回结果转换成现有 `MarkdownResult`
- 把异常包装成项目内统一错误

适配层不依赖 `markitdown` 内部目录结构、私有函数或子模块实现，只依赖其公开入口，降低升级成本。

### 4. 错误策略

如果用户启用了 `MarkItDown`：

- 依赖缺失 -> 明确报错
- 转换失败 -> 明确报错

不自动回退到 `native`。原因是静默回退会导致设置失真，后续也难定位问题。

### 5. UI 设计

在设置页新增一个下拉框：

- 中文：`非 OCR 文档转 Markdown 后端`
- 英文：`Non-OCR Markdown Backend`

选项：

- `native` -> `内置转换器`
- `markitdown` -> `MarkItDown（实验）`

该设置与 OCR 模式并列，但语义独立。保存时写入配置，加载时正确回显。

### 6. 依赖与维护性

依赖通过 `uv` 管理，直接加入项目依赖。

为了避免过度耦合：

- 不把 `markitdown` API 调用分散到多个模块
- 只在新适配器内保留与官方库的直接交互
- 由路由层决定何时调用适配器

这样后续升级 `markitdown` 时，主要维护成本集中在一个文件。

## 测试策略

采用 TDD：

1. 先写配置测试
2. 再写路由测试
3. 再写设置页测试
4. 最后实现最小代码通过测试
5. 完成后运行相关测试与格式检查

关键覆盖点：

- 默认值与非法值回退
- `docx/pptx` 路由正确切换
- `pdf/image` 不受设置影响
- 设置页保存与加载
- 依赖缺失时的清晰错误

## 风险

### 风险 1：MarkItDown 公开 API 在后续版本变化

缓解方式：

- 只耦合一个薄适配层
- 在测试里覆盖调用入口和返回值映射

### 风险 2：主依赖引入后包体与安装时间上升

缓解方式：

- 当前只引入基础依赖，不额外扩展 OCR/全部 extras
- 仅在被选中时延迟导入

### 风险 3：用户误以为所有文档都会切到 MarkItDown

缓解方式：

- 设置文案明确写“非 OCR 文档”
- 转换路由保持 `pdf/image` 独立

## 预期结果

用户可以在设置页切换 `docx/pptx` 的 Markdown 转换后端，而不影响现有 OCR 主链和普通文本导入流程。实现方式对现有架构侵入较小，对 `MarkItDown` 的升级维护也足够收敛。
