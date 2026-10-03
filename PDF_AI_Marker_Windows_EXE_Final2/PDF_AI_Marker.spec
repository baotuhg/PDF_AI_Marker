# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for PDF AI Marker v3
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

added_files = [
    ('license_core.py', '.'),
    ('license_dialog.py', '.'),
    ('license_cloud.py', '.'),
    ('cloud_config.json', '.'),
    ('md_postprocess.py', '.'),
    ('app_icon.ico', '.'),
    ('app_icon.png', '.'),
    ('custom_rules.json.example', '.'),
    ('HUONG_DAN_SU_DUNG.txt', '.'),
]

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'license_core',
        'license_dialog',
        'license_cloud',
        'inspector',
        'chat_window',
        'rag_engine',
        'PySide6.QtPdf',
        'md_postprocess',
        'marker_bridge',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['keygen'],
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
    name='PDF_AI_Marker',
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
    icon=['app_icon.ico'],
    version='version_info.txt',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PDF_AI_Marker',
)
