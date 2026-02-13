from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
RELEASE_DIR = DIST_DIR / "release"

APP_BUILD_DIR = DIST_DIR / "Ankismart"
STAGED_APP_DIR = RELEASE_DIR / "app"
PORTABLE_ROOT = RELEASE_DIR / "portable"
INSTALLER_ROOT = RELEASE_DIR / "installer"

UNUSED_DEPENDENCY_DIRS = {
    "matplotlib",
    "pandas",
    "scipy",
    "sklearn",
    "jupyter",
    "notebook",
    "IPython",
    "PyQt5",
    "PySide2",
    "PySide6",
    "tkinter",
}

UNUSED_BUILD_TOOL_PREFIXES = ("pip", "setuptools", "wheel")


def _print(msg: str) -> None:
    print(f"[build] {msg}")


def run(cmd: list[str], description: str) -> None:
    _print(f"{description}: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def clean() -> None:
    for path in (BUILD_DIR, DIST_DIR):
        if path.exists():
            _print(f"清理目录: {path}")
            shutil.rmtree(path)


def pyinstaller_build(spec_file: Path) -> None:
    if not spec_file.exists():
        raise FileNotFoundError(f"未找到 spec 文件: {spec_file}")

    run(
        [sys.executable, "-m", "PyInstaller", "--clean", "-y", str(spec_file)],
        "执行 PyInstaller",
    )

    if not APP_BUILD_DIR.exists():
        raise FileNotFoundError(f"PyInstaller 输出不存在: {APP_BUILD_DIR}")


def ensure_runtime_dirs(target_dir: Path) -> None:
    for name in ("config", "data", "logs", "cache"):
        (target_dir / name).mkdir(parents=True, exist_ok=True)


def remove_ocr_models(target_dir: Path) -> None:
    candidates = [
        target_dir / "model",
        target_dir / "models",
        target_dir / ".paddleocr",
        target_dir / "paddleocr_models",
    ]

    for path in candidates:
        if path.exists():
            _print(f"移除 OCR 模型目录: {path}")
            shutil.rmtree(path, ignore_errors=True)


def prune_unused_dependencies(target_dir: Path) -> None:
    for dep_name in UNUSED_DEPENDENCY_DIRS:
        for path in target_dir.rglob(dep_name):
            if path.is_dir():
                _print(f"移除非必要依赖目录: {path}")
                shutil.rmtree(path, ignore_errors=True)

    for path in target_dir.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

    for extension in ("*.pyc", "*.pyo", "*.pyd.debug"):
        for path in target_dir.rglob(extension):
            if path.is_file():
                path.unlink(missing_ok=True)

    for path in sorted(target_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        name = path.name.lower()
        if not any(name == prefix or name.startswith(f"{prefix}-") for prefix in UNUSED_BUILD_TOOL_PREFIXES):
            continue

        if path.is_dir():
            _print(f"移除构建工具目录: {path}")
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file():
            _print(f"移除构建工具文件: {path}")
            path.unlink(missing_ok=True)


def stage_app_files() -> None:
    if STAGED_APP_DIR.exists():
        shutil.rmtree(STAGED_APP_DIR)

    STAGED_APP_DIR.mkdir(parents=True, exist_ok=True)
    _print(f"整理应用文件到: {STAGED_APP_DIR}")

    for item in APP_BUILD_DIR.iterdir():
        destination = STAGED_APP_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)

    remove_ocr_models(STAGED_APP_DIR)
    prune_unused_dependencies(STAGED_APP_DIR)
    ensure_runtime_dirs(STAGED_APP_DIR)


def create_portable_package(version: str) -> Path:
    portable_dir = PORTABLE_ROOT / f"Ankismart-Portable-{version}"

    if portable_dir.exists():
        shutil.rmtree(portable_dir)

    portable_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(STAGED_APP_DIR, portable_dir)

    (portable_dir / ".portable").write_text(
        "portable_mode: true\nconfig_dir: ./config\ndata_dir: ./data\nlogs_dir: ./logs\ncache_dir: ./cache\n",
        encoding="utf-8",
    )

    ensure_runtime_dirs(portable_dir)
    remove_ocr_models(portable_dir)

    readme = portable_dir / "README-Portable.txt"
    readme.write_text(
        "Ankismart 便携版\n\n"
        "目录说明:\n"
        "- Ankismart.exe: 主程序\n"
        "- config/: 配置文件\n"
        "- data/: 业务数据\n"
        "- logs/: 日志\n"
        "- cache/: 缓存\n"
        "\n"
        "说明:\n"
        "- 未内置 OCR 模型，首次使用 OCR 时按需下载。\n"
        "- 所有运行数据都保存在当前目录。\n",
        encoding="utf-8",
    )

    archive_base = portable_dir.parent / portable_dir.name
    archive_file = shutil.make_archive(str(archive_base), "zip", portable_dir.parent, portable_dir.name)
    _print(f"便携版压缩包: {archive_file}")
    return portable_dir


def resolve_iscc() -> Path | None:
    env_path = Path((
        Path(sys.executable).parent / "ISCC.exe"
    ))
    if env_path.exists():
        return env_path

    candidates = [
        Path("C:/Program Files (x86)/Inno Setup 6/ISCC.exe"),
        Path("C:/Program Files/Inno Setup 6/ISCC.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def create_installer(version: str) -> Path | None:
    iss_path = PROJECT_ROOT / "ankismart.iss"
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


def verify_layout() -> None:
    required = [
        STAGED_APP_DIR,
        PORTABLE_ROOT,
    ]
    for path in required:
        if not path.exists():
            raise RuntimeError(f"发布目录缺失: {path}")

    model_paths = [
        STAGED_APP_DIR / "model",
        STAGED_APP_DIR / "models",
        STAGED_APP_DIR / ".paddleocr",
    ]
    for path in model_paths:
        if path.exists():
            raise RuntimeError(f"检测到被打包的 OCR 模型目录: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 Ankismart 安装版 + 便携版")
    parser.add_argument("--clean", action="store_true", help="构建前清理 build/dist")
    parser.add_argument("--skip-installer", action="store_true", help="跳过安装版构建")
    parser.add_argument("--spec", default="ankismart.spec", help="PyInstaller spec 文件")
    args = parser.parse_args()

    if args.clean:
        clean()

    version = read_version(PROJECT_ROOT / "pyproject.toml")
    _print(f"版本: {version}")

    pyinstaller_build(PROJECT_ROOT / args.spec)
    stage_app_files()

    portable_dir = create_portable_package(version)
    installer_file = None if args.skip_installer else create_installer(version)

    verify_layout()

    _print("构建完成")
    _print(f"应用分发目录: {STAGED_APP_DIR}")
    _print(f"便携版目录: {portable_dir}")
    if installer_file is not None:
        _print(f"安装版文件: {installer_file}")
    elif not args.skip_installer:
        _print("安装版未生成（通常是本机未安装 Inno Setup）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
