from __future__ import annotations

from pathlib import Path


def test_ui_python_files_are_utf8_encoded() -> None:
    ui_root = Path("src/ankismart/ui")
    for file_path in ui_root.rglob("*.py"):
        file_path.read_text(encoding="utf-8")

