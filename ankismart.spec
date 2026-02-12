# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

# 获取项目根目录
root_dir = Path(SPECPATH)
src_dir = root_dir / 'src'

a = Analysis(
    ['src/ankismart/ui/app.py'],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        # UI assets
        ('src/ankismart/ui/assets', 'ankismart/ui/assets'),
    ],
    hiddenimports=[
        'ankismart',
        'ankismart.ui',
        'ankismart.ui.app',
        'ankismart.ui.main_window',
        'ankismart.ui.import_page',
        'ankismart.ui.preview_page',
        'ankismart.ui.result_page',
        'ankismart.ui.settings_page',
        'ankismart.ui.card_preview_page',
        'ankismart.ui.card_edit_widget',
        'ankismart.ui.error_handler',
        'ankismart.ui.log_exporter',
        'ankismart.ui.shortcuts',
        'ankismart.ui.shortcuts_dialog',
        'ankismart.ui.workers',
        'ankismart.ui.i18n',
        'ankismart.ui.styles',
        'ankismart.ui.utils',
        'ankismart.anki_gateway',
        'ankismart.anki_gateway.client',
        'ankismart.anki_gateway.gateway',
        'ankismart.anki_gateway.apkg_exporter',
        'ankismart.anki_gateway.styling',
        'ankismart.card_gen',
        'ankismart.card_gen.generator',
        'ankismart.card_gen.llm_client',
        'ankismart.card_gen.prompts',
        'ankismart.converter',
        'ankismart.converter.converter',
        'ankismart.converter.ocr_converter',
        'ankismart.converter.cache',
        'ankismart.core',
        'ankismart.core.config',
        'ankismart.core.logging',
        'ankismart.core.models',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'qfluentwidgets',
        'paddleocr',
        'paddlepaddle',
        'genanki',
        'openai',
        'httpx',
        'pydantic',
        'yaml',
        'docx',
        'pptx',
        'PIL',
        'numpy',
        'pypdfium2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
        'jupyter',
        'notebook',
        'IPython',
    ],
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
    name='Ankismart',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='src/ankismart/ui/assets/icon.ico' if (root_dir / 'src/ankismart/ui/assets/icon.ico').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Ankismart',
)
