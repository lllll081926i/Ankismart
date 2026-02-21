# Ankismart

<p align="center">
  <img src="docs/images/hero.svg" alt="Ankismart hero" width="100%" />
</p>

<p align="center">
  <a href="./README.md">简体中文</a> ·
  <a href="./README.en.md">English</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/UI-PyQt6%20%2B%20Fluent-4B8BBE" alt="ui" />
  <img src="https://img.shields.io/badge/OCR-PaddleOCR-0052D9" alt="ocr" />
  <img src="https://img.shields.io/badge/Anki-AnkiConnect-78A8D8" alt="anki" />
</p>

***

Ankismart 是一个桌面端智能制卡工具，核心流程是：

`导入文档 -> 转 Markdown（含 OCR）-> 生成卡片 -> 卡片预览编辑 -> 推送 Anki / 导出 APKG`

<p align="center">
  <img src="docs/images/workflow.svg" alt="Workflow" width="92%" />
</p>

## 1. 快速开始

### 1.1 环境要求

- Python `3.11+`

- 推荐 `uv`（用于安装依赖和运行）

- Windows 桌面版 Anki（若要推送）

- AnkiConnect 插件（若要推送）

### 1.2 安装与运行

```bash
uv sync
uv run ankismart
```

或：

```bash
uv run python -m ankismart.ui.app
```

### 1.3 首次使用建议

1. 在设置页先配置并测试 LLM 提供商。
2. 配置并测试 AnkiConnect（URL/密钥/代理）。
3. 导入文件前先确认 OCR 档位与下载源。
4. 首次处理 PDF/图片时按提示下载 OCR 模型。

## 2. AnkiConnect 配置与使用

### 2.1 必备条件

- 已安装并启动 Anki 桌面版

- 已安装 AnkiConnect 插件

- Ankismart 设置中的 `AnkiConnect URL` 可访问（默认 `http://127.0.0.1:8765`）

### 2.2 设置项说明

- `AnkiConnect URL`：AnkiConnect HTTP 地址，默认本机回环地址

- `AnkiConnect 密钥`：可选；若你在 AnkiConnect 里启用了 key，需要与这里一致

- `代理设置`：手动代理时会用于外部请求；对本机回环地址（`127.0.0.1/localhost`）默认直连

### 2.3 推送模式

- `仅新增 (create_only)`：只创建新笔记

- `仅更新 (update_only)`：仅更新已存在笔记，不存在则失败

- `新增或更新 (create_or_update)`：存在则更新，不存在则新增

### 2.4 重复检查策略

- 检查范围：当前牌组 / 所有牌组

- 可配置“允许重复”开关

- 推送时会按卡片字段与模型规则执行重复判断

### 2.5 最小自检步骤

1. 打开 Anki 桌面版并确认 AnkiConnect 已启用。
2. 在 Ankismart 设置页点击“测试连接”。
3. 如果失败，先检查 URL、密钥和代理配置。

### 2.6 常见问题

- 报错“Cannot connect to AnkiConnect”

  - 确认 Anki 正在运行且插件已启用

  - 确认 URL 未写错端口

- 报错“AnkiConnect error: ...”

  - 检查 key、字段模型映射、牌组名是否合法

- 只能导出不能推送

  - 通常是 AnkiConnect 不通；APKG 导出不依赖 Anki 进程

## 3. 打包与发布

### 3.1 一键构建

```bash
uv run python packaging/build.py --clean
```

仅构建应用目录和便携版：

```bash
uv run python packaging/build.py --clean --skip-installer
```

## 4. 开发命令

安装依赖：

```bash
uv sync
```

运行应用：

```bash
uv run ankismart
```

运行测试：

```bash
uv run pytest -q
```

只跑转换模块：

```bash
uv run pytest tests/test_converter -q
```

静态检查：

```bash
uv run ruff check src tests
```

## 5. 常用环境变量

- `ANKISMART_APP_DIR`：覆盖应用数据目录

- `ANKISMART_CONFIG_PATH`：覆盖配置文件路径

- `ANKISMART_OCR_DEVICE`：`auto/cpu/gpu`

- `ANKISMART_OCR_MODEL_DIR`：OCR 模型根目录

- `ANKISMART_OCR_CPU_MKLDNN`：CPU 推理是否启用 MKLDNN

- `ANKISMART_OCR_CPU_THREADS`：CPU 线程数

- `ANKISMART_OCR_PDF_RENDER_SCALE`：PDF 渲染倍率

- `ANKISMART_CUDA_CACHE_TTL_SECONDS`：CUDA 检测缓存时间

## 6. 目录结构

```text
src/ankismart/
├─ ui/                 # PyQt6 页面与交互
├─ converter/          # 文档解析、OCR、缓存、类型检测
├─ card_gen/           # LLM 生成与后处理
├─ anki_gateway/       # AnkiConnect / APKG 导出
└─ core/               # 配置、日志、错误模型、追踪

packaging/             # PyInstaller + Inno Setup 构建脚本
tests/                 # 单元测试与回归测试
docs/                  # 图片与文档资源
```

## 7. 技术栈

- UI：PyQt6 + PyQt-Fluent-Widgets

- OCR：PaddleOCR + PaddlePaddle

- 文档处理：python-docx / python-pptx / pypdfium2

- LLM：OpenAI 兼容接口（多 Provider）

- Anki 集成：AnkiConnect + genanki
