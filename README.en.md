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

Ankismart is a desktop tool for intelligent flashcard generation. Core flow:

`Import documents -> Convert to Markdown (with OCR) -> Generate cards -> Preview/Edit cards -> Push to Anki / Export APKG`

<p align="center">
  <img src="docs/images/workflow.svg" alt="Workflow" width="92%" />
</p>

## 1. Quick Start

### 1.1 Requirements

- Python `3.11+`

- `uv` is recommended (dependency install and running)

- Desktop Anki on Windows (for push)

- AnkiConnect add-on (for push)

### 1.2 Install and Run

```bash
uv sync
uv run ankismart
```

Or:

```bash
uv run python -m ankismart.ui.app
```

### 1.3 First-time Suggestions

1. Configure and test an LLM provider in Settings.
2. Configure and test AnkiConnect (URL/key/proxy).
3. Confirm OCR tier and download source before import.
4. Download OCR models when prompted on first PDF/image conversion.

## 2. AnkiConnect Configuration and Usage

### 2.1 Prerequisites

- Anki desktop is installed and running

- AnkiConnect add-on is installed

- `AnkiConnect URL` in Ankismart is reachable (default `http://127.0.0.1:8765`)

### 2.2 Settings

- `AnkiConnect URL`: AnkiConnect HTTP endpoint, default loopback address

- `AnkiConnect Key`: optional; if enabled in AnkiConnect, it must match

- `Proxy`: used for external requests when set manually; loopback (`127.0.0.1/localhost`) is direct by default

### 2.3 Push Modes

- `Create Only (create_only)`: only create new notes

- `Update Only (update_only)`: update existing notes only; fail if not found

- `Create or Update (create_or_update)`: update if found, create otherwise

### 2.4 Duplicate Check Strategy

- Scope: current deck / all decks

- Optional “allow duplicates” switch

- Duplicate logic is applied during push based on card fields and note model rules

### 2.5 Quick Self-check

1. Start Anki desktop and ensure AnkiConnect is enabled.
2. Click “Test Connection” in Ankismart Settings.
3. If failed, check URL, key, and proxy config first.

### 2.6 Common Issues

- Error: `Cannot connect to AnkiConnect`

  - Ensure Anki is running and AnkiConnect is enabled

  - Ensure URL and port are correct

- Error: `AnkiConnect error: ...`

  - Check key, field/model mapping, and deck name validity

- Export works but push does not

  - Usually AnkiConnect connectivity issue; APKG export does not depend on Anki runtime

## 3. Packaging and Release

### 3.1 One-command Build

```bash
uv run python packaging/build.py --clean
```

Build app directory + portable package only:

```bash
uv run python packaging/build.py --clean --skip-installer
```

## 4. Development Commands

Install dependencies:

```bash
uv sync
```

Run app:

```bash
uv run ankismart
```

Run tests:

```bash
uv run pytest -q
```

Run converter tests only:

```bash
uv run pytest tests/test_converter -q
```

Run lint:

```bash
uv run ruff check src tests
```

## 5. Common Environment Variables

- `ANKISMART_APP_DIR`: override app data directory

- `ANKISMART_CONFIG_PATH`: override config file path

- `ANKISMART_OCR_DEVICE`: `auto/cpu/gpu`

- `ANKISMART_OCR_MODEL_DIR`: OCR model root directory

- `ANKISMART_OCR_CPU_MKLDNN`: enable MKLDNN on CPU runtime

- `ANKISMART_OCR_CPU_THREADS`: CPU thread count

- `ANKISMART_OCR_PDF_RENDER_SCALE`: PDF render scale

- `ANKISMART_CUDA_CACHE_TTL_SECONDS`: CUDA detection cache TTL

## 6. Project Structure

```text
src/ankismart/
├─ ui/                 # PyQt6 pages and interactions
├─ converter/          # document parsing, OCR, cache, type detection
├─ card_gen/           # LLM generation and post-processing
├─ anki_gateway/       # AnkiConnect / APKG export
└─ core/               # config, logging, errors, tracing

packaging/             # PyInstaller + Inno Setup scripts
tests/                 # unit and regression tests
docs/                  # docs and images
```

## 7. Tech Stack

- UI: PyQt6 + PyQt-Fluent-Widgets

- OCR: PaddleOCR + PaddlePaddle

- Document processing: python-docx / python-pptx / pypdfium2

- LLM: OpenAI-compatible API (multi-provider)

- Anki integration: AnkiConnect + genanki

