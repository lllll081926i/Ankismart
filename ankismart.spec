# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


block_cipher = None

root_dir = Path(SPECPATH)
src_dir = root_dir / "src"

hiddenimports = collect_submodules("ankismart") + [
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


a = Analysis(
    ["src/ankismart/ui/app.py"],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        ("src/ankismart/ui/assets", "ankismart/ui/assets"),
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
    icon="src/ankismart/ui/assets/icon.ico" if (root_dir / "src/ankismart/ui/assets/icon.ico").exists() else None,
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

