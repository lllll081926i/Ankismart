from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
RELEASE_DIR = DIST_DIR / "release"

APP_BUILD_DIR = DIST_DIR / "Ankismart"
STAGED_APP_DIR = RELEASE_DIR / "app"
PORTABLE_ROOT = RELEASE_DIR / "portable"
INSTALLER_ROOT = RELEASE_DIR / "installer"
APP_EXE_NAME = "Ankismart.exe"

OCR_MODEL_DIR_NAMES = {
    "model",
    "models",
    "inference",
    ".paddleocr",
    "paddleocr_models",
    "ocr_models",
}

OCR_MODEL_EXTENSIONS = {
    ".pdmodel",
    ".pdiparams",
    ".onnx",
    ".nb",
}

UNUSED_DEPENDENCY_DIRS = {
    "matplotlib",
    "pandas",
    "sklearn",
    "jupyter",
    "notebook",
    "IPython",
    "PyQt5",
    "PySide2",
    "PySide6",
    "tkinter",
    "paddle",
    "paddleocr",
    "paddlex",
    "cv2",
}

PADDLE_RELATED_KEYWORDS = ("paddle", "paddlex", "paddleocr", "cv2")


def _print(msg: str) -> None:
    print(f"[build] {msg}")


def run(cmd: list[str], description: str) -> None:
    _print(f"{description}: {' '.join(str(item) for item in cmd)}")
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def clean() -> None:
    for path in (BUILD_DIR, DIST_DIR):
        if path.exists():
            _print(f"清理目录: {path}")
            shutil.rmtree(path)


def pyinstaller_build(spec_file: Path) -> None:
    if not spec_file.exists():
        raise FileNotFoundError(f"未找到 spec 文件: {spec_file}")

    run([sys.executable, "-m", "PyInstaller", "--clean", "-y", str(spec_file)], "执行 PyInstaller")

    if not APP_BUILD_DIR.exists():
        raise FileNotFoundError(f"PyInstaller 输出目录不存在: {APP_BUILD_DIR}")


def ensure_runtime_dirs(target_dir: Path) -> None:
    for name in ("config", "data", "logs", "cache"):
        (target_dir / name).mkdir(parents=True, exist_ok=True)


def remove_ocr_model_artifacts(target_dir: Path) -> tuple[int, int]:
    removed_dirs = 0
    removed_files = 0

    dir_candidates = [
        p for p in target_dir.rglob("*") if p.is_dir() and p.name.lower() in OCR_MODEL_DIR_NAMES
    ]
    for path in sorted(dir_candidates, key=lambda p: len(p.parts), reverse=True):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)
            removed_dirs += 1

    file_candidates = [
        p for p in target_dir.rglob("*") if p.is_file() and p.suffix.lower() in OCR_MODEL_EXTENSIONS
    ]
    for path in file_candidates:
        path.unlink(missing_ok=True)
        removed_files += 1

    return removed_dirs, removed_files


def prune_unused_dependencies(target_dir: Path) -> None:
    # 清理未使用的依赖目录
    for dep_name in UNUSED_DEPENDENCY_DIRS:
        for path in target_dir.rglob(dep_name):
            if path.is_dir():
                _print(f"移除未使用依赖: {path.relative_to(target_dir)}")
                shutil.rmtree(path, ignore_errors=True)

    # 清理所有 paddle 相关的 dist-info 目录
    for path in target_dir.rglob("*.dist-info"):
        if path.is_dir():
            name_lower = path.name.lower()
            if any(keyword in name_lower for keyword in PADDLE_RELATED_KEYWORDS):
                _print(f"移除 paddle dist-info: {path.relative_to(target_dir)}")
                shutil.rmtree(path, ignore_errors=True)

    # 清理 __pycache__
    for path in target_dir.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

    # 清理编译文件
    for extension in ("*.pyc", "*.pyo", "*.pyd.debug"):
        for path in target_dir.rglob(extension):
            if path.is_file():
                path.unlink(missing_ok=True)


def stage_app_files() -> None:
    if STAGED_APP_DIR.exists():
        shutil.rmtree(STAGED_APP_DIR)

    STAGED_APP_DIR.mkdir(parents=True, exist_ok=True)

    for item in APP_BUILD_DIR.iterdir():
        destination = STAGED_APP_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)

    staged_exe = STAGED_APP_DIR / APP_EXE_NAME
    if not staged_exe.exists():
        fallback_candidates = [
            APP_BUILD_DIR / APP_EXE_NAME,
            BUILD_DIR / "ankismart" / APP_EXE_NAME,
        ]
        for candidate in fallback_candidates:
            if candidate.exists():
                shutil.copy2(candidate, staged_exe)
                _print(f"检测到可执行文件不在 dist 目录，已回填: {candidate} -> {staged_exe}")
                break
        if not staged_exe.exists():
            raise FileNotFoundError(f"未找到应用可执行文件: {APP_EXE_NAME}")

    prune_unused_dependencies(STAGED_APP_DIR)
    removed_dirs, removed_files = remove_ocr_model_artifacts(STAGED_APP_DIR)
    _print(f"已清理 OCR 模型目录 {removed_dirs} 个，模型文件 {removed_files} 个")
    ensure_runtime_dirs(STAGED_APP_DIR)


