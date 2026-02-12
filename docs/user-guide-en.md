# Ankismart User Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation & Configuration](#installation--configuration)
3. [Quick Start](#quick-start)
4. [Features](#features)
5. [Card Generation Strategies](#card-generation-strategies)
6. [Math Formula Support](#math-formula-support)
7. [Long Document Splitting](#long-document-splitting)
8. [FAQ](#faq)

---

## Introduction

Ankismart is an intelligent Anki flashcard generation tool that automatically converts various document formats into high-quality Anki learning cards.

### Key Features

- **Multi-format Support**: Supports Markdown, Word (DOCX), PowerPoint (PPTX), PDF, images, and more
- **Intelligent OCR**: Built-in PaddleOCR for automatic text recognition from images and PDFs
- **8 Generation Strategies**: Multiple card generation strategies for different learning scenarios
- **Math Formula Support**: Full LaTeX math formula support with MathJax rendering
- **Batch Processing**: Import multiple documents at once for batch card generation
- **Real-time Preview**: Preview and edit each card before generation
- **Flexible Export**: Push directly to Anki or export as .apkg files
- **Multi-language Interface**: Supports Chinese and English interfaces

---

## Installation & Configuration

### System Requirements

- **Operating System**: Windows 10/11, macOS, Linux
- **Python Version**: Python 3.11 or higher
- **Memory**: 4GB+ recommended (8GB+ for OCR features)
- **Disk Space**: At least 2GB (OCR models ~500MB)

### Installation Steps

#### Method 1: Using Pre-compiled Version (Recommended)

1. Download the latest version from the [Releases](https://github.com/your-repo/ankismart/releases) page
2. Extract to any directory
3. Run `Ankismart.exe` (Windows) or the corresponding executable

#### Method 2: Install from Source

```bash
# 1. Clone the repository
git clone https://github.com/your-repo/ankismart.git
cd ankismart

# 2. Create virtual environment
python -m venv .venv

# 3. Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 4. Install dependencies
pip install -e .

# 5. Run the application
python -m ankismart.ui.app
```

### Initial Configuration

After launching Ankismart for the first time, you need to configure the following:

#### 1. Configure LLM Provider

Ankismart uses Large Language Models (LLM) to generate cards. You need to configure at least one LLM provider.

1. Click the **"Settings"** icon in the left navigation bar
2. In the **"LLM Configuration"** section, click **"Add Provider"**
3. Fill in the following information:
   - **Provider Name**: e.g., "OpenAI", "DeepSeek", etc.
   - **Base URL**: API endpoint address
   - **API Key**: Your API key
   - **Model**: Model name to use
   - **RPM Limit**: Requests per minute limit (optional, 0 = unlimited)

**Common Provider Configuration Examples:**

| Provider | Base URL | Recommended Models |
|----------|----------|-------------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o`, `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Zhipu AI | `https://open.bigmodel.cn/api/paas/v4` | `glm-4` |
| Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-turbo` |
| Ollama (Local) | `http://localhost:11434/v1` | `llama3`, `qwen2` |

4. Click **"Save"**
5. Click **"Test"** to verify the connection
6. Click **"Activate"** to set as the current provider

#### 2. Configure AnkiConnect

To push cards directly to Anki, you need to install and configure the AnkiConnect plugin.

**Install AnkiConnect:**

1. Open Anki desktop application
2. Select **Tools → Add-ons → Get Add-ons**
3. Enter plugin code: `2055492159`
4. Restart Anki

**Configure AnkiConnect:**

1. In Ankismart settings page, find the **"Anki Configuration"** section
2. Fill in the following information:
   - **AnkiConnect URL**: Default is `http://127.0.0.1:8765`
   - **AnkiConnect Key**: If you set a key in Anki, enter it here (optional)
   - **Default Deck**: Default deck name for new cards (e.g., "Default")
   - **Default Tags**: Default tags for new cards, comma-separated (e.g., "ankismart, imported")

3. Click **"Test Connection"** to verify the configuration
4. Click **"Save Configuration"**

#### 3. Other Settings (Optional)

- **Theme**: Choose light, dark, or auto theme
- **Language**: Choose Chinese or English interface
- **Proxy Settings**: If you need to access LLM API through a proxy, enter the proxy URL
- **OCR Correction**: Enable to use LLM for automatic OCR error correction (increases API calls)
- **LLM Parameters**:
  - **Temperature**: Controls generation randomness (0.0 = deterministic, 2.0 = creative), recommended 0.3-0.7
  - **Max Tokens**: Maximum tokens to generate, 0 = use provider default

---

## Quick Start

### Basic Workflow

```
Import Documents → Select Strategy → Generate Cards → Preview & Edit → Export to Anki
```

### Step-by-Step Guide

#### 1. Import Documents

1. Click the **"Import"** icon in the left navigation bar
2. Add documents using one of the following methods:
   - Click **"Select Files"** button to browse files
   - Drag and drop files directly into the file list area
3. Supported file formats:
   - Markdown (`.md`)
   - Word documents (`.docx`)
   - PowerPoint presentations (`.pptx`)
   - PDF documents (`.pdf`)
   - Images (`.png`, `.jpg`, `.jpeg`, `.bmp`)
   - Plain text (`.txt`)

#### 2. Configure Generation Options

At the bottom of the import page, configure the following options:

- **Target Deck**: Select or enter the target Anki deck name
- **Tags**: Add tags for generated cards, comma-separated
- **Generation Strategy**: Choose an appropriate card generation strategy (see [Card Generation Strategies](#card-generation-strategies))
- **Update Mode**:
  - **Add New Cards Only**: Only add new cards, don't modify existing ones
  - **Update Existing Cards**: Update existing card content

#### 3. Generate Cards

1. Click the **"Start Generation"** button
2. Wait for document conversion and card generation (progress bar shows current status)
3. Automatically navigate to preview page when complete

#### 4. Preview and Edit

On the preview page, you can:

- **View All Cards**: Left panel shows all generated cards
- **Edit Card Content**:
  - Click a card to view details
  - Click **"Edit"** button to modify front and back content
  - Supports Markdown and LaTeX formulas
- **Delete Cards**: Click **"Delete"** button to remove unwanted cards
- **Real-time Preview**: Right panel shows rendered card effect

#### 5. Export Cards

After preview and confirmation, choose an export method:

- **Push to Anki**: Click **"Push to Anki"** button to add cards directly to Anki (requires Anki running with AnkiConnect configured)
- **Export as .apkg**: Click **"Export APKG"** button to save as Anki package file for manual import later

---

## Features

### Document Conversion

Ankismart automatically detects document type and uses the appropriate converter:

#### Markdown Documents
- Preserves original format and structure
- Supports code blocks, tables, lists, etc.
- Automatically extracts math formulas

#### Word Documents (DOCX)
- Extracts text content and basic formatting
- Preserves heading hierarchy
- Supports tables and lists

#### PowerPoint (PPTX)
- Extracts content page by page
- Preserves titles and body text
- Extracts notes content

#### PDF and Images
- Uses PaddleOCR for text recognition
- Supports mixed Chinese and English recognition
- Optional LLM correction for improved accuracy
- Automatically downloads OCR models on first use (~500MB)

#### Plain Text (TXT)
- Automatically detects encoding (supports UTF-8, GBK, etc.)
- Preserves original format

### Batch Processing

Ankismart supports processing multiple documents at once:

1. Add multiple files on the import page
2. All files will use the same generation strategy and configuration
3. Generated cards are merged into the same preview list
4. Can export together or process separately

### Card Editing

On the preview page, each card can be edited individually:

- **Markdown Support**: Use Markdown syntax to format text
- **Formula Editing**: Use `$...$` or `$$...$$` to insert LaTeX formulas
- **Real-time Preview**: Right panel shows rendered effect while editing
- **Undo/Redo**: Supports edit history

### Export Options

#### Push to Anki
- Requires Anki to be running
- Automatically creates non-existent decks
- Supports updating existing cards
- Automatically adds tags

#### Export APKG
- Generates standard Anki package file
- Can be imported on any device
- Includes all card data and formatting
- Supports math formula rendering

---

## Card Generation Strategies

Ankismart provides 8 card generation strategies for different learning scenarios and content types.

### 1. Basic Q&A

**Use Cases:**
- General learning materials
- Conceptual knowledge
- Factual information

**Card Format:**
- Front: Question
- Back: Answer

**Example:**
```
Front: What is photosynthesis?
Back: Photosynthesis is the process by which plants convert light energy into chemical energy, producing glucose and oxygen from CO2 and water.
```

**Features:**
- Concise and clear questions
- Direct and informative answers
- Suitable for quick review

### 2. Cloze Deletion

**Use Cases:**
- Memorizing key terms
- Definitions and formulas
- Important numbers and dates

**Card Format:**
- Uses `{{c1::content}}` syntax for cloze deletions
- Supports multiple deletions `{{c1::...}}`, `{{c2::...}}`

**Example:**
```
Photosynthesis converts {{c1::light energy}} into {{c2::chemical energy}}, producing glucose.
```

**Features:**
- Complete context
- Precise memorization of key information
- Suitable for terms and definitions

### 3. Image-based Q&A

**Use Cases:**
- Charts and diagrams
- Annotated images
- Visual learning materials

**Card Format:**
- Front: Question about image elements
- Back: Answer with location and relationship description

**Example:**
```
Front: In the cell diagram, what organelle is responsible for energy production?
Back: Mitochondria - located in the cytoplasm, converts nutrients into ATP.
```

**Features:**
- Emphasizes visual elements
- Includes spatial relationships
- Suitable for illustrated content

### 4. Concept Explanation

**Use Cases:**
- Deep understanding of concepts
- Theoretical knowledge
- Topics requiring detailed explanation

**Card Format:**
- Front: Concept name
- Back: Detailed explanation (principle, significance, example)

**Example:**
```
Front: Photosynthesis
Back: Photosynthesis is the biological process by which green plants convert light energy into chemical energy. It occurs in chloroplasts via two stages: light-dependent reactions (in thylakoids) and the Calvin cycle (in stroma). Significance: it is the primary source of oxygen and organic matter on Earth. Example: leaves appear green because chlorophyll reflects green light while absorbing red and blue.
```

**Features:**
- Comprehensive and in-depth explanation
- Includes principles and examples
- Suitable for understanding-based learning

### 5. Key Terms

**Use Cases:**
- Professional terminology learning
- Vocabulary building
- Technical documentation

**Card Format:**
- Front: Term
- Back: Definition + example sentence

**Example:**
```
Front: Chloroplast
Back: Definition: A membrane-bound organelle found in plant cells that is the site of photosynthesis. It contains chlorophyll, which captures light energy.

Example: "The chloroplasts in leaf cells give plants their green color and enable them to produce glucose from sunlight."
```

**Features:**
- Accurate definitions
- Provides usage context
- Suitable for term memorization

### 6. Single Choice

**Use Cases:**
- Exam preparation
- Knowledge testing
- Distinguishing similar concepts

**Card Format:**
- Front: Question + 4 options (A/B/C/D)
- Back: Correct answer + brief explanation

**Example:**
```
Front: What is the derivative of $f(x) = x^3$?

A. $2x^2$
B. $3x^2$
C. $x^2$
D. $3x$

Back: B

Using the power rule $\frac{d}{dx}(x^n) = nx^{n-1}$, we get $f'(x) = 3x^2$.
```

**Features:**
- Simulates exam scenarios
- Trains discrimination ability
- Includes problem-solving approach

### 7. Multiple Choice

**Use Cases:**
- Complex knowledge points
- Multiple correct answers
- Comprehensive testing

**Card Format:**
- Front: Question + 4-5 options
- Back: All correct answers + explanation

**Example:**
```
Front: Which of the following are solutions to $x^2 - 5x + 6 = 0$?

A. $x = 1$
B. $x = 2$
C. $x = 3$
D. $x = 6$

Back: B, C

Factoring gives $(x-2)(x-3) = 0$, so $x = 2$ or $x = 3$.
```

**Features:**
- Tests comprehensiveness
- Combines multiple knowledge points
- Suitable for comprehensive review

### 8. Custom Strategy

**Use Cases:**
- Special requirements
- Custom formats
- Experimental purposes

**Description:**
- Can customize generation logic by modifying prompts
- Requires some technical background
- See developer documentation for details

---

## Math Formula Support

Ankismart fully supports LaTeX math formulas, rendered with MathJax in Anki.

### Formula Syntax

#### Inline Formulas
Use single `$` to wrap:

```
Pythagorean theorem: $a^2 + b^2 = c^2$
```

Rendered: Pythagorean theorem: $a^2 + b^2 = c^2$

#### Display Formulas
Use double `$$` to wrap:

```
$$
\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}
$$
```

Rendered:
$$
\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}
$$

### Common Formula Examples

#### Fractions
```
$\frac{a}{b}$, $\frac{dy}{dx}$
```

#### Superscripts and Subscripts
```
$x^2$, $x_i$, $x^{2n}$, $x_{i,j}$
```

#### Roots
```
$\sqrt{2}$, $\sqrt[3]{8}$
```

#### Summation and Integration
```
$\sum_{i=1}^{n} x_i$, $\int_a^b f(x) dx$
```

#### Greek Letters
```
$\alpha$, $\beta$, $\gamma$, $\Delta$, $\pi$, $\Omega$
```

#### Matrices
```
$$
\begin{pmatrix}
a & b \\
c & d
\end{pmatrix}
$$
```

#### Systems of Equations
```
$$
\begin{cases}
x + y = 5 \\
2x - y = 1
\end{cases}
$$
```

### Notes

1. **Escape Characters**: In JSON, backslashes need double escaping, e.g., `\\frac` instead of `\frac`
2. **Anki Configuration**: Ensure Anki has MathJax support enabled (enabled by default)
3. **Preview**: Real-time formula rendering preview available in Ankismart preview page
4. **Compatibility**: Generated cards display correctly in Anki desktop, AnkiWeb, and mobile apps

---

## Long Document Splitting

For very long documents, Ankismart provides an experimental automatic splitting feature.

### Feature Description

When document character count exceeds the set threshold, automatically split the document into multiple segments, generate cards separately, and merge results.

### How to Enable

1. Go to **Settings** page
2. Find the **"Experimental Features"** section
3. Enable **"Enable Long Document Auto-split"**
4. Set **"Split Threshold"** (default 70,000 characters)
5. Click **"Save Configuration"**

### How It Works

1. Detect document length
2. If exceeds threshold, intelligently split by paragraphs
3. Generate cards for each segment independently
4. Merge cards from all segments
5. Deduplicate and optimize

### Notes

⚠️ **Warning: This is an experimental feature and may affect card quality and generation time.**

- **Advantages**:
  - Can process very long documents
  - Avoids LLM context length limitations
  - Improves generation success rate

- **Disadvantages**:
  - May lose cross-segment context
  - Longer generation time
  - Increased API calls
  - May produce duplicate cards

- **Recommendations**:
  - Only enable when processing very long documents
  - Prefer manual document splitting
  - Carefully check card quality after generation
  - Adjust threshold based on document type

---

## FAQ

### Installation and Configuration

**Q: What to do when OCR models are missing on first run?**

A: Ankismart will automatically download models (~500MB) on first OCR use. Ensure network connection is stable and wait for download to complete. If download fails, you can manually download model files and place them in the `~/.paddleocr/` directory.

**Q: How to configure a proxy?**

A: In the settings page "Other Settings" section, enter the proxy URL in the format `http://proxy.example.com:8080` or `socks5://proxy.example.com:1080`.

**Q: Which LLM providers are supported?**

A: Ankismart supports all providers compatible with OpenAI API format, including OpenAI, DeepSeek, Moonshot, Zhipu AI, Qwen, Ollama, etc. Just enter the correct API endpoint and key.

### Usage Issues

**Q: Too few or too many cards generated?**

A: Card count is automatically determined by the LLM based on content density (typically 3-10 cards). If unsatisfied, you can:
- Adjust document content detail level
- Try different generation strategies
- Manually add or delete cards on the preview page

**Q: OCR recognition is inaccurate?**

A: Try the following methods:
- Enable "OCR Correction" feature (in settings)
- Use higher resolution images or PDFs
- Ensure text is clear with high contrast
- Manually edit recognition results

**Q: Math formulas not displaying correctly?**

A: Check the following:
- Ensure correct LaTeX syntax is used
- Use `$...$` for inline formulas, `$$...$$` for display formulas
- Check rendering effect in Ankismart preview page
- Ensure Anki has MathJax support enabled

**Q: Push to Anki failed?**

A: Please check:
- Is Anki running?
- Is AnkiConnect plugin installed? (code: 2055492159)
- Is AnkiConnect URL correct? (default `http://127.0.0.1:8765`)
- Is firewall blocking the connection?
- Click "Test Connection" in settings page to verify configuration

**Q: How to update existing cards?**

A: On the import page, select "Update Mode" as "Update Existing Cards". Ankismart will match existing cards based on content and update them.

### Performance Issues

**Q: Card generation is very slow?**

A: Possible causes and solutions:
- **Network Latency**: Check network connection, consider using domestic LLM providers
- **Document Too Long**: Enable long document splitting feature, or manually split document
- **OCR Processing**: OCR recognition takes time, please be patient
- **Slow LLM Response**: Try switching providers or models

**Q: Application uses too much memory?**

A: OCR features use significant memory (especially when processing large images). Recommendations:
- Close unnecessary applications
- Restart application after processing to free memory
- Use smaller images or PDFs

### Other Issues

**Q: How to backup configuration?**

A: Configuration file is located at:
- Windows: `%USERPROFILE%\.local\ankismart\config.yaml`
- macOS/Linux: `~/.local/ankismart/config.yaml`

Copy this file to backup configuration.

**Q: How to reset all settings?**

A: In settings page, click "Reset Settings" → "Restore Defaults", or delete the configuration file and restart the application.

**Q: Which languages are supported?**

A: Interface supports Chinese and English. Card content language is determined by source document, and LLM will automatically match document language to generate cards.

**Q: How to report bugs or make suggestions?**

A: Please visit [GitHub Issues](https://github.com/your-repo/ankismart/issues) to submit issues or suggestions.

---

## Get Help

- **Documentation**: [Full Documentation](https://github.com/your-repo/ankismart/docs)
- **FAQ**: [Frequently Asked Questions](./faq.md)
- **Issues**: [GitHub Issues](https://github.com/your-repo/ankismart/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/ankismart/discussions)

---

**Version**: v0.1.0
**Last Updated**: 2026-02-12
