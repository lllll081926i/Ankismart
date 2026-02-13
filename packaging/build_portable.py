from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCE_DIR = PROJECT_ROOT / "dist" / "release" / "app"
OUTPUT_ROOT = PROJECT_ROOT / "dist" / "release" / "portable"


def read_version(pyproject_path: Path) -> str:
    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version ="):
            return stripped.split("=", 1)[1].strip().strip('"')
    return "0.1.0"


def ensure_runtime_dirs(target_dir: Path) -> None:
    for name in ("config", "data", "logs", "cache"):
        (target_dir / name).mkdir(parents=True, exist_ok=True)


def remove_ocr_models(target_dir: Path) -> None:
    for name in ("model", "models", ".paddleocr", "paddleocr_models"):
        path = target_dir / name
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def build_portable(source_dir: Path, output_root: Path, version: str) -> Path:
    if not source_dir.exists():
        raise FileNotFoundError(f"未找到应用目录: {source_dir}")

    output_dir = output_root / f"Ankismart-Portable-{version}"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    output_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, output_dir)

    (output_dir / ".portable").write_text(
        "portable_mode: true\nconfig_dir: ./config\ndata_dir: ./data\nlogs_dir: ./logs\ncache_dir: ./cache\n",
        encoding="utf-8",
    )

    ensure_runtime_dirs(output_dir)
    remove_ocr_models(output_dir)

    (output_dir / "README-Portable.txt").write_text(
        "Ankismart 便携版\n"
        "- 不包含 OCR 模型\n"
        "- 首次 OCR 按需下载模型\n"
        "- 运行数据位于当前目录的 config/data/logs/cache\n",
        encoding="utf-8",
    )

    archive_base = output_root / output_dir.name
    shutil.make_archive(str(archive_base), "zip", output_root, output_dir.name)
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="单独构建 Ankismart 便携版")
    parser.add_argument("--source", default=str(SOURCE_DIR), help="输入应用目录")
    parser.add_argument("--output", default=str(OUTPUT_ROOT), help="输出目录")
    args = parser.parse_args()

    version = read_version(PROJECT_ROOT / "pyproject.toml")
    output = build_portable(Path(args.source), Path(args.output), version)
    print(f"[portable] 便携版目录: {output}")
    print(f"[portable] 压缩包: {output.with_suffix('.zip')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

