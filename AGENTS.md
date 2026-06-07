# Repository Guidelines

## Project Structure & Module Organization
Core code lives in `src/ankismart/`:
- `ui/`: PyQt6 pages, workers, and interaction flow.
- `converter/`: document parsing, OCR pipeline, and format detection.
- `card_gen/`: LLM card generation and post-processing.
- `anki_gateway/`: AnkiConnect integration and APKG export.
- `core/`: config, logging, error models, and tracing.

Tests are under `tests/` (unit/integration) and `tests/e2e/` (workflow-level scenarios with page objects). Packaging scripts are in `packaging/`, while docs and examples are in `docs/` and `examples/`.

## Build, Test, and Development Commands
- `uv sync --group dev`: install runtime + dev dependencies.
- `uv run ankismart`: launch the desktop app.
- `uv run pytest tests --ignore=tests/e2e -q --maxfail=1`: run unit/integration suite.
- `uv run pytest tests/e2e/scenarios -m "fast" -q --maxfail=1`: run fast E2E layer.
- `uv run pytest tests/e2e/gate -m "p0 and gate_real" -q --maxfail=1`: run gate-real smoke path.
- `uv run ruff check src tests`: lint + import/order checks.
- `uv run ruff format src tests`: apply formatting.
- `uv run python packaging/build.py --clean`: build portable + installer artifacts.

For headless CI-style runs, set `QT_QPA_PLATFORM=offscreen`.

## Coding Style & Naming Conventions
Use Python 3.11+ and follow Ruff config in `pyproject.toml` (`line-length = 100`, rules `E,F,I,N,W`). Prefer:
- `snake_case` for modules/functions/variables.
- `PascalCase` for classes.
- `UPPER_SNAKE_CASE` for constants.

Keep imports grouped (stdlib, third-party, local) and add type hints for public APIs.

## Testing Guidelines
Framework: `pytest` with markers `p0`, `p1`, `fast`, `gate`, `gate_real`. Name tests as `test_*.py` and keep module-aligned folders (for example `tests/test_converter/`, `tests/test_ui/`).

Coverage expectations:
- Global configured threshold: `75%` (`tool.coverage.report.fail_under`).
- UI risk gate in CI: `50%` for selected UI modules.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commits (`feat:`, `fix:`, `chore:`, `test:`, `release:`), often with optional scope (for example `feat(ui): ...`).

Before opening a PR:
1. Run lint, format, and relevant tests locally.
2. Keep PR description focused on behavior changes and risk.
3. Link related issues (for example `Closes #123`).
4. Include screenshots or short recordings for UI changes.
5. Ensure GitHub Actions quality gates pass.

## Security & Configuration Tips
Do not commit API keys or local runtime configs. Store sensitive settings in local config paths (for example `.local/`) or environment variables, and verify AnkiConnect/OCR settings locally before release validation.
