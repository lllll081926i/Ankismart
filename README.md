# Ankismart

<div align="center">

**智能 Anki 闪卡生成工具 | Intelligent Anki Flashcard Generator**

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

[English](#english) | [中文](#中文)

</div>

---

## 中文

### 📖 简介

Ankismart 是一款基于大语言模型（LLM）的智能 Anki 闪卡生成工具，能够将各种格式的文档自动转换为高质量的学习卡片。无论是学习笔记、教材、论文还是技术文档，Ankismart 都能帮助您快速构建个性化的 Anki 卡片库。

### ✨ 核心特性

#### 🎯 多格式支持
- **文档格式**：Markdown (`.md`)、Word (`.docx`)、PowerPoint (`.pptx`)、PDF (`.pdf`)、纯文本 (`.txt`)
- **图片格式**：PNG、JPG、JPEG、BMP
- **智能识别**：自动检测文档类型并选择最佳转换方式

#### 🤖 智能 OCR
- 内置 **PaddleOCR** 引擎，支持中英文混合识别
- 可选 **LLM 校正**功能，自动修正 OCR 识别错误
- 首次使用自动下载模型，无需手动配置

#### 🎨 8 种生成策略
1. **基础问答**：传统的问题-答案格式，适合通用学习
2. **填空题**：使用 Anki Cloze 语法，精确记忆关键信息
3. **图片问答**：针对图表和示意图的专门策略
4. **概念解释**：深度解释概念，包含原理、意义和示例
5. **关键术语**：术语定义 + 例句，适合专业词汇学习
6. **单选题**：模拟考试场景，训练辨析能力
7. **多选题**：综合性测试，考察全面理解
8. **自定义策略**：支持自定义提示词（高级功能）

#### 📐 完整的数学公式支持
- 支持 **LaTeX** 语法，使用 **MathJax** 渲染
- 行内公式：`$x^2 + y^2 = z^2$`
- 独立公式：`$$\int_0^\infty e^{-x^2} dx$$`
- 在预览页面实时查看渲染效果

#### 🔄 批量处理与实时预览
- 一次导入多个文档，批量生成卡片
- 实时预览每张卡片的渲染效果
- 支持逐张编辑、删除和调整
- Markdown 编辑器，支持语法高亮

#### 📤 灵活的导出方式
- **直接推送到 Anki**：通过 AnkiConnect 插件实时同步
- **导出 .apkg 文件**：标准 Anki 包，可在任何设备导入
- 支持自定义牌组和标签
- 支持更新已存在的卡片

#### 🌍 多语言与多主题
- 界面语言：中文、English
- 主题：浅色、深色、自动（跟随系统）
- 卡片内容自动匹配文档语言

#### 🔧 高级功能
- **长文档自动分割**：处理超长文档，避免 LLM 上下文限制
- **多 LLM 提供商支持**：OpenAI、DeepSeek、Moonshot、智谱 AI、通义千问、Ollama 等
- **代理配置**：支持 HTTP/HTTPS/SOCKS5 代理
- **配置加密**：敏感信息（API Key）自动加密存储

### 📸 功能截图

> 提示：以下位置可添加应用截图

1. **主界面**：`docs/screenshots/main-window.png`
2. **导入页面**：`docs/screenshots/import-page.png`
3. **预览页面**：`docs/screenshots/preview-page.png`
4. **设置页面**：`docs/screenshots/settings-page.png`

### 🚀 快速开始

#### 安装

**方法一：使用预编译版本（推荐）**

1. 从 [Releases](https://github.com/your-repo/ankismart/releases) 下载最新版本
2. 解压到任意目录
3. 运行 `Ankismart.exe`（Windows）或对应的可执行文件

**方法二：从源码安装**

```bash
# 克隆仓库
git clone https://github.com/your-repo/ankismart.git
cd ankismart

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -e .

# 运行应用
python -m ankismart.ui.app
```

#### 配置

1. **配置 LLM 提供商**（必需）
   - 打开设置页面
   - 添加至少一个 LLM 提供商（OpenAI、DeepSeek 等）
   - 填写 API Key 和模型名称
   - 测试连接并激活

2. **配置 AnkiConnect**（推送到 Anki 时需要）
   - 在 Anki 中安装 AnkiConnect 插件（代码：`2055492159`）
   - 在 Ankismart 设置中填写 AnkiConnect URL（默认：`http://127.0.0.1:8765`）
   - 测试连接

3. **开始使用**
   - 导入文档
   - 选择生成策略
   - 生成卡片
   - 预览和编辑
   - 导出到 Anki

详细配置说明请参考 [用户指南](docs/user-guide.md)。

### 📚 文档

- **[用户指南](docs/user-guide.md)**：完整的使用说明和功能介绍
- **[常见问题](docs/faq.md)**：安装、配置、使用问题的解决方案
- **[示例文档](docs/examples/)**：包含数学公式的示例文档

### 🛠️ 技术栈

- **界面框架**：PySide6 + QFluentWidgets
- **文档转换**：python-docx、python-pptx、pypdfium2
- **OCR 引擎**：PaddleOCR + PaddlePaddle
- **LLM 集成**：OpenAI API（兼容格式）
- **Anki 集成**：AnkiConnect + genanki
- **配置管理**：Pydantic + PyYAML
- **加密存储**：cryptography

### 📋 系统要求

- **操作系统**：Windows 10/11、macOS 10.15+、Linux
- **Python 版本**：3.11 或更高
- **内存**：4GB+（使用 OCR 功能建议 8GB+）
- **磁盘空间**：至少 2GB（OCR 模型约 500MB）

### 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

### 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

### 🙏 致谢

- [Anki](https://apps.ankiweb.net/) - 强大的间隔重复学习软件
- [AnkiConnect](https://foosoft.net/projects/anki-connect/) - Anki 的 API 插件
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - 优秀的 OCR 工具
- [QFluentWidgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) - 现代化的 Qt 组件库
- [OpenAI](https://openai.com/) - 提供强大的 LLM API

### 📧 联系方式

- **Issues**：[GitHub Issues](https://github.com/your-repo/ankismart/issues)
- **Discussions**：[GitHub Discussions](https://github.com/your-repo/ankismart/discussions)
- **Email**：your-email@example.com

---

## English

### 📖 Introduction

Ankismart is an intelligent Anki flashcard generation tool powered by Large Language Models (LLM). It automatically converts various document formats into high-quality learning cards. Whether it's study notes, textbooks, papers, or technical documentation, Ankismart helps you quickly build a personalized Anki card library.

### ✨ Key Features

#### 🎯 Multi-format Support
- **Document Formats**: Markdown (`.md`), Word (`.docx`), PowerPoint (`.pptx`), PDF (`.pdf`), Plain Text (`.txt`)
- **Image Formats**: PNG, JPG, JPEG, BMP
- **Smart Detection**: Automatically detects document type and selects optimal conversion method

#### 🤖 Intelligent OCR
- Built-in **PaddleOCR** engine with Chinese and English recognition
- Optional **LLM correction** to automatically fix OCR errors
- Automatic model download on first use, no manual configuration needed

#### 🎨 8 Generation Strategies
1. **Basic Q&A**: Traditional question-answer format for general learning
2. **Cloze Deletion**: Uses Anki Cloze syntax for precise memorization
3. **Image-based Q&A**: Specialized strategy for charts and diagrams
4. **Concept Explanation**: In-depth concept explanation with principles and examples
5. **Key Terms**: Term definitions + example sentences for vocabulary learning
6. **Single Choice**: Simulates exam scenarios, trains discrimination ability
7. **Multiple Choice**: Comprehensive testing for thorough understanding
8. **Custom Strategy**: Supports custom prompts (advanced feature)

#### 📐 Full Math Formula Support
- Supports **LaTeX** syntax with **MathJax** rendering
- Inline formulas: `$x^2 + y^2 = z^2$`
- Display formulas: `$$\int_0^\infty e^{-x^2} dx$$`
- Real-time preview in preview page

#### 🔄 Batch Processing & Real-time Preview
- Import multiple documents at once for batch generation
- Real-time preview of each card's rendered effect
- Support for individual editing, deletion, and adjustment
- Markdown editor with syntax highlighting

#### 📤 Flexible Export Options
- **Push to Anki**: Real-time sync via AnkiConnect plugin
- **Export .apkg file**: Standard Anki package for import on any device
- Support for custom decks and tags
- Support for updating existing cards

#### 🌍 Multi-language & Multi-theme
- Interface languages: Chinese, English
- Themes: Light, Dark, Auto (follow system)
- Card content automatically matches document language

#### 🔧 Advanced Features
- **Long Document Auto-split**: Handle very long documents, avoid LLM context limits
- **Multi-LLM Provider Support**: OpenAI, DeepSeek, Moonshot, Zhipu AI, Qwen, Ollama, etc.
- **Proxy Configuration**: Supports HTTP/HTTPS/SOCKS5 proxy
- **Configuration Encryption**: Sensitive information (API Keys) automatically encrypted

### 📸 Screenshots

> Tip: Add application screenshots at the following locations

1. **Main Window**: `docs/screenshots/main-window.png`
2. **Import Page**: `docs/screenshots/import-page.png`
3. **Preview Page**: `docs/screenshots/preview-page.png`
4. **Settings Page**: `docs/screenshots/settings-page.png`

### 🚀 Quick Start

#### Installation

**Method 1: Using Pre-compiled Version (Recommended)**

1. Download the latest version from [Releases](https://github.com/your-repo/ankismart/releases)
2. Extract to any directory
3. Run `Ankismart.exe` (Windows) or the corresponding executable

**Method 2: Install from Source**

```bash
# Clone repository
git clone https://github.com/your-repo/ankismart.git
cd ankismart

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -e .

# Run application
python -m ankismart.ui.app
```

#### Configuration

1. **Configure LLM Provider** (Required)
   - Open settings page
   - Add at least one LLM provider (OpenAI, DeepSeek, etc.)
   - Fill in API Key and model name
   - Test connection and activate

2. **Configure AnkiConnect** (Required for pushing to Anki)
   - Install AnkiConnect plugin in Anki (code: `2055492159`)
   - Fill in AnkiConnect URL in Ankismart settings (default: `http://127.0.0.1:8765`)
   - Test connection

3. **Start Using**
   - Import documents
   - Select generation strategy
   - Generate cards
   - Preview and edit
   - Export to Anki

For detailed configuration instructions, see [User Guide](docs/user-guide-en.md).

### 📚 Documentation

- **[User Guide](docs/user-guide-en.md)**: Complete usage instructions and feature introduction
- **[FAQ](docs/faq.md)**: Solutions for installation, configuration, and usage issues
- **[Example Documents](docs/examples/)**: Sample documents with math formulas

### 🛠️ Tech Stack

- **UI Framework**: PySide6 + QFluentWidgets
- **Document Conversion**: python-docx, python-pptx, pypdfium2
- **OCR Engine**: PaddleOCR + PaddlePaddle
- **LLM Integration**: OpenAI API (compatible format)
- **Anki Integration**: AnkiConnect + genanki
- **Configuration Management**: Pydantic + PyYAML
- **Encrypted Storage**: cryptography

### 📋 System Requirements

- **Operating System**: Windows 10/11, macOS 10.15+, Linux
- **Python Version**: 3.11 or higher
- **Memory**: 4GB+ (8GB+ recommended for OCR features)
- **Disk Space**: At least 2GB (OCR models ~500MB)

### 🤝 Contributing

Contributions, bug reports, and suggestions are welcome!

1. Fork this repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

### 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

### 🙏 Acknowledgments

- [Anki](https://apps.ankiweb.net/) - Powerful spaced repetition learning software
- [AnkiConnect](https://foosoft.net/projects/anki-connect/) - API plugin for Anki
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - Excellent OCR tool
- [QFluentWidgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) - Modern Qt component library
- [OpenAI](https://openai.com/) - Powerful LLM API provider

### 📧 Contact

- **Issues**: [GitHub Issues](https://github.com/your-repo/ankismart/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/ankismart/discussions)
- **Email**: your-email@example.com

---

<div align="center">

**Made with ❤️ by Ankismart Team**

⭐ Star us on GitHub if you find this project helpful!

</div>
