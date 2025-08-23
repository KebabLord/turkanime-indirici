# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['turkanime_api\\gui\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('docs/TurkAnimu.ico', 'docs'), ('gereksinimler.json', '.')],
    hiddenimports=['yt_dlp', 'curl_cffi', 'Crypto', 'PyQt6'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='turkanime-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['docs\\TurkAnimu.ico'],
)