def create_portable_package(version: str) -> Path:
    portable_dir = PORTABLE_ROOT / f"Ankismart-Portable-{version}"
    if portable_dir.exists():
        shutil.rmtree(portable_dir)

    portable_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(STAGED_APP_DIR, portable_dir)

    ensure_runtime_dirs(portable_dir)
    remove_ocr_model_artifacts(portable_dir)

    archive_base = portable_dir.parent / portable_dir.name
    archive_file = shutil.make_archive(str(archive_base), "zip", portable_dir.parent, portable_dir.name)
    _print(f"便携版压缩包: {archive_file}")
    return portable_dir


def resolve_iscc() -> Path | None:
    candidates = [Path(sys.executable).parent / "ISCC.exe"]

    local_app_data = os.getenv("LOCALAPPDATA", "")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Programs" / "Inno Setup 6" / "ISCC.exe")

    candidates.extend(
        [
            Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
            Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def create_installer(version: str) -> Path | None:
    iss_path = SCRIPT_DIR / "ankismart.iss"
    if not iss_path.exists():
        raise FileNotFoundError(f"未找到安装脚本: {iss_path}")

    iscc = resolve_iscc()
    if iscc is None:
        _print("未找到 Inno Setup，跳过安装版构建。")
        return None

    INSTALLER_ROOT.mkdir(parents=True, exist_ok=True)
    run(
        [
            str(iscc),
            f"/DMyAppVersion={version}",
            f"/DProjectRoot={PROJECT_ROOT}",
            f"/DSourceDir={STAGED_APP_DIR}",
            f"/DOutputDir={INSTALLER_ROOT}",
            str(iss_path),
        ],
        "构建安装版",
    )

    installers = sorted(INSTALLER_ROOT.glob("*.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
    return installers[0] if installers else None


def read_version(pyproject_path: Path) -> str:
    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version ="):
            return stripped.split("=", 1)[1].strip().strip('"')
    return "0.1.0"


def verify_no_ocr_models(target_dir: Path) -> None:
    bad_dirs = [
        p for p in target_dir.rglob("*") if p.is_dir() and p.name.lower() in OCR_MODEL_DIR_NAMES
    ]
    bad_files = [
        p for p in target_dir.rglob("*") if p.is_file() and p.suffix.lower() in OCR_MODEL_EXTENSIONS
    ]

    if bad_dirs or bad_files:
        raise RuntimeError(
            f"检测到 OCR 模型残留: dirs={len(bad_dirs)}, files={len(bad_files)}"
        )


def verify_no_portable_helper_files(target_dir: Path) -> None:
    helper_files = [target_dir / ".portable", target_dir / "README-Portable.txt"]
    exists = [str(p) for p in helper_files if p.exists()]
    if exists:
        raise RuntimeError(f"检测到不应打包的便携辅助文件: {exists}")


def verify_no_paddle_related(target_dir: Path) -> None:
    bad_dirs = [
        p for p in target_dir.rglob("*")
        if p.is_dir() and any(keyword in p.name.lower() for keyword in PADDLE_RELATED_KEYWORDS)
    ]
    if bad_dirs:
        raise RuntimeError(f"检测到不应存在的 paddle 相关目录: {bad_dirs[:5]}")


def verify_layout(version: str) -> None:
    portable_dir = PORTABLE_ROOT / f"Ankismart-Portable-{version}"
    required = [STAGED_APP_DIR, portable_dir]
    for path in required:
        if not path.exists():
            raise RuntimeError(f"发布目录缺失: {path}")

    app_exe = STAGED_APP_DIR / APP_EXE_NAME
    portable_exe = portable_dir / APP_EXE_NAME
    if not app_exe.exists():
        raise RuntimeError(f"应用分发目录缺少可执行文件: {app_exe}")
    if not portable_exe.exists():
        raise RuntimeError(f"便携版目录缺少可执行文件: {portable_exe}")

    verify_no_ocr_models(STAGED_APP_DIR)
    verify_no_ocr_models(portable_dir)
    verify_no_paddle_related(STAGED_APP_DIR)
    verify_no_paddle_related(portable_dir)
    verify_no_portable_helper_files(STAGED_APP_DIR)
    verify_no_portable_helper_files(portable_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 Ankismart 安装版 + 便携版（不含 OCR 模型）")
    parser.add_argument("--clean", action="store_true", help="构建前清理 build/dist")
    parser.add_argument("--skip-installer", action="store_true", help="跳过安装版构建")
    parser.add_argument("--spec", default=str(SCRIPT_DIR / "ankismart.spec"), help="PyInstaller spec 文件")
    args = parser.parse_args()

    if args.clean:
        clean()

    version = read_version(PROJECT_ROOT / "pyproject.toml")
    _print(f"版本: {version}")

    spec_path = Path(args.spec)
    if not spec_path.is_absolute():
        spec_path = PROJECT_ROOT / spec_path

    pyinstaller_build(spec_path)
    stage_app_files()
    portable_dir = create_portable_package(version)
    installer_file = None if args.skip_installer else create_installer(version)

    verify_layout(version)

    _print("构建完成")
    _print(f"应用分发目录: {STAGED_APP_DIR}")
    _print(f"便携版目录: {portable_dir}")
    if installer_file:
        _print(f"安装版文件: {installer_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
