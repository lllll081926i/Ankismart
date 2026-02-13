# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules


block_cipher = None

spec_dir = Path(SPECPATH)
project_root = spec_dir.parent
src_dir = project_root / "src"

hiddenimports = [
    *collect_submodules("ankismart"),
    "qfluentwidgets",
    "openai",
    "paddle",
    "paddleocr",
    "genanki",
    "pypdfium2",
]

excludes = [
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
    "torch",
    "tensorflow",
]


def filter_ocr_models(src, names):
    """排除 OCR 模型文件和目录"""
    excluded = set()

    model_dir_names = {
        "model", "models", "inference", ".paddleocr",
        "paddleocr_models", "ocr_models"
    }

    model_extensions = {".pdmodel", ".pdiparams", ".onnx", ".nb"}

    for name in names:
        name_lower = name.lower()
        if name_lower in model_dir_names:
            excluded.add(name)
        elif any(name.endswith(ext) for ext in model_extensions):
            excluded.add(name)

    return excluded


a = Analysis(
    [str(project_root / "src" / "ankismart" / "ui" / "app.py")],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        (str(project_root / "src" / "ankismart" / "ui" / "assets"), "ankismart/ui/assets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

icon_path = project_root / "src" / "ankismart" / "ui" / "assets" / "icon.ico"

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Ankismart",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_path) if icon_path.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Ankismart",
)
