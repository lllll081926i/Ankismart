from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load_build_module():
    build_path = Path(__file__).resolve().parents[1] / "packaging" / "build.py"
    spec = importlib.util.spec_from_file_location("ankismart_packaging_build", build_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_script_module(relative_path: str, module_name: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
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
    (portable_dir / ".portable").write_text("", encoding="utf-8")

    monkeypatch.setattr(build, "STAGED_APP_DIR", staged_app_dir)
    monkeypatch.setattr(build, "PORTABLE_ROOT", portable_dir.parent)

    build.smoke_test_release(version)


def test_smoke_test_release_requires_portable_marker(tmp_path, monkeypatch) -> None:
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

    with pytest.raises(RuntimeError, match="\\.portable"):
        build.smoke_test_release(version)


def test_create_portable_package_writes_portable_marker(tmp_path, monkeypatch) -> None:
    build = _load_build_module()
    version = "9.9.9"
    staged_app_dir = tmp_path / "release" / "app"
    portable_root = tmp_path / "release" / "portable"

    staged_app_dir.mkdir(parents=True, exist_ok=True)
    (staged_app_dir / build.APP_EXE_NAME).write_text("exe", encoding="utf-8")
    for name in ("config", "data", "logs", "cache"):
        (staged_app_dir / name).mkdir()

    monkeypatch.setattr(build, "STAGED_APP_DIR", staged_app_dir)
    monkeypatch.setattr(build, "PORTABLE_ROOT", portable_root)

    portable_dir = build.create_portable_package(version)

    assert portable_dir == portable_root / f"Ankismart-Portable-{version}"
    assert (portable_dir / ".portable").exists()


def test_build_release_metadata_uses_stable_channel_and_gate_checklist() -> None:
    build = _load_build_module()

    metadata = build.build_release_metadata("9.9.9")

    assert metadata["version"] == "9.9.9"
    assert metadata["channel"] == "stable"
    assert "task recovery smoke passed" in metadata["checklist"]
    assert "fast e2e passed" in metadata["checklist"]
    assert "gate real passed" in metadata["checklist"]
    assert "portable build verified" in metadata["checklist"]


def test_console_safe_text_replaces_unencodable_characters() -> None:
    build = _load_build_module()

    text = build._console_safe_text("[build] 版本: 0.1.6", encoding="cp1252")

    assert text == "[build] ??: 0.1.6"


def test_installer_script_defaults_to_chinese_and_customizes_wizard_copy() -> None:
    iss_path = Path(__file__).resolve().parents[1] / "packaging" / "ankismart.iss"
    content = iss_path.read_text(encoding="utf-8")
    zh_lang_path = (
        Path(__file__).resolve().parents[1]
        / "packaging"
        / "languages"
        / "ChineseSimplified.isl"
    )

    assert (
        'Name: "chinesesimplified"; MessagesFile: '
        '"{#ProjectRoot}\\packaging\\languages\\ChineseSimplified.isl"'
        in content
    )
    assert 'Name: "english"; MessagesFile: "compiler:Default.isl"' in content
    assert zh_lang_path.exists()
    assert 'LanguageDetectionMethod=none' in content
    assert 'ShowLanguageDialog=yes' in content
    assert 'UsePreviousLanguage=no' in content
    assert 'chinesesimplified.WelcomeHeadline=' in content
    assert 'chinesesimplified.FinishedHeadline=' in content
    assert 'procedure InitializeWizard();' in content


def test_installer_script_adds_optional_uninstall_user_data_cleanup() -> None:
    iss_path = Path(__file__).resolve().parents[1] / "packaging" / "ankismart.iss"
    content = iss_path.read_text(encoding="utf-8")

    assert 'chinesesimplified.RemoveUserDataOnUninstall=' in content
    assert 'english.RemoveUserDataOnUninstall=' in content
    assert 'RemoveUserDataCheck := TNewCheckBox.Create' in content
    assert 'RemoveUserDataCheck.Checked := False' in content
    assert "ExpandConstant('{localappdata}\\ankismart')" in content
    assert "DelTree(userDataDir, True, True, True)" in content


def test_installer_script_uses_directory_page_and_finish_page_options() -> None:
    iss_path = Path(__file__).resolve().parents[1] / "packaging" / "ankismart.iss"
    content = iss_path.read_text(encoding="utf-8")

    assert "DisableProgramGroupPage=yes" in content
    assert "DefaultDirName={localappdata}\\{#MyAppName}" in content
    assert '[Tasks]' not in content
    assert 'Tasks: desktopicon' not in content
    assert "function ShouldSkipPage(PageID: Integer): Boolean;" in content
    assert "PageID = wpWelcome" in content
    assert "PageID = wpReady" in content
    assert "DesktopIconCheck := TNewCheckBox.Create(WizardForm.FinishedPage)" in content
    assert "DesktopIconCheck.Checked := True" in content
    assert "DesktopIconCheck.Height := ScaleY(26)" in content
    assert (
        "DesktopIconCheck.Top := WizardForm.FinishedLabel.Top + "
        "WizardForm.FinishedLabel.Height + ScaleY(16)"
    ) in content
    assert "LaunchAppCheck := TNewCheckBox.Create(WizardForm.FinishedPage)" in content
    assert "LaunchAppCheck.Checked := False" in content
    assert "LaunchAppCheck.Height := ScaleY(26)" in content
    assert (
        "LaunchAppCheck.Top := DesktopIconCheck.Top + "
        "DesktopIconCheck.Height + ScaleY(6)"
    ) in content
    assert "WizardForm.RunList.Visible := False" in content
    assert "WizardForm.RunList.Height := 0" in content
    assert "WizardForm.RunList.Checked[0] := LaunchAppCheck.Checked" in content
    assert "if CurPageID = wpFinished then" in content
    assert "WizardForm.RunList.Visible := False;" in content
    assert "WizardForm.RunList.Height := 0;" in content
    assert "WizardForm.RunList.Checked[1] := False" not in content
    assert 'chinesesimplified.OpenInstallDirOnFinish=' not in content
    assert 'english.OpenInstallDirOnFinish=' not in content
    assert 'Description: "{cm:OpenInstallDirOnFinish}"' not in content


def test_dev_demo_script_builds_demo_payload_without_entering_release_bundle() -> None:
    demo = _load_script_module("scripts/dev_demo.py", "ankismart_dev_demo")
    spec_path = Path(__file__).resolve().parents[1] / "packaging" / "ankismart.spec"
    spec_content = spec_path.read_text(encoding="utf-8")

    payload = demo.build_demo_payload()

    assert len(payload.file_paths) >= 3
    assert all(path.exists() for path in payload.file_paths)
    assert len(payload.batch_result.documents) == len(payload.file_paths)
    assert len(payload.cards) >= 5
    assert payload.push_result.total == len(payload.cards)
    assert payload.push_result.succeeded > 0
    assert "scripts/dev_demo.py" not in spec_content
