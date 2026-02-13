# Ankismart

<p align="center">
  <img src="docs/images/hero.svg" alt="Ankismart hero" width="100%" />
</p>

<p align="center">
  <a href="#中文">中文</a> ·
  <a href="#english-collapsible">English</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/UI-PyQt6%20%2B%20Fluent-4B8BBE" alt="ui" />
  <img src="https://img.shields.io/badge/OCR-PaddleOCR-0052D9" alt="ocr" />
  <img src="https://img.shields.io/badge/Anki-AnkiConnect-78A8D8" alt="anki" />
</p>

---

## 中文

Ankismart 是一个桌面端智能制卡工具：导入文档 → 提取内容（含 OCR）→ 生成 Anki 卡片 → 预览编辑 → 推送或导出 APKG。

<p align="center">
  <img src="docs/images/workflow.svg" alt="Workflow" width="92%" />
</p>

### 核心能力

- 多格式导入：`md`、`txt`、`docx`、`pptx`、`pdf`、图片
- 智能 OCR：本地模型按需下载（不内置模型），支持模型档位切换
- 卡片生成：支持多种题型与策略配比
- 结果复核：批量编辑标签/牌组、重试失败项、导出 APKG
- 主题与界面：侧边栏主题切换（浅色 / 深色 / 跟随系统）

### 快速开始

#### 1) 环境准备

- Python `3.11+`
- 建议使用虚拟环境（Windows / Linux / macOS 均可）

#### 2) 安装依赖

```bash
pip install -e .
```

#### 3) 启动应用

```bash
python -m ankismart.ui.app
```

### 打包发布（安装版 + 便携版）

项目已提供一键脚本，默认生成：

- 安装版（Inno Setup，可选）
- 便携版（ZIP）
- 且**不打包 OCR 模型**（首次 OCR 时按需下载）

```bash
# 完整构建（若本机安装了 Inno Setup，会同时产出安装包）
python packaging/build.py --clean

# 仅构建应用分发目录 + 便携版
python packaging/build.py --clean --skip-installer
```

输出目录结构（扁平且清晰）：

```text
dist/release/
├─ app/                      # 安装版源目录（无 OCR 模型）
├─ portable/
│  ├─ Ankismart-Portable-x.y.z/
│  └─ Ankismart-Portable-x.y.z.zip
└─ installer/
   └─ Ankismart-Setup-x.y.z.exe
```

### 文档

- 使用指南：`docs/user-guide.md`
- 常见问题：`docs/faq.md`
- 架构说明：`docs/architecture.md`
- 变更日志：`docs/changelog.md`

### 技术栈

- UI：PyQt6 + PyQt-Fluent-Widgets
- OCR：PaddleOCR + PaddlePaddle
- 文档处理：python-docx / python-pptx / pypdfium2
- LLM：OpenAI 兼容接口
- Anki 集成：AnkiConnect + genanki

---

<a id="english-collapsible"></a>
<details>
<summary><strong>English (click to expand)</strong></summary>

## Ankismart (English)

Ankismart is a desktop app for turning documents into high-quality Anki cards: import → OCR/extract → generate → review/edit → push/export.

### Highlights

- Multi-format input: `md`, `txt`, `docx`, `pptx`, `pdf`, images
- OCR with on-demand local model download (models are not bundled)
- Multiple generation strategies and mixed ratios
- Result review with batch tag/deck editing and APKG export
- Sidebar theme switch: Light / Dark / Follow System

### Quick Start

```bash
pip install -e .
python -m ankismart.ui.app
```

### Packaging

```bash
# Full release build (installer + portable if Inno Setup exists)
python packaging/build.py --clean

# Portable-only release flow
python packaging/build.py --clean --skip-installer
```

Release layout:

```text
dist/release/
├─ app/
├─ portable/
└─ installer/
```

### Docs

- User Guide: `docs/user-guide-en.md`
- FAQ: `docs/faq.md`
- Architecture: `docs/architecture.md`

</details>


