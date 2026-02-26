from __future__ import annotations

import argparse
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SOURCE_DIR = PROJECT_ROOT / "dist" / "release" / "app"
OUTPUT_ROOT = PROJECT_ROOT / "dist" / "release" / "portable"

OCR_MODEL_DIR_NAMES = {
    "model",
    "models",
    "inference",
    ".paddleocr",
    "paddleocr_models",
    "ocr_models",
    "paddle",
    "paddleocr",
    "paddlex",
    "cv2",
}

OCR_MODEL_EXTENSIONS = {
    ".pdmodel",
    ".pdiparams",
    ".onnx",
    ".nb",
}

PADDLE_RELATED_KEYWORDS = ("paddle", "paddlex", "paddleocr", "cv2")


def read_version(pyproject_path: Path) -> str:
    for line in pyproject_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version ="):
            return stripped.split("=", 1)[1].strip().strip('"')
    return "0.1.2"


def ensure_runtime_dirs(target_dir: Path) -> None:
    for name in ("config", "data", "logs", "cache"):
        (target_dir / name).mkdir(parents=True, exist_ok=True)


def remove_ocr_models(target_dir: Path) -> None:
    """删除所有 OCR 和 paddle 相关的文件和目录"""
    # 收集所有需要删除的目录
    dir_candidates = []
    for path in target_dir.rglob("*"):
        if not path.is_dir():
            continue

        name_lower = path.name.lower()

        # 匹配 OCR 目录名
        if name_lower in OCR_MODEL_DIR_NAMES:
            dir_candidates.append(path)
            continue

        # 匹配 paddle 相关的任何目录（包括 dist-info）
        if any(keyword in name_lower for keyword in PADDLE_RELATED_KEYWORDS):
            dir_candidates.append(path)

    # 按深度倒序删除（先删除子目录）
    for path in sorted(dir_candidates, key=lambda p: len(p.parts), reverse=True):
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)

    # 删除 OCR 模型文件
    for path in target_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in OCR_MODEL_EXTENSIONS:
            path.unlink(missing_ok=True)


def build_portable(source_dir: Path, output_root: Path, version: str) -> Path:
    if not source_dir.exists():
        raise FileNotFoundError(f"未找到应用目录: {source_dir}")

    output_dir = output_root / f"Ankismart-Portable-{version}"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    output_root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, output_dir)

    ensure_runtime_dirs(output_dir)
    remove_ocr_models(output_dir)

    archive_base = output_root / output_dir.name
    shutil.make_archive(str(archive_base), "zip", output_root, output_dir.name)
    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="单独构建 Ankismart 便携版（不含 OCR 模型）")
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
