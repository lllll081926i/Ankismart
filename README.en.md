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

---

Ankismart is a PyQt6 desktop app for smart card generation: import documents -> extract content (with OCR) -> generate Anki cards -> preview/edit -> push or export APKG.

<p align="center">
  <img src="docs/images/workflow.svg" alt="Workflow" width="92%" />
</p>

### Core Capabilities

- Multi-format import: `md`, `txt`, `docx`, `pptx`, `pdf`, images
- Smart OCR: on-demand local model download (models are not bundled), with model tier switching
- Card generation: multiple card types and mixed strategy ratios
- Result review: batch edit tags/decks, retry failed items, export APKG
- Theme and UI: sidebar theme switch (Light / Dark / Follow System)

### Prerequisites

- Python `3.11+`
- `uv` is recommended for environment and dependency management
- Desktop Anki installed, with AnkiConnect enabled (default port `8765`)
- At least one available LLM provider configured in Settings (model, endpoint, API key)
- For PDF/image conversion, OCR models are downloaded on demand at first use

### Application Flow

1. Start the app and load local configuration (theme, language, LLM provider, Anki connection, OCR settings).
2. On the Import page, choose files and set deck, tags, target total cards, and strategy ratios.
3. Convert documents in batch: group by file type, convert text files directly, run OCR for PDF/images, and output Markdown.
4. Review and edit Markdown on the Preview page.
5. During generation, the app first converts "strategy ratios + target total" into exact per-strategy counts locally, then distributes them across documents.
6. LLM requests are sent per strategy with `target_count`, and prompts explicitly include `Generate exactly N cards`.
7. Model output is parsed and post-processed into normalized card drafts.
8. In Card Preview, inspect, filter, and refine cards by type.
9. Push to Anki (create only / update only / create or update) with per-card result tracking.
10. In Result, review statistics, retry failed cards, repush edited cards, or export APKG.

### Quick Start

#### 1) Setup

- `uv` is recommended for Python environment management

#### 2) Install and Run

```bash
uv sync
uv run python -m ankismart.ui.app
```

#### 3) First-time Configuration

- Test LLM provider connectivity in Settings
- Test AnkiConnect connectivity (make sure Anki is running)
- Return to Import page and start batch card generation

### Packaging (Installer + Portable)

The project provides a one-command build flow to produce:

- Installer (Inno Setup, optional)
- Portable package (ZIP)

```bash
# Full build (installer is generated if Inno Setup is installed)
uv run python packaging/build.py --clean

# Build app distribution + portable package only
uv run python packaging/build.py --clean --skip-installer
```

Output layout:

```text
dist/release/
├─ app/                      # installer source folder (without OCR models)
├─ portable/
│  ├─ Ankismart-Portable-x.y.z/
│  └─ Ankismart-Portable-x.y.z.zip
└─ installer/
   └─ Ankismart-Setup-x.y.z.exe
```

### FAQ

- Cannot connect to AnkiConnect
  - Ensure Anki is running, AnkiConnect is installed, and URL/key are correct
- Unexpected generated card count
  - Check target total and strategy ratios; at least one strategy ratio must be greater than 0
- OCR is unavailable
  - Ensure you are using the full package and complete OCR model download on first run

### Tech Stack

- UI: PyQt6 + PyQt-Fluent-Widgets
- OCR: PaddleOCR + PaddlePaddle
- Document processing: python-docx / python-pptx / pypdfium2
- LLM: OpenAI-compatible API
- Anki integration: AnkiConnect + genanki
