# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# Hidden imports - collect all submodules for better compatibility
hiddenimports = (
    collect_submodules('yt_dlp') +
    collect_submodules('curl_cffi') +
    collect_submodules('Crypto') +
    collect_submodules('customtkinter') +
    ['yt_dlp', 'curl_cffi', 'Crypto', 'customtkinter']
)

# Include bin directory if it exists
bin_data = [('bin', 'bin')] if os.path.isdir('bin') else []

a = Analysis(
    ['turkanime_api/gui/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('docs/TurkAnimu.ico', 'docs'),
        ('gereksinimler.json', '.'),
    ] + bin_data,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='turkanime-gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='docs/TurkAnimu.ico'
)
