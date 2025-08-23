# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules, collect_all

block_cipher = None

hiddenimports = collect_submodules('yt_dlp') + collect_submodules('curl_cffi') + collect_submodules('Crypto') + collect_submodules('PyQt6')

# Collect PyQt6 data/binaries to avoid missing Qt DLLs/plugins
pyqt6_all = collect_all('PyQt6')
pyqt6_qt_all = collect_all('PyQt6.Qt6')

a = Analysis([
    'turkanime_api/gui/boot.py',
],
             pathex=[],
             binaries=pyqt6_all[1] + pyqt6_qt_all[1],
             datas=[
                 ('docs/TurkAnimu.ico', 'docs'),
                 ('gereksinimler.json', '.'),
                 ('bin', 'bin'),
             ] + pyqt6_all[0] + pyqt6_qt_all[0],
             hiddenimports=hiddenimports + pyqt6_all[2] + pyqt6_qt_all[2],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=['pyinstaller_hooks/qt6_runtime_hook.py'],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='turkanime-gui',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          console=False,
          icon='docs/TurkAnimu.ico')

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               upx_exclude=[],
               name='turkanime-gui')
