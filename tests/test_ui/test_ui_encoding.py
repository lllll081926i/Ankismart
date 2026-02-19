from __future__ import annotations

from pathlib import Path


def test_ui_python_files_are_utf8_encoded() -> None:
    ui_root = Path("src/ankismart/ui")
    files = list(ui_root.rglob("*.py"))
    assert files, f"No Python files found under {ui_root}"

    for file_path in files:
        file_path.read_text(encoding="utf-8")
