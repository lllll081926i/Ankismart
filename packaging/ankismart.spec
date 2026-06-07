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
    "paddle",
    "paddleocr",
    "paddlex",
    "cv2",
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

# 读取版本号用于嵌入文件属性
import tomllib
pyproject_path = project_root / "pyproject.toml"
version_data = tomllib.loads(pyproject_path.read_text(encoding='utf-8'))
app_version = version_data['project']['version']

# 创建版本信息文件
version_info_path = project_root / 'version_info.txt'
version_parts = app_version.replace('-rc', '.').replace('-alpha', '.').replace('-beta', '.').split('.')
version_tuple = ','.join(version_parts[:4] if len(version_parts) >= 4 else version_parts + ['0'] * (4 - len(version_parts)))

version_info_content = f'''# UTF-8
#
# Version Information
#
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_tuple}),
    prodvers=({version_tuple}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', 'AnkiSmart Team'),
        StringStruct('FileDescription', 'AnkiSmart - Intelligent Anki Flashcard Generator'),
        StringStruct('FileVersion', '{app_version}'),
        StringStruct('InternalName', 'Ankismart'),
        StringStruct('LegalCopyright', 'Copyright (C) 2024-2026 AnkiSmart Team'),
        StringStruct('OriginalFilename', 'Ankismart.exe'),
        StringStruct('ProductName', 'AnkiSmart'),
        StringStruct('ProductVersion', '{app_version}')])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''
version_info_path.write_text(version_info_content, encoding='utf-8')

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
    version=str(version_info_path),
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
