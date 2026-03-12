from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_build_module():
    build_path = Path(__file__).resolve().parents[1] / "packaging" / "build.py"
    spec = importlib.util.spec_from_file_location("ankismart_packaging_build", build_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_verify_runtime_dirs_requires_standard_runtime_folders(tmp_path) -> None:
    build = _load_build_module()
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "config").mkdir()
    (app_dir / "data").mkdir()
    (app_dir / "logs").mkdir()

    with pytest.raises(RuntimeError, match="cache"):
        build.verify_runtime_dirs(app_dir)


def test_smoke_test_release_checks_staged_and_portable_layout(tmp_path, monkeypatch) -> None:
    build = _load_build_module()
    version = "9.9.9"
    staged_app_dir = tmp_path / "release" / "app"
    portable_dir = tmp_path / "release" / "portable" / f"Ankismart-Portable-{version}"

    for target_dir in (staged_app_dir, portable_dir):
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / build.APP_EXE_NAME).write_text("exe", encoding="utf-8")
        for name in ("config", "data", "logs", "cache"):
            (target_dir / name).mkdir()

    monkeypatch.setattr(build, "STAGED_APP_DIR", staged_app_dir)
    monkeypatch.setattr(build, "PORTABLE_ROOT", portable_dir.parent)

    build.smoke_test_release(version)


def test_console_safe_text_replaces_unencodable_characters() -> None:
    build = _load_build_module()

    text = build._console_safe_text("[build] 版本: 0.1.6", encoding="cp1252")

    assert text == "[build] ??: 0.1.6"
